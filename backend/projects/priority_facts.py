"""Current Validator inputs, scoped to a project or a progress revision."""

import re

from django.db import transaction

from .models import Project, ProjectPriorityFacts, ProjectRevision
from .priority_scoring import GAD, READINESS, REGIONAL_SPATIAL_LABELS, _fact_key


CHOICES = {
    "readinessLevel": READINESS,
    "gadResponsiveness": GAD,
    "spatialCoverageScope": {"specific_lgus", "region_wide", "interregional", "none"},
    "sceeedTrack": {"economic", "environment"},
    "regionalSpatialCategory": REGIONAL_SPATIAL_LABELS,
}
COUNTS = ("beneficiaryCount", "contributedOutcomeCount")
FACT_KEYS = (*CHOICES, *COUNTS, "readinessNotes")


class StalePriorityFacts(ValueError):
    pass


def priority_facts_state(project, revision=None, *, latest=None):
    state = ProjectPriorityFacts.objects.filter(project=project, revision=revision).first()
    if state is not None:
        return state
    if latest is None:
        latest = project.priority_analyses.filter(revision=revision).first()
    source = latest.supplements if latest and isinstance(latest.supplements, dict) else {}
    values = {key: source[key] for key in FACT_KEYS if key in source}
    for key, options in CHOICES.items():
        if key in values:
            canonical = _fact_key(values[key])
            if canonical in options:
                values[key] = canonical
    return ProjectPriorityFacts(project=project, revision=revision, values=values)


def lock_priority_scope(project, revision):
    locked_project = Project.objects.select_for_update().get(pk=project.pk)
    return ProjectRevision.objects.select_for_update().get(pk=revision.pk) if revision else locked_project


@transaction.atomic
def save_priority_facts(project, revision, validator, incoming, expected_version, applicable):
    scope = lock_priority_scope(project, revision)
    if scope.workflow_status != Project.WORKFLOW_PENDING:
        raise StalePriorityFacts("Priority decisions are locked after endorsement.")
    state = priority_facts_state(project, revision)
    if expected_version is not None and expected_version != state.version:
        raise StalePriorityFacts("Validator facts changed in another request. Reload the project and retry.")
    if not isinstance(incoming, dict):
        raise ValueError("Validator facts must be an object.")
    values = dict(state.values)
    for key in FACT_KEYS:
        if key not in incoming or (not applicable and key in (*COUNTS, "regionalSpatialCategory")):
            continue
        value = incoming[key]
        if isinstance(value, bool) or not isinstance(value, (str, int, type(None))):
            raise ValueError(f"Invalid Validator fact: {key}.")
        value = "" if value is None else str(value).strip()
        if key in CHOICES and value:
            value = _fact_key(value)
            if value not in CHOICES[key]:
                raise ValueError(f"Invalid Validator selection: {key}.")
        if key in COUNTS and value:
            value = value.replace(",", "")
            if not re.fullmatch(r"[0-9]{1,12}", value):
                raise ValueError(f"{key} must be a nonnegative whole number.")
            value = str(int(value))
        if key == "readinessNotes" and len(value) > 2000:
            raise ValueError("Readiness Evidence Notes must be at most 2,000 characters.")
        if value or key in values:
            values[key] = value
    changed_keys = sorted(key for key, value in values.items() if value != state.values.get(key))
    if changed_keys:
        state.version += 1
        state.values = values
    if not state.pk or changed_keys:
        state.updated_by = validator
        state.save()
    return state, changed_keys
