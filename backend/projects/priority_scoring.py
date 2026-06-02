import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP

from .models import PriorityRuleSet, ProjectPriorityAnalysis, ProjectPriorityConfirmation
from .utils import derive_ncr_lgus


RULE_VERSION = "rdc-priority-v1"
ALGORITHM_VERSION = "expert-v1"
REGIONAL_THRESHOLD = 200_000_000

PRIORITY_LABELS = {
    "high": "High Priority",
    "medium": "Medium Priority",
    "low": "Low Priority",
    "incomplete": "Incomplete",
}

READINESS = {
    "completed_documents": (10, "Completed pre-FS/FS/POW and detailed design, where applicable."),
    "ongoing_documents": (6, "Ongoing pre-FS/FS/POW and detailed design, where applicable."),
    "project_profile": (3, "Comprehensive project profile is available."),
    "concept_only": (0, "Concept paper or no completed preparation document."),
}
GAD = {
    "gender_responsive": (10, "Program/project is gender-responsive."),
    "gender_sensitive": (6, "Program/project is gender-sensitive."),
    "promising_prospects": (3, "Program/project has promising GAD prospects."),
    "invisible": (0, "GAD is invisible in the program/project."),
}

COMMON_OUTCOMES = [
    ("capabilities", "Develop and protect capabilities of individuals and families", 10, ["health", "education", "family", "community", "social", "housing"]),
    ("jobs", "Transform production sector to generate more quality jobs and competitive products", 5, ["employment", "livelihood", "jobs", "industry", "business", "trade"]),
]
SECTOR_OUTCOMES = {
    "infrastructure": [
        ("connectivity", "Achieve seamless and inclusive connectivity", 20, ["road", "bridge", "transport", "connectivity", "traffic", "rail", "port"]),
        ("sustainable_utilities", "Provide sustainable energy and water infrastructure", 10, ["water", "drainage", "flood", "energy", "sewer", "irrigation"]),
        ("social_support", "Support social development through infrastructure", 5, ["school", "hospital", "housing", "community", "facility"]),
    ],
    "social": [
        ("human_social", "Promote human and social development", 20, ["health", "education", "housing", "community", "social", "nutrition"]),
        ("vulnerability", "Reduce vulnerabilities and protect purchasing power", 10, ["vulnerable", "poverty", "protection", "food", "nutrition", "resilience"]),
        ("income", "Increase income-earning ability", 5, ["employment", "livelihood", "skills", "training", "jobs"]),
    ],
    "economic": [
        ("agriculture", "Modernize agriculture and agri-business", 5, ["agriculture", "agri", "farm", "fishery", "food"]),
        ("industry_services", "Revitalize industry and reinvigorate services", 20, ["industry", "services", "tourism", "enterprise", "business"]),
        ("trade_rd", "Promote trade and investments and advance R&D, technology, and innovation", 10, ["trade", "investment", "research", "innovation", "technology", "digital"]),
    ],
    "environment": [
        ("livable", "Establish livable communities", 10, ["livable", "housing", "urban", "community", "green", "waste"]),
        ("climate", "Advance climate change adaptation and mitigation", 15, ["climate", "flood", "resilience", "river", "environment", "green"]),
        ("disaster", "Strengthen disaster preparedness, relief, recovery, and reconstruction", 10, ["disaster", "preparedness", "flood", "risk", "recovery", "drainage"]),
    ],
    "financial_admin": [
        ("finance", "Promote financial inclusion and improve public financial management", 5, ["finance", "financial", "budget", "fiscal"]),
        ("governance", "Promote culture-sensitive governance and development", 10, ["governance", "administration", "institution", "culture", "service"]),
        ("peace_justice", "Ensure peace and security and enhance administration of justice", 20, ["security", "safety", "peace", "justice", "police"]),
    ],
}

NEGATIVE_RULES = [
    ("administrative_support", "General administrative or support expenditure", ["office supplies", "administrative support", "operating expense"]),
    ("standalone_preparation", "Standalone infrastructure preparation activity", ["feasibility study", "pre-feasibility", "detailed engineering design", "right of way", "rowa"]),
    ("single_building", "Single building or unit construction, improvement, rehabilitation, restoration, or maintenance", ["office building", "perimeter fence", "reception area", "single building"]),
    ("landscaping", "Landscaping, site development, or similar non-infrastructure item", ["landscaping", "site development", "perimeter fence"]),
    ("lot_acquisition", "Lot acquisition", ["lot acquisition", "land acquisition"]),
]


