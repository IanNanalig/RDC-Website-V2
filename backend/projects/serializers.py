from rest_framework import serializers
from datetime import datetime
from copy import deepcopy
from cms.form_schema import CURRENT_PROJECT_STATUS_VALUES, FormSchemaError, validate_simplified_answers
from .project_status import canonical_implementation_status
from .models import (
    AccessRequest,
    Notification,
    PasswordResetRequest,
    PublicEvent,
    PriorityRuleSet,
    Project,
    ProjectComment,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    ProjectDocumentAssessment,
    ProjectSupportingDocument,
    ProjectRevision,
    User,
    UserActivity,
)

SYSTEM_MANAGED_DIFF_ROOTS = {
    "public_summary",
    "public_summary_override",
    "simplified_form_meta",
    "validator_review",
    "validator_revision_access",
    "contributor_snapshot",
    "form_schema",
}


def _user_display_name(user):
    return (user.get_full_name() or user.get_username() or "").strip()


class ContributorFormVersionStatusMixin:
    """Expose whether a saved simplified project predates the live CMS form."""

    def _form_profile(self, obj):
        return obj.profile_data if isinstance(obj.profile_data, dict) else {}

    def _saved_form_marker(self, obj):
        profile = self._form_profile(obj)
        simplified = isinstance(profile.get("simplified_form"), dict)
        submission_type = str(profile.get("submission_type") or "").strip().lower()
        if not simplified and submission_type != "simplified":
            return None
        marker = profile.get("form_schema")
        return marker if isinstance(marker, dict) else {"key": "simplified-rdip", "version": 1}

    def _saved_form_version(self, obj):
        marker = self._saved_form_marker(obj)
        if marker is None:
            return None
        try:
            version = int(marker.get("version") or 1)
        except (TypeError, ValueError):
            version = 1
        return max(version, 1)

    def _live_form_version(self, obj):
        marker = self._saved_form_marker(obj)
        if marker is None:
            return None
        key = str(marker.get("key") or "simplified-rdip").strip() or "simplified-rdip"
        cache = self.context.setdefault("_contributor_form_live_versions", {})
        if key not in cache:
            # Imported lazily to keep the projects/cms serializer dependency one-way.
            from cms.models import CMSContributorForm

            cache[key] = CMSContributorForm.objects.filter(key=key).values_list(
                "current_published_version__version_number", flat=True
            ).first()
        return cache[key]

    def get_form_version(self, obj):
        return self._saved_form_version(obj)

    def get_current_form_version(self, obj):
        return self._live_form_version(obj)

    def get_uses_outdated_form(self, obj):
        saved = self._saved_form_version(obj)
        current = self._live_form_version(obj)
        return bool(saved is not None and current is not None and saved < current)


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "role",
            "is_active",
            "password",
            "first_name",
            "last_name",
            "agency",
            "agency_head",
            "office",
            "division",
            "position",
            "contact_number",
            "phone_number",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password", None) or "ChangeMe123!"
        role = validated_data.get("role")
        if role == "contributor":
            validated_data["role"] = "staff"
        elif role == "content-editor":
            validated_data["role"] = "content_editor"
        user = User(**validated_data)
        user.is_staff = user.role == "admin"
        user.set_password(password)
        user.save()
        return user

    def validate_first_name(self, value):
        return self._validate_person_name(value)

    def validate_last_name(self, value):
        return self._validate_person_name(value)

    def _validate_person_name(self, value):
        value = value.strip()
        if not value or len(value) > 150 or not any(character.isalpha() for character in value) or any(
            not (character.isalpha() or character in " '-") for character in value
        ):
            raise serializers.ValidationError(
                "Use 1–150 letters, spaces, apostrophes, or hyphens."
            )
        return value

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        role = validated_data.get("role")
        if role == "contributor":
            validated_data["role"] = "staff"
        elif role == "content-editor":
            validated_data["role"] = "content_editor"
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if "role" in validated_data:
            instance.is_staff = instance.role == "admin"
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class PublicEventSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    day = serializers.SerializerMethodField()
    month = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    end_time = serializers.SerializerMethodField()

    class Meta:
        model = PublicEvent
        fields = [
            "id",
            "title",
            "description",
            "event_type",
            "start_at",
            "end_at",
            "day",
            "month",
            "time",
            "end_time",
            "location",
            "is_virtual",
            "meeting_link",
            "status",
            "review_notes",
            "created_by_name",
            "submitted_by_name",
            "reviewed_by_name",
            "published_at",
            "archived_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by_name",
            "submitted_by_name",
            "reviewed_by_name",
            "published_at",
            "archived_at",
            "created_at",
            "updated_at",
        ]

    def _name(self, user):
        if not user:
            return ""
        return _user_display_name(user) or user.username

    def get_created_by_name(self, obj):
        return self._name(obj.created_by)

    def get_submitted_by_name(self, obj):
        return self._name(obj.submitted_by)

    def get_reviewed_by_name(self, obj):
        return self._name(obj.reviewed_by)

    def get_day(self, obj):
        return obj.start_at.day if obj.start_at else None

    def get_month(self, obj):
        return obj.start_at.strftime("%b").upper() if obj.start_at else ""

    def get_time(self, obj):
        return obj.start_at.strftime("%I:%M %p").lstrip("0") if obj.start_at else ""

    def get_end_time(self, obj):
        return obj.end_at.strftime("%I:%M %p").lstrip("0") if obj.end_at else ""

    def validate(self, attrs):
        start_at = attrs.get("start_at", getattr(self.instance, "start_at", None))
        end_at = attrs.get("end_at", getattr(self.instance, "end_at", None))
        meeting_link = str(attrs.get("meeting_link", getattr(self.instance, "meeting_link", "")) or "").strip()
        is_virtual = bool(attrs.get("is_virtual", getattr(self.instance, "is_virtual", False)))
        location = str(attrs.get("location", getattr(self.instance, "location", "")) or "").strip()
        if end_at and start_at and end_at <= start_at:
            raise serializers.ValidationError("End date/time must be after the start date/time.")
        if is_virtual and not meeting_link and not location:
            raise serializers.ValidationError("Virtual events need a meeting link or public location note.")
        return attrs


