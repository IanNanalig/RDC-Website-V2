from copy import deepcopy

from django.db import transaction

from cms.form_schema import (
    FormSchemaError,
    build_form_migration_plan,
    schema_fields,
    validate_simplified_answers,
)
from cms.models import CMSContributorForm, CMSContributorFormVersion
from projects.models import Project, ProjectRevision
from projects.public_summary import build_public_summary
from projects.utils import derive_ncr_lgus


ACTIVE_REVISION_STATES = ("draft", "submitted", "validator_draft", "reviewed")


def saved_form_marker(profile_data):
    if not isinstance(profile_data, dict) or not isinstance(profile_data.get("simplified_form"), dict):
        return None
    marker = profile_data.get("form_schema") if isinstance(profile_data.get("form_schema"), dict) else {}
    key = str(marker.get("key") or "simplified-rdip").strip() or "simplified-rdip"
    try:
        version = max(1, int(marker.get("version") or 1))
    except (TypeError, ValueError):
        version = 1
    return key, version


def _field_value(simplified, key):
    if key.startswith("custom_"):
        custom = simplified.get("custom_fields")
        return custom.get(key) if isinstance(custom, dict) else None
    if key.startswith("priorityAnalysisFacts."):
        facts = simplified.get("priorityAnalysisFacts")
        return facts.get(key.split(".", 1)[1]) if isinstance(facts, dict) else None
    return simplified.get(key)


def _is_empty(value):
    return value is None or value == "" or (isinstance(value, (list, dict)) and not value)


def _target_version(profile_data, version_cache=None):
    marker = saved_form_marker(profile_data)
    if marker is None:
        return None, None, "Only simplified contributor-form projects can be migrated."
    key, source_number = marker
    cache_key = (key, source_number)
    if version_cache is not None and cache_key in version_cache:
        return version_cache[cache_key]
    form_cache_key = ("form", key)
    if version_cache is not None and form_cache_key in version_cache:
        form = version_cache[form_cache_key]
    else:
        form = CMSContributorForm.objects.select_related("current_published_version").filter(key=key).first()
        if version_cache is not None:
            version_cache[form_cache_key] = form
    if not form or not form.current_published_version:
        result = (None, None, "No published contributor form is available.")
    else:
        source = CMSContributorFormVersion.objects.filter(form=form, version_number=source_number).first()
        result = (
            (source, form.current_published_version, "")
            if source is not None
            else (None, None, f"Contributor form version {source_number} is unavailable.")
        )
    if version_cache is not None:
        version_cache[cache_key] = result
    return result


def _normalize_location(profile_data, target_schema):
    location_field = next(
        (
            field for field in schema_fields(target_schema)
            if field.get("key") == "location" and field.get("type") == "multiselect_dropdown"
        ),
        None,
    )
    if location_field is None:
        return profile_data, ""
    simplified = profile_data.get("simplified_form")
    if not isinstance(simplified, dict):
        return profile_data, "The project has no simplified-form answers."
    allowed = {
        str(option.get("value")): str(option.get("label") or option.get("value"))
        for option in location_field.get("options", []) if isinstance(option, dict) and option.get("value")
    }
    raw = simplified.get("location")
    if isinstance(raw, list):
        selected = [str(item).strip() for item in raw if str(item).strip()]
    else:
        text = str(raw or "").strip()
        lookup = {
            str(candidate).strip().casefold(): value
            for value, label in allowed.items()
            for candidate in (value, label)
        }
        direct = lookup.get(text.casefold()) if text else None
        selected = [direct] if direct else [item for item in derive_ncr_lgus(text) if item in allowed]
    unsupported = [item for item in selected if item not in allowed]
    if raw and (not selected or unsupported):
        return profile_data, "The saved location cannot be matched safely to the latest location choices."
    migrated = deepcopy(profile_data)
    migrated["simplified_form"]["location"] = selected
    return migrated, ""


