from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


_NUM_RE = re.compile(r"[^0-9.\-]+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_number(raw: Any) -> float:
    if raw is None:
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return 0.0
    s = _NUM_RE.sub("", s)
    try:
        n = float(s)
    except Exception:
        return 0.0
    if n < 0:
        return 0.0
    return n


def _money(n: float) -> str:
    if n <= 0:
        return "PHP 0"
    # Public-facing: keep it clean. Add decimals only when needed.
    if abs(n - round(n)) < 1e-9:
        return f"PHP {int(round(n)):,}"
    return f"PHP {n:,.2f}"


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _snippet(text: str, max_len: int) -> str:
    s = _safe_str(text)
    if not s:
        return ""
    # Prefer first sentence-ish chunk.
    for sep in [". ", "\n", "\r\n", "; "]:
        if sep in s:
            s = s.split(sep, 1)[0].strip()
            break
    if len(s) <= max_len:
        return s
    return (s[: max_len - 1].rstrip() + "…") if max_len > 1 else s[:max_len]


def _sum_year_map(raw: Any) -> float:
    if not isinstance(raw, dict):
        return 0.0
    total = 0.0
    for _, v in raw.items():
        total += _to_number(v)
    return total


def build_public_summary(simplified_form: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic, template-based summary used by the public dashboard.

    IMPORTANT:
    - This function must not include internal-only fields (e.g., UACS code).
    - Caller is responsible for storing it in profile_data["public_summary"].
    """
    sf = simplified_form if isinstance(simplified_form, dict) else {}

    agency = _safe_str(sf.get("agencyName"))
    program = _safe_str(sf.get("program"))
    activity = _safe_str(sf.get("projectActivity"))
    location_raw = _safe_str(sf.get("location"))
    objective = _safe_str(sf.get("objective"))
    description = _safe_str(sf.get("description"))

    start_year = _safe_str(sf.get("startYear"))
    end_year = _safe_str(sf.get("endYear"))
    status = _safe_str(sf.get("status"))
    sector = _safe_str(sf.get("developmentSector"))
    chapter = _safe_str(sf.get("rdpMainChapter"))

    sdgs = sf.get("sdgSelections") if isinstance(sf.get("sdgSelections"), list) else []
    sdgs_clean = [str(v).strip() for v in sdgs if str(v).strip()]

    fr_total = _to_number(sf.get("fundingRequirementTotal"))
    aa_total = _to_number(sf.get("actualApprovedTotal"))
    if fr_total <= 0:
        fr_total = _sum_year_map(sf.get("fundingRequirementByYear"))
    if aa_total <= 0:
        aa_total = _sum_year_map(sf.get("actualFundingByYear"))

    # Summary paragraph (2-4 sentences).
    pieces: List[str] = []
    head = activity or program or "This project"
    if agency and location_raw:
        pieces.append(f"{head} is an initiative by {agency} in {location_raw}.")
    elif agency:
        pieces.append(f"{head} is an initiative by {agency}.")
    elif location_raw:
        pieces.append(f"{head} is located in {location_raw}.")
    else:
        pieces.append(f"{head} is listed under the RDC-NCR investment programming dashboard.")

    # Add purpose/context (this is usually what the public cares about most).
    purpose = _snippet(objective, 220) or _snippet(description, 220)
    if purpose:
        if objective:
            pieces.append(f"It aims to {purpose.rstrip('.')}.")
        else:
            pieces.append(f"It focuses on {purpose.rstrip('.')}.")

    if start_year or end_year:
        if start_year and end_year:
            pieces.append(f"Implementation period: {start_year} to {end_year}.")
        elif start_year:
            pieces.append(f"Implementation start year: {start_year}.")
        else:
            pieces.append(f"Implementation end year: {end_year}.")

    if status:
        pieces.append(f"Status: {status}.")

    if sector or chapter:
        details = []
        if sector:
            details.append(sector)
        if chapter:
            details.append(chapter)
        pieces.append(f"Alignment: {' | '.join(details)}.")

    # Funding sentence only when we have something meaningful.
    if fr_total > 0 or aa_total > 0:
        if fr_total > 0 and aa_total > 0:
            pieces.append(
                f"Funding requirement is {_money(fr_total)} and actual/approved funding is {_money(aa_total)}."
            )
        elif fr_total > 0:
            pieces.append(f"Funding requirement is {_money(fr_total)}.")
        else:
            pieces.append(f"Actual/approved funding is {_money(aa_total)}.")

    summary_text = " ".join(pieces[:4]).strip()

    # Bullets (5-10, only if present)
    bullets: List[str] = []
    if objective:
        bullets.append(f"Objective: {_snippet(objective, 240)}")
    if description:
        bullets.append(f"Description: {_snippet(description, 240)}")
    if program:
        bullets.append(f"Program: {program}")
    if activity:
        bullets.append(f"Project/Activity: {activity}")
    if location_raw:
        bullets.append(f"Location: {location_raw}")
    if start_year or end_year:
        bullets.append(f"Implementation Period: {start_year or '-'} to {end_year or '-'}")
    if status:
        bullets.append(f"Status: {status}")
    if sector:
        bullets.append(f"RDC-NCR Development Sector: {sector}")
    if chapter:
        bullets.append(f"RDP-NCR Main Chapter: {chapter}")
    if sdgs_clean:
        bullets.append(f"SDGs: {', '.join(sdgs_clean[:8])}{'...' if len(sdgs_clean) > 8 else ''}")
    if fr_total > 0:
        bullets.append(f"Funding Requirement Total: {_money(fr_total)}")
    if aa_total > 0:
        bullets.append(f"Actual/Approved Funding Total: {_money(aa_total)}")

    bullets = bullets[:10]

    key_facts = {
        "agency": agency,
        "location": location_raw,
        "objective": _snippet(objective, 360),
        "start_year": start_year,
        "end_year": end_year,
        "status": status,
        "development_sector": sector,
        "rdp_main_chapter": chapter,
        "sdg_count": len(sdgs_clean),
        "funding_requirement_total": fr_total,
        "actual_approved_total": aa_total,
    }

    return {
        "generated_at": _now_iso(),
        "generated_by": "system",
        "text": summary_text,
        "bullets": bullets,
        "key_facts": key_facts,
    }