class ProjectSerializer(ContributorFormVersionStatusMixin, serializers.ModelSerializer):
    # Frontend compatibility: accepts and returns title while storing as name.
    title = serializers.CharField(source="name", required=False)
    status = serializers.CharField(required=False)
    submitted_by = UserSerializer(source="created_by", read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    validated_by = serializers.SerializerMethodField()
    priority_analysis = serializers.SerializerMethodField()
    workflow_status = serializers.SerializerMethodField()
    workflow_status_label = serializers.SerializerMethodField()
    submission_type = serializers.SerializerMethodField()
    official_priority = serializers.SerializerMethodField()
    official_priority_label = serializers.SerializerMethodField()
    validation_comment = serializers.SerializerMethodField()
    document_assessment = serializers.SerializerMethodField()

    form_version = serializers.SerializerMethodField()
    current_form_version = serializers.SerializerMethodField()
    uses_outdated_form = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "name",
            "description",
            "agency",
            "budget",
            "completion",
            "profile_data",
            "status",
            "created_at",
            "updated_at",
            "submitted_by",
            "submitted_by_name",
            "validated_by",
            "archived",
            "validated",
            "municipality",
            "implementing_agency",
            "cost",
            "latitude",
            "longitude",
            "year",
            "priority_analysis_eligible",
            "priority_analysis",
            "workflow_status",
            "workflow_status_label",
            "submission_type",
            "official_priority",
            "official_priority_label",
            "validation_comment",
            "form_version",
            "current_form_version",
            "uses_outdated_form",
            "supporting_document_policy",
            "document_assessment",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "submitted_by",
            "submitted_by_name",
            "validated_by",
            "workflow_status",
            "workflow_status_label",
            "official_priority",
            "official_priority_label",
            "validation_comment",
            "supporting_document_policy",
            "document_assessment",
        ]
        extra_kwargs = {
            "name": {"required": False},
            "implementing_agency": {"required": False},
            "municipality": {"required": False},
            "status": {"required": False},
            "cost": {"required": False},
            "latitude": {"required": False},
            "description": {"required": False},
            "profile_data": {"required": False},
        }

    def get_validated_by(self, obj):
        # Current schema has no validated_by foreign key.
        return None

    def get_submission_type(self, obj):
        profile = obj.profile_data if isinstance(obj.profile_data, dict) else {}
        marker = str(profile.get("submission_type") or "").strip().lower()
        return "simplified" if marker == "simplified" or (marker != "detailed" and isinstance(profile.get("simplified_form"), dict)) else "unsupported"

    def get_submitted_by_name(self, obj):
        if not obj.created_by:
            return ""
        return _user_display_name(obj.created_by) or obj.created_by.username

    def get_priority_analysis(self, obj):
        analysis = self._latest_analysis(obj)
        if not analysis:
            return None
        confirmations = list(analysis.confirmations.all())
        confirmation = confirmations[0] if confirmations else None
        return {
            "analysis_id": analysis.id,
            "score": float(analysis.base_score),
            "suggested_priority": analysis.suggested_priority,
            "final_priority": confirmation.final_priority if confirmation else "",
            "confirmed": bool(confirmation),
            "created_at": analysis.created_at,
        }

    def _validator_review(self, obj):
        profile_data = obj.profile_data if isinstance(obj.profile_data, dict) else {}
        review = profile_data.get("validator_review")
        return review if isinstance(review, dict) else {}

    def get_workflow_status(self, obj):
        review_status = str(self._validator_review(obj).get("review_status") or "").lower()
        if review_status in ("reviewed", "rejected"):
            return "needs_revision" if review_status == "reviewed" else "rejected"
        if review_status in ("endorsed", "validated") or obj.validated or obj.status == "completed":
            return "validated"
        if obj.status == "proposed":
            return "pending_validation"
        if obj.status == "planning":
            return "draft"
        return obj.status or ""

    def get_workflow_status_label(self, obj):
        return {
            "draft": "Draft",
            "pending_validation": "Pending Validation",
            "needs_revision": "Needs Revision",
            "validated": "Validated",
            "rejected": "Rejected",
            "ongoing": "Ongoing",
            "completed": "Validated",
        }.get(self.get_workflow_status(obj), self.get_workflow_status(obj).replace("_", " ").title())

    def _latest_confirmation(self, obj):
        analysis = self._latest_analysis(obj)
        if not analysis:
            return None
        confirmations = list(analysis.confirmations.all())
        return confirmations[0] if confirmations else None

    def _latest_analysis(self, obj):
        if hasattr(obj, "_serializer_latest_analysis"):
            return obj._serializer_latest_analysis
        prefetched = getattr(obj, "_latest_priority_analyses", None)
        if prefetched is not None:
            analysis = prefetched[0] if prefetched else None
        else:
            analysis = obj.priority_analyses.prefetch_related("confirmations").order_by("-created_at").first()
        obj._serializer_latest_analysis = analysis
        return analysis

    def get_official_priority(self, obj):
        confirmation = self._latest_confirmation(obj)
        return confirmation.final_priority if confirmation else ""

    def get_official_priority_label(self, obj):
        value = self.get_official_priority(obj)
        if value == "high":
            return "Priority"
        if value in ("medium", "low"):
            return "Non-Priority"
        return ""

    def get_validation_comment(self, obj):
        return str(self._validator_review(obj).get("review_notes") or "")

    def get_document_assessment(self, obj):
        from .document_assessments import serialize_document_assessment

        return serialize_document_assessment(obj)

    def validate_status(self, value):
        mapping = {
            "draft": "planning",
            "pending_validation": "proposed",
            "approved": "completed",
            "validated": "completed",
            "rejected": "planning",
        }
        return mapping.get(value, value)

    def validate_profile_data(self, value):
        if value in (None, ""):
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError("profile_data must be a JSON object.")
        simplified = value.get("simplified_form")
        marker = str(value.get("submission_type") or "").strip().lower()
        if marker not in ("", "simplified") or not isinstance(simplified, dict):
            raise serializers.ValidationError("Only the simplified project form is supported.")
        if isinstance(simplified, dict):
            value = deepcopy(value)
            value["submission_type"] = "simplified"
            project_status = str(simplified.get("status") or "").strip()
            previous_status = ""
            if self.instance and isinstance(self.instance.profile_data, dict):
                previous_form = self.instance.profile_data.get("simplified_form")
                if isinstance(previous_form, dict):
                    previous_status = str(previous_form.get("status") or "").strip()
            if project_status and project_status not in CURRENT_PROJECT_STATUS_VALUES and project_status != previous_status:
                raise serializers.ValidationError(
                    "Choose a current project status: Completed, New, Ongoing, or Not Implemented."
                )
            self._validate_simplified_funding(simplified)
            value = deepcopy(value)
            if self.instance and isinstance(self.instance.profile_data, dict):
                existing_marker = self.instance.profile_data.get("form_schema")
                if isinstance(existing_marker, dict):
                    value["form_schema"] = deepcopy(existing_marker)
                else:
                    value["form_schema"] = {"key": "simplified-rdip", "version": 1, "legacy": True}
            else:
                if isinstance(value.get("form_schema"), dict):
                    # The version number is still selected by the server; the marker only signals
                    # that this client supports versioned contributor forms.
                    value["form_schema"] = {"key": "simplified-rdip"}
                else:
                    # Old frontends remain pinned to the legacy definition during staggered deploys.
                    value["form_schema"] = {"key": "simplified-rdip", "version": 1, "legacy": True}
            try:
                validate_simplified_answers(
                    value,
                    require_complete=False,
                    legacy_status=previous_status if project_status == previous_status else None,
                )
            except FormSchemaError as exc:
                raise serializers.ValidationError(str(exc)) from exc
        return value

    def validate(self, attrs):
        request = self.context.get("request")
        if (
            request is not None
            and request.method == "POST"
            and str(attrs.get("status") or "").strip().lower() == "proposed"
        ):
            raise serializers.ValidationError(
                {"status": "Save the project as a draft, upload its supporting documents, then submit it."}
            )
        if (
            request is not None
            and request.method == "POST"
            and str(attrs.get("status") or "").strip().lower() == "proposed"
            and not isinstance((attrs.get("profile_data") or {}).get("simplified_form"), dict)
        ):
            raise serializers.ValidationError({"profile_data": "A simplified project form is required for submission."})
        return attrs

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        profile_data = rep.get("profile_data")
        if isinstance(profile_data, dict):
            validator_review = profile_data.get("validator_review")
            if isinstance(validator_review, dict):
                raw_fields = validator_review.get("edited_fields")
                if isinstance(raw_fields, list):
                    clean_fields = []
                    for item in raw_fields:
                        if not isinstance(item, dict):
                            continue
                        root = str(item.get("field") or "").split(".")[0]
                        if root in SYSTEM_MANAGED_DIFF_ROOTS:
                            continue
                        clean_fields.append(item)
                    next_review = dict(validator_review)
                    next_review["edited_fields"] = clean_fields
                    next_review["edited_fields_count"] = len(clean_fields)
                    next_review["edited"] = bool(clean_fields)
                    next_profile = dict(profile_data)
                    next_profile["validator_review"] = next_review
                    rep["profile_data"] = next_profile
        request = self.context.get("request")
        role = getattr(getattr(request, "user", None), "role", "") if request else ""
        if role not in ("staff", "employee"):
            return rep
        profile_data = rep.get("profile_data")
        if not isinstance(profile_data, dict):
            return rep
        meta = profile_data.get("simplified_form_meta")
        if not isinstance(meta, dict):
            return rep
        edits = meta.get("field_edits")
        if not isinstance(edits, dict) or not edits:
            return rep

        def parse_at(value):
            if not value:
                return None
            raw = str(value).strip()
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            try:
                return datetime.fromisoformat(raw)
            except Exception:
                return None

        entries = []
        for key, val in edits.items():
            if not isinstance(val, dict):
                continue
            at = val.get("at")
            if not at:
                continue
            entries.append((str(key), val, str(at), parse_at(at)))
        if len(entries) < 6:
            return rep

        # Heuristic for legacy drafts: initial fill created edit meta for almost every field at the same timestamp.
        # If so, hide that initial-fill batch so only post-baseline edits are highlighted.
        counts = {}
        earliest = None
        for _, _, at_str, at_dt in entries:
            counts[at_str] = counts.get(at_str, 0) + 1
            if at_dt is not None:
                earliest = at_dt if earliest is None else min(earliest, at_dt)

        earliest_at_str = None
        if earliest is not None:
            for _, _, at_str, at_dt in entries:
                if at_dt == earliest:
                    earliest_at_str = at_str
                    break
        if earliest_at_str is None:
            earliest_at_str = sorted(counts.keys())[0]

        total = len(entries)
        earliest_count = counts.get(earliest_at_str, 0)
        if earliest_count >= max(8, int(total * 0.6)):
            next_edits = {k: v for k, v in edits.items() if not (isinstance(v, dict) and str(v.get("at") or "") == earliest_at_str)}
            next_meta = dict(meta)
            next_meta["field_edits"] = next_edits
            next_profile = dict(profile_data)
            next_profile["simplified_form_meta"] = next_meta
            rep["profile_data"] = next_profile
        return rep

    def _parse_year(self, value):
        try:
            n = int(str(value or "").strip())
        except Exception:
            return None
        if n < 1900 or n > 2200:
            return None
        return n

    def _validate_simplified_funding(self, simplified):
        start = self._parse_year(simplified.get("startYear"))
        end = self._parse_year(simplified.get("endYear"))
        if start is None or end is None:
            raise serializers.ValidationError("Start Year and End Year must be valid years.")
        if end < start:
            raise serializers.ValidationError("End Year must be the same as or later than Start Year.")
        if end - start > 15:
            raise serializers.ValidationError("Year range is too large (max 15 years).")
        allowed = set()
        if start <= 2022:
            allowed.add("2022_prior")
            first = max(2023, start)
        else:
            first = start
        for year in range(first, end + 1):
            allowed.add(str(year))

        for field in ("fundingRequirementByYear", "actualFundingByYear"):
            raw = simplified.get(field) or {}
            if not isinstance(raw, dict):
                raise serializers.ValidationError(f"{field} must be an object.")
            for key in raw.keys():
                key_str = str(key)
                if key_str not in allowed:
                    raise serializers.ValidationError(f"{field} contains out-of-range key: {key_str}.")

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        validated_data.setdefault("name", validated_data.get("name", "Untitled Project"))
        validated_data.setdefault("implementing_agency", validated_data.get("agency", "N/A"))
        validated_data.setdefault("municipality", "NCR")
        validated_data.setdefault("cost", validated_data.get("budget", 0) or 0)
        validated_data.setdefault("latitude", 14.5995)
        validated_data.setdefault("agency", validated_data.get("agency", ""))
        validated_data.setdefault("budget", validated_data.get("budget", 0))
        validated_data.setdefault("completion", validated_data.get("completion", 0))
        validated_data.setdefault("description", validated_data.get("description", ""))
        validated_data.setdefault("status", validated_data.get("status", "planning"))
        return super().create(validated_data)

    def update(self, instance, validated_data):
        project = super().update(instance, validated_data)
        request = self.context.get("request")
        role = getattr(getattr(request, "user", None), "role", "")
        profile = project.profile_data if isinstance(project.profile_data, dict) else {}
        review = profile.get("validator_review") if isinstance(profile.get("validator_review"), dict) else {}
        if (
            role in ("staff", "employee")
            and not project.supporting_document_policy
            and (project.status == "planning" or str(review.get("review_status") or "").lower() == "reviewed")
        ):
            from .document_policy import current_document_policy

            policy = current_document_policy("simplified-rdip")
            if policy:
                project.supporting_document_policy = policy
                project.save(update_fields=["supporting_document_policy", "updated_at"])
        return project


