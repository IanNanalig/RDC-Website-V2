import hashlib
import json
import re
from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from .models import PriorityRuleSet, ProjectPriorityAnalysis, ProjectPriorityConfirmation
from .utils import derive_ncr_lgus


RULE_VERSION = "rdc-priority-v1"
ALGORITHM_VERSION = "expert-v1"
REGIONAL_THRESHOLD = 200_000_000
ANALYSIS_GUIDANCE_VERSION = "contextual-explanations-v3"

DEFAULT_OUTCOME_CONTEXT_PHRASES = [
    "improve", "increase", "expand", "provide", "strengthen", "reduce", "protect",
    "develop", "upgrade", "enhance", "support", "deliver", "implement", "restore",
    "modernize", "promote", "ensure", "construct", "build", "rehabilitate", "establish",
]

OUTCOME_CONTEXT_RULES = {
    "capabilities": {
        "guidance": "Valid evidence must describe how a project intervention will improve access, quality, protection, or measurable outcomes for individuals, families, or communities in areas such as health, education, housing, or social protection.",
        "phrases": ["improve health", "improve learning", "expand access", "increase coverage", "deliver services", "protect families", "support families", "provide housing", "strengthen social protection", "benefit households", "reduce mortality"],
    },
    "jobs": {
        "guidance": "Valid evidence must connect employment, livelihood, industry, business, or trade terms to job creation, higher incomes, improved productivity, enterprise growth, skills development, or product competitiveness.",
        "phrases": ["create jobs", "generate employment", "increase income", "support livelihoods", "develop skills", "expand enterprises", "improve productivity", "strengthen industry", "increase competitiveness", "grow businesses", "promote trade"],
    },
    "connectivity": {
        "guidance": "Valid evidence must explain how transport or digital infrastructure will connect locations or users, reduce travel time or congestion, increase capacity, or improve safe and inclusive mobility.",
        "phrases": ["improve connectivity", "connect communities", "reduce travel time", "decongest traffic", "increase transport capacity", "improve mobility", "expand access", "upgrade roads", "construct roads", "rehabilitate bridges", "link growth centers"],
    },
    "sustainable_utilities": {
        "guidance": "Valid evidence must connect water, drainage, flood, energy, sewerage, or irrigation infrastructure to expanded coverage, reliability, resilience, treatment capacity, or reduced service disruption and flooding.",
        "phrases": ["expand water supply", "improve water access", "provide potable water", "reduce flooding", "improve drainage", "increase energy capacity", "provide reliable energy", "construct sewerage", "treat wastewater", "rehabilitate irrigation", "improve service reliability"],
    },
    "social_support": {
        "guidance": "Valid evidence must show how infrastructure will expand or improve delivery of education, health, housing, or community services, especially capacity and access for intended beneficiaries.",
        "phrases": ["expand service access", "increase facility capacity", "construct schools", "rehabilitate hospitals", "provide housing", "improve community services", "support education delivery", "support health services", "benefit underserved communities"],
    },
    "human_social": {
        "guidance": "Valid evidence must describe a concrete improvement in health, education, nutrition, housing, community welfare, or access to social services and identify the people or communities expected to benefit.",
        "phrases": ["improve health outcomes", "expand education access", "improve nutrition", "provide housing", "strengthen community services", "increase social service coverage", "support vulnerable families", "improve quality of life"],
    },
    "vulnerability": {
        "guidance": "Valid evidence must explain how the project reduces exposure to poverty, food insecurity, price shocks, disasters, or other risks, or strengthens protection and resilience for vulnerable groups.",
        "phrases": ["reduce vulnerability", "reduce poverty", "protect purchasing power", "improve food security", "strengthen resilience", "provide social protection", "reduce disaster risk", "support vulnerable groups", "stabilize household income"],
    },
    "income": {
        "guidance": "Valid evidence must connect skills, training, employment, livelihood, or enterprise support to increased employability, sustainable income, job placement, or livelihood opportunities.",
        "phrases": ["increase income", "improve employability", "create employment", "support livelihoods", "develop skills", "provide training", "expand job opportunities", "support enterprises", "place workers"],
    },
    "agriculture": {
        "guidance": "Valid evidence must connect agriculture, fisheries, farming, or food systems to modernization, productivity, value-chain development, market access, food security, or farmer and fisher income.",
        "phrases": ["modernize agriculture", "increase farm productivity", "improve food security", "support farmers", "support fishers", "expand market access", "develop value chains", "reduce post-harvest losses", "increase agricultural income"],
    },
    "industry_services": {
        "guidance": "Valid evidence must explain how the project strengthens industry, services, tourism, enterprises, or business activity through productivity, market growth, investment, capacity, or service innovation.",
        "phrases": ["revitalize industry", "improve services", "grow tourism", "support enterprises", "increase productivity", "attract investment", "expand markets", "strengthen businesses", "create economic activity"],
    },
    "trade_rd": {
        "guidance": "Valid evidence must connect trade, investment, research, technology, digitalization, or innovation to commercialization, adoption, productivity, market access, investment generation, or measurable research outputs.",
        "phrases": ["promote trade", "attract investment", "advance research", "develop technology", "adopt technology", "support innovation", "commercialize research", "expand market access", "increase digital adoption", "improve productivity"],
    },
    "livable": {
        "guidance": "Valid evidence must show how housing, urban development, green space, waste management, or community facilities improve safety, environmental quality, accessibility, or living conditions.",
        "phrases": ["establish livable communities", "improve living conditions", "provide affordable housing", "improve urban services", "expand green spaces", "improve waste management", "reduce landfill waste", "recover solid waste", "recycle waste", "create safe communities", "improve accessibility", "revitalize neighborhoods"],
    },
    "climate": {
        "guidance": "Valid evidence must identify a climate hazard or emissions source and explain how project activities reduce exposure, increase adaptive capacity, strengthen resilience, or mitigate greenhouse-gas emissions.",
        "phrases": ["adapt to climate change", "climate mitigation", "reduce climate risk", "strengthen climate resilience", "improve environmental resilience", "mitigate emissions", "reduce greenhouse gas emissions", "protect against flooding", "restore ecosystems", "increase adaptive capacity", "reduce heat exposure"],
    },
    "disaster": {
        "guidance": "Valid evidence must connect disaster or risk terms to preparedness, prevention, early warning, emergency response, relief, recovery, reconstruction, or reduced loss of life and assets.",
        "phrases": ["strengthen disaster preparedness", "reduce disaster risk", "improve early warning", "support emergency response", "provide disaster relief", "accelerate recovery", "support reconstruction", "protect lives and assets", "reduce flood risk"],
    },
    "finance": {
        "guidance": "Valid evidence must show how the project expands access to financial services or improves budgeting, revenue, expenditure, fiscal controls, transparency, or public financial management outcomes.",
        "phrases": ["expand financial access", "improve financial inclusion", "improve budgeting", "strengthen fiscal management", "increase revenue efficiency", "improve expenditure management", "strengthen financial controls", "improve fiscal transparency"],
    },
    "governance": {
        "guidance": "Valid evidence must connect governance, administration, institutions, culture, or public service terms to accountability, participation, institutional capacity, service quality, efficiency, or culture-sensitive delivery.",
        "phrases": ["improve governance", "strengthen institutions", "increase accountability", "improve public services", "increase participation", "build institutional capacity", "improve administrative efficiency", "promote culture-sensitive development", "strengthen transparency"],
    },
    "peace_justice": {
        "guidance": "Valid evidence must explain how security, safety, peace, justice, or policing interventions prevent harm, improve emergency or law-enforcement capacity, expand access to justice, or strengthen public safety.",
        "phrases": ["improve public safety", "strengthen peace and order", "prevent crime", "expand access to justice", "improve law enforcement", "protect communities", "strengthen emergency response", "reduce violence", "improve justice services"],
    },
}


def _outcome_context_defaults(key, label):
    configured = OUTCOME_CONTEXT_RULES.get(str(key), {})
    return {
        "guidance": configured.get("guidance") or (
            f"Valid evidence must connect this criterion's matching terms to a concrete project action, output, "
            f"beneficiary effect, or measurable result that supports {str(label).strip().lower()}."
        ),
        "phrases": list(configured.get("phrases") or DEFAULT_OUTCOME_CONTEXT_PHRASES),
    }

