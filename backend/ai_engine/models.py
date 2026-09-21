from django.conf import settings
from django.db import models


class AITrainingRecord(models.Model):
    TARGET_CHOICES = [
        ("high", "High Priority"),
        ("low", "Low Priority"),
    ]

    confirmation = models.OneToOneField(
        "projects.ProjectPriorityConfirmation",
        on_delete=models.CASCADE,
        related_name="ai_training_record",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="ai_training_records",
    )
    rule_set = models.ForeignKey(
        "projects.PriorityRuleSet",
        on_delete=models.PROTECT,
        related_name="ai_training_records",
    )
    feature_schema_version = models.CharField(max_length=60)
    feature_snapshot = models.JSONField(default=dict)
    normalized_text = models.TextField(blank=True)
    target_priority = models.CharField(max_length=20, choices=TARGET_CHOICES)
    source_hash = models.CharField(max_length=64, db_index=True)
    is_eligible = models.BooleanField(default=True, db_index=True)
    exclusion_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-confirmation__created_at", "-id"]

    def __str__(self):
        return f"Training record {self.pk}: {self.project_id} -> {self.target_priority}"


class AIModelVersion(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("retired", "Retired"),
    ]

    version = models.CharField(max_length=80, unique=True)
    algorithm = models.CharField(max_length=80, default="multinomial-logistic-regression")
    feature_schema_version = models.CharField(max_length=60)
    dataset_version = models.CharField(max_length=64, db_index=True)
    sample_count = models.PositiveIntegerField(default=0)
    class_labels = models.JSONField(default=list)
    feature_names = models.JSONField(default=list)
    parameters = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active", db_index=True)
    trained_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trained_ai_models",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.version} ({self.status})"


class AIModelTrainingRecord(models.Model):
    SPLIT_CHOICES = [("train", "Training"), ("test", "Held-out test")]

    model_version = models.ForeignKey(
        AIModelVersion,
        on_delete=models.CASCADE,
        related_name="dataset_memberships",
    )
    training_record = models.ForeignKey(
        AITrainingRecord,
        on_delete=models.PROTECT,
        related_name="model_memberships",
    )
    split = models.CharField(max_length=10, choices=SPLIT_CHOICES, default="train")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["model_version", "training_record"],
                name="unique_ai_model_training_record",
            )
        ]


class AIProjectAnalysis(models.Model):
    STATUS_CHOICES = [
        ("untrained", "No trained model"),
        ("insufficient_evidence", "Required evidence is incomplete"),
        ("ready", "Prediction available"),
    ]

    priority_analysis = models.ForeignKey(
        "projects.ProjectPriorityAnalysis",
        on_delete=models.CASCADE,
        related_name="learning_assessments",
    )
    guideline_rule_set = models.ForeignKey(
        "projects.PriorityRuleSet",
        on_delete=models.PROTECT,
        related_name="ai_project_analyses",
    )
    model_version = models.ForeignKey(
        AIModelVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="project_analyses",
    )
    inference_version = models.CharField(max_length=80)
    feature_schema_version = models.CharField(max_length=60)
    feature_snapshot = models.JSONField(default=dict)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES)
    predicted_priority = models.CharField(max_length=20, blank=True)
    confidence = models.FloatField(default=0)
    class_probabilities = models.JSONField(default=dict)
    explanation = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["priority_analysis", "inference_version"],
                name="unique_ai_inference_per_analysis_version",
            )
        ]

    def __str__(self):
        return f"AI assessment {self.priority_analysis_id} ({self.inference_version})"


class AISimilarProject(models.Model):
    analysis = models.ForeignKey(
        AIProjectAnalysis,
        on_delete=models.CASCADE,
        related_name="similar_projects",
    )
    training_record = models.ForeignKey(
        AITrainingRecord,
        on_delete=models.PROTECT,
        related_name="similarity_matches",
    )
    rank = models.PositiveSmallIntegerField()
    similarity_score = models.FloatField(default=0)
    shared_features = models.JSONField(default=list)

    class Meta:
        ordering = ["rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["analysis", "training_record"],
                name="unique_ai_similar_project",
            ),
            models.UniqueConstraint(
                fields=["analysis", "rank"],
                name="unique_ai_similar_project_rank",
            ),
        ]