class ProjectSummarySerializer(ContributorFormVersionStatusMixin, serializers.ModelSerializer):
    """Compact, additive projection used only when list callers request view=summary."""

    title = serializers.CharField(source="name", read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    workflow_status = serializers.SerializerMethodField()
    workflow_status_label = serializers.SerializerMethodField()
    official_priority = serializers.SerializerMethodField()
    official_priority_label = serializers.SerializerMethodField()
    validation_comment = serializers.SerializerMethodField()
    submission_type = serializers.SerializerMethodField()
    rdip_status = serializers.SerializerMethodField()
    review_status = serializers.SerializerMethodField()
    reviewed_by_username = serializers.SerializerMethodField()
    validator_edited = serializers.SerializerMethodField()
    validator_edited_fields_count = serializers.SerializerMethodField()
    form_version = serializers.SerializerMethodField()
    current_form_version = serializers.SerializerMethodField()
    uses_outdated_form = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "name",
            "agency",
            "budget",
            "completion",
            "status",
            "workflow_status",
            "workflow_status_label",
            "official_priority",
            "official_priority_label",
            "validation_comment",
            "updated_at",
            "validated",
            "submitted_by_name",
            "submission_type",
            "rdip_status",
            "review_status",
            "reviewed_by_username",
            "validator_edited",
            "validator_edited_fields_count",
            "form_version",
            "current_form_version",
            "uses_outdated_form",
        ]
        read_only_fields = fields

    def _full(self):
        serializer = getattr(self, "_full_serializer", None)
        if serializer is None:
            serializer = ProjectSerializer(context=self.context)
            self._full_serializer = serializer
        return serializer

    def _profile(self, obj):
        return obj.profile_data if isinstance(obj.profile_data, dict) else {}

    def _review(self, obj):
        review = self._profile(obj).get("validator_review")
        return review if isinstance(review, dict) else {}

    def get_submitted_by_name(self, obj):
        return self._full().get_submitted_by_name(obj)

    def get_workflow_status(self, obj):
        return self._full().get_workflow_status(obj)

    def get_workflow_status_label(self, obj):
        return self._full().get_workflow_status_label(obj)

    def get_official_priority(self, obj):
        return self._full().get_official_priority(obj)

    def get_official_priority_label(self, obj):
        return self._full().get_official_priority_label(obj)

    def get_validation_comment(self, obj):
        return self._full().get_validation_comment(obj)

    def get_submission_type(self, obj):
        profile = self._profile(obj)
        value = str(profile.get("submission_type") or "").strip().lower()
        return "simplified" if value == "simplified" or (value != "detailed" and isinstance(profile.get("simplified_form"), dict)) else "unsupported"

    def get_rdip_status(self, obj):
        simplified = self._profile(obj).get("simplified_form")
        return canonical_implementation_status(simplified.get("status")) if isinstance(simplified, dict) else ""

    def get_review_status(self, obj):
        return str(self._review(obj).get("review_status") or "").strip().lower()

    def get_reviewed_by_username(self, obj):
        return str(self._review(obj).get("reviewed_by_username") or "").strip()

    def _edited_fields(self, obj):
        raw = self._review(obj).get("edited_fields")
        if not isinstance(raw, list):
            return []
        return [
            item
            for item in raw
            if isinstance(item, dict)
            and str(item.get("field") or "").split(".")[0] not in SYSTEM_MANAGED_DIFF_ROOTS
        ]

    def get_validator_edited(self, obj):
        return bool(self._edited_fields(obj))

    def get_validator_edited_fields_count(self, obj):
        return len(self._edited_fields(obj))


