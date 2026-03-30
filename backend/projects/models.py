from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("validator", "Validator"),
        ("staff", "Staff"),
    ]
    email = models.EmailField(unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    full_name = models.CharField(max_length=200, blank=True, default="")
    agency = models.CharField(max_length=200, blank=True, default="")
    agency_head = models.CharField(max_length=200, blank=True, default="")
    office = models.CharField(max_length=200, blank=True, default="")
    division = models.CharField(max_length=200, blank=True, default="")
    position = models.CharField(max_length=200, blank=True, default="")
    contact_number = models.CharField(max_length=50, blank=True, default="")
    phone_number = models.CharField(max_length=50, blank=True, default="")
    created_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_users",
    )
    created_at = models.DateTimeField(default=timezone.now)
    last_password_change = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.username} ({self.role})"


class Project(models.Model):
    STATUS_CHOICES = [
        ("proposed", "Proposed"),
        ("planning", "Planning"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
    ]

    name = models.CharField(max_length=200)
    implementing_agency = models.CharField(max_length=100)
    municipality = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    cost = models.DecimalField(max_digits=15, decimal_places=2)
    description = models.TextField(blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField(null=True, blank=True)
    year = models.IntegerField(null=True, blank=True)
    validated = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    edit_requested = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="projects"
    )

    # Added by existing migration 0003.
    agency = models.CharField(max_length=200, null=True, blank=True)
    budget = models.IntegerField(default=0)
    completion = models.IntegerField(default=0)
    profile_data = models.JSONField(null=True, blank=True)

    @property
    def title(self):
        return self.name

    def submit_for_validation(self):
        # Keep flow simple for current schema.
        if self.status == "planning":
            self.status = "proposed"
            self.save(update_fields=["status", "updated_at"])

    def change_status(self, new_status):
        if new_status in dict(self.STATUS_CHOICES):
            self.status = new_status
            self.save(update_fields=["status", "updated_at"])

    def __str__(self):
        return self.name


class EditRequest(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="edit_requests")
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reason = models.TextField(blank=True)
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditTrail(models.Model):
    ACTION_CHOICES = [
        ("create", "create"),
        ("update", "update"),
        ("request_edit", "request_edit"),
        ("approve_edit", "approve_edit"),
        ("validate", "validate"),
        ("archive", "archive"),
        ("freeze", "freeze"),
        ("unfreeze", "unfreeze"),
    ]

    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    detail = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)


class SystemSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(null=True, blank=True)


class AccessRequest(models.Model):
    ROLE_CHOICES = [
        ("validator", "Validator"),
        ("contributor", "Contributor"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    office_unit = models.CharField(max_length=150)
    requested_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    justification = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_access_requests"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.full_name} ({self.requested_role}) - {self.status}"


class UserActivity(models.Model):
    EVENT_CHOICES = [
        ("login", "Login"),
        ("auth_reset_request", "Auth Reset Request"),
        ("auth_reset_approve", "Auth Reset Approve"),
        ("auth_reset_reject", "Auth Reset Reject"),
        ("user_create", "User Create"),
        ("project_create", "Project Create"),
        ("project_update", "Project Update"),
        ("project_submit", "Project Submit"),
        ("project_approve", "Project Approve"),
        ("project_reject", "Project Reject"),
        ("project_archive", "Project Archive"),
        ("validator_draft", "Validator Draft"),
        ("validator_reviewed", "Validator Reviewed"),
        ("validator_endorsed", "Validator Endorsed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="activities")
    role = models.CharField(max_length=20, blank=True)
    event = models.CharField(max_length=40, choices=EVENT_CHOICES)
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.CharField(max_length=64, blank=True)
    location_hint = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} {self.event} {self.created_at.isoformat()}"


class PasswordSetupToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_setup_tokens")
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def is_valid(self):
        if self.used_at:
            return False
        return timezone.now() <= self.expires_at


class PasswordResetRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    email = models.EmailField()
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="password_reset_requests")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    requested_ip = models.CharField(max_length=64, blank=True)
    requested_user_agent = models.CharField(max_length=255, blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_password_resets"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} - {self.status}"


class PublicContent(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("tl", "Tagalog"),
    ]

    slug = models.CharField(max_length=150)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    url = models.CharField(max_length=200, blank=True)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default="en")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("slug", "language")
        ordering = ["slug", "language"]

    def __str__(self):
        return f"{self.slug} ({self.language})"


class PublicChatFAQ(models.Model):
    question_normalized = models.CharField(max_length=255, unique=True)
    question_sample = models.CharField(max_length=255, blank=True)
    count = models.IntegerField(default=1)
    last_asked = models.DateTimeField(default=timezone.now)
    last_matched_content = models.ForeignKey(
        PublicContent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="faq_matches",
    )

    class Meta:
        ordering = ["-count", "-last_asked"]

    def __str__(self):
        return f"{self.question_normalized} ({self.count})"
