from django.db import migrations, models
import django.db.models.deletion


def migration_plan(previous_schema, next_schema):
    def fields(schema):
        return {
            str(field.get("key")): field
            for section in (schema or {}).get("sections", [])
            if isinstance(section, dict)
            for field in section.get("fields", [])
            if isinstance(field, dict) and field.get("key")
        }

    old_fields = fields(previous_schema)
    new_fields = fields(next_schema)
    rules = []
    incompatible = []
    attention = []
    for key, target in new_fields.items():
        source = old_fields.get(key)
        if source is None:
            required = bool(target.get("required"))
            rules.append({"field": key, "action": "add", "required": required})
            if required and target.get("visible") is not False:
                attention.append(key)
            continue
        source_type = str(source.get("type") or "")
        target_type = str(target.get("type") or "")
        if source_type != target_type:
            if key == "location" and target_type == "multiselect_dropdown":
                rules.append({"field": key, "action": "transform_location", "from": source_type, "to": target_type})
            else:
                item = {"field": key, "reason": f"Field type changed from {source_type} to {target_type}."}
                incompatible.append(item)
                rules.append({"field": key, "action": "unsupported", **item})
            continue
        removed_values = []
        if target_type in {"select", "multiselect", "multiselect_dropdown"}:
            old_values = {str(item.get("value")) for item in source.get("options", []) if isinstance(item, dict)}
            new_values = {str(item.get("value")) for item in target.get("options", []) if isinstance(item, dict)}
            removed_values = sorted(old_values - new_values)
        rules.append({"field": key, "action": "copy", "removed_option_values": removed_values})
    for key, source in old_fields.items():
        if key not in new_fields:
            rules.append({"field": key, "action": "retain_hidden", "source_type": source.get("type")})
    return {"format": 1, "rules": rules, "attention_fields": attention, "incompatible_changes": incompatible}


def link_existing_versions(apps, schema_editor):
    Version = apps.get_model("cms", "CMSContributorFormVersion")
    for form_id in Version.objects.values_list("form_id", flat=True).distinct():
        previous = None
        for version in Version.objects.filter(form_id=form_id).order_by("version_number", "id"):
            if previous is not None:
                version.based_on_version_id = previous.id
                version.migration_plan_json = migration_plan(previous.schema_json, version.schema_json)
                version.save(update_fields=["based_on_version", "migration_plan_json"])
            previous = version


class Migration(migrations.Migration):

    # PostgreSQL defers the self-referencing foreign-key index until the schema
    # editor exits. Existing-version updates below can leave trigger events
    # pending, so the schema and data operations must commit independently.
    atomic = False

    dependencies = [
        ("cms", "0013_repair_legacy_location_versions"),
    ]

    operations = [
        migrations.AddField(
            model_name="cmscontributorformversion",
            name="based_on_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="derived_versions", to="cms.cmscontributorformversion"),
        ),
        migrations.AddField(
            model_name="cmscontributorformversion",
            name="migration_plan_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(link_existing_versions, migrations.RunPython.noop),
    ]