PRIORITY_LABELS = {
    "high": "High Priority",
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

DEFAULT_GUIDELINES = [
    "The score is a rule-based recommendation and must be reviewed by a validator.",
    "Only use project information that is accurate and supported by evidence.",
    "Only validator-confirmed historical outcomes may enter a controlled administrator-started model training run.",
    "A validator must explain any final-priority override.",
]

SCORING_TEXT_FIELDS = [
    "program",
    "projectActivity",
    "location",
    "description",
    "objective",
    "remarks",
    "rdpMainChapter",
    "mainInfrastructureSector",
    "mainInfrastructureSubsector",
    "spatialCoverageByCost",
    "spatialCoverageByImpact",
    "status",
]

SCORING_FIELD_LABELS = {
    "program": "Program",
    "projectActivity": "Project/Activity",
    "location": "Location",
    "description": "Description",
    "objective": "Objective",
    "remarks": "Remarks",
    "rdpMainChapter": "RDP Main Chapter",
    "mainInfrastructureSector": "Main Infrastructure Sector",
    "mainInfrastructureSubsector": "Main Infrastructure Subsector",
    "spatialCoverageByCost": "Spatial Coverage by Cost",
    "spatialCoverageByImpact": "Spatial Coverage by Impact",
    "status": "Status",
    "sdgSelections": "SDG Selections",
}

FACT_VALUE_LABELS = {
    "completed_documents": "Completed supporting documents",
    "ongoing_documents": "Ongoing supporting documents",
    "project_profile": "Comprehensive project profile",
    "concept_only": "Concept paper or no completed preparation document",
    "gender_responsive": "Gender-responsive",
    "gender_sensitive": "Gender-sensitive",
    "promising_prospects": "Promising GAD prospects",
    "invisible": "GAD invisible",
    "specific_lgus": "Specific LGUs",
    "region_wide": "Region-wide",
    "interregional": "Interregional",
    "none": "No declared coverage",
}


def _criterion_rule(key, label, weight, keywords):
    context_defaults = _outcome_context_defaults(key, label)
    return {
        "key": str(key),
        "label": str(label),
        "weight": float(weight),
        "keywords": [str(keyword) for keyword in keywords],
        "description": (
            f"Measures whether the documented project activities and intended results contribute to "
            f"{str(label).strip().lower()}."
        ),
        "matching_guidance": context_defaults["guidance"],
        "match_mode": "contextual",
        "context_phrases": context_defaults["phrases"],
    }


def _scale_rules(values):
    return [
        {"key": str(key), "raw": float(details[0]), "guideline": str(details[1])}
        for key, details in values.items()
    ]


def default_priority_rule_config():
    return {
        "thresholds": {
            "high": 81,
            "regional_project_cost": REGIONAL_THRESHOLD,
            "pap_weights": {"readiness": 20, "gad_responsiveness": 15, "spatial_coverage": 15},
        },
        "sector_criteria": {
            sector: [_criterion_rule(*criterion) for criterion in criteria]
            for sector, criteria in SECTOR_OUTCOMES.items()
        },
        "keyword_dictionaries": {
            "common_outcomes": [_criterion_rule(*criterion) for criterion in COMMON_OUTCOMES],
            "negative_rules": [
                {"key": str(key), "label": str(label), "keywords": [str(keyword) for keyword in keywords]}
                for key, label, keywords in NEGATIVE_RULES
            ],
            "readiness": _scale_rules(READINESS),
            "gad": _scale_rules(GAD),
            "outcome_rating": {
                "chapter_and_two_keywords": 10,
                "chapter_or_three_keywords": 8,
                "one_keyword": 5,
                "no_keywords": 0,
            },
            "guidelines": list(DEFAULT_GUIDELINES),
        },
    }


def _number(value, label, minimum=0, maximum=None):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a number.")
    if parsed < minimum or (maximum is not None and parsed > maximum):
        limit = f" between {minimum:g} and {maximum:g}" if maximum is not None else f" at least {minimum:g}"
        raise ValueError(f"{label} must be{limit}.")
    return int(parsed) if parsed.is_integer() else parsed


def _rule_key(value, label):
    key = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_]+", key):
        raise ValueError(f"{label} must use only lowercase letters, numbers, and underscores.")
    return key


