import hashlib
import json
from collections import Counter

from django.db import transaction
from django.utils import timezone

from projects.models import ProjectPriorityConfirmation, UserActivity

from .features import FEATURE_NAMES, FEATURE_SCHEMA_VERSION, extract_feature_snapshot, feature_vector
from .ml import evaluate_model, feature_contributions, predict_probabilities, train_logistic_regression
from .models import (
    AIModelTrainingRecord,
    AIModelVersion,
    AIProjectAnalysis,
    AISimilarProject,
    AITrainingRecord,
)
from .similarity import find_similar_projects


PRIORITY_CLASSES = ["low", "high"]
MINIMUM_TRAINING_PROJECTS = 2


def sync_training_record(confirmation):
    analysis = confirmation.analysis
    features = extract_feature_snapshot(analysis)
    defaults = {
        "project": analysis.project,
        "rule_set": analysis.rule_set,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_snapshot": features,
        "normalized_text": features.get("text", ""),
        "target_priority": confirmation.final_priority,
        "source_hash": analysis.source_hash,
    }
    record, created = AITrainingRecord.objects.get_or_create(
        confirmation=confirmation,
        defaults=defaults,
    )
    if not created:
        changed = []
        for field, value in defaults.items():
            comparison = value.pk if field in {"project", "rule_set"} else value
            current = getattr(record, f"{field}_id") if field in {"project", "rule_set"} else getattr(record, field)
            if current != comparison:
                setattr(record, field, value)
                changed.append(field)
        if changed:
            record.save(update_fields=[*changed, "updated_at"])
    return record


def sync_all_training_records():
    confirmations = ProjectPriorityConfirmation.objects.select_related(
        "analysis__project", "analysis__rule_set"
    ).order_by("created_at", "id")
    return [sync_training_record(confirmation) for confirmation in confirmations]


def _latest_eligible_records():
    records = AITrainingRecord.objects.filter(
        is_eligible=True,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
    ).select_related(
        "project", "confirmation__validator", "confirmation__analysis", "rule_set"
    ).order_by("-confirmation__created_at", "-id")
    latest = []
    seen_projects = set()
    for record in records:
        if record.project_id in seen_projects:
            continue
        seen_projects.add(record.project_id)
        latest.append(record)
    return latest


def training_dataset_summary(sync=False):
    if sync:
        sync_all_training_records()
    records = _latest_eligible_records()
    counts = Counter(record.target_priority for record in records)
    dataset_version = _dataset_version(records)
    active_model = get_active_model()
    ready_to_train = (
        len(records) >= MINIMUM_TRAINING_PROJECTS
        and all(counts.get(label, 0) for label in PRIORITY_CLASSES)
    )
    return {
        "candidate_count": AITrainingRecord.objects.count(),
        "eligible_project_count": len(records),
        "excluded_count": AITrainingRecord.objects.filter(is_eligible=False).count(),
        "label_counts": {label: counts.get(label, 0) for label in PRIORITY_CLASSES},
        "minimum_projects": MINIMUM_TRAINING_PROJECTS,
        "required_labels": PRIORITY_CLASSES,
        "ready_to_train": ready_to_train,
        "dataset_version": dataset_version,
        "active_dataset_version": active_model.dataset_version if active_model else "",
        "active_model_version": active_model.version if active_model else "",
        "active_sample_count": active_model.sample_count if active_model else 0,
        "last_trained_at": active_model.created_at if active_model else None,
        "is_current": bool(active_model and active_model.dataset_version == dataset_version),
        "requires_retraining": bool(
            ready_to_train and (not active_model or active_model.dataset_version != dataset_version)
        ),
    }


