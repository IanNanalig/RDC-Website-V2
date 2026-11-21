from django.db import transaction
from rest_framework import permissions, serializers
from rest_framework.exceptions import MethodNotAllowed, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.form_catalogs import OUTCOME_GROUPS
from projects.models import CommitteeOutcomeGroup, ProjectLocation, SectoralCommittee


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectLocation
        fields = ("code", "name", "map_key", "kind", "region", "is_active")
        read_only_fields = ("code", "map_key", "kind", "region")

    def validate_name(self, value):
        if ProjectLocation.objects.exclude(pk=self.instance.pk).filter(name__iexact=value).exists():
            raise serializers.ValidationError("A location already has this name.")
        return value


class CommitteeSerializer(serializers.ModelSerializer):
    groups = serializers.ListField(child=serializers.ChoiceField(choices=OUTCOME_GROUPS), required=False)

    class Meta:
        model = SectoralCommittee
        fields = ("code", "acronym", "name", "description", "is_active", "groups")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["groups"] = sorted(link.group for link in instance.outcome_links.all())
        return data

    def validate(self, attrs):
        instance = self.instance
        code = instance.code if instance else attrs["code"]
        if instance and attrs.get("code", code) != code:
            raise serializers.ValidationError({"code": "The committee code is system-managed."})
        acronym = attrs.get("acronym", instance.acronym if instance else "")
        if SectoralCommittee.objects.exclude(pk=code).filter(acronym__iexact=acronym).exists():
            raise serializers.ValidationError({"acronym": "A committee already uses this acronym."})
        if not instance and SectoralCommittee.objects.filter(pk=code).exists():
            raise serializers.ValidationError({"code": "A committee already uses this code."})
        groups = attrs.get("groups", [link.group for link in instance.outcome_links.all()] if instance else [])
        if len(set(groups)) != len(groups):
            raise serializers.ValidationError({"groups": "Select each outcome group once."})
        active = attrs.get("is_active", instance.is_active if instance else False)
        from projects.priority_scoring import get_active_priority_rule_set, priority_rule_config
        from projects.form_catalogs import validate_committee_links

        rubric = priority_rule_config(get_active_priority_rule_set())["sector_criteria"]
        try:
            validate_committee_links(rubric, replacement=(code, active, set(groups)))
        except ValueError as exc:
            raise serializers.ValidationError({"groups": str(exc)}) from exc
        return attrs

    def _save_groups(self, committee, groups):
        if groups is not None:
            existing = set(committee.outcome_links.values_list("group", flat=True))
            committee.outcome_links.exclude(group__in=groups).delete()
            CommitteeOutcomeGroup.objects.bulk_create([
                CommitteeOutcomeGroup(committee=committee, group=group) for group in groups if group not in existing
            ])
        return committee

    def create(self, validated_data):
        groups = validated_data.pop("groups", [])
        return self._save_groups(super().create(validated_data), groups)

    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)
        return self._save_groups(super().update(instance, validated_data), groups)


class ContributorFormCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request.user, "role", "") != "admin":
            raise PermissionDenied("Only administrators can manage Contributor form catalogs.")

    def get(self, request):
        return Response({
            "locations": LocationSerializer(ProjectLocation.objects.all(), many=True).data,
            "committees": CommitteeSerializer(SectoralCommittee.objects.prefetch_related("outcome_links"), many=True).data,
            "groups": [{"value": key, "label": label} for key, label in OUTCOME_GROUPS.items()],
        })


class CommitteeCatalogView(ContributorFormCatalogView):
    http_method_names = ["post", "patch", "options"]

    @transaction.atomic
    def post(self, request, code=None):
        if code is not None:
            raise MethodNotAllowed(request.method)
        list(SectoralCommittee.objects.order_by("pk").select_for_update())
        serializer = CommitteeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)

    @transaction.atomic
    def patch(self, request, code=None):
        from django.shortcuts import get_object_or_404

        if code is None:
            raise MethodNotAllowed(request.method)
        list(SectoralCommittee.objects.order_by("pk").select_for_update())
        serializer = CommitteeSerializer(get_object_or_404(SectoralCommittee, pk=code), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class LocationCatalogView(ContributorFormCatalogView):
    http_method_names = ["patch", "options"]

    @transaction.atomic
    def patch(self, request, code):
        from django.shortcuts import get_object_or_404

        list(ProjectLocation.objects.order_by("pk").select_for_update())
        location = get_object_or_404(ProjectLocation, pk=code)
        serializer = LocationSerializer(location, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_active") is False and not ProjectLocation.objects.exclude(pk=code).filter(is_active=True).exists():
            raise serializers.ValidationError({"is_active": "Keep at least one location available for Contributor forms."})
        serializer.save()
        return Response(serializer.data)