def analyze_profile_migration(profile_data, *, version_cache=None):
    source, target, error = _target_version(profile_data, version_cache=version_cache)
    if error:
        return {"compatible": False, "issues": [error]}
    if source.version_number >= target.version_number:
        return {
            "compatible": True,
            "already_current": True,
            "source_version": source.version_number,
            "target_version": target.version_number,
            "profile_data": deepcopy(profile_data),
            "attention_fields": [],
            "issues": [],
        }

    plan = target.migration_plan_json if target.based_on_version_id == source.id else None
    if not isinstance(plan, dict) or not isinstance(plan.get("rules"), list):
        plan = build_form_migration_plan(source.schema_json, target.schema_json)
    simplified = profile_data.get("simplified_form")
    if not isinstance(simplified, dict):
        return {"compatible": False, "issues": ["The project has no simplified-form answers."]}

    issues = []
    for rule in plan.get("rules", []):
        if not isinstance(rule, dict):
            continue
        key = str(rule.get("field") or "")
        value = _field_value(simplified, key)
        if rule.get("action") == "unsupported":
            issues.append(str(rule.get("reason") or f"{key} cannot be migrated safely."))
        removed = {str(item) for item in rule.get("removed_option_values", [])}
        selected = value if isinstance(value, list) else [value]
        invalid_selected = [str(item) for item in selected if not _is_empty(item) and str(item) in removed]
        if invalid_selected:
            issues.append(f"{key} uses choices removed from the latest form: {', '.join(invalid_selected)}.")
    if issues:
        return {
            "compatible": False,
            "source_version": source.version_number,
            "target_version": target.version_number,
            "issues": issues,
        }

    migrated = deepcopy(profile_data)
    migrated, location_error = _normalize_location(migrated, target.schema_json)
    if location_error:
        return {
            "compatible": False,
            "source_version": source.version_number,
            "target_version": target.version_number,
            "issues": [location_error],
        }
    migrated["form_schema"] = {"key": target.form.key, "version": target.version_number}
    attention = []
    for field in schema_fields(target.schema_json):
        if field.get("type") == "document_upload" or field.get("visible") is False:
            continue
        if (field.get("required") or field.get("condition_required")) and _is_empty(
            _field_value(migrated["simplified_form"], str(field.get("key") or ""))
        ):
            attention.append(str(field.get("key") or ""))
    try:
        validate_simplified_answers(migrated, require_complete=False, schema_version=target)
    except FormSchemaError as exc:
        return {
            "compatible": False,
            "source_version": source.version_number,
            "target_version": target.version_number,
            "issues": [str(exc)],
        }
    return {
        "compatible": True,
        "already_current": False,
        "source_version": source.version_number,
        "target_version": target.version_number,
        "profile_data": migrated,
        "attention_fields": sorted(set(attention)),
        "issues": [],
    }


def migration_eligibility(project):
    if project.archived or not project.is_active:
        return False, "Archived projects must be restored before migration."
    profile = project.profile_data if isinstance(project.profile_data, dict) else {}
    simplified = profile.get("simplified_form") if isinstance(profile.get("simplified_form"), dict) else {}
    if str(simplified.get("status") or "").strip().casefold() == "completed":
        return False, "Implementation-completed projects are read-only."
    if project.status == "proposed":
        return False, "Projects in validation or correction cannot be migrated."
    active = project.revisions.filter(revision_type="progress_update", state__in=ACTIVE_REVISION_STATES).first()
    if active and active.state != "draft":
        return False, "A progress update is already in review."
    if project.status != "planning" and not project.validated:
        return False, "The project has not passed validation."
    return True, ""


def prepare_project_migration(project, *, user, trigger):
    """Migrate a draft in place or prepare a non-public revision for a validated project."""
    with transaction.atomic():
        project = Project.objects.select_for_update().get(pk=project.pk)
        eligible, reason = migration_eligibility(project)
        if not eligible:
            return {"status": "skipped", "project": project, "reason": reason}
        active = (
            ProjectRevision.objects.select_for_update()
            .filter(project=project, revision_type="progress_update", state="draft")
            .order_by("-updated_at")
            .first()
        )
        source_profile = active.profile_data_snapshot if active else project.profile_data
        result = analyze_profile_migration(source_profile)
        if not result.get("compatible"):
            return {"status": "blocked", "project": project, **result}
        if result.get("already_current"):
            return {"status": "current", "project": project, "revision": active, **result}
        metadata = {
            "source_version": result["source_version"],
            "target_version": result["target_version"],
            "trigger": trigger,
            "warnings": result.get("issues", []),
            "attention_fields": result.get("attention_fields", []),
        }
        if project.status == "planning":
            project.profile_data = result["profile_data"]
            project.save(update_fields=["profile_data", "updated_at"])
            return {"status": "migrated", "project": project, "revision": None, "form_migration": metadata, **result}
        if active is None:
            last_number = project.revisions.order_by("-revision_number").values_list("revision_number", flat=True).first() or 0
            active = ProjectRevision.objects.create(
                project=project,
                revision_number=last_number + 1,
                revision_type="progress_update",
                state="draft",
                profile_data_snapshot=result["profile_data"],
                public_summary_snapshot=build_public_summary(result["profile_data"].get("simplified_form", {})),
                changed_fields=[],
                form_migration=metadata,
                created_by=user,
            )
        else:
            active.profile_data_snapshot = result["profile_data"]
            active.public_summary_snapshot = build_public_summary(result["profile_data"].get("simplified_form", {}))
            active.form_migration = metadata
            active.save(update_fields=["profile_data_snapshot", "public_summary_snapshot", "form_migration", "updated_at"])
        return {"status": "prepared", "project": project, "revision": active, "form_migration": metadata, **result}