def _keywords(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of words or phrases.")
    cleaned = []
    for keyword in value:
        word = re.sub(r"\s+", " ", str(keyword or "").strip().lower())
        if word and word not in cleaned:
            cleaned.append(word)
    if not cleaned:
        raise ValueError(f"{label} must contain at least one word or phrase.")
    return cleaned


def _optional_keywords(value, label):
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list of words or phrases.")
    cleaned = []
    for keyword in value:
        word = re.sub(r"\s+", " ", str(keyword or "").strip().lower())
        if word and word not in cleaned:
            cleaned.append(word)
    return cleaned


def _criterion_rules(value, label):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must contain at least one criterion.")
    rows = []
    seen = set()
    for index, item in enumerate(value, start=1):
        if isinstance(item, (list, tuple)) and len(item) >= 4:
            item = {"key": item[0], "label": item[1], "weight": item[2], "keywords": item[3]}
        if not isinstance(item, dict):
            raise ValueError(f"{label} criterion {index} is invalid.")
        key = _rule_key(item.get("key"), f"{label} criterion {index} key")
        if key in seen:
            raise ValueError(f"{label} contains the duplicate key '{key}'.")
        seen.add(key)
        title = str(item.get("label") or "").strip()
        if not title:
            raise ValueError(f"{label} criterion {index} requires a label.")
        context_defaults = _outcome_context_defaults(key, title)
        description = str(item.get("description") or "").strip() or (
            f"Measures whether the documented project activities and intended results contribute to {title.lower()}."
        )
        matching_guidance = str(item.get("matching_guidance") or "").strip() or context_defaults["guidance"]
        match_mode = str(item.get("match_mode") or "keyword").strip().lower()
        if match_mode not in ("keyword", "contextual"):
            raise ValueError(f"{title} matching mode must be keyword or contextual.")
        context_phrases = _optional_keywords(item.get("context_phrases"), f"{title} supporting context phrases")
        if item.get("context_phrases") is None:
            context_phrases = context_defaults["phrases"]
        if match_mode == "contextual" and not context_phrases:
            raise ValueError(f"{title} requires at least one supporting context phrase in contextual mode.")
        rows.append({
            "key": key,
            "label": title,
            "weight": _number(item.get("weight"), f"{title} weight", 0, 100),
            "keywords": _keywords(item.get("keywords"), f"{title} keywords"),
            "description": description,
            "matching_guidance": matching_guidance,
            "match_mode": match_mode,
            "context_phrases": context_phrases,
        })
    return rows


def _scale_rule_rows(value, label):
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must contain at least one scoring option.")
    rows = []
    seen = set()
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{label} option {index} is invalid.")
        key = _rule_key(item.get("key"), f"{label} option {index} key")
        if key in seen:
            raise ValueError(f"{label} contains the duplicate key '{key}'.")
        seen.add(key)
        guideline = str(item.get("guideline") or "").strip()
        if not guideline:
            raise ValueError(f"{label} option {index} requires guidance text.")
        rows.append({
            "key": key,
            "raw": _number(item.get("raw"), f"{label} option {key} score", 0, 10),
            "guideline": guideline,
        })
    return rows


def validate_priority_rule_config(config):
    if not isinstance(config, dict):
        raise ValueError("The AI scoring rules must be an object.")
    thresholds = config.get("thresholds")
    sectors = config.get("sector_criteria")
    dictionaries = config.get("keyword_dictionaries")
    if not isinstance(thresholds, dict) or not isinstance(sectors, dict) or not isinstance(dictionaries, dict):
        raise ValueError("Thresholds, sector criteria, and keyword dictionaries are required.")

    high = _number(thresholds.get("high"), "High-priority threshold", 0, 100)
    if high != 81:
        raise ValueError("The high-priority threshold must be 81. Scores from 0 to 80 are low priority.")
    pap_weights_value = thresholds.get("pap_weights")
    if not isinstance(pap_weights_value, dict):
        raise ValueError("PAP criterion weights are required.")
    pap_weights = {
        key: _number(pap_weights_value.get(key), f"{label} weight", 0, 100)
        for key, label in (
            ("readiness", "Readiness"),
            ("gad_responsiveness", "GAD responsiveness"),
            ("spatial_coverage", "Spatial coverage"),
        )
    }

    common = _criterion_rules(dictionaries.get("common_outcomes"), "Common outcomes")
    normalized_sectors = {}
    all_keys = {row["key"] for row in common}
    for sector in SECTOR_OUTCOMES:
        rows = _criterion_rules(sectors.get(sector), f"{sector.replace('_', ' ').title()} outcomes")
        duplicate = all_keys.intersection(row["key"] for row in rows)
        if duplicate:
            raise ValueError(f"Outcome criterion keys must be unique. Duplicate: {sorted(duplicate)[0]}.")
        normalized_sectors[sector] = rows

    pap_total = sum(float(value) for value in pap_weights.values())
    common_total = sum(float(row["weight"]) for row in common)
    for sector, rows in normalized_sectors.items():
        total = pap_total + common_total + sum(float(row["weight"]) for row in rows)
        if abs(total - 100) > 0.01:
            raise ValueError(
                f"The PAP, common, and {sector.replace('_', ' ')} weights must total 100; current total is {total:g}."
            )

    negative_value = dictionaries.get("negative_rules")
    if not isinstance(negative_value, list):
        raise ValueError("Negative-list rules must be a list.")
    negative_rules = []
    negative_keys = set()
    for index, item in enumerate(negative_value, start=1):
        if isinstance(item, (list, tuple)) and len(item) >= 3:
            item = {"key": item[0], "label": item[1], "keywords": item[2]}
        if not isinstance(item, dict):
            raise ValueError(f"Negative-list rule {index} is invalid.")
        key = _rule_key(item.get("key"), f"Negative-list rule {index} key")
        if key in negative_keys:
            raise ValueError(f"Negative-list rules contain the duplicate key '{key}'.")
        negative_keys.add(key)
        title = str(item.get("label") or "").strip()
        if not title:
            raise ValueError(f"Negative-list rule {index} requires a label.")
        negative_rules.append({"key": key, "label": title, "keywords": _keywords(item.get("keywords"), f"{title} keywords")})

    rating_value = dictionaries.get("outcome_rating")
    if not isinstance(rating_value, dict):
        raise ValueError("Outcome text-matching scores are required.")
    outcome_rating = {
        key: _number(rating_value.get(key), f"{label} score", 0, 10)
        for key, label in (
            ("chapter_and_two_keywords", "Chapter plus two matching words"),
            ("chapter_or_three_keywords", "Chapter or three matching words"),
            ("one_keyword", "At least one matching word"),
            ("no_keywords", "No matching words"),
        )
    }
    if not (
        outcome_rating["chapter_and_two_keywords"] >= outcome_rating["chapter_or_three_keywords"]
        >= outcome_rating["one_keyword"] >= outcome_rating["no_keywords"]
    ):
        raise ValueError("Text-matching scores must decrease from strongest match to no match.")

    guidelines_value = dictionaries.get("guidelines")
    if not isinstance(guidelines_value, list):
        raise ValueError("Employee guidelines must be a list.")
    guidelines = [re.sub(r"\s+", " ", str(value or "").strip()) for value in guidelines_value]
    guidelines = [value for value in guidelines if value]
    if not guidelines:
        raise ValueError("Add at least one employee guideline.")

    return {
        "thresholds": {
            "high": 81,
            "regional_project_cost": _number(
                thresholds.get("regional_project_cost"), "Regional-project cost threshold", 0
            ),
            "pap_weights": pap_weights,
        },
        "sector_criteria": normalized_sectors,
        "keyword_dictionaries": {
            "common_outcomes": common,
            "negative_rules": negative_rules,
            "readiness": _scale_rule_rows(dictionaries.get("readiness"), "Readiness rules"),
            "gad": _scale_rule_rows(dictionaries.get("gad"), "GAD responsiveness rules"),
            "outcome_rating": outcome_rating,
            "guidelines": guidelines,
        },
    }


def priority_rule_config(rule_set=None):
    config = default_priority_rule_config()
    if rule_set is None:
        return validate_priority_rule_config(config)

    if isinstance(rule_set.thresholds, dict):
        incoming_thresholds = deepcopy(rule_set.thresholds)
        incoming_pap = incoming_thresholds.pop("pap_weights", None)
        config["thresholds"].update(incoming_thresholds)
        if isinstance(incoming_pap, dict):
            config["thresholds"]["pap_weights"].update(incoming_pap)
    if isinstance(rule_set.sector_criteria, dict) and rule_set.sector_criteria:
        config["sector_criteria"].update(deepcopy(rule_set.sector_criteria))
    if isinstance(rule_set.keyword_dictionaries, dict):
        config["keyword_dictionaries"].update(deepcopy(rule_set.keyword_dictionaries))
    try:
        return validate_priority_rule_config(config)
    except ValueError:
        return validate_priority_rule_config(default_priority_rule_config())


def contextual_priority_rule_draft(rule_set=None):
    """Prepare an editable contextual-only draft without mutating the active rule version."""
    config = priority_rule_config(rule_set)
    outcome_rules = [*config["keyword_dictionaries"]["common_outcomes"]]
    for sector_rules in config["sector_criteria"].values():
        outcome_rules.extend(sector_rules)
    for rule in outcome_rules:
        rule["match_mode"] = "contextual"
        configured = OUTCOME_CONTEXT_RULES.get(rule["key"])
        if configured:
            rule["matching_guidance"] = configured["guidance"]
            rule["context_phrases"] = list(configured["phrases"])
    return validate_priority_rule_config(config)


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


def _scoring_form(snapshot):
    """Expose detailed and simplified submissions through one scoring shape."""
    form = _simplified(snapshot)
    if not isinstance(form, dict):
        return {}
    if isinstance(snapshot, dict) and isinstance(snapshot.get("simplified_form"), dict):
        return form
    if str(form.get("submission_type") or "").lower() != "detailed" and not form.get("projectTitle"):
        return form

    normalized = dict(form)
    normalized.setdefault("program", form.get("programOrProject") or "")
    normalized.setdefault("projectActivity", form.get("projectTitle") or "")
    normalized.setdefault("rdpMainChapter", form.get("mainPdpChapter") or "")
    normalized.setdefault("developmentSector", form.get("mainInfrastructureSector") or "")
    normalized.setdefault(
        "location",
        " | ".join(
            str(value).strip()
            for value in (
                form.get("costLocalities"),
                form.get("costProvinces"),
                form.get("impactProvinces"),
                form.get("convergenceLgu"),
                form.get("spatialCoverageByCost"),
                form.get("spatialCoverageByImpact"),
            )
            if str(value or "").strip()
        ),
    )
    physical_status = str(form.get("physicalFinancialStatus") or "")
    normalized.setdefault("status", "New" if "proposed" in physical_status.lower() else physical_status)
    if not isinstance(normalized.get("fundingRequirementByYear"), dict):
        normalized["fundingRequirementByYear"] = {"total": form.get("totalProjectCost") or 0}
    return normalized


def _normalized_text(form):
    raw = " ".join(str(form.get(field) or "") for field in SCORING_TEXT_FIELDS)
    raw += " " + " ".join(str(item) for item in form.get("sdgSelections") or [])
    return re.sub(r"\s+", " ", raw.lower()).strip()


def _compact_text(value, maximum=180):
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= maximum:
        return text
    return f"{text[:maximum - 3].rstrip()}..."


def _term_in_text(term, text):
    normalized_term = re.sub(r"\s+", " ", str(term or "").strip().lower())
    normalized_text = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not normalized_term or not normalized_text:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized_text) is not None


