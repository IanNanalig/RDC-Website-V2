"""Validation and calculation of human scoring without changing AI suggestions."""

from decimal import Decimal, InvalidOperation

from .models import ProjectPriorityEvaluation
from .priority_scoring import (
    SCORE_TOTAL_VERSION, bounded_score, overall_score, priority_rule_config, regional_eligibility,
    weighted_points, _priority_with_regional_budget, _money_total,
)


def calculate_evaluation(analysis, adjusted_scores, validator_remarks):
    if not isinstance(adjusted_scores, dict) or not isinstance(validator_remarks, dict):
        raise ValueError("Scores and remarks must be objects.")
    suggested = analysis.suggested_scores if isinstance(analysis.suggested_scores, dict) else {}
    regional = analysis.regional_scorecard if isinstance(analysis.regional_scorecard, dict) else {}
    groups = {
        "pap": suggested.get("pap") or [],
        "rdp": suggested.get("rdp_outcomes") or [],
        "regional": (regional.get("criteria") or []) if regional.get("applicable") else [],
    }
    allowed = {f"{group}:{item['key']}" for group, items in groups.items() for item in items}
    def canonical_keys(values):
        normalized = {}
        for key, value in values.items():
            if key in allowed:
                target = key
            else:
                matches = [candidate for candidate in allowed if candidate.endswith(f":{key}")]
                target = matches[0] if len(matches) == 1 else key
            normalized[target] = value
        return normalized
    adjusted_scores = canonical_keys(adjusted_scores)
    validator_remarks = canonical_keys(validator_remarks)
    if set(adjusted_scores) - allowed or set(validator_remarks) - allowed:
        raise ValueError("An unknown scoring criterion was supplied.")
    clean_scores, clean_remarks = {}, {}
    totals = {"pap": Decimal("0"), "rdp": Decimal("0"), "regional": Decimal("0")}
    for group, items in groups.items():
        for item in items:
            key = f"{group}:{item['key']}"
            raw = adjusted_scores.get(key, item["raw"])
            try:
                number = Decimal(str(raw))
            except (InvalidOperation, ValueError, TypeError):
                raise ValueError(f"{item['criterion']} must be a whole number from 0 to 10.")
            if (
                not number.is_finite() or not 0 <= number <= 10
                or (number != number.to_integral_value() and number != Decimal(str(item["raw"])))
            ):
                raise ValueError(f"{item['criterion']} must be a whole number from 0 to 10.")
            clean_scores[key] = int(number) if number == number.to_integral_value() else float(number)
            remark = validator_remarks.get(key, "")
            if not isinstance(remark, str) or len(remark) > 2000:
                raise ValueError(f"{item['criterion']} remarks must be at most 2,000 characters.")
            clean_remarks[key] = remark.strip()
            try:
                weight = Decimal(str(item["weight"]))
            except (InvalidOperation, ValueError, TypeError):
                raise ValueError(f"{item['criterion']} has an invalid saved weight.")
            if not weight.is_finite() or not 0 <= weight <= 100:
                raise ValueError(f"{item['criterion']} has an invalid saved weight.")
            totals[group] += weighted_points(number, weight)
    current_formula = suggested.get("score_total_version") == SCORE_TOTAL_VERSION
    score = overall_score(
        totals["pap"], totals["rdp"], totals["regional"],
        include_regional=current_formula and regional.get("applicable"),
    )
    regional_score = bounded_score(totals["regional"])
    rules = priority_rule_config(analysis.rule_set)["thresholds"]
    form = analysis.input_snapshot.get("simplified_form") if isinstance(analysis.input_snapshot, dict) else {}
    funding = (
        Decimal(regional_eligibility(analysis.input_snapshot, rules)["total"])
        if current_formula else _money_total((form or {}).get("fundingRequirementByYear"))
    )
    incomplete = analysis.suggested_priority == "incomplete" or bool(suggested.get("missing_facts"))
    priority = _priority_with_regional_budget(float(score), rules, funding, incomplete)
    return clean_scores, clean_remarks, score, regional_score, priority


def save_evaluation(analysis, validator, adjusted_scores, validator_remarks):
    scores, remarks, score, regional_score, priority = calculate_evaluation(
        analysis, adjusted_scores, validator_remarks
    )
    evaluation, _ = ProjectPriorityEvaluation.objects.update_or_create(
        analysis=analysis,
        defaults={
            "validator": validator,
            "adjusted_scores": scores,
            "validator_remarks": remarks,
            "effective_score": score,
            "regional_effective_score": regional_score,
            "calculated_priority": priority,
        },
    )
    return evaluation