def _money_total(value):
    if not isinstance(value, dict):
        return 0
    total = Decimal("0")
    for raw in value.values():
        cleaned = re.sub(r"[^0-9.-]", "", str(raw or ""))
        try:
            total += max(Decimal("0"), Decimal(cleaned or "0"))
        except Exception:
            continue
    return int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _simplified(snapshot):
    if not isinstance(snapshot, dict):
        return {}
    value = snapshot.get("simplified_form")
    return value if isinstance(value, dict) else snapshot


def _normalized_text(form):
    fields = [
        "program",
        "projectActivity",
        "location",
        "description",
        "objective",
        "remarks",
        "rdpMainChapter",
        "status",
    ]
    raw = " ".join(str(form.get(field) or "") for field in fields)
    raw += " " + " ".join(str(item) for item in form.get("sdgSelections") or [])
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _merge_facts(form, supplements):
    contributor = form.get("priorityAnalysisFacts")
    facts = dict(contributor) if isinstance(contributor, dict) else {}
    for key, value in (supplements or {}).items():
        if value not in (None, ""):
            facts[key] = value
    return facts


def _fact_key(value):
    key = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return {
        "completed_supporting_documents": "completed_documents",
        "ongoing_supporting_documents": "ongoing_documents",
        "comprehensive_project_profile": "project_profile",
        "concept_paper_none": "concept_only",
        "gad_invisible": "invisible",
    }.get(key, key)


def _criterion(key, label, raw, weight, remarks, evidence=None):
    points = (Decimal(str(raw)) / Decimal("10") * Decimal(str(weight))).quantize(Decimal("0.01"))
    return {
        "key": key,
        "criterion": label,
        "raw": raw,
        "weight": weight,
        "score": float(points),
        "remarks": remarks,
        "evidence": evidence or [],
    }


def _spatial_rating(scope, lgu_count):
    if scope == "interregional":
        return 10, "Interregional coverage."
    if scope == "region_wide":
        return 10, "Region-wide coverage."
    if scope == "none":
        return 0, "No location coverage is declared."
    if scope == "specific_lgus":
        if 6 <= lgu_count <= 12:
            return 6, f"{lgu_count} cities/municipalities are covered."
        if 1 <= lgu_count <= 5:
            return 3, f"{lgu_count} cities/municipalities are covered."
        return None, "Coverage count does not map to an official PAP category. Validator selection is required."
    return None, "Spatial coverage scope is required."


def _sector_track(form, facts, text):
    sector = str(form.get("developmentSector") or "")
    if "Infrastructure" in sector:
        return "infrastructure"
    if "Social" in sector:
        return "social"
    if "Finance" in sector:
        return "financial_admin"
    if "Economic and Environment" in sector:
        selected = str(facts.get("sceeedTrack") or "").strip().lower()
        if selected in ("economic", "environment"):
            return selected
        environment_hits = sum(text.count(token) for token in ["climate", "environment", "flood", "river", "waste", "green"])
        economic_hits = sum(text.count(token) for token in ["trade", "industry", "business", "tourism", "agriculture", "investment"])
        return "environment" if environment_hits > economic_hits else "economic"
    return "social"


def _outcome_rating(text, chapter, keywords):
    hits = sorted({keyword for keyword in keywords if keyword in text})
    chapter_hit = any(keyword in chapter for keyword in keywords)
    if chapter_hit and len(hits) >= 2:
        return 10, hits
    if chapter_hit or len(hits) >= 3:
        return 8, hits
    if len(hits) >= 1:
        return 5, hits
    return 0, []


def _priority_for(score):
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def _active_ruleset():
    rule_set = PriorityRuleSet.objects.filter(is_active=True).order_by("-created_at").first()
    if rule_set:
        return rule_set
    return PriorityRuleSet.objects.create(
        version=RULE_VERSION,
        algorithm_version=ALGORITHM_VERSION,
        is_active=True,
        thresholds={"high": 80, "medium": 50},
        sector_criteria=SECTOR_OUTCOMES,
        keyword_dictionaries={"negative_rules": NEGATIVE_RULES},
    )