def _contextual_outcome_matches(form, keywords, context_phrases):
    """Count primary terms only when the same sentence contains supporting context."""
    sources = []
    matched_terms = set()
    values = [(field, form.get(field)) for field in SCORING_TEXT_FIELDS if field != "rdpMainChapter"]
    values.append(("sdgSelections", form.get("sdgSelections") or []))
    for field, raw_value in values:
        if isinstance(raw_value, (list, tuple)):
            display_value = ", ".join(str(value) for value in raw_value if str(value).strip())
        else:
            display_value = str(raw_value or "")
        segments = [
            re.sub(r"\s+", " ", segment).strip()
            for segment in re.split(r"(?:[.!?;]+|\r?\n)+", display_value)
            if segment.strip()
        ]
        for segment in segments:
            primary_matches = [term for term in keywords if _term_in_text(term, segment)]
            supporting_matches = [term for term in context_phrases if _term_in_text(term, segment)]
            if not primary_matches or not supporting_matches:
                continue
            matched_terms.update(primary_matches)
            sources.append({
                "field": field,
                "label": SCORING_FIELD_LABELS.get(field, field),
                "matches": primary_matches,
                "context_matches": supporting_matches,
                "excerpt": _compact_text(segment),
            })
    return sorted(matched_terms), sources


def _evidence_sources(form, evidence):
    """Locate matched rule terms in human-readable project fields."""
    terms = [str(value).strip().lower() for value in evidence or [] if str(value).strip()]
    if not terms:
        return []
    values = [(field, form.get(field)) for field in SCORING_TEXT_FIELDS]
    values.append(("sdgSelections", form.get("sdgSelections") or []))
    sources = []
    for field, raw_value in values:
        if isinstance(raw_value, (list, tuple)):
            display_value = ", ".join(str(value) for value in raw_value if str(value).strip())
        else:
            display_value = str(raw_value or "")
        normalized = display_value.lower()
        matches = [term for term in terms if term in normalized]
        if not matches:
            continue
        sources.append({
            "field": field,
            "label": SCORING_FIELD_LABELS.get(field, field),
            "matches": matches,
            "excerpt": _compact_text(display_value),
        })
    return sources


def _fact_label(value):
    key = _fact_key(value)
    return FACT_VALUE_LABELS.get(key, str(value or "").replace("_", " ").strip().title())


def _weighted_calculation(raw, weight, score):
    return (
        f"The rule assigned a raw rating of {raw:g}/10. With a weight of {weight:g} points, "
        f"the calculation is {raw:g}/10 x {weight:g} = {score:.2f} points."
    )


def _pap_explanation(key, raw, weight, score, remarks, facts, form):
    if key == "readiness":
        selected = facts.get("readinessLevel")
        if not selected:
            reason = (
                "No readiness level was supplied by the validator. The scorer does not infer completed studies, "
                "designs, or preparation documents from general narrative text, so this required fact received no points."
            )
        else:
            reason = (
                f"The validator selected '{_fact_label(selected)}'. Under the current readiness guideline, "
                f"this means: {remarks} This selection determines the raw rating; project wording alone cannot raise it."
            )
    elif key == "gad_responsiveness":
        selected = facts.get("gadResponsiveness")
        if not selected:
            reason = (
                "No GAD responsiveness category was supplied by the validator. The scorer therefore has no verified "
                "basis for judging the project's gender analysis, beneficiaries, activities, or indicators."
            )
        else:
            reason = (
                f"The validator selected '{_fact_label(selected)}'. The current GAD guideline describes this as: "
                f"{remarks} The score follows that verified category rather than assuming GAD responsiveness from keywords."
            )
    else:
        selected = facts.get("spatialCoverageScope")
        location = _compact_text(form.get("location"), maximum=140)
        if not selected:
            reason = (
                "No official spatial coverage category was supplied by the validator. A location written in the form "
                "does not by itself establish whether coverage is local, region-wide, or interregional."
            )
        else:
            location_text = f" The project location is recorded as '{location}'." if location else ""
            reason = (
                f"The validator selected '{_fact_label(selected)}'. {remarks}{location_text} "
                "The rating follows the official coverage category and, for specific LGUs, the number of recognized NCR localities."
            )
    return f"{reason} {_weighted_calculation(raw, weight, score)}"


def _outcome_explanation(item, form):
    raw = float(item.get("raw") or 0)
    weight = float(item.get("weight") or 0)
    score = float(item.get("score") or 0)
    evidence = [str(value).strip().lower() for value in item.get("evidence") or [] if str(value).strip()]
    sources = item.get("evidence_sources") if isinstance(item.get("evidence_sources"), list) else []
    if not sources:
        sources = _evidence_sources(form, evidence)
    chapter = str(form.get("rdpMainChapter") or "").lower()
    chapter_match = bool(item.get("chapter_match")) if "chapter_match" in item else any(
        _term_in_text(term, chapter) for term in evidence
    )
    match_mode = str(item.get("match_mode") or "keyword")
    rule_description = str(item.get("rule_description") or "").strip()
    matching_guidance = str(item.get("matching_guidance") or "").strip()
    ai_explanation = str(item.get("ai_explanation") or "").strip()

    if ai_explanation:
        evidence_note = ""
        if evidence:
            evidence_note = " Evidence cited from the project: " + "; ".join(
                f"'{value}'" for value in evidence[:5]
            ) + "."
        return (
            f"Contextual Assessment: {ai_explanation}{evidence_note} "
            f"{_weighted_calculation(raw, weight, score)} The result is advisory and must be confirmed by the validator."
        ).strip()

    if match_mode == "contextual" and chapter_match and len(evidence) >= 2:
        basis = (
            "The selected RDP Main Chapter aligns with the criterion, and at least two distinct matching terms appear "
            "in sentences that also describe a project action, output, beneficiary effect, or intended result. "
            "This meets the strongest contextual-alignment condition."
        )
    elif match_mode == "contextual" and chapter_match and evidence:
        basis = (
            "The selected RDP Main Chapter aligns with the criterion, and the narrative contains a context-supported "
            "matching term. This meets the chapter-plus-context condition."
        )
    elif match_mode == "contextual" and len(evidence) >= 3:
        basis = (
            "The project narrative contains at least three distinct matching terms in sentences that also describe "
            "concrete actions or intended results. The selected RDP Main Chapter did not add an alignment signal."
        )
    elif match_mode == "contextual" and evidence:
        basis = (
            f"The scorer found {len(evidence)} distinct context-supported matching "
            f"term{'s' if len(evidence) != 1 else ''}. This shows a limited documented connection, so the criterion "
            "did not qualify for a stronger rating."
        )
    elif match_mode == "contextual" and chapter_match:
        basis = (
            "The selected RDP Main Chapter contains aligned wording, but no project sentence connects a matching term "
            "to a concrete action, output, beneficiary effect, or intended result. The chapter selection alone therefore "
            "received no outcome-alignment points under this contextual rule."
        )
    elif match_mode == "contextual":
        basis = (
            "No context-supported evidence for this outcome was found. A matching word by itself was not counted unless "
            "the same sentence connected it to a concrete project action, output, beneficiary effect, or intended result."
        )
    elif chapter_match and len(evidence) >= 2:
        basis = (
            "The RDP Main Chapter contains aligned wording and the analyzed project fields contain at least two relevant terms. "
            "This meets the strongest text-alignment condition in the legacy keyword rule."
        )
    elif chapter_match:
        basis = (
            "The RDP Main Chapter contains aligned wording. The legacy keyword rule treats this as a strong alignment signal."
        )
    elif len(evidence) >= 3:
        basis = (
            "The project narrative contains at least three distinct relevant terms, which meets the stronger "
            "narrative-alignment condition in the legacy keyword rule."
        )
    elif evidence:
        basis = (
            f"The legacy keyword rule found only {len(evidence)} distinct relevant "
            f"term{'s' if len(evidence) != 1 else ''}, so it assigned only a limited text-alignment rating."
        )
    else:
        basis = (
            "No relevant wording for this outcome was found in the analyzed project title, program, location, description, "
            "objective, planning alignment, sector, remarks, status, or SDG selections. The rule therefore found no documented text alignment."
        )

    if sources:
        source_parts = []
        for source in sources[:4]:
            terms = ", ".join(f"'{term}'" for term in source["matches"])
            context_terms = ", ".join(f"'{term}'" for term in source.get("context_matches") or [])
            context_text = f" with supporting context {context_terms}" if context_terms else ""
            source_parts.append(
                f"{source['label']} contains {terms}{context_text} in the text '{source['excerpt']}'"
            )
        source_text = " Evidence was found in these fields: " + "; ".join(source_parts) + "."
    else:
        source_text = ""

    rule_context = ""
    if rule_description:
        rule_context += f" Criterion intent: {rule_description}"
    if matching_guidance:
        rule_context += f" CMS matching guidance: {matching_guidance}"
    limitation = (
        " These matches show why the rule assigned the rating, but they do not prove that the project will achieve the outcome; "
        "the validator must confirm that the described activities and measurable outputs genuinely support it."
        if evidence
        else " The validator should add or verify outcome evidence only when it is factually supported by the project."
    )
    return f"{rule_context.strip()} {basis}{source_text} {_weighted_calculation(raw, weight, score)}{limitation}".strip()


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


