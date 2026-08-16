from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("validator", "Validator"),
        ("staff", "Staff"),
        ("content_editor", "Content Editor"),
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
    session_version = models.PositiveIntegerField(default=0)
    last_session_at = models.DateTimeField(null=True, blank=True)
    last_session_ip = models.CharField(max_length=64, blank=True, default="")
    last_session_user_agent = models.TextField(blank=True, default="")

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
    budget = models.BigIntegerField(default=0)
    completion = models.IntegerField(default=0)
    profile_data = models.JSONField(null=True, blank=True)
    priority_analysis_eligible = models.BooleanField(default=True)

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


class ProjectRevision(models.Model):
    REVISION_TYPE_CHOICES = [
        ("initial_submission", "Initial Submission"),
        ("progress_update", "Progress Update"),
    ]
    STATE_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("validator_draft", "Validator Draft"),
        ("reviewed", "Reviewed"),
        ("endorsed", "Endorsed"),
        ("rejected", "Rejected"),
        ("superseded", "Superseded"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="revisions")
    revision_number = models.PositiveIntegerField()
    revision_type = models.CharField(max_length=30, choices=REVISION_TYPE_CHOICES)
    state = models.CharField(max_length=30, choices=STATE_CHOICES, default="draft")
    profile_data_snapshot = models.JSONField(default=dict, blank=True)
    public_summary_snapshot = models.JSONField(default=dict, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    public_note = models.TextField(blank=True)
    is_public_current = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_project_revisions"
    )
    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_project_revisions"
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_project_revisions"
    )
    endorsed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="endorsed_project_revisions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    endorsed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "revision_number"],
                name="unique_project_revision_number",
            )
        ]

    def __str__(self):
        return f"{self.project_id} v{self.revision_number} {self.state}"


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
        ("project_comment", "Project Comment"),
        ("validator_draft", "Validator Draft"),
        ("validator_reviewed", "Validator Reviewed"),
        ("validator_endorsed", "Validator Endorsed"),
        ("priority_analysis_run", "Priority Analysis Run"),
        ("priority_analysis_reused", "Priority Analysis Reused"),
        ("priority_analysis_confirmed", "Priority Analysis Confirmed"),
        ("priority_analysis_overridden", "Priority Analysis Overridden"),
        ("public_summary_overridden", "Public Summary Overridden"),
        ("encoding_window_updated", "Encoding Window Updated"),
        ("progress_window_updated", "Progress Update Window Updated"),
        ("project_revision_created", "Project Revision Created"),
        ("project_revision_updated", "Project Revision Updated"),
        ("project_revision_submitted", "Project Revision Submitted"),
        ("project_revision_reviewed", "Project Revision Reviewed"),
        ("project_revision_endorsed", "Project Revision Endorsed"),
        ("project_revision_rejected", "Project Revision Rejected"),
        ("cms_event_created", "CMS Event Created"),
        ("cms_event_updated", "CMS Event Updated"),
        ("cms_event_submitted", "CMS Event Submitted"),
        ("cms_event_published", "CMS Event Published"),
        ("cms_event_rejected", "CMS Event Rejected"),
        ("cms_event_archived", "CMS Event Archived"),
        ("cms_content_created", "CMS Content Created"),
        ("cms_content_updated", "CMS Content Updated"),
        ("cms_content_submitted", "CMS Content Submitted"),
        ("cms_content_published", "CMS Content Published"),
        ("cms_content_rejected", "CMS Content Rejected"),
        ("cms_content_archived", "CMS Content Archived"),
        ("chat_knowledge_approved", "Chat Knowledge Approved"),
        ("chat_knowledge_rejected", "Chat Knowledge Rejected"),
        ("chat_content_updated", "Chat Content Updated"),
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


class ProjectComment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="project_comments")
    role = models.CharField(max_length=20, blank=True)
    agency = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project_id} {self.user.username} {self.created_at.isoformat()}"


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_notifications"
    )
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications")
    comment = models.ForeignKey(
        ProjectComment, on_delete=models.SET_NULL, null=True, blank=True, related_name="notifications"
    )
    event_type = models.CharField(max_length=60)
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    link_path = models.CharField(max_length=255, blank=True)
    dedupe_key = models.CharField(max_length=160, unique=True, null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "read_at", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient_id} {self.event_type} {self.created_at.isoformat()}"


class PriorityRuleSet(models.Model):
    version = models.CharField(max_length=40, unique=True)
    algorithm_version = models.CharField(max_length=40, default="expert-v1")
    is_active = models.BooleanField(default=False)
    thresholds = models.JSONField(default=dict, blank=True)
    sector_criteria = models.JSONField(default=dict, blank=True)
    keyword_dictionaries = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.version} ({self.algorithm_version})"


