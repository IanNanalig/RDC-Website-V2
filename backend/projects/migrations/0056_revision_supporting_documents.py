from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("projects", "0055_priority_evaluation")]

    operations = [
        migrations.AddField(
            model_name="projectsupportingdocument",
            name="revision",
            field=models.ForeignKey(
                to="projects.projectrevision", on_delete=django.db.models.deletion.CASCADE,
                related_name="supporting_documents", null=True, blank=True,
            ),
        ),
        migrations.RemoveConstraint(
            model_name="projectsupportingdocument", name="unique_active_project_doc_hash",
        ),
        migrations.AddConstraint(
            model_name="projectsupportingdocument",
            constraint=models.UniqueConstraint(
                fields=("project", "checksum_sha256"),
                condition=models.Q(removed_at__isnull=True, revision__isnull=True),
                name="unique_active_project_doc_hash",
            ),
        ),
        migrations.AddConstraint(
            model_name="projectsupportingdocument",
            constraint=models.UniqueConstraint(
                fields=("revision", "checksum_sha256"),
                condition=models.Q(removed_at__isnull=True, revision__isnull=False),
                name="unique_active_revision_doc_hash",
            ),
        ),
    ]