def source_hash(snapshot, supplements, rule_set=None):
    rules = rule_set or _active_ruleset()
    payload = {
        "snapshot": snapshot if isinstance(snapshot, dict) else {},
        "supplements": supplements if isinstance(supplements, dict) else {},
        "rules": rules.version,
        "algorithm": rules.algorithm_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def analyze_project(project, validator, snapshot, supplements=None):
    supplements = supplements if isinstance(supplements, dict) else {}
    rules = _active_ruleset()
    digest = source_hash(snapshot, supplements, rules)
    existing = ProjectPriorityAnalysis.objects.filter(project=project, rule_set=rules, source_hash=digest).first()
    if existing:
        return existing, True

    form = _simplified(snapshot)
    facts = _merge_facts(form, supplements)
    text = _normalized_text(form)
    lgu_count = len(derive_ncr_lgus(str(form.get("location") or "")))
    missing = []

    readiness = READINESS.get(_fact_key(facts.get("readinessLevel")))
    if readiness is None:
        missing.append("Readiness level")
        readiness = (0, "Readiness level must be supplied by the validator.")
    gad = GAD.get(_fact_key(facts.get("gadResponsiveness")))
    if gad is None:
        missing.append("GAD responsiveness")
        gad = (0, "GAD responsiveness must be supplied by the validator.")
    spatial = _spatial_rating(_fact_key(facts.get("spatialCoverageScope")), lgu_count)
    if spatial[0] is None:
        missing.append("Official spatial coverage category")
        spatial = (0, spatial[1])

    pap = [
        _criterion("readiness", "Readiness", readiness[0], 20, readiness[1]),
        _criterion("gad_responsiveness", "Level of GAD Responsiveness", gad[0], 15, gad[1]),
        _criterion("spatial_coverage", "Spatial Coverage", spatial[0], 15, spatial[1]),
    ]
    pap_total = sum(item["score"] for item in pap)

    track = _sector_track(form, facts, text)
    if "Economic and Environment" in str(form.get("developmentSector") or "") and not facts.get("sceeedTrack"):
        missing.append("SCEED Economic or Environment track confirmation")
    chapter = str(form.get("rdpMainChapter") or "").lower()
    outcomes = []
    for key, label, weight, keywords in COMMON_OUTCOMES + SECTOR_OUTCOMES[track]:
        raw, evidence = _outcome_rating(text, chapter, keywords)
        outcomes.append(_criterion(key, label, raw, weight, "Deterministic text alignment suggestion.", evidence))
    outcome_total = sum(item["score"] for item in outcomes)
    base_score = round(pap_total + outcome_total, 2)

    funding_total = _money_total(form.get("fundingRequirementByYear"))
    regional = {"applicable": funding_total >= REGIONAL_THRESHOLD, "total": 0, "criteria": []}
    if regional["applicable"]:
        beneficiary_raw = facts.get("beneficiaryCount")
        try:
            beneficiary_count = int(str(beneficiary_raw or "").replace(",", ""))
        except Exception:
            beneficiary_count = None
        regional_scope = str(facts.get("regionalSpatialCategory") or "")
        try:
            contributed_outcomes = int(facts.get("contributedOutcomeCount"))
        except Exception:
            contributed_outcomes = None
        if beneficiary_count is None:
            missing.append("Regional beneficiary count")
        if not regional_scope:
            missing.append("Regional spatial coverage category")
        if contributed_outcomes is None:
            missing.append("Number of contributed RDP outcomes")
        cost_raw = 10 if funding_total >= 5_000_000_000 else 8 if funding_total > 3_000_000_000 else 6 if funding_total > 1_000_000_000 else 4 if funding_total > 500_000_000 else 2
        spatial_raw = {"interregional": 10, "region_wide": 8, "eight_to_twelve_lgus": 6, "single_city": 4}.get(regional_scope, 0)
        outcome_raw = 10 if (contributed_outcomes or 0) >= 7 else 8 if (contributed_outcomes or 0) >= 5 else 6 if (contributed_outcomes or 0) >= 3 else 4 if contributed_outcomes == 2 else 2 if contributed_outcomes == 1 else 0
        beneficiary_score = 10 if (beneficiary_count or 0) > 3_000_000 else 6 if (beneficiary_count or 0) > 1_000_000 else 3 if (beneficiary_count or 0) >= 1 else 0
        regional["criteria"] = [
            _criterion("regional_cost", "Total Regional Project Cost", cost_raw, 25, f"Funding requirement: PHP {funding_total:,}."),
            _criterion("regional_spatial", "Spatial Coverage", spatial_raw, 25, "Validator-confirmed regional spatial category."),
            _criterion("regional_outcomes", "RDP Sectoral Outcome Contribution", outcome_raw, 25, f"{contributed_outcomes or 0} contributed outcomes."),
            _criterion("regional_beneficiaries", "Magnitude of Beneficiaries", beneficiary_score, 25, f"{beneficiary_count or 0:,} estimated beneficiaries."),
        ]
        regional["total"] = sum(item["score"] for item in regional["criteria"])
    else:
        regional["message"] = "Not applicable: classified as a Sectoral Project."

    negative = []
    for key, label, keywords in NEGATIVE_RULES:
        matches = [word for word in keywords if word in text]
        if matches:
            negative.append({"key": key, "label": label, "evidence": matches})
    risks = []
    if str(form.get("status") or "").lower() != "new" and not str(form.get("physicalAccomplishment") or "").strip():
        risks.append("No physical accomplishment is reported.")
    if _money_total(form.get("actualFundingByYear")) > 0 and not str(form.get("financialAccomplishment") or "").strip():
        risks.append("Actual funding is reported without a financial accomplishment narrative.")
    if missing:
        risks.append("Official score confirmation requires missing factual inputs.")

    suggested_priority = "incomplete" if missing else _priority_for(base_score)
    strongest = sorted(pap + outcomes, key=lambda item: item["score"], reverse=True)[:2]
    if missing:
        summary = "Priority analysis is incomplete. Supply the missing factual inputs before confirming an official recommendation."
    else:
        strengths = " and ".join(item["criterion"].lower() for item in strongest if item["score"] > 0)
        summary = f"The project is classified as {PRIORITY_LABELS[suggested_priority].lower()} with a base score of {base_score:.2f}/100."
        if strengths:
            summary += f" Its strongest scoring contributions are {strengths}."
        if risks:
            summary += f" Review {len(risks)} identified risk flag(s) before endorsement."

    analysis = ProjectPriorityAnalysis.objects.create(
        project=project,
        validator=validator,
        rule_set=rules,
        source_hash=digest,
        input_snapshot=snapshot if isinstance(snapshot, dict) else {},
        supplements=supplements,
        suggested_scores={
            "pap": pap,
            "pap_total": round(pap_total, 2),
            "rdp_track": track,
            "rdp_outcomes": outcomes,
            "rdp_total": round(outcome_total, 2),
            "base_total": base_score,
            "missing_facts": missing,
        },
        regional_scorecard=regional,
        flags={"negative_matches": negative, "risks": risks},
        summary=summary,
        suggested_priority=suggested_priority,
        base_score=base_score,
    )
    return analysis, False


def has_matching_confirmation(project, snapshot):
    analysis = project.priority_analyses.filter(confirmations__isnull=False).order_by("-created_at").first()
    if not analysis:
        return False
    return analysis.source_hash == source_hash(snapshot, analysis.supplements, analysis.rule_set)


def confirm_analysis(analysis, validator, adjusted_scores, final_priority, override_rationale, confirmed_flags):
    missing = analysis.suggested_scores.get("missing_facts") or []
    if missing:
        raise ValueError("Supply all missing factual inputs and run the scorer again before confirmation.")
    if final_priority not in ("high", "medium", "low"):
        raise ValueError("Final priority must be high, medium, or low.")
    if final_priority != analysis.suggested_priority and not str(override_rationale or "").strip():
        raise ValueError("An override rationale is required when changing the suggested priority.")
    return ProjectPriorityConfirmation.objects.create(
        analysis=analysis,
        validator=validator,
        adjusted_scores=adjusted_scores if isinstance(adjusted_scores, dict) else {},
        final_priority=final_priority,
        override_rationale=str(override_rationale or "").strip(),
        confirmed_flags=confirmed_flags if isinstance(confirmed_flags, list) else [],
    )
