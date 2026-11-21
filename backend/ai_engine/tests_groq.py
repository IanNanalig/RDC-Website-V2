import json
import io
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from .groq_client import GroqCompletion, GroqUnavailable, complete_json
from .groq_priority import analyze_priority_with_groq


class GroqClientTests(SimpleTestCase):
    @override_settings(
        GROQ_ENABLED=True, GROQ_API_KEY="test-key",
        GROQ_PRIMARY_MODEL="meta-llama/llama-prompt-guard-2-86m",
        GROQ_BACKUP_MODEL="meta-llama/llama-prompt-guard-2-22m",
    )
    @patch("ai_engine.groq_client.urllib.request.urlopen")
    def test_classification_only_models_fail_before_provider_request(self, urlopen):
        with self.assertRaises(GroqUnavailable) as raised:
            complete_json([])
        self.assertEqual(raised.exception.reason, "provider_model")
        self.assertIn("classification-only", str(raised.exception))
        urlopen.assert_not_called()

    @override_settings(
        GROQ_ENABLED=True,
        GROQ_API_KEY="test-key",
        GROQ_PRIMARY_MODEL="primary-model",
        GROQ_BACKUP_MODEL="backup-model",
        GROQ_API_URL="https://example.test/chat/completions",
        GROQ_TIMEOUT_SECONDS=5,
        GROQ_MAX_COMPLETION_TOKENS=512,
    )
    @patch("ai_engine.groq_client.urllib.request.urlopen")
    def test_primary_failure_uses_backup_model(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {"choices": [{"message": {"content": json.dumps({"answer": "ok"})}}]}
        ).encode("utf-8")
        urlopen.side_effect = [
            urllib.error.URLError("primary unavailable"),
            response,
        ]

        result = complete_json([{"role": "user", "content": "Return JSON."}])

        self.assertEqual(result.data, {"answer": "ok"})
        self.assertEqual(result.model, "backup-model")
        self.assertTrue(result.used_backup)
        self.assertEqual(result.attempted_models, ("primary-model", "backup-model"))
        first_payload = json.loads(urlopen.call_args_list[0].args[0].data.decode("utf-8"))
        second_payload = json.loads(urlopen.call_args_list[1].args[0].data.decode("utf-8"))
        self.assertEqual(first_payload["model"], "primary-model")
        self.assertEqual(second_payload["model"], "backup-model")
        self.assertEqual(first_payload["response_format"], {"type": "json_object"})

    @override_settings(
        GROQ_ENABLED=True, GROQ_API_KEY="test-key",
        GROQ_PRIMARY_MODEL="openai/gpt-oss-20b", GROQ_BACKUP_MODEL="legacy-model",
    )
    @patch("ai_engine.groq_client.urllib.request.urlopen")
    def test_structured_mode_keeps_legacy_fallback_and_logs_actual_status(self, urlopen):
        urlopen.side_effect = [
            urllib.error.HTTPError("https://example.test", 429, "private error text", None, None),
            urllib.error.HTTPError("https://example.test", 429, "private error text", None, None),
        ]
        schema = {"name": "test", "strict": True, "schema": {"type": "object"}}
        with self.assertRaises(GroqUnavailable) as raised:
            complete_json([], response_schema=schema)
        self.assertEqual(raised.exception.reason, "rate_limited")
        self.assertIn("openai/gpt-oss-20b: HTTP 429", str(raised.exception))
        self.assertNotIn("private error text", str(raised.exception))
        modes = [json.loads(call.args[0].data)["response_format"] for call in urlopen.call_args_list]
        self.assertEqual(modes, [{"type": "json_schema", "json_schema": schema}, {"type": "json_object"}])

    @override_settings(GROQ_ENABLED=True, GROQ_API_KEY="test-key", GROQ_PRIMARY_MODEL="one", GROQ_BACKUP_MODEL="")
    @patch("ai_engine.groq_client.urllib.request.urlopen")
    def test_http_error_logs_safe_provider_code_without_body(self, urlopen):
        payload = {"error": {"code": "context_length_exceeded", "message": "private context"}}
        urlopen.side_effect = urllib.error.HTTPError(
            "https://example.test", 400, "Bad Request", None, io.BytesIO(json.dumps(payload).encode()),
        )
        with self.assertRaises(GroqUnavailable) as raised:
            complete_json([])
        self.assertEqual(raised.exception.reason, "request_too_large")
        self.assertIn("HTTP 400 (context_length_exceeded)", str(raised.exception))
        self.assertNotIn("private context", str(raised.exception))

    @override_settings(
        GROQ_ENABLED=True,
        GROQ_API_KEY="test-key",
        GROQ_PRIMARY_MODEL="primary-model",
        GROQ_BACKUP_MODEL="backup-model",
    )
    @patch("ai_engine.groq_client.urllib.request.urlopen")
    def test_all_model_failures_raise_safe_error_without_key(self, urlopen):
        urlopen.side_effect = urllib.error.URLError("offline")

        with self.assertRaises(GroqUnavailable) as raised:
            complete_json([{"role": "user", "content": "Return JSON."}])

        self.assertNotIn("test-key", str(raised.exception))
        self.assertEqual(urlopen.call_count, 2)


