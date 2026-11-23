"""Searchable, validator-endorsed references kept separately from model training."""
from collections import Counter
from datetime import timedelta
import logging
import re

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from projects.models import Project, ProjectPriorityConfirmation
from .models import HistoricalProjectReference, HistoricalReferenceTerm
from .similarity import find_similar_projects, tokenize


logger = logging.getLogger(__name__)
PRIVATE_CONTACT = re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|(?:\+?63|0)9(?:[ -]?\d){9}", re.I)
REFERENCE_TEXT_FIELDS = ("projectActivity", "projectTitle", "program", "description", "objective", "scope", "expectedOutputs", "targetBeneficiaries")
PHASE = re.compile(r"\b(?:phase|stage|package)\s+([0-9]+|[ivx]+)\b", re.I)


def _safe_text(value, limit=450):
    return PRIVATE_CONTACT.sub("[redacted]", value.strip()[:limit]) if isinstance(value, str) else ""


def _labels(value):
    items = value if isinstance(value, list) else [value]
    return sorted({_safe_text(item, 120).casefold() for item in items if _safe_text(item, 120)})


def reference_features(snapshot, sector=""):
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    form = snapshot.get("simplified_form")
    form = form if isinstance(form, dict) else snapshot
    fields = {key: _safe_text(form.get(key)) for key in REFERENCE_TEXT_FIELDS}
    title = fields["projectActivity"] or fields["projectTitle"] or fields["program"]
    phase = PHASE.search(title)
    from .features import _budget_total
    return {
        "text": " ".join(filter(None, fields.values())),
        "context": {
            "title": title, "phase": phase.group(1).casefold() if phase else "",
            "provider_text": " ".join(filter(None, (title, fields["description"], fields["objective"]))),
            "agency": _safe_text(form.get("agencyName"), 120).casefold(),
            "collaborators": _labels(form.get("collaboratingAgencies")),
            "locations": _labels(form.get("location")),
            "scope": fields["scope"] or fields["expectedOutputs"],
            "beneficiaries": fields["targetBeneficiaries"],
            "budget": _budget_total(form),
            "start": _safe_text(str(form.get("startYear") or ""), 4),
            "end": _safe_text(str(form.get("endYear") or ""), 4),
            "sector": _safe_text(sector, 60),
        },
    }


def _terms(text, limit):
    return [term for term, _ in Counter(token for token in tokenize(text) if len(token) <= 48).most_common(limit)]


def queue_historical_reference(project_id, confirmation_id, *, force=False):
    if not confirmation_id:
        return None
    with transaction.atomic():
        reference, created = HistoricalProjectReference.objects.select_for_update().get_or_create(
            project_id=project_id, defaults={"requested_confirmation_id": confirmation_id},
        )
        if not created and reference.requested_confirmation_id > confirmation_id:
            return reference
        if not created and (force or reference.requested_confirmation_id != confirmation_id):
            reference.requested_confirmation_id = confirmation_id
            reference.state = "pending"
            reference.attempts = 0
            reference.retry_after = None
            reference.last_error = ""
            reference.save(update_fields=["requested_confirmation", "state", "attempts", "retry_after", "last_error"])
        if reference.state in {"pending", "failed"}:
            transaction.on_commit(lambda: index_reference(reference.pk), robust=True)
    return reference


def _eligible(confirmation):
    analysis = confirmation.analysis
    scores = analysis.suggested_scores if isinstance(analysis.suggested_scores, dict) else {}
    return (
        confirmation.validator_id is not None
        and confirmation.final_priority in {"low", "high"}
        and analysis.suggested_priority != "incomplete" and not scores.get("missing_facts")
        and (analysis.revision_id is None or analysis.revision.state == "endorsed")
    )


@transaction.atomic
def index_reference(reference_id):
    reference = HistoricalProjectReference.objects.select_for_update().filter(pk=reference_id).first()
    if not reference or reference.state not in {"pending", "failed"}:
        return
    if reference.retry_after and reference.retry_after > timezone.now():
        return
    try:
        with transaction.atomic():
            confirmation = ProjectPriorityConfirmation.objects.select_related(
                "analysis__project", "analysis__revision", "analysis__rule_set",
            ).get(pk=reference.requested_confirmation_id)
            project = confirmation.analysis.project
            if project.pk != reference.project_id or not project.validated or project.workflow_status != Project.WORKFLOW_VALIDATED or not _eligible(confirmation):
                reference.state = "ineligible"
                reference.save(update_fields=["state"])
                return
            from .services import sync_training_record
            record = sync_training_record(confirmation)
            if not record.is_eligible:
                reference.state = "ineligible"
                reference.save(update_fields=["state"])
                return
            features = reference_features(confirmation.analysis.input_snapshot, record.feature_snapshot.get("context", {}).get("sector", ""))
            reference.terms.all().delete()
            HistoricalReferenceTerm.objects.bulk_create([
                HistoricalReferenceTerm(reference=reference, term=term) for term in _terms(features["text"], 64)
            ])
            reference.indexed_record = record
            reference.normalized_text = features["text"]
            reference.metadata = features["context"]
            reference.indexed_at = timezone.now()
            reference.state = "ready"
            reference.retry_after = None
            reference.last_error = ""
            reference.save(update_fields=["indexed_record", "normalized_text", "metadata", "indexed_at", "state", "retry_after", "last_error"])
    except Exception as exc:
        logger.exception("Historical indexing failed for reference %s", reference_id)
        reference.state = "failed"
        reference.attempts += 1
        reference.retry_after = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** min(reference.attempts, 7)))
        reference.last_error = type(exc).__name__
        reference.save(update_fields=["state", "attempts", "retry_after", "last_error"])


