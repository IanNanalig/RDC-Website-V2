from django.db import migrations, models


def backfill_workflow(apps, schema_editor):
    Project = apps.get_model("projects", "Project")
    Revision = apps.get_model("projects", "ProjectRevision")
    unresolved = []
    for project in Project.objects.all().iterator():
        profile = project.profile_data if isinstance(project.profile_data, dict) else {}
        review = profile.get("validator_review") if isinstance(profile.get("validator_review"), dict) else {}
        review_state = str(review.get("review_status") or "").lower()
        if project.validated:
            state = "validated"
        elif review_state in {"reviewed", "rejected"}:
            state = "needs_revision"
        elif project.status == "planning":
            state = "draft"
        elif project.status == "proposed":
            state = "pending_validation"
        else:
            unresolved.append(project.pk)
            continue
        Project.objects.filter(pk=project.pk).update(workflow_status=state)
    if unresolved:
        raise RuntimeError(
            "Cannot safely infer workflow status for project IDs "
            + ", ".join(map(str, unresolved[:30]))
            + ". Resolve these records before applying this migration."
        )
    state_map = {
        "draft": "draft",
        "submitted": "pending_validation",
        "validator_draft": "pending_validation",
        "reviewed": "needs_revision",
        "rejected": "needs_revision",
        "endorsed": "validated",
    }
    for old, new in state_map.items():
        Revision.objects.filter(state=old).update(workflow_status=new)


class Migration(migrations.Migration):
    dependencies = [("projects", "0056_revision_supporting_documents")]

    operations = [
        migrations.AddField(
            model_name="project",
            name="workflow_status",
            field=models.CharField(max_length=20, null=True, db_index=True),
        ),
        migrations.AddField(
            model_name="projectrevision",
            name="workflow_status",
            field=models.CharField(max_length=20, null=True, blank=True, db_index=True),
        ),
        migrations.RunPython(backfill_workflow, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="project",
            name="workflow_status",
            field=models.CharField(
                max_length=20,
                default="draft",
                db_index=True,
                choices=[
                    ("draft", "Draft"),
                    ("pending_validation", "Pending Validation"),
                    ("needs_revision", "Needs Revision"),
                    ("validated", "Validated"),
                ],
            ),
        ),
        migrations.AlterField(
            model_name="projectrevision",
            name="workflow_status",
            field=models.CharField(
                max_length=20,
                null=True,
                blank=True,
                db_index=True,
                choices=[
                    ("draft", "Draft"),
                    ("pending_validation", "Pending Validation"),
                    ("needs_revision", "Needs Revision"),
                    ("validated", "Validated"),
                ],
            ),
        ),
    ]