class ProjectPriorityAnalysis(models.Model):
    PRIORITY_CHOICES = [
        ("high", "High Priority"),
        ("medium", "Medium Priority"),
        ("low", "Low Priority"),
        ("incomplete", "Incomplete"),
    ]

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="priority_analyses")
    validator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="priority_analyses")
    rule_set = models.ForeignKey(PriorityRuleSet, on_delete=models.PROTECT, related_name="analyses")
    source_hash = models.CharField(max_length=64, db_index=True)
    input_snapshot = models.JSONField(default=dict)
    supplements = models.JSONField(default=dict, blank=True)
    suggested_scores = models.JSONField(default=dict)
    regional_scorecard = models.JSONField(default=dict, blank=True)
    flags = models.JSONField(default=dict, blank=True)
    summary = models.TextField(blank=True)
    suggested_priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    base_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "rule_set", "source_hash"],
                name="unique_project_priority_analysis_snapshot",
            ),
        ]

    def __str__(self):
        return f"{self.project_id} {self.suggested_priority} {self.base_score}"


class ProjectPriorityConfirmation(models.Model):
    PRIORITY_CHOICES = [
        ("high", "High Priority"),
        ("medium", "Medium Priority"),
        ("low", "Low Priority"),
    ]

    analysis = models.ForeignKey(ProjectPriorityAnalysis, on_delete=models.CASCADE, related_name="confirmations")
    validator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="priority_confirmations")
    adjusted_scores = models.JSONField(default=dict, blank=True)
    final_priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES)
    override_rationale = models.TextField(blank=True)
    confirmed_flags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.analysis_id} {self.final_priority}"


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


class PublicEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ("meeting", "Meeting"),
        ("forum", "Forum"),
        ("consultation", "Consultation"),
        ("deadline", "Deadline"),
        ("summit", "Summit"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted for Review"),
        ("published", "Published"),
        ("rejected", "Rejected"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=30, choices=EVENT_TYPE_CHOICES, default="meeting")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    is_virtual = models.BooleanField(default=False)
    meeting_link = models.URLField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")
    review_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_public_events"
    )
    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_public_events"
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_public_events"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_at", "title"]

    def __str__(self):
        return f"{self.title} ({self.status})"


class PublicPageContent(models.Model):
    PAGE_CHOICES = [
        ("home", "Home"),
        ("about_rdc", "About RDC"),
        ("region_profile", "Region Profile"),
        ("publications", "Publications"),
        ("news", "News"),
        ("projects_dashboard", "Projects Dashboard"),
        ("contact", "Contact Us"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted for Review"),
        ("published", "Published"),
        ("rejected", "Rejected"),
        ("archived", "Archived"),
    ]

    page = models.CharField(max_length=50, choices=PAGE_CHOICES)
    section_key = models.CharField(max_length=80)
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=250, blank=True)
    body = models.TextField(blank=True)
    image_url = models.CharField(max_length=500, blank=True)
    cta_label = models.CharField(max_length=120, blank=True)
    cta_url = models.CharField(max_length=250, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")
    review_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_public_page_content"
    )
    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="submitted_public_page_content"
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_public_page_content"
    )
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page", "section_key", "-updated_at"]
        indexes = [
            models.Index(fields=["page", "section_key", "status"]),
        ]

    def __str__(self):
        return f"{self.get_page_display()} / {self.section_key} ({self.status})"


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


class PublicChatInteraction(models.Model):
    ANSWER_TYPE_CHOICES = [
        ("direct", "Direct Answer"),
        ("related", "Possibly Related"),
        ("fallback", "Fallback"),
        ("blocked", "Blocked"),
    ]
    FEEDBACK_CHOICES = [
        ("", "No Feedback"),
        ("up", "Helpful"),
        ("down", "Not Helpful"),
    ]

    question_normalized = models.CharField(max_length=255, db_index=True)
    question_sample = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=10, choices=PublicContent.LANGUAGE_CHOICES, default="en")
    matched_content = models.ForeignKey(
        PublicContent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_interactions",
    )
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    answer_type = models.CharField(max_length=20, choices=ANSWER_TYPE_CHOICES, default="fallback")
    feedback = models.CharField(max_length=10, choices=FEEDBACK_CHOICES, blank=True, default="")
    ip_address = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.answer_type}: {self.question_sample or self.question_normalized}"


class PublicChatKnowledgeGap(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    question_normalized = models.CharField(max_length=255, unique=True)
    question_sample = models.CharField(max_length=255, blank=True)
    language = models.CharField(max_length=10, choices=PublicContent.LANGUAGE_CHOICES, default="en")
    count = models.PositiveIntegerField(default=1)
    last_asked = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    suggested_title = models.CharField(max_length=200, blank=True)
    suggested_summary = models.TextField(blank=True)
    suggested_body = models.TextField(blank=True)
    suggested_tags = models.JSONField(default=list, blank=True)
    matched_content = models.ForeignKey(
        PublicContent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge_gap_matches",
    )
    approved_content = models.ForeignKey(
        PublicContent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_chat_gaps",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_chat_gaps",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["status", "-count", "-last_asked"]

    def __str__(self):
        return f"{self.question_normalized} ({self.status}, {self.count})"