def _criterion(key, label, raw, weight, remarks, evidence=None, extra=None):
    points = (Decimal(str(raw)) / Decimal("10") * Decimal(str(weight))).quantize(Decimal("0.01"))
    result = {
        "key": key,
        "criterion": label,
        "raw": raw,
        "weight": weight,
        "score": float(points),
        "remarks": remarks,
        "evidence": evidence or [],
    }
    if isinstance(extra, dict):
        result.update(extra)
    return result


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
    selected = str(facts.get("sceeedTrack") or "").strip().lower()
    if selected in ("economic", "environment"):
        return selected
    sector = str(form.get("developmentSector") or "")
    if "Infrastructure" in sector:
        return "infrastructure"
    if "Social" in sector:
        return "social"
    if "Finance" in sector:
        return "financial_admin"
    if "Economic and Environment" in sector:
        environment_hits = sum(text.count(token) for token in ["climate", "environment", "flood", "river", "waste", "green"])
        economic_hits = sum(text.count(token) for token in ["trade", "industry", "business", "tourism", "agriculture", "investment"])
        return "environment" if environment_hits > economic_hits else "economic"
    return "social"


def _outcome_rating(form, text, chapter, outcome_rule, rating_rules):
    keywords = outcome_rule["keywords"]
    match_mode = outcome_rule.get("match_mode") or "keyword"
    chapter_hit = any(_term_in_text(keyword, chapter) for keyword in keywords)
    if match_mode == "contextual":
        hits, evidence_sources = _contextual_outcome_matches(
            form,
            keywords,
            outcome_rule.get("context_phrases") or [],
        )
        if chapter_hit and len(hits) >= 2:
            raw = rating_rules["chapter_and_two_keywords"]
        elif (chapter_hit and hits) or len(hits) >= 3:
            raw = rating_rules["chapter_or_three_keywords"]
        elif hits:
            raw = rating_rules["one_keyword"]
        else:
            raw = rating_rules["no_keywords"]
        return raw, hits, chapter_hit, evidence_sources

    hits = sorted({keyword for keyword in keywords if keyword in text})
    if chapter_hit and len(hits) >= 2:
        raw = rating_rules["chapter_and_two_keywords"]
    elif chapter_hit or len(hits) >= 3:
        raw = rating_rules["chapter_or_three_keywords"]
    elif hits:
        raw = rating_rules["one_keyword"]
    else:
        raw = rating_rules["no_keywords"]
    return raw, hits, chapter_hit, _evidence_sources(form, hits)


def _priority_for(score, thresholds):
    if score >= thresholds["high"]:
        return "high"
    return "low"


def _scale_rating(rows, value):
    key = _fact_key(value)
    item = next((row for row in rows if row["key"] == key), None)
    return (item["raw"], item["guideline"]) if item else None


def _guidance_field(key, label, source="contributor"):
    return {"key": key, "label": label, "source": source}


def _guidance_field_map(snapshot):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    detailed = (
        str(snapshot.get("submission_type") or "").lower() == "detailed"
        or "projectTitle" in snapshot
    )
    if detailed:
        outcome_fields = [
            _guidance_field("objective", "Project Objective"),
            _guidance_field("description", "Project Description"),
            _guidance_field("mainPdpChapter", "Main PDP Chapter"),
            _guidance_field("mainPdpOutcome", "Main PDP Outcome"),
            _guidance_field("mainPdpSubOutcome", "Main PDP Sub-outcome"),
            _guidance_field("mainPdpIndicator", "Main PDP Indicator"),
            _guidance_field("mainInfrastructureSector", "Main Infrastructure Sector"),
            _guidance_field("mainInfrastructureSubsector", "Main Infrastructure Subsector"),
            _guidance_field("expectedOutputIndicator", "Expected Output Indicator"),
            _guidance_field("remarks", "Remarks"),
        ]
        return {
            "readiness": [
                _guidance_field("supplement.readinessLevel", "Readiness Level", "validator"),
                _guidance_field("supplement.readinessNotes", "Readiness Evidence Notes", "validator"),
                _guidance_field("implementationReadinessLevel", "Implementation Readiness Level"),
                _guidance_field("projectReadinessItems", "Project Readiness Checklist"),
                _guidance_field("projectReadiness", "Project Readiness"),
            ],
            "gad_responsiveness": [
                _guidance_field("supplement.gadResponsiveness", "GAD Responsiveness", "validator"),
                _guidance_field("gadResponsiveness", "GAD Responsiveness"),
                _guidance_field("gadScore", "GAD Score"),
            ],
            "spatial_coverage": [
                _guidance_field("supplement.spatialCoverageScope", "Spatial Coverage", "validator"),
                _guidance_field("spatialCoverageByCost", "Spatial Coverage by Cost"),
                _guidance_field("spatialCoverageByImpact", "Spatial Coverage by Impact"),
                _guidance_field("costLocalities", "Cost Coverage Localities"),
                _guidance_field("costProvinces", "Cost Coverage Provinces"),
                _guidance_field("impactProvinces", "Impact Coverage Provinces"),
            ],
            "outcomes": outcome_fields,
            "regional_cost": [
                _guidance_field("totalProjectCost", "Total Project Cost"),
                _guidance_field("projectCostRows", "Project Cost Matrix Rows"),
            ],
            "regional_spatial": [
                _guidance_field("supplement.regionalSpatialCategory", "Regional Spatial Category", "validator"),
                _guidance_field("spatialCoverageByImpact", "Spatial Coverage by Impact"),
                _guidance_field("impactProvinces", "Impact Coverage Provinces"),
            ],
            "regional_outcomes": [
                _guidance_field("supplement.contributedOutcomeCount", "Contributed RDP Outcomes", "validator"),
                *outcome_fields,
            ],
            "regional_beneficiaries": [
                _guidance_field("supplement.beneficiaryCount", "Estimated Beneficiaries", "validator"),
                _guidance_field("objective", "Project Objective"),
                _guidance_field("description", "Project Description"),
                _guidance_field("expectedOutputValue", "Expected Output Value"),
            ],
            "status": [
                _guidance_field("physicalFinancialStatus", "Physical and Financial Status"),
                _guidance_field("updatesAsOf", "Updates as of"),
            ],
            "negative": [
                _guidance_field("projectTitle", "Project Title"),
                _guidance_field("objective", "Project Objective"),
                _guidance_field("description", "Project Description"),
                _guidance_field("remarks", "Remarks"),
            ],
        }

    outcome_fields = [
        _guidance_field("projectActivity", "Project/Activity"),
        _guidance_field("objective", "Objective"),
        _guidance_field("description", "Description"),
        _guidance_field("rdpMainChapter", "RDP Main Chapter"),
        _guidance_field("developmentSector", "Development Sector"),
        _guidance_field("remarks", "Remarks"),
    ]
    return {
        "readiness": [
            _guidance_field("supplement.readinessLevel", "Readiness Level", "validator"),
            _guidance_field("supplement.readinessNotes", "Readiness Evidence Notes", "validator"),
        ],
        "gad_responsiveness": [
            _guidance_field("supplement.gadResponsiveness", "GAD Responsiveness", "validator"),
        ],
        "spatial_coverage": [
            _guidance_field("supplement.spatialCoverageScope", "Spatial Coverage", "validator"),
            _guidance_field("location", "Location"),
        ],
        "outcomes": outcome_fields,
        "regional_cost": [
            _guidance_field("fundingRequirementByYear", "Funding Requirement", "contributor"),
        ],
        "regional_spatial": [
            _guidance_field("supplement.regionalSpatialCategory", "Regional Spatial Category", "validator"),
            _guidance_field("location", "Location"),
        ],
        "regional_outcomes": [
            _guidance_field("supplement.contributedOutcomeCount", "Contributed RDP Outcomes", "validator"),
            *outcome_fields,
        ],
        "regional_beneficiaries": [
            _guidance_field("supplement.beneficiaryCount", "Estimated Beneficiaries", "validator"),
            _guidance_field("objective", "Objective"),
            _guidance_field("description", "Description"),
        ],
        "status": [
            _guidance_field("status", "Status"),
            _guidance_field("physicalAccomplishment", "Physical Accomplishment"),
            _guidance_field("financialAccomplishment", "Financial Accomplishment"),
            _guidance_field("remarks", "Remarks"),
        ],
        "negative": [
            _guidance_field("projectActivity", "Project/Activity"),
            _guidance_field("objective", "Objective"),
            _guidance_field("description", "Description"),
            _guidance_field("remarks", "Remarks"),
        ],
    }


