import re
import unicodedata


# Canonical NCR LGU keys must match frontend `src/services/ncrCityCenters.ts`.
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


def derive_ncr_lgu(location_text: str | None) -> str | None:
    """
    Best-effort extraction of NCR LGU from human-entered `location` text.
    Strict matching: returns a canonical NCR LGU key or None when not recognized.
    """
    raw = str(location_text or "").strip()
    if not raw:
        return None

    # Normalize
    lowered = raw.lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9\s\-\.]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    plain = _strip_accents(lowered)
    plain = re.sub(r"\s+", " ", plain).strip()

    candidates = {lowered, plain}

    # Direct keyword matching
    for canonical, variants in NCR_LGU_CANONICAL.items():
        for v in variants:
            if v in candidates:
                return canonical
        # Also match within longer strings, e.g. "Pasig City", "QC District".
        for v in variants:
            if v and (v in lowered or v in plain):
                return canonical

    return None


