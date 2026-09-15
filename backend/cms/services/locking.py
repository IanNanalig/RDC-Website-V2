from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from cms.models import CMSContributorForm, CMSPageSection


def lock_timeout():
    return timedelta(seconds=getattr(settings, "CMS_SECTION_LOCK_SECONDS", 600))


def lock_is_active(section, now=None):
    now = now or timezone.now()
    return bool(
        section.lock_owner_id
        and section.lock_acquired_at
        and section.lock_acquired_at >= now - lock_timeout()
    )


def acquire_section_lock(section_id, user):
    with transaction.atomic():
        section = CMSPageSection.objects.select_for_update().select_related("page").get(pk=section_id)
        if lock_is_active(section) and section.lock_owner_id != user.id:
            return section, False
        section.lock_owner = user
        section.lock_acquired_at = timezone.now()
        section.save(update_fields=["lock_owner", "lock_acquired_at", "updated_at"])
        return section, True


def heartbeat_section_lock(section_id, user):
    with transaction.atomic():
        section = CMSPageSection.objects.select_for_update().select_related("page").get(pk=section_id)
        if not lock_is_active(section) or section.lock_owner_id != user.id:
            return section, False
        section.lock_acquired_at = timezone.now()
        section.save(update_fields=["lock_acquired_at", "updated_at"])
        return section, True


def acquire_form_lock(form_id, user):
    with transaction.atomic():
        # Lock only the form row. Joining the nullable lock_owner relation makes
        # PostgreSQL reject FOR UPDATE with "nullable side of an outer join".
        form = CMSContributorForm.objects.select_for_update().get(pk=form_id)
        if lock_is_active(form) and form.lock_owner_id != user.id:
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


def release_section_lock(section_id, user, force=False):
    with transaction.atomic():
        section = CMSPageSection.objects.select_for_update().select_related("page").get(pk=section_id)
        if lock_is_active(section) and section.lock_owner_id != user.id and not force:
            return section, False
        section.lock_owner = None
        section.lock_acquired_at = None
        section.save(update_fields=["lock_owner", "lock_acquired_at", "updated_at"])
        return section, True
