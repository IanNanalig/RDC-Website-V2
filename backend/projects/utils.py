import re
import unicodedata


# Canonical NCR LGU keys must match frontend `frontend/src/services/ncrCityCenters.ts`.
NCR_LGU_CANONICAL = {
    "Manila": {"manila", "city of manila", "maynila", "mnl"},
    "Quezon City": {"quezon city", "quezon", "qc", "q.c", "q c"},
    "Pasig": {"pasig"},
    "Makati": {"makati"},
    "Caloocan": {"caloocan", "kalookan"},
    "Taguig": {"taguig"},
    "Pasay": {"pasay"},
    "Parañaque": {"paranaque", "parañaque"},
    "Las Piñas": {"las pinas", "las piñas", "laspiñas", "las-pinas"},
    "Mandaluyong": {"mandaluyong"},
    "Marikina": {"marikina"},
    "Muntinlupa": {"muntinlupa"},
    "Navotas": {"navotas"},
    "San Juan": {"san juan", "sanjuan"},
    "Valenzuela": {"valenzuela"},
    "Malabon": {"malabon"},
    "Pateros": {"pateros"},
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_location_text(text: str) -> str:
    lowered = _strip_accents(text.lower())
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9\s\-\.]", " ", lowered)
    lowered = re.sub(r"[\-\.]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def derive_ncr_lgus(location_text: str | None) -> list[str]:
    """
    Extract every NCR LGU mentioned in human-entered `location` text.
    Results follow the order in which locations appear in the source text.
    """
    raw = str(location_text or "").strip()
    if not raw:
        return []

    normalized = _normalize_location_text(raw)
    # "Metro Manila" describes the region, not the City of Manila.
    searchable = re.sub(r"\bmetro manila\b", " ", normalized)
    searchable = re.sub(r"\s+", " ", searchable).strip()

    matches: list[tuple[int, str]] = []
    for canonical, variants in NCR_LGU_CANONICAL.items():
        positions = []
        for variant in variants:
            normalized_variant = _normalize_location_text(variant)
            if not normalized_variant:
                continue
            pattern = rf"(?<![a-z0-9]){re.escape(normalized_variant)}(?![a-z0-9])"
            found = re.search(pattern, searchable)
            if found:
                positions.append(found.start())
        if positions:
            matches.append((min(positions), canonical))

    matches.sort(key=lambda item: item[0])
    return [canonical for _, canonical in matches]


def derive_ncr_lgu(location_text: str | None) -> str | None:
    """
    Best-effort extraction of NCR LGU from human-entered `location` text.
    Strict matching: returns a canonical NCR LGU key or None when not recognized.
    """
    lgus = derive_ncr_lgus(location_text)
    return lgus[0] if lgus else None


