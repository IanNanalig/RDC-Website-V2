from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


CMS_STATUS_DRAFT = "draft"
CMS_STATUS_SUBMITTED = "submitted"
CMS_STATUS_PUBLISHED = "published"
CMS_STATUS_REJECTED = "rejected"
CMS_STATUS_ARCHIVED = "archived"
CMS_STATUS_CHOICES = [
    (CMS_STATUS_DRAFT, "Draft"),
    (CMS_STATUS_SUBMITTED, "Submitted for review"),
    (CMS_STATUS_PUBLISHED, "Published"),
    (CMS_STATUS_REJECTED, "Rejected"),
    (CMS_STATUS_ARCHIVED, "Archived"),
]


class CMSMediaAsset(models.Model):
    FILE_TYPE_IMAGE = "image"
    FILE_TYPE_DOCUMENT = "document"
    FILE_TYPE_OTHER = "other"
    FILE_TYPE_CHOICES = [
        (FILE_TYPE_IMAGE, "Image"),
        (FILE_TYPE_DOCUMENT, "Document"),
        (FILE_TYPE_OTHER, "Other"),
    ]

    file = models.FileField(upload_to="cms/%Y/%m/")
    storage_backend = models.CharField(max_length=20, default="local")
    storage_key = models.CharField(max_length=500, blank=True)
    public_url = models.URLField(max_length=1000, blank=True)
    file_type = models.CharField(max_length=30, choices=FILE_TYPE_CHOICES, default=FILE_TYPE_OTHER)
    mime_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    alt_text = models.CharField(max_length=250, blank=True)
    caption = models.CharField(max_length=250, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uploaded_cms_media",
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["file_type", "is_archived"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return self.file.name

    @property
    def resolved_public_url(self):
        if self.public_url:
            return self.public_url
        try:
            return self.file.url
        except ValueError:
            return ""


class CMSPage(models.Model):
    STATUS_DRAFT = CMS_STATUS_DRAFT
    STATUS_SUBMITTED = CMS_STATUS_SUBMITTED
    STATUS_PUBLISHED = CMS_STATUS_PUBLISHED
    STATUS_REJECTED = CMS_STATUS_REJECTED
    STATUS_ARCHIVED = CMS_STATUS_ARCHIVED
    STATUS_CHOICES = CMS_STATUS_CHOICES

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    published_snapshot_json = models.JSONField(default=dict, blank=True)
    has_unpublished_changes = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_cms_pages",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_cms_pages",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_cms_pages",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_cms_pages",
    )
    review_notes = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
            models.Index(fields=["has_unpublished_changes"]),
        ]

    def __str__(self):
        return self.title


class CMSPageSection(models.Model):
    page = models.ForeignKey(CMSPage, on_delete=models.CASCADE, related_name="sections")
    section_key = models.SlugField(max_length=120)
    section_type = models.CharField(max_length=60)
    order = models.PositiveIntegerField(default=1)
    content_json = models.JSONField(default=dict, blank=True)
    schema_version = models.PositiveIntegerField(default=1)
    is_visible = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=CMS_STATUS_CHOICES, default=CMS_STATUS_DRAFT)
    lock_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="locked_cms_sections",
    )
    lock_acquired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["page", "section_key"], name="unique_cms_section_key_per_page"),
            models.UniqueConstraint(fields=["page", "order"], name="unique_cms_section_order_per_page"),
        ]
        indexes = [
            models.Index(fields=["page", "status", "is_visible", "order"]),
            models.Index(fields=["section_type"]),
            models.Index(fields=["lock_acquired_at"]),
        ]

    def __str__(self):
        return f"{self.page.slug}:{self.section_key}"


class CMSArticle(models.Model):
    STATUS_DRAFT = CMS_STATUS_DRAFT
    STATUS_SUBMITTED = CMS_STATUS_SUBMITTED
    STATUS_PUBLISHED = CMS_STATUS_PUBLISHED
    STATUS_REJECTED = CMS_STATUS_REJECTED
    STATUS_ARCHIVED = CMS_STATUS_ARCHIVED
    STATUS_CHOICES = CMS_STATUS_CHOICES

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=140, unique=True)
    category = models.CharField(max_length=80, default="Updates")
    summary = models.CharField(max_length=350, blank=True)
    body = models.TextField(blank=True)
    thumbnail = models.ForeignKey(
        CMSMediaAsset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="thumbnail_articles",
    )
    author = models.CharField(max_length=150, blank=True)
    publication_date = models.DateField(null=True, blank=True)
    featured = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    published_snapshot_json = models.JSONField(default=dict, blank=True)
    has_unpublished_changes = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_cms_articles",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_cms_articles",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_cms_articles",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_cms_articles",
    )
    review_notes = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-updated_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status", "featured"]),
            models.Index(fields=["category"]),
            models.Index(fields=["has_unpublished_changes"]),
        ]

    def __str__(self):
        return self.title


