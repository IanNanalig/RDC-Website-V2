"""Resolve public project agency labels without rewriting historical answers."""

from .models import Agency


def agency_lookup():
    lookup = {}
    for agency in Agency.objects.all():
        for raw in (agency.code, agency.name):
            key = " ".join(str(raw or "").split()).casefold()
            if not key:
                continue
            if key not in lookup:
                lookup[key] = agency
            elif lookup[key] is not None and lookup[key].pk != agency.pk:
                lookup[key] = None
    return lookup


def resolve_project_agency(project, lookup):
    linked = getattr(project, "primary_agency", None)
    if linked:
        return linked
    profile = project.profile_data if isinstance(project.profile_data, dict) else {}
    simplified = profile.get("simplified_form") if isinstance(profile.get("simplified_form"), dict) else {}
    raw = simplified.get("agencyName") or project.agency
    return lookup.get(" ".join(str(raw or "").split()).casefold())


def public_agency(agency):
    return {"id": agency.pk, "code": agency.code, "name": agency.name} if agency else None
