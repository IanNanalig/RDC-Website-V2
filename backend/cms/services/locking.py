from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from cms.models import CMSContributorForm, CMSPage, CMSPageSection


def lock_timeout():
    return timedelta(seconds=getattr(settings, "CMS_SECTION_LOCK_SECONDS", 600))


def lock_is_active(section, now=None):
    now = now or timezone.now()
    return bool(
        section.lock_owner_id
        and section.lock_acquired_at
        and section.lock_acquired_at >= now - lock_timeout()
    )


def section_lock_version(section):
    if not lock_is_active(section):
        return ""
    identity = section.edit_lease or section.lock_acquired_at.isoformat()
    return sha256(f"{section.pk}:{section.lock_owner_id}:{identity}".encode()).hexdigest()[:24]


def owns_section_lease(section, user, lease):
    return bool(
        lock_is_active(section) and section.lock_owner_id == user.pk
        and section.edit_lease and str(section.edit_lease) == str(lease)
    )


@transaction.atomic
def acquire_section_lock(section_id, page_id, user, *, override=False, expected_version=""):
    page = CMSPage.objects.select_for_update().get(pk=page_id)
    section = CMSPageSection.objects.select_for_update().get(pk=section_id)
    if section.status == "archived" or (
        user.role != "admin" and (section.status == "submitted" or page.status == "submitted")
    ):
        return section, "unavailable"
    version = section_lock_version(section)
    if version and (section.lock_owner_id != user.pk or section.edit_lease):
        may_replace = user.role == "admin" or section.lock_owner_id == user.pk
        if not (may_replace and override and expected_version == version):
            return section, "blocked"
    section.lock_owner = user
    section.edit_lease = uuid4()
    section.lock_acquired_at = timezone.now()
    section.save(update_fields=["lock_owner", "edit_lease", "lock_acquired_at"])
    return section, "acquired"


@transaction.atomic
def heartbeat_section_lock(section_id, user, lease):
    section = CMSPageSection.objects.select_for_update().get(pk=section_id)
    if not owns_section_lease(section, user, lease):
        return section, False
    section.lock_acquired_at = timezone.now()
    section.save(update_fields=["lock_acquired_at"])
    return section, True


def acquire_form_lock(form_id, user, force=False):
    with transaction.atomic():
        # Lock only the form row. Joining the nullable lock_owner relation makes
        # PostgreSQL reject FOR UPDATE with "nullable side of an outer join".
        form = CMSContributorForm.objects.select_for_update().get(pk=form_id)
        if lock_is_active(form) and form.lock_owner_id != user.id and not force:
            return form, False
        form.lock_owner = user
        form.lock_acquired_at = timezone.now()
        form.save(update_fields=["lock_owner", "lock_acquired_at", "updated_at"])
        return form, True


def release_form_lock(form_id, user, force=False):
    with transaction.atomic():
        form = CMSContributorForm.objects.select_for_update().get(pk=form_id)
        if form.lock_owner_id and form.lock_owner_id != user.id and not force and lock_is_active(form):
            return form, False
        form.lock_owner = None
        form.lock_acquired_at = None
        form.save(update_fields=["lock_owner", "lock_acquired_at", "updated_at"])
        return form, True


def heartbeat_form_lock(form_id, user):
    with transaction.atomic():
        form = CMSContributorForm.objects.select_for_update().get(pk=form_id)
        if form.lock_owner_id != user.id or not lock_is_active(form):
            return form, False
        form.lock_acquired_at = timezone.now()
        form.save(update_fields=["lock_acquired_at", "updated_at"])
        return form, True


def release_section_lock(section_id, user, force=False, lease=None):
    with transaction.atomic():
        section = CMSPageSection.objects.select_for_update().get(pk=section_id)
        if not force and not owns_section_lease(section, user, lease):
            return section, False
        section.lock_owner = None
        section.lock_acquired_at = None
        section.edit_lease = None
        section.save(update_fields=["lock_owner", "lock_acquired_at", "edit_lease"])
        return section, True
