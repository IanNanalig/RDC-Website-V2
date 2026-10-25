from copy import deepcopy

from cms.form_schema import (
    DOCUMENT_UPLOAD_EXTENSIONS,
    DOCUMENT_UPLOAD_MAX_BYTES,
    DOCUMENT_UPLOAD_MAX_FILES,
)


PROJECT_DOCUMENT_MAX_TOTAL_BYTES = 200 * 1024 * 1024


def document_policy_from_schema(schema, *, form_key="simplified-rdip", form_version=1):
    """Return the single visible document field as a bounded project policy."""
    if not isinstance(schema, dict):
        return {}
    for section in schema.get("sections") or []:
        if not isinstance(section, dict) or section.get("visible") is False or section.get("admin_only"):
            continue
        for field in section.get("fields") or []:
            if (
                not isinstance(field, dict)
                or field.get("type") != "document_upload"
                or field.get("visible") is False
            ):
                continue
            extensions = []
            for value in field.get("allowed_extensions") or []:
                value = str(value or "").strip().lower().lstrip(".")
                if value in DOCUMENT_UPLOAD_EXTENSIONS and value not in extensions:
                    extensions.append(value)
            if not extensions:
                extensions = sorted(DOCUMENT_UPLOAD_EXTENSIONS)
            max_files = min(max(int(field.get("max_files") or DOCUMENT_UPLOAD_MAX_FILES), 1), DOCUMENT_UPLOAD_MAX_FILES)
            required = bool(field.get("required"))
            min_files = min(max(int(field.get("min_files") or (1 if required else 0)), 0), max_files)
            if required:
                min_files = max(min_files, 1)
            max_file_bytes = min(
                max(int(field.get("max_file_bytes") or DOCUMENT_UPLOAD_MAX_BYTES), 1),
                DOCUMENT_UPLOAD_MAX_BYTES,
            )
            return {
                "field_key": str(field.get("key") or "custom_supporting_documents")[:120],
                "label": str(field.get("label") or "Supporting Documents")[:200],
                "help_text": str(field.get("help_text") or "")[:2000],
                "required": required,
                "min_files": min_files,
                "max_files": max_files,
                "max_file_bytes": max_file_bytes,
                "max_total_bytes": PROJECT_DOCUMENT_MAX_TOTAL_BYTES,
                "allowed_extensions": extensions,
                "ai_sufficiency_instructions": str(field.get("ai_sufficiency_instructions") or "")[:4000],
                "form_key": str(form_key or "simplified-rdip")[:120],
                "form_version": max(int(form_version or 1), 1),
            }
    return {}


def current_document_policy(form_key="simplified-rdip"):
    from cms.models import CMSContributorForm

    form = CMSContributorForm.objects.select_related("current_published_version").filter(key=form_key).first()
    if not form or not form.current_published_version:
        return {}
    version = form.current_published_version
    return document_policy_from_schema(
        version.schema_json,
        form_key=form.key,
        form_version=version.version_number,
    )


def resolve_project_document_policy(project, *, persist=False):
    existing = project.supporting_document_policy if isinstance(project.supporting_document_policy, dict) else {}
    if existing:
        return deepcopy(existing)
    profile = project.profile_data if isinstance(project.profile_data, dict) else {}
    if not isinstance(profile.get("simplified_form"), dict):
        return {}
    marker = profile.get("form_schema") if isinstance(profile.get("form_schema"), dict) else {}
    form_key = str(marker.get("key") or "simplified-rdip")
    version_number = marker.get("version")
    schema = None
    if version_number:
        from cms.models import CMSContributorFormVersion

        version = CMSContributorFormVersion.objects.filter(
            form__key=form_key,
            version_number=version_number,
        ).first()
        if version:
            schema = version.schema_json
    if schema is not None:
        policy = document_policy_from_schema(schema, form_key=form_key, form_version=version_number)
    else:
        policy = current_document_policy(form_key)
    if persist and policy:
        project.supporting_document_policy = deepcopy(policy)
        project.save(update_fields=["supporting_document_policy", "updated_at"])
    return policy


def active_project_documents(project):
    return project.supporting_documents.filter(removed_at__isnull=True)


def validate_project_documents_for_submit(project, policy=None):
    policy = policy if isinstance(policy, dict) else resolve_project_document_policy(project, persist=True)
    if not policy:
        return None
    documents = list(active_project_documents(project))
    if policy.get("required") and len(documents) < int(policy.get("min_files") or 1):
        return f"Upload at least {int(policy.get('min_files') or 1)} supporting document(s) before submitting."
    pending = [item.original_filename for item in documents if item.extraction_status in {"queued", "processing"}]
    if pending:
        return "Supporting documents are still being processed: " + ", ".join(pending[:3])
    failed = [item.original_filename for item in documents if item.extraction_status == "failed"]
    if failed:
        return "Retry or replace failed supporting documents before submitting: " + ", ".join(failed[:3])
    return None
