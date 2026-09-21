import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("projects", "0030_useractivity_actor_full_name_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AIModelVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.CharField(max_length=80, unique=True)),
                ("algorithm", models.CharField(default="multinomial-logistic-regression", max_length=80)),
                ("feature_schema_version", models.CharField(max_length=60)),
                ("dataset_version", models.CharField(db_index=True, max_length=64)),
                ("sample_count", models.PositiveIntegerField(default=0)),
                ("class_labels", models.JSONField(default=list)),
                ("feature_names", models.JSONField(default=list)),
                ("parameters", models.JSONField(default=dict)),
                ("metrics", models.JSONField(default=dict)),
                ("status", models.CharField(choices=[("active", "Active"), ("retired", "Retired")], db_index=True, default="active", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("trained_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="trained_ai_models", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="AITrainingRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("feature_schema_version", models.CharField(max_length=60)),
                ("feature_snapshot", models.JSONField(default=dict)),
                ("normalized_text", models.TextField(blank=True)),
                ("target_priority", models.CharField(choices=[("high", "High Priority"), ("medium", "Medium Priority"), ("low", "Low Priority")], max_length=20)),
                ("source_hash", models.CharField(db_index=True, max_length=64)),
                ("is_eligible", models.BooleanField(db_index=True, default=True)),
                ("exclusion_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("confirmation", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="ai_training_record", to="projects.projectpriorityconfirmation")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ai_training_records", to="projects.project")),
                ("rule_set", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ai_training_records", to="projects.priorityruleset")),
            ],
            options={"ordering": ["-confirmation__created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="AIProjectAnalysis",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inference_version", models.CharField(max_length=80)),
                ("feature_schema_version", models.CharField(max_length=60)),
                ("feature_snapshot", models.JSONField(default=dict)),
                ("status", models.CharField(choices=[("untrained", "No trained model"), ("insufficient_evidence", "Required evidence is incomplete"), ("ready", "Prediction available")], max_length=30)),
                ("predicted_priority", models.CharField(blank=True, max_length=20)),
                ("confidence", models.FloatField(default=0)),
                ("class_probabilities", models.JSONField(default=dict)),
                ("explanation", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("guideline_rule_set", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ai_project_analyses", to="projects.priorityruleset")),
                ("model_version", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="project_analyses", to="ai_engine.aimodelversion")),
                ("priority_analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="learning_assessments", to="projects.projectpriorityanalysis")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="AIModelTrainingRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("split", models.CharField(choices=[("train", "Training"), ("test", "Held-out test")], default="train", max_length=10)),
                ("model_version", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="dataset_memberships", to="ai_engine.aimodelversion")),
                ("training_record", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="model_memberships", to="ai_engine.aitrainingrecord")),
            ],
        ),
        migrations.CreateModel(
            name="AISimilarProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rank", models.PositiveSmallIntegerField()),
                ("similarity_score", models.FloatField(default=0)),
                ("shared_features", models.JSONField(default=list)),
                ("analysis", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="similar_projects", to="ai_engine.aiprojectanalysis")),
                ("training_record", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="similarity_matches", to="ai_engine.aitrainingrecord")),
            ],
            options={"ordering": ["rank"]},
        ),
        migrations.AddConstraint(
            model_name="aiprojectanalysis",
            constraint=models.UniqueConstraint(fields=("priority_analysis", "inference_version"), name="unique_ai_inference_per_analysis_version"),
        ),
        migrations.AddConstraint(
            model_name="aimodeltrainingrecord",
            constraint=models.UniqueConstraint(fields=("model_version", "training_record"), name="unique_ai_model_training_record"),
        ),
        migrations.AddConstraint(
            model_name="aisimilarproject",
            constraint=models.UniqueConstraint(fields=("analysis", "training_record"), name="unique_ai_similar_project"),
        ),
        migrations.AddConstraint(
            model_name="aisimilarproject",
            constraint=models.UniqueConstraint(fields=("analysis", "rank"), name="unique_ai_similar_project_rank"),
        ),
    ]
