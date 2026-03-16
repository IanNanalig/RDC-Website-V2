from rest_framework import serializers
from .models import AccessRequest, PasswordResetRequest, Project, User, UserActivity


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "is_active", "password"]

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
        if obj.created_by.get_full_name():
            return obj.created_by.get_full_name()
        return obj.created_by.username

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
        return value

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
    project_title = serializers.SerializerMethodField()

    class Meta:
        model = UserActivity
        fields = [
            "id",
            "username",
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