class GroqFeatureTests(SimpleTestCase):
    @patch("ai_engine.groq_priority.is_groq_enabled", return_value=True)
    @patch("ai_engine.groq_priority.complete_json")
    @patch("ai_engine.groq_priority._project_payload")
    @patch("ai_engine.groq_priority._historical_context")
    def test_outcome_context_budget_and_size_retry_preserve_scoring_inputs(self, history, project_payload, completion, _enabled):
        examples = [{"project_text": str(index) * 8_000} for index in range(6)]
        history.return_value = (examples, [], "dataset-1", {"version": "history-1"})
        project_payload.return_value = {
            "objective": "Keep the drainage outlet open.",
            "program": "Independent canonical answer",
            "form_fields": [
                {"key": "objective", "answer": "Keep the drainage outlet open.", "answer_state": "answered"},
                {"key": "custom_required", "answer": None, "answer_state": "required_missing"},
                {"key": "custom_hidden", "answer": None, "answer_state": "hidden_by_condition"},
            ],
        }
        facts = {"supporting_document_evidence": {"status": "pass", "summary": "A gated outlet."}}
        criteria = [{"key": "utility", "label": "Utility", "weight": 10}]
        data = {"outcome_assessments": [{"key": "utility", "raw_score": 8, "explanation": "A gated outlet.", "evidence": []}]}
        model_response = GroqCompletion(data, "test-model", False, ("test-model",))
        completion.side_effect = [GroqUnavailable("HTTP 413", reason="request_too_large"), model_response]

        result = analyze_priority_with_groq(SimpleNamespace(pk=1), {}, facts, criteria, "infrastructure", [])

        self.assertEqual(completion.call_count, 2)
        primary, retry = [json.loads(call.args[0][-1]["content"]) for call in completion.call_args_list]
        sent = primary["validator_confirmed_historical_examples"]
        self.assertGreater(len(sent), 0)
        self.assertLess(len(sent), len(examples))
        self.assertEqual(sent, examples[:len(sent)])
        self.assertEqual(retry["validator_confirmed_historical_examples"], [])
        self.assertEqual(retry["validator_facts"], facts)
        self.assertEqual(retry["criteria"], primary["criteria"])
        self.assertEqual(retry["project"]["program"], "Independent canonical answer")
        self.assertEqual([field["key"] for field in retry["project"]["form_fields"]], ["objective", "custom_required"])
        self.assertEqual(retry["project"]["form_fields"][0]["answer"], "Keep the drainage outlet open.")
        self.assertEqual(result["provider"]["historical_project_count"], 0)
        self.assertEqual(result["outcomes"][0]["raw_score"], 8)

        completion.reset_mock(side_effect=True)
        completion.side_effect = GroqUnavailable("HTTP 429", reason="rate_limited")
        with self.assertRaises(GroqUnavailable) as failed:
            analyze_priority_with_groq(SimpleNamespace(pk=1), {}, facts, criteria, "infrastructure", [])
        self.assertEqual(failed.exception.reason, "rate_limited")
        self.assertEqual(completion.call_count, 1)

    @patch("ai_engine.groq_priority._historical_context")
    @patch("ai_engine.groq_priority.complete_json")
    @patch("ai_engine.groq_priority.is_groq_enabled", return_value=True)
    def test_priority_accepts_single_string_evidence_from_provider(
        self,
        _enabled,
        completion,
        historical,
    ):
        historical.return_value = ([], [], "dataset-1", {})
        response_data = {
            "outcome_assessments": [
                {
                    "key": "connectivity",
                    "raw_score": 8,
                    "explanation": "The project reduces travel time.",
                    "evidence": "reduce travel time",
                    "recommendation": "Add a travel-time baseline.",
                    "revision_fields": ["objective"],
                }
            ],
            "overall_reasoning": "The project supports safer movement.",
            "risks": "A baseline is not specified.",
            "historical_prediction": {
                "priority": "high",
                "confidence": 0.8,
                "explanation": "The expected mobility outcome is substantial.",
            },
        }

        def provider_response(messages, **kwargs):
            payload = json.loads(messages[-1]["content"])
            regional = payload["regional_scorecard_context"]
            self.assertEqual(regional["bands"]["outcome_contribution"][0]["minimum"], 11)
            self.assertEqual([item["key"] for item in payload["criteria"]], ["connectivity"])
            self.assertIn("only as context", regional["instruction"])
            self.assertTrue(kwargs["validate"](response_data))
            self.assertEqual(
                kwargs["response_schema"]["schema"]["properties"]["outcome_assessments"]["items"]["properties"]["key"]["enum"],
                ["connectivity"],
            )
            return GroqCompletion(
                data=response_data,
                model="primary-model",
                used_backup=False,
                attempted_models=("primary-model",),
            )

        completion.side_effect = provider_response
        criteria = [{
            "key": "connectivity",
            "label": "Inclusive connectivity",
            "weight": 20,
            "description": "Improve transport connectivity.",
            "matching_guidance": "Require a transport outcome.",
            "keywords": ["road"],
            "context_phrases": ["reduce travel time"],
        }]

        result = analyze_priority_with_groq(
            SimpleNamespace(pk=1),
            {"objective": "The road project will reduce travel time."},
            {},
            criteria,
            "infrastructure",
            [],
            regional_context={"bands": {"outcome_contribution": [{"minimum": 11, "label": "At least 11 outcomes"}]}},
        )

        self.assertEqual(result["outcomes"][0]["evidence"], ["reduce travel time"])
        self.assertEqual(result["risks"], ["A baseline is not specified."])
        self.assertEqual(result["provider"]["model"], "primary-model")

    @patch("ai_engine.groq_priority._historical_context")
    @patch("ai_engine.groq_priority.complete_json")
    @patch("ai_engine.groq_priority.is_groq_enabled", return_value=True)
    def test_priority_rejects_bad_outcomes_and_preserves_valid_zero(
        self,
        _enabled,
        completion,
        historical,
    ):
        historical.return_value = (
            [],
            [],
            "dataset-1",
            {
                "version": "rdc-ml-v1",
                "algorithm": "multinomial-logistic-regression",
                "sample_count": 4,
                "dataset_version": "dataset-1",
                "status": "active",
            },
        )
        completion.return_value = GroqCompletion(
            data={
                "outcome_assessments": [
                    {
                        "key": "connectivity",
                        "raw_score": 15,
                        "explanation": "The project directly reduces travel time.",
                        "evidence": ["reduce travel time"],
                        "recommendation": "Add a measurable travel-time target.",
                        "revision_fields": ["objective", "secretField"],
                    },
                    {"key": "unknown", "raw_score": 10},
                ],
                "overall_reasoning": "The stated intervention aligns with connectivity.",
                "risks": ["The target lacks a baseline."],
                "historical_prediction": {
                    "priority": "high",
                    "confidence": 1.5,
                    "explanation": "Comparable confirmed projects were high priority.",
                },
            },
            model="backup-model",
            used_backup=True,
            attempted_models=("primary-model", "backup-model"),
        )
        criteria = [
            {
                "key": "connectivity",
                "label": "Inclusive connectivity",
                "weight": 20,
                "description": "Improve transport connectivity.",
                "matching_guidance": "Require a transport outcome.",
                "keywords": ["road"],
                "context_phrases": ["reduce travel time"],
            }
        ]

        args = (
            SimpleNamespace(pk=1),
            {"objective": "The road project will reduce travel time."},
            {},
            criteria,
            "infrastructure",
            ["Use supported facts."],
        )
        invalid = completion.return_value.data
        with self.assertRaises(GroqUnavailable):
            analyze_priority_with_groq(*args)
        row = invalid["outcome_assessments"][0]
        invalid["outcome_assessments"] = [row]
        with self.assertRaises(GroqUnavailable):
            analyze_priority_with_groq(*args)
        row["raw_score"] = 0
        for rows in ([], [row, row], [dict(row, raw_score="bad")], [dict(row, key="unknown")]):
            invalid["outcome_assessments"] = rows
            with self.subTest(rows=rows), self.assertRaises(GroqUnavailable):
                analyze_priority_with_groq(*args)
        invalid["outcome_assessments"] = [row]
        self.assertEqual(analyze_priority_with_groq(*args)["historical_prediction"], {})
        invalid.pop("historical_prediction")
        row["evidence"] = None
        row["revision_fields"] = "unstructured advisory field"
        result = analyze_priority_with_groq(*args)
        self.assertEqual(result["historical_prediction"], {})
        self.assertEqual(result["outcomes"][0]["evidence"], [])
        self.assertEqual(result["outcomes"][0]["revision_fields"], [])
        row["revision_fields"] = ["objective", "secretField"]
        invalid["historical_prediction"] = {"priority": "high", "confidence": 1, "explanation": "Advisory only."}
        result = analyze_priority_with_groq(*args)
        self.assertEqual(result["outcomes"][0]["raw_score"], 0)
        self.assertEqual(result["outcomes"][0]["revision_fields"], ["objective"])
        self.assertEqual(result["historical_prediction"]["confidence"], 1)
        self.assertEqual(result["provider"]["model"], "backup-model")
        self.assertTrue(result["provider"]["used_backup"])
        self.assertEqual(result["provider"]["reference_model_version"], "rdc-ml-v1")
        messages = completion.call_args.args[0]
        self.assertIn("primary authority", messages[0]["content"])
        user_payload = json.loads(messages[1]["content"])
        self.assertTrue(user_payload["historical_reference_policy"]["rules_remain_primary"])
        self.assertFalse(user_payload["historical_reference_policy"]["hosted_model_was_fine_tuned"])