def retry_historical_references(limit=5):
    pending = HistoricalProjectReference.objects.filter(state__in=("pending", "failed")).filter(
        Q(retry_after__isnull=True) | Q(retry_after__lte=timezone.now()),
    ).order_by("pk").values_list("pk", flat=True)[:limit]
    for reference_id in list(pending):
        index_reference(reference_id)


def indexed_references():
    return HistoricalProjectReference.objects.filter(
        indexed_record__is_eligible=True, project__validated=True,
        project__workflow_status=Project.WORKFLOW_VALIDATED,
    )


def index_status():
    states = dict(HistoricalProjectReference.objects.values_list("state").annotate(total=Count("pk")))
    return {**states, "available": indexed_references().count()}


def find_historical_matches(snapshot, sector="", project_id=None, limit=6):
    query = reference_features(snapshot, sector)
    terms = _terms(query["text"], 24)
    if not terms:
        return []
    candidates = indexed_references().exclude(project_id=project_id).filter(terms__term__in=terms).annotate(
        matching_terms=Count("terms"),
    ).select_related("indexed_record__project", "indexed_record__confirmation__analysis__rule_set").order_by(
        "-matching_terms", "-indexed_at", "-pk",
    )[:200]
    matches = find_similar_projects(query, candidates, limit=limit)
    for match in matches:
        reference = match["record"]
        category, shared, differences = _assess_match(query["context"], reference.metadata, match["text_score"])
        match.update(record=reference.indexed_record, category=category, shared_features=shared,
                     differences=differences, reference_metadata=reference.metadata)
    return [match for match in matches if match["category"] != "unrelated"]


def _assess_match(current, previous, score):
    shared, differences = [], []
    for field, label in (("agency", "Implementing agency"), ("collaborators", "Collaborating agencies"),
                         ("locations", "Locations"), ("scope", "Scope"), ("beneficiaries", "Beneficiaries")):
        left, right = current.get(field), previous.get(field)
        if left and right:
            equal = left.casefold() == right.casefold() if isinstance(left, str) and isinstance(right, str) else left == right
            if equal:
                shared.append(label)
            else:
                differences.append(label)
    budget, previous_budget = current["budget"], previous["budget"]
    if budget and previous_budget:
        (shared if abs(budget - previous_budget) / max(budget, previous_budget) <= .15 else differences).append("Budget")
    period, previous_period = (current["start"], current["end"]), (previous["start"], previous["end"])
    if all(period) and all(previous_period):
        (shared if period == previous_period else differences).append("Implementation period")
    if score < .30:
        return "unrelated", shared, differences
    if (
        current["phase"] and previous["phase"] and current["phase"] != previous["phase"]
        and {"Locations", "Implementing agency"}.issubset(shared)
    ):
        return "possible_continuation", shared, [*differences, "Project phase"]
    if score >= .70 and {"Locations", "Implementing agency"}.issubset(shared) and not {"Locations", "Scope", "Implementation period"}.intersection(differences):
        return "potential_duplicate", shared, differences
    return "similar_project", shared, differences


def find_legacy_confirmation(project):
    """Backfill only confirmations tied to the validated, endorsed project copy."""
    from projects.priority_scoring import _confirmation_snapshot_hash
    revision = project.revisions.filter(state="endorsed", is_public_current=True).first()
    if revision is None or revision.endorsed_at is None:
        return None
    candidates = ProjectPriorityConfirmation.objects.filter(analysis__project=project).select_related("analysis__revision", "ai_training_record")
    if revision.revision_type == "initial_submission":
        candidates = candidates.filter(analysis__revision__isnull=True, created_at__lte=revision.endorsed_at)
    else:
        candidates = candidates.filter(analysis__revision=revision, created_at__lte=revision.endorsed_at)
    expected = _confirmation_snapshot_hash(revision.profile_data_snapshot)
    for confirmation in candidates.order_by("-created_at", "-pk"):
        record = getattr(confirmation, "ai_training_record", None)
        if _eligible(confirmation) and (record is None or record.is_eligible) and _confirmation_snapshot_hash(confirmation.analysis.input_snapshot) == expected:
            return confirmation.pk
    return None


def rebuild_historical_batch(after=0, limit=25, *, dry_run=False):
    projects = list(Project.objects.filter(
        pk__gt=after, validated=True, workflow_status=Project.WORKFLOW_VALIDATED,
    ).order_by("pk")[:limit + 1])
    scheduled = 0
    for project in projects[:limit]:
        existing = HistoricalProjectReference.objects.filter(project=project).values_list("requested_confirmation_id", flat=True).first()
        confirmation_id = existing or find_legacy_confirmation(project)
        if confirmation_id:
            if not dry_run:
                queue_historical_reference(project.pk, confirmation_id, force=True)
            scheduled += 1
    return {"scheduled": scheduled, "scanned": min(limit, len(projects)),
            "next": projects[limit - 1].pk if len(projects) > limit else None}