def _dataset_version(records):
    payload = [
        {
            "record": record.pk,
            "project": record.project_id,
            "source_hash": record.source_hash,
            "target": record.target_priority,
            "updated_at": record.updated_at.isoformat(),
        }
        for record in sorted(records, key=lambda item: item.pk)
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def reference_dataset_version(exclude_project_id=None):
    """Return the activated RAG identity used for confirmation freshness.

    Live bootstrap references remain deliberately unversioned. Confirming this or
    another project must not invalidate a confirmed validator copy. Once an
    administrator creates a controlled reference version, its stable dataset hash
    participates in freshness checks.
    """
    active_model = get_active_model()
    if active_model:
        return active_model.dataset_version
    return "live-unversioned"


def _split_records(records):
    by_label = {label: [] for label in PRIORITY_CLASSES}
    for record in sorted(records, key=lambda item: item.pk):
        by_label[record.target_priority].append(record)
    if len(records) >= 10 and all(len(by_label[label]) >= 3 for label in PRIORITY_CLASSES):
        test_ids = {items[-1].pk for items in by_label.values()}
        return (
            [record for record in records if record.pk not in test_ids],
            [record for record in records if record.pk in test_ids],
            "held_out",
        )
    return list(records), [], "training_only_insufficient_data_for_holdout"


def _rows(records):
    return [feature_vector(record.feature_snapshot, FEATURE_NAMES) for record in records]


def _unique_model_version():
    base = timezone.now().strftime("rdc-ml-v%Y%m%d-%H%M%S")
    version = base
    suffix = 2
    while AIModelVersion.objects.filter(version=version).exists():
        version = f"{base}-{suffix}"
        suffix += 1
    return version


def _log_activity(user, action, details):
    UserActivity.objects.create(
        user=user,
        actor_username=getattr(user, "username", "") or "",
        actor_full_name=(getattr(user, "full_name", "") or getattr(user, "get_full_name", lambda: "")()).strip(),
        role=getattr(user, "role", "") or "",
        event="api_action",
        details={"action": action, **details},
    )


@transaction.atomic
def train_new_model(user):
    sync_all_training_records()
    records = _latest_eligible_records()
    counts = Counter(record.target_priority for record in records)
    if len(records) < MINIMUM_TRAINING_PROJECTS:
        raise ValueError(
            f"At least {MINIMUM_TRAINING_PROJECTS} validator-confirmed projects are required before training."
        )
    missing_labels = [label for label in PRIORITY_CLASSES if not counts.get(label)]
    if missing_labels:
        raise ValueError(
            "Training requires at least one validator-confirmed project for each final priority: low and high. "
            f"Missing: {', '.join(missing_labels)}."
        )
    dataset_version = _dataset_version(records)
    current_model = get_active_model()
    if current_model and current_model.dataset_version == dataset_version:
        raise ValueError(
            f"Model {current_model.version} is already trained on the current eligible historical dataset."
        )

    training_records, test_records, evaluation_scope = _split_records(records)
    provisional = train_logistic_regression(
        _rows(training_records),
        [record.target_priority for record in training_records],
        PRIORITY_CLASSES,
    )
    evaluation_records = test_records or training_records
    evaluation = evaluate_model(
        provisional,
        _rows(evaluation_records),
        [record.target_priority for record in evaluation_records],
    )
    final_parameters = train_logistic_regression(
        _rows(records),
        [record.target_priority for record in records],
        PRIORITY_CLASSES,
    )
    AIModelVersion.objects.filter(status="active").update(status="retired")
    model = AIModelVersion.objects.create(
        version=_unique_model_version(),
        algorithm="multinomial-logistic-regression",
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        dataset_version=dataset_version,
        sample_count=len(records),
        class_labels=PRIORITY_CLASSES,
        feature_names=FEATURE_NAMES,
        parameters=final_parameters,
        metrics={
            **evaluation,
            "evaluation_scope": evaluation_scope,
            "label_counts": {label: counts.get(label, 0) for label in PRIORITY_CLASSES},
            "held_out_count": len(test_records),
            "warning": (
                "Accuracy is measured on the training records because the dataset is not yet large enough for a reliable held-out test."
                if not test_records else "Accuracy is measured on a held-out set not used for provisional model fitting."
            ),
        },
        status="active",
        trained_by=user,
    )
    test_ids = {record.pk for record in test_records}
    AIModelTrainingRecord.objects.bulk_create([
        AIModelTrainingRecord(
            model_version=model,
            training_record=record,
            split="test" if record.pk in test_ids else "train",
        )
        for record in records
    ])
    _log_activity(user, "ai_model_trained", {
        "operation": "historical_reference_rebuilt",
        "rules_remain_primary": True,
        "hosted_model_fine_tuned": False,
        "model_version": model.version,
        "dataset_version": model.dataset_version,
        "sample_count": model.sample_count,
        "metrics": model.metrics,
    })
    return model


def get_active_model():
    return AIModelVersion.objects.filter(
        status="active", feature_schema_version=FEATURE_SCHEMA_VERSION
    ).order_by("-created_at", "-id").first()


def set_training_record_eligibility(record, user, is_eligible, reason=""):
    reason = str(reason or "").strip()
    if not is_eligible and not reason:
        raise ValueError("Explain why this validated project is excluded from model training.")
    record.is_eligible = bool(is_eligible)
    record.exclusion_reason = "" if is_eligible else reason
    record.save(update_fields=["is_eligible", "exclusion_reason", "updated_at"])
    _log_activity(user, "ai_training_record_updated", {
        "training_record_id": record.pk,
        "project_id": record.project_id,
        "is_eligible": record.is_eligible,
        "reason": record.exclusion_reason,
    })
    return record


def ensure_learning_assessment(priority_analysis):
    features = extract_feature_snapshot(priority_analysis)
    candidates = [record for record in _latest_eligible_records() if record.project_id != priority_analysis.project_id]
    scores = priority_analysis.suggested_scores if isinstance(priority_analysis.suggested_scores, dict) else {}
    provider = scores.get("ai_provider") if isinstance(scores.get("ai_provider"), dict) else {}
    groq_analysis = scores.get("groq_analysis") if isinstance(scores.get("groq_analysis"), dict) else {}
    groq_prediction = (
        groq_analysis.get("historical_prediction")
        if isinstance(groq_analysis.get("historical_prediction"), dict)
        else {}
    )
    if provider.get("name") == "groq" and provider.get("model"):
        reference_model = AIModelVersion.objects.filter(
            version=str(provider.get("reference_model_version") or ""),
        ).first()
        if reference_model:
            candidates = list(
                AITrainingRecord.objects.filter(
                    model_memberships__model_version=reference_model,
                ).exclude(project_id=priority_analysis.project_id).select_related(
                    "project", "confirmation__validator", "confirmation__analysis", "rule_set"
                ).order_by("-confirmation__created_at", "-id")
            )
        dataset_version = str(provider.get("dataset_version") or "empty")
        inference_version = (
            f"groq-{provider['model']}-{dataset_version}-{priority_analysis.source_hash[:10]}"
        )[:80]
        existing = AIProjectAnalysis.objects.filter(
            priority_analysis=priority_analysis,
            inference_version=inference_version,
        ).select_related("model_version").prefetch_related(
            "similar_projects__training_record__project",
            "similar_projects__training_record__confirmation__validator",
        ).first()
        if existing:
            return existing

        missing_facts = scores.get("missing_facts") or []
        predicted = str(groq_prediction.get("priority") or "").lower()
        if predicted not in PRIORITY_CLASSES:
            predicted = ""
        try:
            confidence = max(0.0, min(1.0, float(groq_prediction.get("confidence") or 0)))
        except (TypeError, ValueError):
            confidence = 0.0
        if missing_facts:
            status = "insufficient_evidence"
            predicted = ""
            confidence = 0.0
            summary = (
                "Groq reviewed the project, but its historical priority prediction is withheld until the required "
                "validator facts are complete."
            )
        elif not candidates:
            status = "untrained"
            predicted = ""
            confidence = 0.0
            summary = (
                "Groq is active, but no eligible validator-confirmed historical projects are available yet. "
                "Confirm projects and keep suitable records eligible in the AI Scoring CMS."
            )
        elif predicted:
            status = "ready"
            summary = str(groq_prediction.get("explanation") or "").strip() or (
                f"Groq compared this project with {len(candidates)} eligible validator-confirmed projects and "
                f"suggested {predicted.title()} Priority as advisory historical context."
            )
        else:
            status = "insufficient_evidence"
            summary = "Groq did not return a reliable historical priority prediction for this project."
        probabilities = {}
        if predicted:
            other = "high" if predicted == "low" else "low"
            probabilities = {predicted: round(confidence, 6), other: round(1.0 - confidence, 6)}
        explanation = {
            "summary": summary,
            "influential_features": [],
            "limitations": [
                "The approved scoring rules and current project evidence remain the primary basis for scoring.",
                "The administrator rebuilds a versioned reference dataset and local calibration model; this does not fine-tune the hosted Groq model.",
                "The prediction is advisory and cannot validate, endorse, reject, or change the project.",
                "The validator must verify all cited evidence and make the final decision.",
            ],
            "provider": "groq",
            "provider_model": provider.get("model"),
            "used_backup": bool(provider.get("used_backup")),
            "dataset_version": dataset_version,
            "sample_count": len(candidates),
            "reference_model_version": reference_model.version if reference_model else "live-unversioned",
        }
        assessment = AIProjectAnalysis.objects.create(
            priority_analysis=priority_analysis,
            guideline_rule_set=priority_analysis.rule_set,
            model_version=reference_model,
            inference_version=inference_version,
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            feature_snapshot=features,
            status=status,
            predicted_priority=predicted,
            confidence=confidence,
            class_probabilities=probabilities,
            explanation=explanation,
        )
        matches = find_similar_projects(features, candidates, limit=3)
        AISimilarProject.objects.bulk_create([
            AISimilarProject(
                analysis=assessment,
                training_record=match["record"],
                rank=index,
                similarity_score=round(match["score"], 6),
                shared_features=match["shared_features"],
            )
            for index, match in enumerate(matches, start=1)
        ])
        return assessment

    model = get_active_model()
    if model:
        inference_version = model.version
    else:
        reference_hash = hashlib.sha256(
            ",".join(str(record.pk) for record in candidates).encode("utf-8")
        ).hexdigest()[:12]
        inference_version = f"untrained-{reference_hash}"
    existing = AIProjectAnalysis.objects.filter(
        priority_analysis=priority_analysis,
        inference_version=inference_version,
    ).select_related("model_version").prefetch_related(
        "similar_projects__training_record__project",
        "similar_projects__training_record__confirmation__validator",
    ).first()
    if existing:
        return existing

    probabilities = {}
    predicted = ""
    confidence = 0.0
    missing_facts = (
        priority_analysis.suggested_scores.get("missing_facts")
        if isinstance(priority_analysis.suggested_scores, dict)
        else []
    ) or []
    if model and missing_facts:
        explanation = {
            "summary": (
                "A historical model is active, but its learned priority prediction is withheld until the required "
                "project facts are complete. The similar-project references below may still help the validator review context."
            ),
            "influential_features": [],
            "limitations": [
                "Complete the deterministic scorer's missing facts and run the analysis again before using a learned prediction.",
                "The model remains advisory and cannot make the final validation decision.",
            ],
        }
        status = "insufficient_evidence"
    elif model:
        row = feature_vector(features, model.feature_names)
        probabilities = predict_probabilities(model.parameters, row)
        predicted = max(probabilities, key=probabilities.get)
        confidence = probabilities[predicted]
        explanation = {
            "summary": (
                f"Model {model.version} compared this project's structured scoring profile with "
                f"{model.sample_count} distinct validator-confirmed projects. Its learned advisory prediction is "
                f"{predicted.title()} Priority."
            ),
            "influential_features": feature_contributions(
                model.parameters, row, model.feature_names, predicted
            ),
            "limitations": [
                "This prediction is advisory and cannot validate, endorse, reject, or change the project.",
                "Confidence reflects patterns in the available confirmed dataset; it is not proof that the recommendation is correct.",
                str(model.metrics.get("warning") or ""),
            ],
        }
        status = "ready"
    else:
        explanation = {
            "summary": (
                "No trained historical model is active yet. Add at least one validator-confirmed low-priority "
                "and high-priority project, then have an administrator train a model in the AI Scoring CMS."
            ),
            "influential_features": [],
            "limitations": ["The deterministic guideline score remains available while the historical model is untrained."],
        }
        status = "untrained"

    assessment = AIProjectAnalysis.objects.create(
        priority_analysis=priority_analysis,
        guideline_rule_set=priority_analysis.rule_set,
        model_version=model,
        inference_version=inference_version,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_snapshot=features,
        status=status,
        predicted_priority=predicted,
        confidence=confidence,
        class_probabilities={key: round(value, 6) for key, value in probabilities.items()},
        explanation=explanation,
    )
    matches = find_similar_projects(features, candidates, limit=3)
    AISimilarProject.objects.bulk_create([
        AISimilarProject(
            analysis=assessment,
            training_record=match["record"],
            rank=index,
            similarity_score=round(match["score"], 6),
            shared_features=match["shared_features"],
        )
        for index, match in enumerate(matches, start=1)
    ])
    return assessment
