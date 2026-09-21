from rest_framework import serializers

from .models import AIModelVersion, AIProjectAnalysis, AITrainingRecord


def _user_name(user):
    if not user:
        return ""
    return (getattr(user, "full_name", "") or user.get_full_name() or user.username).strip()


class AIModelVersionSerializer(serializers.ModelSerializer):
    trained_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AIModelVersion
        fields = [
            "id", "version", "algorithm", "feature_schema_version", "dataset_version",
            "sample_count", "class_labels", "feature_names", "metrics", "status",
            "trained_by", "trained_by_name", "created_at",
        ]
        read_only_fields = fields

    def get_trained_by_name(self, obj):
        return _user_name(obj.trained_by)


class AITrainingRecordSerializer(serializers.ModelSerializer):
    project_title = serializers.CharField(source="project.name", read_only=True)
    agency = serializers.SerializerMethodField()
    rule_version = serializers.CharField(source="rule_set.version", read_only=True)
    validator_name = serializers.SerializerMethodField()
    confirmed_at = serializers.DateTimeField(source="confirmation.created_at", read_only=True)
    sector = serializers.SerializerMethodField()
    submission_type = serializers.SerializerMethodField()

    class Meta:
        model = AITrainingRecord
        fields = [
            "id", "confirmation", "project", "project_title", "agency", "sector",
            "submission_type", "rule_version", "target_priority", "validator_name",
            "confirmed_at", "feature_schema_version", "is_eligible", "exclusion_reason",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def _feature_context(self, obj):
        value = obj.feature_snapshot.get("context") if isinstance(obj.feature_snapshot, dict) else {}
        return value if isinstance(value, dict) else {}

    def get_agency(self, obj):
        return obj.project.agency or obj.project.implementing_agency

    def get_validator_name(self, obj):
        return _user_name(obj.confirmation.validator)

    def get_sector(self, obj):
        return str(self._feature_context(obj).get("sector") or "")

    def get_submission_type(self, obj):
        return str(self._feature_context(obj).get("submission_type") or "")


def serialize_learning_assessment(assessment):
    if not assessment:
        return None
    similar = []
    for match in assessment.similar_projects.all():
        record = match.training_record
        similar.append({
            "project_id": record.project_id,
            "project_title": record.project.name,
            "agency": record.project.agency or record.project.implementing_agency,
            "final_priority": record.target_priority,
            "similarity": round(float(match.similarity_score), 4),
            "shared_features": match.shared_features,
            "confirmed_at": record.confirmation.created_at,
            "validator_name": _user_name(record.confirmation.validator),
        })
    model = assessment.model_version
    return {
        "status": assessment.status,
        "advisory": True,
        "model_version": model.version if model else None,
        "dataset_version": model.dataset_version if model else None,
        "sample_count": model.sample_count if model else 0,
        "predicted_priority": assessment.predicted_priority or None,
        "confidence": round(float(assessment.confidence), 4),
        "class_probabilities": assessment.class_probabilities,
        "explanation": assessment.explanation,
        "similar_projects": similar,
        "generated_at": assessment.created_at,
    }
