from rest_framework import serializers
from datetime import datetime
from .models import (
    AccessRequest,
    PasswordResetRequest,
    PriorityRuleSet,
    Project,
    ProjectComment,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    User,
    UserActivity,
)

SYSTEM_MANAGED_DIFF_ROOTS = {
    "public_summary",
    "public_summary_override",
    "simplified_form_meta",
    "validator_review",
    "contributor_snapshot",
}


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
            "full_name",
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
        user = User(**validated_data)
        user.is_staff = user.role == "admin"
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        role = validated_data.get("role")
        if role == "contributor":
            validated_data["role"] = "staff"
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if "role" in validated_data:
            instance.is_staff = instance.role == "admin"
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class ProjectSerializer(serializers.ModelSerializer):
    # Frontend compatibility: accepts and returns title while storing as name.
    title = serializers.CharField(source="name", required=False)
    status = serializers.CharField(required=False)
    submitted_by = UserSerializer(source="created_by", read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    validated_by = serializers.SerializerMethodField()
    priority_analysis = serializers.SerializerMethodField()

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
        ]
        read_only_fields = ["id", "created_at", "updated_at", "submitted_by", "submitted_by_name", "validated_by"]
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

    def get_submitted_by_name(self, obj):
        if not obj.created_by:
            return ""
        if getattr(obj.created_by, "full_name", "").strip():
            return obj.created_by.full_name
        if obj.created_by.get_full_name():
            return obj.created_by.get_full_name()
        return obj.created_by.username

    def get_priority_analysis(self, obj):
        analysis = obj.priority_analyses.prefetch_related("confirmations").order_by("-created_at").first()
        if not analysis:
            return None
        confirmation = analysis.confirmations.first()
        return {
            "analysis_id": analysis.id,
            "score": float(analysis.base_score),
            "suggested_priority": analysis.suggested_priority,
            "final_priority": confirmation.final_priority if confirmation else "",
            "confirmed": bool(confirmation),
            "created_at": analysis.created_at,
        }

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
        if isinstance(simplified, dict):
            self._validate_simplified_funding(simplified)
        return value

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
        start, end = (start, end) if start <= end else (end, start)
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
            "created_at",
        ]
        read_only_fields = fields

    def get_validator_name(self, obj):
        if not obj.validator:
            return ""
        return obj.validator.full_name.strip() or obj.validator.get_full_name() or obj.validator.username


class ProjectPriorityAnalysisSerializer(serializers.ModelSerializer):
    validator_name = serializers.SerializerMethodField()
    rule_version = serializers.CharField(source="rule_set.version", read_only=True)
    algorithm_version = serializers.CharField(source="rule_set.algorithm_version", read_only=True)
    confirmations = ProjectPriorityConfirmationSerializer(many=True, read_only=True)
    latest_confirmation = serializers.SerializerMethodField()

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
            "created_at",
        ]
        read_only_fields = fields

    def get_validator_name(self, obj):
        if not obj.validator:
            return ""
        return obj.validator.full_name.strip() or obj.validator.get_full_name() or obj.validator.username

    def get_latest_confirmation(self, obj):
        confirmation = obj.confirmations.first()
        if not confirmation:
            return None
        return ProjectPriorityConfirmationSerializer(confirmation).data


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
        # Prefer RDIP status from simplified form (Completed/New/Updated/Ongoing/etc.).
        sf = self._simplified(obj)
        value = str(sf.get("status") or "").strip()
        if value:
            return value
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
        sf = self._simplified(obj)
        return str(sf.get("location") or "").strip()

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
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.SerializerMethodField()
    project_title = serializers.SerializerMethodField()

    class Meta:
        model = UserActivity
        fields = [
            "id",
            "username",
            "full_name",
            "role",
            "event",
            "project",
            "project_title",
            "ip_address",
            "location_hint",
            "details",
            "created_at",
        ]

    def get_project_title(self, obj):
        if not obj.project:
            return ""
        return obj.project.title

    def get_full_name(self, obj):
        user = getattr(obj, "user", None)
        if not user:
            return ""
        if getattr(user, "full_name", "").strip():
            return user.full_name
        full = user.get_full_name()
        return full or user.username


class ProjectCommentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = ProjectComment
        fields = [
            "id",
            "project",
            "user",
            "username",
            "full_name",
            "role",
            "agency",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "project", "user", "username", "full_name", "role", "agency", "created_at"]


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