def _criterion_recommendation(item):
    key = str(item.get("key") or "")
    label = str(item.get("criterion") or "this criterion")
    if key == "readiness":
        return "Document completed preparation requirements and cite verifiable readiness evidence. Select a higher readiness level only when the supporting documents actually exist."
    if key == "gad_responsiveness":
        return "Strengthen the supported gender analysis, intended beneficiaries, responsive activities, indicators, and GAD evidence. Do not raise the category without supporting documentation."
    if key == "spatial_coverage":
        return "Clearly identify every covered LGU, the geographic scope, and whether benefits are city-wide, region-wide, or interregional."
    if key == "regional_cost":
        return "Verify that the complete project cost and yearly funding requirements are recorded. Correct omissions, but do not increase the amount only to obtain a higher score."
    if key == "regional_spatial":
        return "Document the regional reach and enumerate the covered LGUs or regions, then select the matching regional spatial category."
    if key == "regional_outcomes":
        return "Identify each genuinely supported RDP outcome and connect it to measurable project outputs before updating the contributed-outcome count."
    if key == "regional_beneficiaries":
        return "Provide a defensible beneficiary estimate, its basis, and the outputs through which those beneficiaries will be reached."
    return f"If supported by project evidence, clarify the measurable connection to “{label}” in the objective, description, planning alignment, and expected-output fields. Do not add unsupported claims merely to raise the score."


def _build_analysis_guidance(snapshot, scores, regional, flags, suggested_priority, base_score, supplements=None):
    scores = scores if isinstance(scores, dict) else {}
    regional = regional if isinstance(regional, dict) else {}
    flags = flags if isinstance(flags, dict) else {}
    form = _scoring_form(snapshot)
    facts = _merge_facts(form, supplements if isinstance(supplements, dict) else {})
    field_map = _guidance_field_map(snapshot)
    missing = [str(item) for item in scores.get("missing_facts") or []]
    pap = [item for item in scores.get("pap") or [] if isinstance(item, dict)]
    outcomes = [item for item in scores.get("rdp_outcomes") or [] if isinstance(item, dict)]
    base_criteria = pap + outcomes
    reasoning_items = []
    recommendations = []

    missing_by_key = {
        "readiness": "Readiness level",
        "gad_responsiveness": "GAD responsiveness",
        "spatial_coverage": "Official spatial coverage category",
    }
    for item in base_criteria:
        key = str(item.get("key") or "")
        label = str(item.get("criterion") or key or "Criterion")
        raw = float(item.get("raw") or 0)
        weight = float(item.get("weight") or 0)
        score = float(item.get("score") or 0)
        evidence = [str(value) for value in item.get("evidence") or [] if str(value).strip()]
        remarks = str(item.get("remarks") or "").strip()
        if key in ("readiness", "gad_responsiveness", "spatial_coverage"):
            explanation = _pap_explanation(key, raw, weight, score, remarks, facts, form)
            evidence_sources = []
        else:
            explanation = _outcome_explanation(item, form)
            evidence_sources = item.get("evidence_sources") if isinstance(item.get("evidence_sources"), list) else []
            if not evidence_sources:
                evidence_sources = _evidence_sources(form, evidence)
        reasoning_items.append(
            {
                "key": key,
                "criterion": label,
                "raw": raw,
                "weight": weight,
                "score": score,
                "maximum_score": weight,
                "explanation": explanation,
                "evidence": evidence,
                "evidence_sources": evidence_sources,
                "rule_description": str(item.get("rule_description") or ""),
                "matching_guidance": str(item.get("matching_guidance") or ""),
                "match_mode": str(item.get("match_mode") or "keyword"),
            }
        )
        potential_gain = round(max(0.0, weight - score), 2)
        required_fact = missing_by_key.get(key)
        is_missing = bool(required_fact and required_fact in missing)
        if potential_gain > 0 or is_missing:
            recommendations.append(
                {
                    "key": key,
                    "criterion": label,
                    "priority": "required" if is_missing else "high" if potential_gain >= 10 else "medium",
                    "potential_gain": potential_gain,
                    "scorecard": "base",
                    "recommendation": _criterion_recommendation(item),
                    "fields": field_map.get(key, field_map["outcomes"]),
                }
            )

    regional_criteria = [item for item in regional.get("criteria") or [] if isinstance(item, dict)]
    for item in regional_criteria:
        key = str(item.get("key") or "")
        weight = float(item.get("weight") or 0)
        score = float(item.get("score") or 0)
        potential_gain = round(max(0.0, weight - score), 2)
        if potential_gain <= 0:
            continue
        recommendations.append(
            {
                "key": key,
                "criterion": str(item.get("criterion") or key),
                "priority": "high" if potential_gain >= 10 else "medium",
                "potential_gain": potential_gain,
                "scorecard": "regional",
                "recommendation": _criterion_recommendation(item),
                "fields": field_map.get(key, []),
            }
        )

    extra_missing = {
        "SCEED Economic or Environment track confirmation": (
            "sceeed_track",
            "Confirm the applicable SCEED Economic or Environment track from the project’s documented sector and intended outcomes.",
            [_guidance_field("supplement.sceeedTrack", "SCEED Track", "validator"), *field_map["outcomes"]],
        ),
        "Regional beneficiary count": (
            "regional_beneficiaries",
            "Supply a defensible beneficiary estimate and its basis.",
            field_map["regional_beneficiaries"],
        ),
        "Regional spatial coverage category": (
            "regional_spatial",
            "Select the regional spatial category that is supported by the listed project locations.",
            field_map["regional_spatial"],
        ),
        "Number of contributed RDP outcomes": (
            "regional_outcomes",
            "Identify the supported RDP outcomes and enter their verified count.",
            field_map["regional_outcomes"],
        ),
    }
    existing_required = {missing_by_key.get(str(item.get("key") or "")) for item in recommendations}
    for fact in missing:
        if fact in existing_required or fact not in extra_missing:
            continue
        key, recommendation, fields = extra_missing[fact]
        matching = next((item for item in recommendations if item.get("key") == key), None)
        if matching:
            matching["priority"] = "required"
            matching["recommendation"] = recommendation
            matching["fields"] = fields
            continue
        recommendations.append(
            {
                "key": key,
                "criterion": fact,
                "priority": "required",
                "potential_gain": None,
                "scorecard": "required_input",
                "recommendation": recommendation,
                "fields": fields,
            }
        )

    risks = [str(item) for item in flags.get("risks") or []]
    for index, risk in enumerate(risks):
        if risk == "Official score confirmation requires missing factual inputs.":
            continue
        recommendations.append(
            {
                "key": f"risk_{index}",
                "criterion": "Risk flag",
                "priority": "high",
                "potential_gain": None,
                "scorecard": "risk",
                "recommendation": f"Resolve or explain this review flag: {risk}",
                "fields": field_map["status"],
            }
        )
    negative_matches = [item for item in flags.get("negative_matches") or [] if isinstance(item, dict)]
    for item in negative_matches:
        recommendations.append(
            {
                "key": f"negative_{item.get('key')}",
                "criterion": "Possible negative-list match",
                "priority": "high",
                "potential_gain": None,
                "scorecard": "eligibility",
                "recommendation": f"Review whether “{item.get('label')}” accurately applies. Clarify the project scope with evidence; do not remove truthful wording simply to avoid the flag.",
                "fields": field_map["negative"],
            }
        )

    priority_order = {"required": 0, "high": 1, "medium": 2, "low": 3}
    recommendations.sort(
        key=lambda item: (
            priority_order.get(item.get("priority"), 9),
            -(item.get("potential_gain") or 0),
            str(item.get("criterion") or ""),
        )
    )
    revision_fields = {}
    for recommendation in recommendations:
        for field in recommendation.get("fields") or []:
            identity = f"{field.get('source')}:{field.get('key')}"
            current = revision_fields.setdefault(
                identity,
                {**field, "reasons": [], "priority": recommendation.get("priority") or "medium"},
            )
            criterion = str(recommendation.get("criterion") or "").strip()
            if criterion and criterion not in current["reasons"]:
                current["reasons"].append(criterion)
            if priority_order.get(recommendation.get("priority"), 9) < priority_order.get(current["priority"], 9):
                current["priority"] = recommendation.get("priority")

    pap_total = float(scores.get("pap_total") or 0)
    rdp_total = float(scores.get("rdp_total") or 0)
    status_text = PRIORITY_LABELS.get(suggested_priority, "Incomplete")
    overall = (
        f"The {float(base_score):.2f}/100 base score is the sum of {pap_total:.2f} PAP points "
        f"and {rdp_total:.2f} RDP-alignment points. Each weighted score equals the raw rating divided by 10, "
        f"multiplied by the criterion weight. The current high-priority threshold is 81/100. "
        f"This results in a {status_text.lower()} recommendation."
    )
    if suggested_priority == "high":
        overall += f" The score is {max(0.0, float(base_score) - 81):.2f} points above the high-priority threshold."
    elif suggested_priority == "low":
        overall += f" The score is {max(0.0, 81 - float(base_score)):.2f} points below the high-priority threshold."
    if regional.get("applicable"):
        overall += " The regional prioritization scorecard is shown separately and does not change the base score."
    if missing:
        overall += " The recommendation remains incomplete until all required factual inputs are supplied."

    return {
        "guidance_version": ANALYSIS_GUIDANCE_VERSION,
        "reasoning": {"overall": overall, "criteria": reasoning_items},
        "recommendations": recommendations,
        "revision_fields": list(revision_fields.values()),
    }