class CMSContributorForm(models.Model):
    STATUS_DRAFT = CMS_STATUS_DRAFT
    STATUS_SUBMITTED = CMS_STATUS_SUBMITTED
    STATUS_PUBLISHED = CMS_STATUS_PUBLISHED
    STATUS_REJECTED = CMS_STATUS_REJECTED
    STATUS_CHOICES = [choice for choice in CMS_STATUS_CHOICES if choice[0] != CMS_STATUS_ARCHIVED]

    key = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    draft_schema_json = models.JSONField(default=dict)
    current_published_version = models.ForeignKey(
        "CMSContributorFormVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="active_for_forms",
    )
    has_unpublished_changes = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_cms_contributor_forms",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="updated_cms_contributor_forms",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="submitted_cms_contributor_forms",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reviewed_cms_contributor_forms",
    )
    review_notes = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    lock_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="locked_cms_contributor_forms",
    )
    lock_acquired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["status"], name="cms_form_status_idx"),
            models.Index(fields=["lock_acquired_at"], name="cms_form_lock_idx"),
        ]

    def __str__(self):
        return self.name


class CMSContributorFormVersion(models.Model):
    form = models.ForeignKey(CMSContributorForm, on_delete=models.PROTECT, related_name="versions")
    version_number = models.PositiveIntegerField()
    schema_json = models.JSONField(default=dict)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="published_cms_contributor_form_versions",
    )
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["form", "version_number"], name="unique_cms_contributor_form_version"
            )
        ]

    def __str__(self):
        return f"{self.form.key} v{self.version_number}"


class CMSRevision(models.Model):
    CONTENT_PAGE = "page"
    CONTENT_ARTICLE = "article"
    CONTENT_SECTION = "section"
    CONTENT_MEDIA = "media"
    CONTENT_FORM = "form"
    CONTENT_TYPE_CHOICES = [
        (CONTENT_PAGE, "Page"),
        (CONTENT_ARTICLE, "Article"),
        (CONTENT_SECTION, "Section"),
        (CONTENT_MEDIA, "Media"),
        (CONTENT_FORM, "Contributor form"),
    ]

    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_PUBLISH = "publish"
    ACTION_ARCHIVE = "archive"
    ACTION_REORDER = "reorder"
    ACTION_SUBMIT = "submit"
    ACTION_REJECT = "reject"
    ACTION_RESTORE = "restore"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_PUBLISH, "Publish"),
        (ACTION_ARCHIVE, "Archive"),
        (ACTION_REORDER, "Reorder"),
        (ACTION_SUBMIT, "Submit"),
        (ACTION_REJECT, "Reject"),
        (ACTION_RESTORE, "Restore"),
    ]

    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="cms_revisions")
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    version_number = models.PositiveIntegerField()
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    status_before = models.CharField(max_length=40, blank=True)
    status_after = models.CharField(max_length=40, blank=True)
    snapshot_json = models.JSONField(default=dict, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cms_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "version_number"],
                name="unique_cms_revision_version_per_object",
            )
        ]
        indexes = [
            models.Index(fields=["content_type", "object_id", "-version_number"]),
            models.Index(fields=["action"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.content_type.model}#{self.object_id} v{self.version_number}"

    @property
    def content_type_key(self):
        return {
            "cmspage": self.CONTENT_PAGE,
            "cmsarticle": self.CONTENT_ARTICLE,
            "cmspagesection": self.CONTENT_SECTION,
            "cmsmediaasset": self.CONTENT_MEDIA,
            "cmscontributorform": self.CONTENT_FORM,
        }.get(self.content_type.model, self.content_type.model)


class CMSSiteSetting(models.Model):
    key = models.SlugField(max_length=160, unique=True)
    value_json = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_cms_site_settings",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key
