"""Stable Contributor form choices and compatibility with historical answers."""

from copy import deepcopy

from django.utils.text import slugify

from .models import Agency, ProjectLocation, SectoralCommittee
from .utils import NCR_LGU_CANONICAL, _normalize_location_text, derive_ncr_lgus


FORM_CATALOGS = {
    "collaboratingAgencies": "agencies",
    "location": "locations",
    "developmentSector": "committees",
}
OUTCOME_GROUPS = {
    "infrastructure": "Infrastructure",
    "social": "Social",
    "economic": "Economic",
    "environment": "Environment",
    "financial_admin": "Financial and Administrative",
}
COMMITTEE_ALIASES = {
    "scid": ("scid", "Sectoral Committee on Infrastructure Development (SCID)"),
    "scsd": ("scsd", "Sectoral Committee on Social Development (SCSD)"),
    "sceed": ("sceed", "sceeed", "Sectoral Committee on Economic and Environment Development (SCEED)"),
    "scfda": ("scfda", "Sectoral Committee on Finance and Development Administration (SCFDA)"),
}


def catalog_rows():
    agencies = Agency.objects.filter(system_key__isnull=True).order_by("name")
    return {
        "collaboratingAgencies": [
            {"value": f"agency:{row.pk}", "label": row.name, "code": row.code, "active": row.is_active}
            for row in agencies
        ],
        "location": [
            {"value": row.code, "label": row.name, "map_key": row.map_key, "active": row.is_active}
            for row in ProjectLocation.objects.all()
        ],
        "developmentSector": [
            {"value": row.code, "label": f"{row.name} ({row.acronym})", "active": row.is_active}
            for row in SectoralCommittee.objects.all()
        ],
    }


def catalog_fields(schema):
    for section in schema.get("sections", []):
        if not isinstance(section, dict) or not isinstance(section.get("fields"), list):
            continue
        for field in section.get("fields", []):
            if isinstance(field, dict) and field.get("key") in FORM_CATALOGS:
                yield field


def with_catalog_options(schema, saved=None, *, for_editor=False):
    """Populate volatile choices on copies. Historical stored schemas stay immutable."""
    result = deepcopy(schema)
    fields = [field for field in catalog_fields(result) if field.get("catalog")]
    if not fields:
        return result
    saved = saved if isinstance(saved, dict) else {}
    choices = catalog_rows()
    snapshots = saved.get("catalog_selections") or {}
    answers = saved.get("simplified_form") or {}
    for field in fields:
        key = field["key"]
        values = answers.get(key)
        retained = set(values if isinstance(values, list) else [str(values or "")])
        historical = {row["value"]: row for row in snapshots.get(key, [])}
        options = []
        for row in choices[key]:
            value = row["value"]
            if row["active"] or for_editor or value in retained:
                option = dict(row)
                if value in historical:
                    option["label"] = historical[value]["label"]
                options.append(option)
        field["options"] = options
    return result


def catalog_value(key, value, choices):
    """Resolve exact legacy aliases only, leaving ambiguous choices for review."""
    token = str(value or "").strip()
    if any(row["value"] == token for row in choices):
        return token
    if key == "location":
        normalized = _normalize_location_text(token)
        matches = [
            row["value"] for row in choices
            if normalized and normalized in {
                _normalize_location_text(alias)
                for alias in (*NCR_LGU_CANONICAL.get(row["map_key"], ()), row["map_key"], row["label"])
            }
        ]
    elif key == "developmentSector":
        matches = [
            row["value"] for row in choices
            if token.casefold() in {alias.casefold() for alias in (*COMMITTEE_ALIASES.get(row["value"], ()), row["label"])}
        ]
    else:
        matches = [row["value"] for row in choices if token.casefold() in {row["code"].casefold(), row["label"].casefold()}]
    return matches[0] if len(matches) == 1 else None


