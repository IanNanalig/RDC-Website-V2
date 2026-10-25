from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("projects", "0041_supporting_documents")]

    operations = [
        migrations.AddConstraint(
            model_name="projectsupportingdocument",
            constraint=models.UniqueConstraint(
                condition=models.Q(removed_at__isnull=True),
                fields=("project", "checksum_sha256"),
                name="unique_active_project_doc_hash",
            ),
        ),
    ]