def ensure_analysis_guidance(analysis):
    scores = dict(analysis.suggested_scores or {})
    if (
        scores.get("guidance_version") == ANALYSIS_GUIDANCE_VERSION
        and all(key in scores for key in ("reasoning", "recommendations", "revision_fields"))
    ):
        return analysis
    guidance = _build_analysis_guidance(
        analysis.input_snapshot,
        scores,
        analysis.regional_scorecard,
        analysis.flags,
        analysis.suggested_priority,
        analysis.base_score,
        supplements=analysis.supplements,
    )
    scores.update(guidance)
    analysis.suggested_scores = scores
    analysis.save(update_fields=["suggested_scores"])
    return analysis


def _active_ruleset():
    rule_set = PriorityRuleSet.objects.filter(is_active=True).order_by("-created_at").first()
    if rule_set:
        return rule_set
    config = default_priority_rule_config()
    rule_set, _ = PriorityRuleSet.objects.get_or_create(
        version=RULE_VERSION,
        defaults={
            "algorithm_version": ALGORITHM_VERSION,
            "is_active": True,
            **config,
        },
    )
    if not rule_set.is_active:
        rule_set.is_active = True
        rule_set.save(update_fields=["is_active"])
    return rule_set


def get_active_priority_rule_set():
    return _active_ruleset()