def catalog_selection_snapshot(schema, answers, previous=None):
    """Only the server can supply display snapshots or authorize retained inactive values."""
    fields = [field for field in catalog_fields(schema) if field.get("catalog")]
    if not fields:
        return {}
    previous = previous if isinstance(previous, dict) else {}
    choices = catalog_rows()
    result = {}
    for field in fields:
        key = field["key"]
        raw = answers.get(key)
        if raw not in (None, "") and isinstance(raw, list) != (field["type"] == "multiselect_dropdown"):
            raise ValueError(f"Select a valid value for {field['label']}.")
        selected = raw if isinstance(raw, list) else [raw] if raw else []
        if any(not isinstance(value, str) for value in selected) or len(set(selected)) != len(selected):
            raise ValueError(f"Select distinct valid options for {field['label']}.")
        current = {row["value"]: row for row in choices[key]}
        old_answers = (previous.get("simplified_form") or {}).get(key)
        old_values = old_answers if isinstance(old_answers, list) else [old_answers]
        old_ids = {catalog_value(key, value, choices[key]) for value in old_values}
        historical = {row["value"]: row for row in (previous.get("catalog_selections") or {}).get(key, [])}
        if any(value not in current or (not current[value]["active"] and value not in old_ids) for value in selected):
            raise ValueError(f"Select active catalog options for {field['label']}.")
        if selected:
            result[key] = [
                historical.get(value) or {name: item for name, item in current[value].items() if name != "active"}
                for value in selected
            ]
    return result


def upgrade_catalog_answers(profile, schema):
    fields = [field for field in catalog_fields(schema) if field.get("catalog")]
    if not fields:
        return profile
    upgraded = deepcopy(profile)
    answers = upgraded["simplified_form"]
    choices = catalog_rows()
    for field in fields:
        key = field["key"]
        raw = answers.get(key)
        if not raw:
            continue
        values = raw if isinstance(raw, list) else [raw]
        resolved = [catalog_value(key, value, choices[key]) for value in values]
        if any(value is None for value in resolved):
            raise ValueError(f"{field['label']} contains a legacy value that needs catalog review.")
        answers[key] = list(dict.fromkeys(resolved)) if field["type"] == "multiselect_dropdown" else resolved[0]
    return upgraded


def location_map_keys(values):
    """Use canonical IDs for structured selections and keep legacy text interpretation."""
    if not isinstance(values, list):
        return derive_ncr_lgus(values)
    canonical = {f"lgu-{slugify(key)}": key for key in NCR_LGU_CANONICAL}
    aliases = {
        _normalize_location_text(alias): key
        for key, names in NCR_LGU_CANONICAL.items()
        for alias in (*names, key)
    }
    mapped = []
    for value in values:
        token = str(value)
        known = canonical.get(token) or aliases.get(_normalize_location_text(token))
        if known:
            mapped.append(known)
        elif not token.startswith("lgu-"):
            mapped.extend(derive_ncr_lgus(token))
    return list(dict.fromkeys(mapped))


def project_outcome_context(form):
    token = str(form.get("developmentSector") or "").strip()
    if not token:
        return None
    # Catalog-backed selections are exact codes. Only known legacy names can be aliases.
    legacy_code = next((
        code for code, aliases in COMMITTEE_ALIASES.items()
        if token.casefold() in {value.casefold() for value in aliases}
    ), None)
    committee = SectoralCommittee.objects.prefetch_related("outcome_links").filter(pk=legacy_code or token).first()
    if not committee:
        return None
    return {"committee": committee.code, "groups": sorted(link.group for link in committee.outcome_links.all())}


def validate_committee_links(rubric, *, replacement=None, lock=False):
    available = {key for key, criteria in rubric.items() if criteria}
    committees = SectoralCommittee.objects.order_by("pk").prefetch_related("outcome_links")
    if lock:
        committees = committees.select_for_update()
    active = {
        row.code: {link.group for link in row.outcome_links.all()}
        for row in committees if row.is_active and (replacement is None or row.code != replacement[0])
    }
    if replacement and replacement[1]:
        active[replacement[0]] = replacement[2]
    covered = set()
    for code, groups in active.items():
        if not groups or groups - available:
            raise ValueError(f"Active committee {code.upper()} needs valid links to the active outcome groups.")
        if code == "sceed" and not {"economic", "environment"}.issubset(groups):
            raise ValueError("SCEED needs both the Economic and Environment groups while active.")
        covered.update(groups)
    unlinked = available - covered
    if unlinked:
        raise ValueError("Link each active outcome group to an active committee: " + ", ".join(
            OUTCOME_GROUPS[key] for key in sorted(unlinked)
        ) + ".")
