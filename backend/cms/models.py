from django.conf import settings
from django.db import models


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
    def public_url(self):
        try:
            return self.file.url
        except ValueError:
            return ""


class CMSPage(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    ]

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
    published_at = models.DateTimeField(null=True, blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page", "order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["page", "section_key"], name="unique_cms_section_key_per_page"),
            models.UniqueConstraint(fields=["page", "order"], name="unique_cms_section_order_per_page"),
        ]
        indexes = [
            models.Index(fields=["page", "is_visible", "order"]),
            models.Index(fields=["section_type"]),
        ]

    def __str__(self):
        return f"{self.page.slug}:{self.section_key}"


class CMSArticle(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    ]

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
    published_at = models.DateTimeField(null=True, blank=True)
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


class CMSRevision(models.Model):
    CONTENT_PAGE = "page"
    CONTENT_ARTICLE = "article"
    CONTENT_SECTION = "section"
    CONTENT_MEDIA = "media"
    CONTENT_TYPE_CHOICES = [
        (CONTENT_PAGE, "Page"),
        (CONTENT_ARTICLE, "Article"),
        (CONTENT_SECTION, "Section"),
        (CONTENT_MEDIA, "Media"),
    ]

    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_PUBLISH = "publish"
    ACTION_ARCHIVE = "archive"
    ACTION_REORDER = "reorder"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_PUBLISH, "Publish"),
        (ACTION_ARCHIVE, "Archive"),
        (ACTION_REORDER, "Reorder"),
    ]

    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    object_id = models.PositiveBigIntegerField()
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
        return f"{self.content_type}#{self.object_id} v{self.version_number}"