class ProjectPriorityConfirmationSerializer(serializers.ModelSerializer):
    validator_name = serializers.SerializerMethodField()

    class Meta:
        model = ProjectPriorityConfirmation
        fields = [
            "id",
            "validator",
            "validator_name",
            "adjusted_scores",
            "final_priority",
            "override_rationale",
            "confirmed_flags",
            "document_assessment",
            "document_override",
            "document_override_rationale",
            "created_at",
        ]
        read_only_fields = fields

    def get_validator_name(self, obj):
        if not obj.validator:
            return ""
        return _user_display_name(obj.validator) or obj.validator.username


class ProjectPriorityAnalysisSerializer(serializers.ModelSerializer):
    validator_name = serializers.SerializerMethodField()
    rule_version = serializers.CharField(source="rule_set.version", read_only=True)
    algorithm_version = serializers.CharField(source="rule_set.algorithm_version", read_only=True)
    confirmations = ProjectPriorityConfirmationSerializer(many=True, read_only=True)
    latest_confirmation = serializers.SerializerMethodField()
    learning_result = serializers.SerializerMethodField()
    document_assessment = serializers.SerializerMethodField()

    class Meta:
        model = ProjectPriorityAnalysis
        fields = [
            "id",
            "project",
            "validator",
            "validator_name",
            "rule_version",
            "algorithm_version",
            "source_hash",
            "supplements",
            "suggested_scores",
            "regional_scorecard",
            "flags",
            "summary",
            "suggested_priority",
            "base_score",
            "confirmations",
            "latest_confirmation",
            "learning_result",
            "document_assessment",
            "created_at",
        ]
        read_only_fields = fields

    def get_validator_name(self, obj):
        if not obj.validator:
            return ""
        return _user_display_name(obj.validator) or obj.validator.username

    def get_latest_confirmation(self, obj):
        confirmation = obj.confirmations.first()
        if not confirmation:
            return None
        return ProjectPriorityConfirmationSerializer(confirmation).data

    def get_learning_result(self, obj):
        from ai_engine.serializers import serialize_learning_assessment

        assessment = getattr(obj, "_current_learning_assessment", None)
        if assessment is None:
            assessment = obj.learning_assessments.select_related("model_version").prefetch_related(
                "similar_projects__training_record__project",
                "similar_projects__training_record__confirmation__validator",
            ).first()
        return serialize_learning_assessment(assessment)

    def get_document_assessment(self, obj):
        from .document_assessments import serialize_document_assessment

        return serialize_document_assessment(obj.project)


class ProjectSupportingDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ProjectSupportingDocument
        fields = [
            "id", "project", "field_key", "form_key", "form_version", "original_filename",
            "content_type", "extension", "size_bytes", "checksum_sha256", "extraction_status",
            "extraction_metadata", "processing_error", "uploaded_by_name", "created_at", "updated_at",
            "download_url",
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        return _user_display_name(obj.uploaded_by) if obj.uploaded_by else ""

    def get_download_url(self, obj):
        return f"/api/project-supporting-documents/{obj.pk}/download/"


class ProjectRevisionSerializer(ContributorFormVersionStatusMixin, serializers.ModelSerializer):
    project_title = serializers.CharField(source="project.title", read_only=True)
    project_agency = serializers.CharField(source="project.agency", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    endorsed_by_name = serializers.SerializerMethodField()
    form_version = serializers.SerializerMethodField()
    current_form_version = serializers.SerializerMethodField()
    uses_outdated_form = serializers.SerializerMethodField()
    submission_type = serializers.SerializerMethodField()

    class Meta:
        model = ProjectRevision
        fields = [
            "id",
            "project",
            "project_title",
            "project_agency",
            "revision_number",
            "revision_type",
            "state",
            "profile_data_snapshot",
            "public_summary_snapshot",
            "changed_fields",
            "public_note",
            "is_public_current",
            "created_by_name",
            "submitted_by_name",
            "reviewed_by_name",
            "endorsed_by_name",
            "created_at",
            "updated_at",
            "submitted_at",
            "reviewed_at",
            "endorsed_at",
            "form_version",
            "current_form_version",
            "uses_outdated_form",
            "submission_type",
        ]
        read_only_fields = fields

    def _form_profile(self, obj):
        return obj.profile_data_snapshot if isinstance(obj.profile_data_snapshot, dict) else {}

    def _name(self, user):
        if not user:
            return ""
        return _user_display_name(user) or user.username

    def get_submission_type(self, obj):
        profile = self._form_profile(obj)
        marker = str(profile.get("submission_type") or "").strip().lower()
        return "simplified" if marker == "simplified" or (marker != "detailed" and isinstance(profile.get("simplified_form"), dict)) else "unsupported"

    def get_created_by_name(self, obj):
        return self._name(obj.created_by)

    def get_submitted_by_name(self, obj):
        return self._name(obj.submitted_by)

    def get_reviewed_by_name(self, obj):
        return self._name(obj.reviewed_by)

    def get_endorsed_by_name(self, obj):
        return self._name(obj.endorsed_by)


class ProjectRevisionSummarySerializer(ProjectRevisionSerializer):
    budget = serializers.SerializerMethodField()
    submission_type = serializers.SerializerMethodField()

    class Meta(ProjectRevisionSerializer.Meta):
        fields = [
            "id",
            "project",
            "project_title",
            "project_agency",
            "revision_number",
            "revision_type",
            "state",
            "budget",
            "submission_type",
            "created_by_name",
            "submitted_by_name",
            "updated_at",
            "form_version",
            "current_form_version",
            "uses_outdated_form",
        ]
        read_only_fields = fields

    def _profile(self, obj):
        return obj.profile_data_snapshot if isinstance(obj.profile_data_snapshot, dict) else {}

    def get_budget(self, obj):
        summary = self._profile(obj).get("public_summary")
        facts = summary.get("key_facts") if isinstance(summary, dict) else None
        value = facts.get("funding_requirement_total") if isinstance(facts, dict) else None
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0

    def get_submission_type(self, obj):
        profile = self._profile(obj)
        value = str(profile.get("submission_type") or "").strip().lower()
        return "simplified" if value == "simplified" or (value != "detailed" and isinstance(profile.get("simplified_form"), dict)) else "unsupported"


class PublicProjectSerializer(serializers.ModelSerializer):
    # Public-safe projection for the public website dashboard.
    title = serializers.CharField(source="name", read_only=True)
    agency = serializers.SerializerMethodField()
    implementation_status = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    lgu = serializers.SerializerMethodField()
    lgus = serializers.SerializerMethodField()
    location_raw = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    public_summary_text = serializers.SerializerMethodField()
    public_summary_bullets = serializers.SerializerMethodField()
    public_key_facts = serializers.SerializerMethodField()
    last_endorsed_update_at = serializers.SerializerMethodField()
    endorsed_update_count = serializers.SerializerMethodField()
    has_public_updates = serializers.SerializerMethodField()
    public_progress_update_count = serializers.SerializerMethodField()
    latest_update_date = serializers.SerializerMethodField()
    latest_update_headline = serializers.SerializerMethodField()
    latest_update_badges = serializers.SerializerMethodField()
    public_update_timeline = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "agency",
            "implementation_status",
            "budget",
            "year",
            "lgu",
            "lgus",
            "location_raw",
            "description",
            "public_summary_text",
            "public_summary_bullets",
            "public_key_facts",
            "last_endorsed_update_at",
            "endorsed_update_count",
            "has_public_updates",
            "public_progress_update_count",
            "latest_update_date",
            "latest_update_headline",
            "latest_update_badges",
            "public_update_timeline",
            "updated_at",
        ]
        read_only_fields = fields

    def _simplified(self, obj) -> dict:
        pd = getattr(obj, "profile_data", None)
        if isinstance(pd, dict):
            sf = pd.get("simplified_form")
            if isinstance(sf, dict):
                return sf
        return {}

    def get_agency(self, obj):
        sf = self._simplified(obj)
        value = str(sf.get("agencyName") or "").strip()
        if value:
            return value
        return str(getattr(obj, "agency", "") or "").strip()

    def get_implementation_status(self, obj):
        # Prefer RDIP status from the simplified form; keep old names grouped without rewriting history.
        sf = self._simplified(obj)
        value = str(sf.get("status") or "").strip()
        if value:
            return canonical_implementation_status(value)
        return str(getattr(obj, "status", "") or "").strip()

    def get_year(self, obj):
        sf = self._simplified(obj)
        raw = str(sf.get("startYear") or "").strip()
        try:
            year = int(raw)
            if 1900 <= year <= 2200:
                return year
        except Exception:
            pass
        return getattr(obj, "year", None)

    def get_description(self, obj):
        sf = self._simplified(obj)
        value = str(sf.get("description") or "").strip()
        if value:
            return value
        return str(getattr(obj, "description", "") or "").strip()

    def get_location_raw(self, obj):
        from .utils import format_project_locations

        sf = self._simplified(obj)
        return format_project_locations(sf.get("location"))

    def get_lgu(self, obj):
        # Keep a primary LGU for backwards compatibility with older clients.
        try:
            from .utils import derive_ncr_lgu

            return derive_ncr_lgu(self.get_location_raw(obj))
        except Exception:
            return None

    def get_lgus(self, obj):
        try:
            from .utils import derive_ncr_lgus

            return derive_ncr_lgus(self.get_location_raw(obj))
        except Exception:
            return []

    def _public_summary_payload(self, obj) -> dict:
        pd = getattr(obj, "profile_data", None)
        if isinstance(pd, dict):
            # Prefer override for text, but still expose bullets/key facts from the generated summary.
            override = pd.get("public_summary_override")
            base = pd.get("public_summary")
            if isinstance(base, dict):
                payload = dict(base)
            else:
                payload = {}
            if isinstance(override, dict):
                override_text = str(override.get("text") or "").strip()
                if override_text:
                    payload["text"] = override_text
            return payload
        return {}

    def get_public_summary_text(self, obj):
        payload = self._public_summary_payload(obj)
        return str(payload.get("text") or "").strip()

    def get_public_summary_bullets(self, obj):
        payload = self._public_summary_payload(obj)
        raw = payload.get("bullets")
        if isinstance(raw, list):
            return [str(v) for v in raw if str(v).strip()]
        return []

    def get_public_key_facts(self, obj):
        payload = self._public_summary_payload(obj)
        raw = payload.get("key_facts")
        if isinstance(raw, dict):
            return raw
        return {}

    def _endorsed_revisions(self, obj):
        cached = getattr(obj, "_serializer_endorsed_revisions", None)
        if cached is not None:
            return cached
        try:
            prefetched = getattr(obj, "_public_endorsed_revisions", None)
            latest = getattr(obj, "_public_latest_endorsed_revision", None)
            revisions = prefetched if prefetched is not None else latest
            if revisions is None:
                revisions = list(obj.revisions.filter(state="endorsed").order_by("-endorsed_at", "-revision_number"))
        except Exception:
            revisions = []
        obj._serializer_endorsed_revisions = revisions
        return revisions

    def _progress_revisions(self, obj):
        latest = getattr(obj, "_public_latest_progress_revision", None)
        if latest is not None:
            return latest
        return [r for r in self._endorsed_revisions(obj) if r.revision_type == "progress_update"]

    def _field_label(self, field):
        raw = str(field or "").strip()
        if raw.startswith("fundingRequirementByYear."):
            year = raw.split(".", 1)[1]
            return f"Funding Requirement {self._year_label(year)}"
        if raw.startswith("actualFundingByYear."):
            year = raw.split(".", 1)[1]
            return f"Actual/Approved Funding {self._year_label(year)}"
        labels = {
            "status": "Project Status",
            "location": "Location Coverage",
            "sdgSelections": "SDG Tags",
            "physicalAccomplishment": "Physical Accomplishment",
            "financialAccomplishment": "Financial Accomplishment",
            "description": "Project Description",
            "objective": "Project Objective",
            "program": "Program",
            "projectActivity": "Project/Activity",
            "developmentSector": "Development Sector",
            "rdpMainChapter": "RDP Main Chapter",
            "startYear": "Start Year",
            "endYear": "End Year",
            "fundingSource": "Funding Source",
            "remarks": "Remarks",
        }
        return labels.get(raw, raw.replace("_", " ").replace(".", " ").strip().title() or "Project Information")

    def _year_label(self, value):
        return "2022 & Prior" if str(value) == "2022_prior" else str(value)

    def _field_category(self, field):
        raw = str(field or "")
        if raw.startswith("fundingRequirementByYear.") or raw.startswith("actualFundingByYear."):
            return "funding"
        if raw == "status":
            return "status"
        if raw == "location":
            return "location"
        if raw == "sdgSelections":
            return "sdg"
        if raw in ("physicalAccomplishment", "financialAccomplishment"):
            return "accomplishment"
        return "project_info"

    def _format_public_value(self, value):
        if value is None or value == "":
            return ""
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if str(v).strip())
        if isinstance(value, dict):
            return ", ".join(f"{k}: {v}" for k, v in value.items() if str(v).strip())
        return str(value)

    def _public_changed_fields(self, revision):
        raw_changes = revision.changed_fields if isinstance(revision.changed_fields, list) else []
        public_changes = []
        for change in raw_changes:
            if not isinstance(change, dict):
                continue
            field = str(change.get("field") or "").strip()
            if not field or field in {"public_summary", "public_summary_override", "validator_review", "contributor_snapshot"}:
                continue
            public_changes.append(
                {
                    "label": self._field_label(field),
                    "category": self._field_category(field),
                    "before": self._format_public_value(change.get("before")),
                    "after": self._format_public_value(change.get("after")),
                }
            )
        return public_changes

    def _update_badges(self, revision):
        labels = {
            "funding": "Funding updated",
            "status": "Status updated",
            "location": "Location coverage updated",
            "sdg": "SDGs updated",
            "accomplishment": "Accomplishments updated",
            "project_info": "Project information updated",
        }
        seen = []
        for change in self._public_changed_fields(revision):
            category = change.get("category")
            if category in labels and labels[category] not in seen:
                seen.append(labels[category])
        return seen[:5]

    def _update_headline(self, revision):
        note = str(revision.public_note or "").strip()
        if note:
            return note if len(note) <= 180 else f"{note[:177].rstrip()}..."
        badges = self._update_badges(revision)
        if not badges:
            return "Approved project progress update recorded."
        if len(badges) == 1:
            return f"{badges[0]} for this project."
        if len(badges) == 2:
            return f"{badges[0]} and {badges[1].lower()} for this project."
        return f"{', '.join(badges[:-1])}, and {badges[-1].lower()} for this project."

    def _timeline_entry(self, revision):
        summary = revision.public_summary_snapshot if isinstance(revision.public_summary_snapshot, dict) else {}
        key_facts = summary.get("key_facts") if isinstance(summary.get("key_facts"), dict) else {}
        changed_fields = self._public_changed_fields(revision)
        return {
            "revision_number": revision.revision_number,
            "revision_type": revision.revision_type,
            "endorsed_at": revision.endorsed_at.isoformat() if revision.endorsed_at else None,
            "status": key_facts.get("status", ""),
            "budget": key_facts.get("funding_requirement_total", ""),
            "location": key_facts.get("location", ""),
            "changed_fields": changed_fields,
            "change_badges": self._update_badges(revision),
            "headline": self._update_headline(revision),
            "public_note": revision.public_note,
        }

    def get_last_endorsed_update_at(self, obj):
        revisions = self._endorsed_revisions(obj)
        if revisions:
            value = revisions[0].endorsed_at or revisions[0].updated_at
            return value.isoformat() if value else None
        return obj.updated_at.isoformat() if getattr(obj, "validated", False) and obj.updated_at else None

    def get_endorsed_update_count(self, obj):
        count = getattr(obj, "_public_progress_update_count", None)
        return count if count is not None else len(self._progress_revisions(obj))

    def get_has_public_updates(self, obj):
        return self.get_public_progress_update_count(obj) > 0

    def get_public_progress_update_count(self, obj):
        count = getattr(obj, "_public_progress_update_count", None)
        return count if count is not None else len(self._progress_revisions(obj))

    def get_latest_update_date(self, obj):
        revisions = self._progress_revisions(obj)
        if not revisions:
            return None
        value = revisions[0].endorsed_at or revisions[0].updated_at
        return value.isoformat() if value else None

    def get_latest_update_headline(self, obj):
        revisions = self._progress_revisions(obj)
        return self._update_headline(revisions[0]) if revisions else ""

    def get_latest_update_badges(self, obj):
        revisions = self._progress_revisions(obj)
        return self._update_badges(revisions[0]) if revisions else []

    def get_public_update_timeline(self, obj):
        return [self._timeline_entry(revision) for revision in self._endorsed_revisions(obj)]


