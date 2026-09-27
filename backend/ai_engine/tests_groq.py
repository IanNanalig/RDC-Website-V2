import json
import urllib.error
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from .groq_client import GroqCompletion, GroqUnavailable, complete_json
from .groq_priority import analyze_priority_with_groq


class GroqClientTests(SimpleTestCase):
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
    @patch("ai_engine.groq_priority._historical_context")
    @patch("ai_engine.groq_priority.complete_json")
    @patch("ai_engine.groq_priority.is_groq_enabled", return_value=True)
    def test_priority_response_is_bounded_and_unknown_fields_are_rejected(
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

        result = analyze_priority_with_groq(
            SimpleNamespace(pk=1),
            {"objective": "The road project will reduce travel time."},
            {},
            criteria,
            "infrastructure",
            ["Use supported facts."],
        )

        self.assertEqual(result["outcomes"][0]["raw_score"], 10)
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
