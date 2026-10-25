from copy import deepcopy

from django.db import migrations
from django.db.models import Max


DOCUMENT_FIELD = {
    "key": "custom_supporting_documents",
    "label": "Supporting Documents",
    "type": "document_upload",
    "required": True,
    "visible": True,
    "protected": False,
    "help_text": "Required formats: PDF, DOCX, XLSX, CSV, PNG, or JPEG. Files are checked for project relevance and sufficiency.",
    "allowed_extensions": ["pdf", "docx", "xlsx", "csv", "png", "jpg", "jpeg"],
    "min_files": 1,
    "max_files": 10,
    "max_file_bytes": 20 * 1024 * 1024,
    "ai_sufficiency_instructions": "The documents should substantiate the stated project scope, objectives, budget, readiness, intended beneficiaries, or expected outcomes.",
}


def seed_supporting_documents(apps, schema_editor):
    Form = apps.get_model("cms", "CMSContributorForm")
    Version = apps.get_model("cms", "CMSContributorFormVersion")
    alias = schema_editor.connection.alias
    form = Form.objects.using(alias).filter(key="simplified-rdip").first()
    if not form:
        return
    def without_document_uploads(value):
        result = deepcopy(value) if isinstance(value, dict) else {"schema_version": 1, "sections": []}
        cleaned_sections = []
        for section in result.get("sections", []):
            if not isinstance(section, dict):
                continue
            section["fields"] = [
                field for field in section.get("fields", [])
                if not isinstance(field, dict) or field.get("type") != "document_upload"
            ]
            if section["fields"] or section.get("admin_only"):
                cleaned_sections.append(section)
        result["sections"] = cleaned_sections
        return result

    # Migration 0006 historically imported the live Python default. Normalize
    # fresh installations so version 1 remains the immutable pre-upload schema.
    for historical in Version.objects.using(alias).filter(form_id=form.pk):
        cleaned = without_document_uploads(historical.schema_json)
        if cleaned != historical.schema_json:
            Version.objects.using(alias).filter(pk=historical.pk).update(schema_json=cleaned)
    source = without_document_uploads(
        form.current_published_version.schema_json if form.current_published_version_id else form.draft_schema_json
    )
    schema = deepcopy(source)
    sections = schema.setdefault("sections", [])
    section = {
        "key": "supporting_documents",
        "title": "Supporting Documents",
        "description": "Upload evidence that supports the project information and readiness described above.",
        "visible": True,
        "fields": [deepcopy(DOCUMENT_FIELD)],
    }
    insert_at = next((index for index, item in enumerate(sections) if isinstance(item, dict) and item.get("key") == "priority_analysis"), len(sections))
    sections.insert(insert_at, section)
    next_number = (Version.objects.using(alias).filter(form_id=form.pk).aggregate(value=Max("version_number"))["value"] or 0) + 1
    version = Version.objects.using(alias).create(form_id=form.pk, version_number=next_number, schema_json=schema)
    Form.objects.using(alias).filter(pk=form.pk).update(
        draft_schema_json=schema,
        current_published_version_id=version.pk,
        status="published",
        has_unpublished_changes=False,
        published_at=version.published_at,
    )


class Migration(migrations.Migration):
    dependencies = [("cms", "0009_unified_page_workflow_remove_chatbot_setting")]
    operations = [migrations.RunPython(seed_supporting_documents, migrations.RunPython.noop)]
