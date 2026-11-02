"""Stable agency identity, contributor eligibility, and catalog update helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from django.db import transaction

from .models import Agency, Project, User, UserInvitation


PRIMARY_AGENCY_SYSTEM_KEY = "rdc-ncr-primary"

OFFICIAL_AGENCY_CODES = {
    "metropolitan manila development authority": "MMDA",
    "department of public works and highways": "DPWH",
    "department of environment and natural resources": "DENR",
    "regional development council national capital region": "RDC-NCR",
    "department of the interior and local government": "DILG",
    "department of economy, planning, and development": "DEPDev",
    "department of budget and management": "DBM",
    "department of agriculture": "DA",
    "department of agrarian reform": "DAR",
    "department of education": "DepEd",
    "department of health": "DOH",
    "department of human settlements and urban development": "DHSUD",
    "department of information and communications technology": "DICT",
    "department of labor and employment": "DOLE",
    "department of science and technology": "DOST",
    "department of social welfare and development": "DSWD",
    "department of tourism": "DOT",
    "department of trade and industry": "DTI",
    "department of transportation": "DOTr",
    "technical education and skills development authority": "TESDA",
    "commission on higher education": "CHED",
    "philippine statistics authority": "PSA",
}

ACRONYM_STOP_WORDS = {"and", "for", "in", "of", "on", "the", "to"}


@dataclass
class ContributorAgencyError(ValueError):
    detail: str
    code: str = "agency_not_eligible_for_contributor"

    @property
    def payload(self):
        return {"code": self.code, "detail": self.detail}


def normalize_agency_name(value):
    return " ".join(str(value or "").strip().split())


def primary_system_agency(*, active_only=True):
    queryset = Agency.objects.filter(system_key=PRIMARY_AGENCY_SYSTEM_KEY)
    if active_only:
        queryset = queryset.filter(is_active=True)
    return queryset.first()


def is_protected_agency(agency):
    return bool(agency and agency.system_key)


def validate_contributor_agency(agency, *, existing_agency_id=None):
    if agency is None or not agency.is_active:
        raise ContributorAgencyError(
            "Select an active agency that accepts Contributor accounts."
        )
    if is_protected_agency(agency) and agency.pk != existing_agency_id:
        raise ContributorAgencyError(
            "RDC-NCR is reserved for internal portal roles and cannot be selected as a Contributor's primary agency."
        )
    return agency


def suggest_agency_code(name):
    normalized = normalize_agency_name(name)
    if not normalized:
        return "", "generated"
    official = OFFICIAL_AGENCY_CODES.get(normalized.casefold())
    if official:
        return official, "official"
    words = re.findall(r"[A-Za-z0-9]+", normalized)
    meaningful = [word for word in words if word.casefold() not in ACRONYM_STOP_WORDS]
    source_words = meaningful or words
    if len(source_words) > 1:
        code = "".join(word[0] for word in source_words).upper()
    elif source_words:
        code = source_words[0].upper()
    else:
        code = ""
    return code[:50], "generated"


def _matches_old_identity(value, old_code, old_name):
    normalized = normalize_agency_name(value).casefold()
    return normalized in {old_code.casefold(), old_name.casefold()}


@transaction.atomic
def update_agency_metadata(instance, validated_data):
    """Update one agency and its current compatibility mirrors without rewriting history."""
    agency = Agency.objects.select_for_update().get(pk=instance.pk)
    old_code = agency.code
    old_name = agency.name
    new_code = validated_data.get("code", agency.code)
    new_name = validated_data.get("name", agency.name)
    new_head = validated_data.get("head_name", agency.head_name)

    agency.code = new_code
    agency.name = new_name
    agency.head_name = new_head
    for field, value in validated_data.items():
        if field not in {"code", "name", "head_name", "system_key"}:
            setattr(agency, field, value)
    agency.save()

    if new_code != old_code or new_name != old_name:
        User.objects.filter(agency_record=agency).update(agency=new_code)
        User.objects.filter(agency_record=agency, office__iexact=old_code).update(office=new_code)
        User.objects.filter(agency_record=agency, office__iexact=old_name).update(office=new_code)
        UserInvitation.objects.filter(
            agency_record=agency,
            status__in=[UserInvitation.STATUS_PENDING, UserInvitation.STATUS_SENT],
        ).update(agency=new_code)

        for project in Project.objects.select_for_update().filter(primary_agency=agency).iterator():
            update_fields = []
            if project.agency != new_code:
                project.agency = new_code
                update_fields.append("agency")
            if _matches_old_identity(project.implementing_agency, old_code, old_name):
                project.implementing_agency = new_code
                update_fields.append("implementing_agency")
            profile = project.profile_data if isinstance(project.profile_data, dict) else None
            simplified = profile.get("simplified_form") if profile else None
            if isinstance(simplified, dict) and _matches_old_identity(
                simplified.get("agencyName"), old_code, old_name
            ):
                copied_profile = dict(profile)
                copied_simplified = dict(simplified)
                copied_simplified["agencyName"] = new_code
                copied_profile["simplified_form"] = copied_simplified
                project.profile_data = copied_profile
                update_fields.append("profile_data")
            if update_fields:
                project.save(update_fields=list(dict.fromkeys(update_fields)))

    return agency
