import math
import re


FEATURE_SCHEMA_VERSION = "rdc-priority-features-v2"
SECTOR_TRACKS = ("infrastructure", "social", "economic", "environment", "financial_admin")
PRIORITY_LABELS = ("low", "high")

FEATURE_NAMES = [
    "base_score",
    "pap_total",
    "rdp_total",
    "regional_applicable",
    "regional_total",
    "readiness_raw",
    "gad_raw",
    "spatial_raw",
    "outcome_raw_average",
    "missing_fact_count",
    "negative_match_count",
    "risk_count",
    "budget_log",
    "simplified_submission",
    *[f"sector_{track}" for track in SECTOR_TRACKS],
    *[f"rule_suggested_{priority}" for priority in PRIORITY_LABELS],
]


TEXT_FIELDS = (
    "program",
    "programOrProject",
    "projectActivity",
    "projectTitle",
    "location",
    "description",
    "objective",
    "remarks",
    "rdpMainChapter",
    "mainPdpChapter",
    "mainPdpOutcome",
    "mainPdpSubOutcome",
    "mainPdpIndicator",
    "developmentSector",
    "mainInfrastructureSector",
    "mainInfrastructureSubsector",
    "expectedOutputIndicator",
    "expectedOutputValue",
)


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _form(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    simplified = snapshot.get("simplified_form")
    return simplified if isinstance(simplified, dict) else snapshot


def normalized_project_text(snapshot):
    form = _form(snapshot)
    values = [str(form.get(field) or "") for field in TEXT_FIELDS]
    for key in ("sdgSelections", "basisSelections", "projectReadinessItems"):
        selected = form.get(key)
        if isinstance(selected, list):
            values.extend(str(item) for item in selected)
    text = re.sub(r"\s+", " ", " ".join(values).lower()).strip()
    return text[:20000]


def _criterion_raw(criteria, key):
    for item in criteria or []:
        if isinstance(item, dict) and item.get("key") == key:
            return _number(item.get("raw")) / 10.0
    return 0.0


def _budget_total(form):
    values = form.get("fundingRequirementByYear")
    if isinstance(values, dict):
        candidates = values.values()
    else:
        candidates = (form.get("totalProjectCost"), form.get("budget"))
    total = 0.0
    for value in candidates:
        cleaned = re.sub(r"[^0-9.-]", "", str(value or ""))
        try:
            total += max(0.0, float(cleaned or 0))
        except ValueError:
            continue
    return total


def extract_feature_snapshot(priority_analysis):
    scores = priority_analysis.suggested_scores if isinstance(priority_analysis.suggested_scores, dict) else {}
    regional = priority_analysis.regional_scorecard if isinstance(priority_analysis.regional_scorecard, dict) else {}
    flags = priority_analysis.flags if isinstance(priority_analysis.flags, dict) else {}
    snapshot = priority_analysis.input_snapshot if isinstance(priority_analysis.input_snapshot, dict) else {}
    form = _form(snapshot)
    pap = scores.get("pap") if isinstance(scores.get("pap"), list) else []
    outcomes = scores.get("rdp_outcomes") if isinstance(scores.get("rdp_outcomes"), list) else []
    outcome_raw = [_number(item.get("raw")) for item in outcomes if isinstance(item, dict)]
    track = str(scores.get("rdp_track") or "").strip().lower()
    suggested = str(priority_analysis.suggested_priority or "").strip().lower()
    is_simplified = isinstance(snapshot.get("simplified_form"), dict) or str(
        snapshot.get("submission_type") or ""
    ).lower() == "simplified"
    values = {
        "base_score": _number(priority_analysis.base_score) / 100.0,
        "pap_total": _number(scores.get("pap_total")) / 100.0,
        "rdp_total": _number(scores.get("rdp_total")) / 100.0,
        "regional_applicable": 1.0 if regional.get("applicable") else 0.0,
        "regional_total": _number(regional.get("total")) / 100.0,
        "readiness_raw": _criterion_raw(pap, "readiness"),
        "gad_raw": _criterion_raw(pap, "gad_responsiveness"),
        "spatial_raw": _criterion_raw(pap, "spatial_coverage"),
        "outcome_raw_average": (sum(outcome_raw) / len(outcome_raw) / 10.0) if outcome_raw else 0.0,
        "missing_fact_count": min(len(scores.get("missing_facts") or []), 10) / 10.0,
        "negative_match_count": min(len(flags.get("negative_matches") or []), 10) / 10.0,
        "risk_count": min(len(flags.get("risks") or []), 10) / 10.0,
        "budget_log": min(math.log10(_budget_total(form) + 1.0), 12.0) / 12.0,
        "simplified_submission": 1.0 if is_simplified else 0.0,
    }
    values.update({f"sector_{name}": 1.0 if track == name else 0.0 for name in SECTOR_TRACKS})
    values.update({f"rule_suggested_{name}": 1.0 if suggested == name else 0.0 for name in PRIORITY_LABELS})
    return {
        "schema_version": FEATURE_SCHEMA_VERSION,
        "values": values,
        "text": normalized_project_text(snapshot),
        "context": {
            "sector": track,
            "agency": priority_analysis.project.agency or priority_analysis.project.implementing_agency,
            "submission_type": "simplified" if is_simplified else "detailed",
            "rule_suggested_priority": suggested,
            "rule_version": priority_analysis.rule_set.version,
        },
    }


def feature_vector(feature_snapshot, names=None):
    values = feature_snapshot.get("values") if isinstance(feature_snapshot, dict) else {}
    values = values if isinstance(values, dict) else {}
    return [_number(values.get(name)) for name in (names or FEATURE_NAMES)]