def source_hash(
    snapshot,
    supplements,
    rule_set=None,
    project=None,
):
    rules = rule_set or _active_ruleset()
    historical_dataset_version = ""
    if getattr(settings, "GROQ_ENABLED", False):
        try:
            from ai_engine.services import reference_dataset_version

            historical_dataset_version = reference_dataset_version(
                exclude_project_id=getattr(project, "pk", None),
            )
        except Exception:
            historical_dataset_version = "unavailable"
    payload = {
        "snapshot": snapshot if isinstance(snapshot, dict) else {},
        "supplements": supplements if isinstance(supplements, dict) else {},
        "rules": rules.version,
        "algorithm": rules.algorithm_version,
        "ai_provider": "groq" if getattr(settings, "GROQ_ENABLED", False) else "local-fallback",
        "ai_primary_model": getattr(settings, "GROQ_PRIMARY_MODEL", "") if getattr(settings, "GROQ_ENABLED", False) else "",
        "ai_backup_model": getattr(settings, "GROQ_BACKUP_MODEL", "") if getattr(settings, "GROQ_ENABLED", False) else "",
        "historical_dataset_version": historical_dataset_version,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _confirmation_snapshot_hash(snapshot):
    """Hash only the validator-visible project copy used for confirmation.

    AI provider, model, and historical-reference changes are intentionally not
    included here. Those may create a new analysis, but they must not make an
    already confirmed, unchanged validator copy impossible to endorse.
    """
    normalized = deepcopy(snapshot) if isinstance(snapshot, dict) else {}
    for key in ("validator_review", "contributor_snapshot", "public_summary"):
        normalized.pop(key, None)
    if isinstance(normalized.get("simplified_form"), dict):
        marker = normalized.get("form_schema")
        if isinstance(marker, dict):
            normalized["form_schema"] = {
                "key": str(marker.get("key") or "simplified-rdip"),
                "version": marker.get("version") or 1,
            }
        else:
            normalized["form_schema"] = {"key": "simplified-rdip", "version": 1}
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def analyze_project(project, validator, snapshot, supplements=None):
    supplements = supplements if isinstance(supplements, dict) else {}
    rules = _active_ruleset()
    rule_config = priority_rule_config(rules)
    thresholds = rule_config["thresholds"]
    dictionaries = rule_config["keyword_dictionaries"]
    digest = source_hash(snapshot, supplements, rules, project=project)
    existing = ProjectPriorityAnalysis.objects.filter(project=project, rule_set=rules, source_hash=digest).first()
    if existing:
        existing = ensure_analysis_guidance(existing)
        from ai_engine.services import ensure_learning_assessment
        existing._current_learning_assessment = ensure_learning_assessment(existing)
        return existing, True

    form = _scoring_form(snapshot)
    facts = _merge_facts(form, supplements)
    text = _normalized_text(form)
    lgu_count = len(derive_ncr_lgus(str(form.get("location") or "")))
    missing = []

    readiness = _scale_rating(dictionaries["readiness"], facts.get("readinessLevel"))
    if readiness is None:
        missing.append("Readiness level")
        readiness = (0, "Readiness level must be supplied by the validator.")
    gad = _scale_rating(dictionaries["gad"], facts.get("gadResponsiveness"))
    if gad is None:
        missing.append("GAD responsiveness")
        gad = (0, "GAD responsiveness must be supplied by the validator.")
    spatial = _spatial_rating(_fact_key(facts.get("spatialCoverageScope")), lgu_count)
    if spatial[0] is None:
        missing.append("Official spatial coverage category")
        spatial = (0, spatial[1])

    pap_weights = thresholds["pap_weights"]
    pap = [
        _criterion("readiness", "Readiness", readiness[0], pap_weights["readiness"], readiness[1]),
        _criterion(
            "gad_responsiveness",
            "Level of GAD Responsiveness",
            gad[0],
            pap_weights["gad_responsiveness"],
            gad[1],
        ),
        _criterion(
            "spatial_coverage",
            "Spatial Coverage",
            spatial[0],
            pap_weights["spatial_coverage"],
            spatial[1],
        ),
    ]
    pap_total = sum(item["score"] for item in pap)

    track = _sector_track(form, facts, text)
    if "Economic and Environment" in str(form.get("developmentSector") or "") and not facts.get("sceeedTrack"):
        missing.append("SCEED Economic or Environment track confirmation")
    chapter = str(form.get("rdpMainChapter") or "").lower()
    outcomes = []
    outcome_rules = dictionaries["common_outcomes"] + rule_config["sector_criteria"][track]
    for outcome_rule in outcome_rules:
        key = outcome_rule["key"]
        label = outcome_rule["label"]
        weight = outcome_rule["weight"]
        raw, evidence, chapter_match, evidence_sources = _outcome_rating(
            form,
            text,
            chapter,
            outcome_rule,
            dictionaries["outcome_rating"],
        )
        outcomes.append(_criterion(
            key,
            label,
            raw,
            weight,
            "The suggested rating is based on relevant words found in the project details.",
            evidence,
            {
                "rule_description": outcome_rule.get("description") or "",
                "matching_guidance": outcome_rule.get("matching_guidance") or "",
                "match_mode": outcome_rule.get("match_mode") or "keyword",
                "context_phrases": outcome_rule.get("context_phrases") or [],
                "chapter_match": chapter_match,
                "evidence_sources": evidence_sources,
            },
        ))

    groq_analysis = None
    try:
        from ai_engine.groq_priority import analyze_priority_with_groq

        groq_analysis = analyze_priority_with_groq(
            project,
            snapshot,
            supplements,
            outcome_rules,
            track,
            dictionaries.get("guidelines") or [],
        )
    except Exception:
        # An external inference failure must not block a validator from using the existing safe scorecard.
        groq_analysis = None
    if groq_analysis:
        assessment_by_key = {
            item["key"]: item
            for item in groq_analysis.get("outcomes") or []
            if isinstance(item, dict) and item.get("key")
        }
        for outcome in outcomes:
            assessment = assessment_by_key.get(outcome["key"])
            if not assessment:
                continue
            raw = max(0.0, min(10.0, float(assessment.get("raw_score") or 0)))
            outcome["raw"] = raw
            outcome["score"] = float(
                (Decimal(str(raw)) / Decimal("10") * Decimal(str(outcome["weight"]))).quantize(Decimal("0.01"))
            )
            outcome["remarks"] = "Groq evaluated the project narrative against the active CMS criterion guidance."
            outcome["evidence"] = assessment.get("evidence") or []
            outcome["evidence_sources"] = []
            outcome["match_mode"] = "groq_contextual"
            outcome["ai_explanation"] = assessment.get("explanation") or ""
            outcome["ai_recommendation"] = assessment.get("recommendation") or ""
            outcome["ai_revision_fields"] = assessment.get("revision_fields") or []
    outcome_total = sum(item["score"] for item in outcomes)
    base_score = round(pap_total + outcome_total, 2)

    funding_total = _money_total(form.get("fundingRequirementByYear"))
    regional = {"applicable": funding_total >= thresholds["regional_project_cost"], "total": 0, "criteria": []}
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
    for negative_rule in dictionaries["negative_rules"]:
        key = negative_rule["key"]
        label = negative_rule["label"]
        keywords = negative_rule["keywords"]
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
    if groq_analysis:
        for risk in groq_analysis.get("risks") or []:
            if risk and risk not in risks:
                risks.append(risk)

    suggested_priority = "incomplete" if missing else _priority_for(base_score, thresholds)
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

    suggested_scores = {
        "pap": pap,
        "pap_total": round(pap_total, 2),
        "rdp_track": track,
        "rdp_outcomes": outcomes,
        "rdp_total": round(outcome_total, 2),
        "base_total": base_score,
        "missing_facts": missing,
    }
    if groq_analysis:
        suggested_scores["ai_provider"] = groq_analysis.get("provider") or {"name": "groq"}
        suggested_scores["groq_analysis"] = {
            "historical_prediction": groq_analysis.get("historical_prediction") or {},
        }
    elif getattr(settings, "GROQ_ENABLED", False):
        suggested_scores["ai_provider"] = {
            "name": "groq",
            "status": "unavailable",
            "mode": "deterministic_emergency_fallback",
            "primary_model": getattr(settings, "GROQ_PRIMARY_MODEL", ""),
            "backup_model": getattr(settings, "GROQ_BACKUP_MODEL", ""),
        }
    else:
        suggested_scores["ai_provider"] = {
            "name": "local",
            "status": "not_configured",
            "mode": "deterministic_fallback",
        }
    suggested_scores.update(
        _build_analysis_guidance(
            snapshot,
            suggested_scores,
            regional,
            {"negative_matches": negative, "risks": risks},
            suggested_priority,
            base_score,
            supplements=supplements,
        )
    )
    if groq_analysis:
        overall_reasoning = str(groq_analysis.get("overall_reasoning") or "").strip()
        if overall_reasoning:
            existing_overall = str(suggested_scores.get("reasoning", {}).get("overall") or "")
            suggested_scores["reasoning"]["overall"] = (
                f"Assessment: {overall_reasoning} {existing_overall}"
            ).strip()
        recommendations = list(suggested_scores.get("recommendations") or [])
        revisions = {
            (item.get("source"), item.get("key")): item
            for item in suggested_scores.get("revision_fields") or []
            if isinstance(item, dict)
        }
        for outcome in outcomes:
            recommendation = str(outcome.get("ai_recommendation") or "").strip()
            field_keys = [str(value) for value in outcome.get("ai_revision_fields") or [] if str(value)]
            fields = []
            for key in field_keys:
                field = {
                    "key": key,
                    "label": SCORING_FIELD_LABELS.get(key, key.replace("_", " ").title()),
                    "source": "contributor",
                    "reasons": [outcome["criterion"]],
                    "priority": "high" if float(outcome.get("raw") or 0) < 5 else "medium",
                }
                fields.append(field)
                revisions[("contributor", key)] = field
            if recommendation:
                recommendations = [
                    item for item in recommendations
                    if not (isinstance(item, dict) and item.get("scorecard") == "base" and item.get("key") == outcome["key"])
                ]
                recommendations.append(
                    {
                        "key": outcome["key"],
                        "criterion": outcome["criterion"],
                        "priority": "high" if float(outcome.get("raw") or 0) < 5 else "medium",
                        "potential_gain": round(max(0.0, float(outcome["weight"]) - float(outcome["score"])), 2),
                        "scorecard": "base",
                        "recommendation": recommendation,
                        "fields": fields,
                    }
                )
        suggested_scores["recommendations"] = recommendations
        suggested_scores["revision_fields"] = list(revisions.values())
    analysis = ProjectPriorityAnalysis.objects.create(
        project=project,
        validator=validator,
        rule_set=rules,
        source_hash=digest,
        input_snapshot=snapshot if isinstance(snapshot, dict) else {},
        supplements=supplements,
        suggested_scores=suggested_scores,
        regional_scorecard=regional,
        flags={"negative_matches": negative, "risks": risks},
        summary=summary,
        suggested_priority=suggested_priority,
        base_score=base_score,
    )
    from ai_engine.services import ensure_learning_assessment
    analysis._current_learning_assessment = ensure_learning_assessment(analysis)
    return analysis, False


def has_matching_confirmation(project, snapshot):
    active_rules = _active_ruleset()
    current_snapshot_hash = _confirmation_snapshot_hash(snapshot)
    confirmed_analyses = project.priority_analyses.filter(
        confirmations__isnull=False,
        rule_set=active_rules,
    ).distinct().only("input_snapshot")
    return any(
        _confirmation_snapshot_hash(analysis.input_snapshot) == current_snapshot_hash
        for analysis in confirmed_analyses
    )


def confirm_analysis(analysis, validator, adjusted_scores, final_priority, override_rationale, confirmed_flags):
    missing = analysis.suggested_scores.get("missing_facts") or []
    if missing:
        raise ValueError("Supply all missing factual inputs and run the scorer again before confirmation.")
    if final_priority not in ("high", "low"):
        raise ValueError("Final priority must be high or low.")
    if final_priority != analysis.suggested_priority and not str(override_rationale or "").strip():
        raise ValueError("An override rationale is required when changing the suggested priority.")
    confirmation = ProjectPriorityConfirmation.objects.create(
        analysis=analysis,
        validator=validator,
        adjusted_scores=adjusted_scores if isinstance(adjusted_scores, dict) else {},
        final_priority=final_priority,
        override_rationale=str(override_rationale or "").strip(),
        confirmed_flags=confirmed_flags if isinstance(confirmed_flags, list) else [],
    )
    from ai_engine.services import sync_training_record
    sync_training_record(confirmation)
    return confirmation