class PublicProjectSummarySerializer(PublicProjectSerializer):
    class Meta(PublicProjectSerializer.Meta):
        fields = [
            "id",
            "title",
            "agency",
            "implementation_status",
            "budget",
            "year",
            "lgu",
            "lgus",
            "location_raw",
            "last_endorsed_update_at",
            "has_public_updates",
            "public_progress_update_count",
            "latest_update_date",
            "latest_update_headline",
            "latest_update_badges",
            "updated_at",
        ]
        read_only_fields = fields


class AccessRequestSerializer(serializers.ModelSerializer):
    reviewed_by = UserSerializer(read_only=True)

    class Meta:
        model = AccessRequest
        fields = [
            "id",
            "full_name",
            "email",
            "office_unit",
            "requested_role",
            "justification",
            "status",
            "review_notes",
            "reviewed_by",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = ["status", "review_notes", "reviewed_by", "reviewed_at", "created_at"]


class UserActivitySerializer(serializers.ModelSerializer):
    username = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    project_title = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()

    class Meta:
        model = UserActivity
        fields = [
            "id",
            "username",
            "display_name",
            "role",
            "event",
            "project",
            "project_title",
            "project_id_snapshot",
            "target_label",
            "ip_address",
            "location_hint",
            "details",
            "created_at",
        ]

    def get_project_title(self, obj):
        return obj.project_title_snapshot or (obj.project.title if obj.project else "")

    def get_target_label(self, obj):
        if obj.project_title_snapshot or obj.project:
            return self.get_project_title(obj)
        details = obj.details if isinstance(obj.details, dict) else {}
        for key in ("title", "email", "attempted_email", "name", "slug", "key"):
            value = details.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:160]
        for key, prefix in (("target_user_id", "User"), ("form_id", "Form"), ("event_id", "Event"), ("id", "Content")):
            if details.get(key) is not None:
                return f"{prefix} #{details[key]}"
        return "—"

    def get_username(self, obj):
        return obj.actor_username or (obj.user.username if obj.user else "Deleted user")

    def get_display_name(self, obj):
        user = getattr(obj, "user", None)
        if not user:
            return obj.actor_full_name or obj.actor_username or "Deleted user"
        if obj.actor_full_name:
            return obj.actor_full_name
        return _user_display_name(user) or user.username


class ProjectCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = ProjectComment
        fields = [
            "id",
            "project",
            "user",
            "username",
            "first_name",
            "last_name",
            "role",
            "agency",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "project", "user", "username", "first_name", "last_name", "role", "agency", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    project_title = serializers.SerializerMethodField()
    submission_type = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "actor",
            "actor_name",
            "project",
            "project_title",
            "submission_type",
            "comment",
            "event_type",
            "title",
            "message",
            "link_path",
            "read_at",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if not obj.actor:
            return "System"
        return _user_display_name(obj.actor) or obj.actor.username

    def get_project_title(self, obj):
        if not obj.project:
            return ""
        return obj.project.title

    def get_submission_type(self, obj):
        if not obj.project:
            return ""
        profile = obj.project.profile_data if isinstance(obj.project.profile_data, dict) else {}
        value = str(profile.get("submission_type") or "").strip().lower()
        return "simplified" if value == "simplified" or (value != "detailed" and isinstance(profile.get("simplified_form"), dict)) else "unsupported"

    def get_is_read(self, obj):
        return bool(obj.read_at)


class PasswordResetRequestSerializer(serializers.ModelSerializer):
    reviewed_by = UserSerializer(read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = PasswordResetRequest
        fields = [
            "id",
            "email",
            "user",
            "user_email",
            "user_username",
            "status",
            "requested_ip",
            "requested_user_agent",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "created_at",
        ]
        read_only_fields = [
            "status",
            "requested_ip",
            "requested_user_agent",
            "reviewed_by",
            "reviewed_at",
            "review_notes",
            "created_at",
            "user",
            "user_email",
            "user_username",
        ]
