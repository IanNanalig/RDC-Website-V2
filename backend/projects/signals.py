from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from .audit import current_audit_request, mark_audit_record
from .models import Project, AuditTrail, SystemSetting, UserActivity


@receiver(post_save, sender=Project)
def project_post_save(sender, instance, created, **kwargs):
    request = current_audit_request()
    request_user = getattr(request, "user", None) if request is not None else None
    actor = request_user if getattr(request_user, "is_authenticated", False) else (
        instance.created_by if created else None
    )
    if created:
        AuditTrail.objects.create(
            actor=actor,
            action='create',
            project=instance,
            detail='Project created'
        )
    else:
        AuditTrail.objects.create(
            actor=actor,
            action='update',
            project=instance,
            detail='Project updated'
        )

    # Public dashboard cache invalidation (version bump).
    version_key = "public_projects:version"
    try:
        if cache.get(version_key) is None:
            cache.add(version_key, 1, None)
        cache.incr(version_key)
    except Exception:
        try:
            cache.set(version_key, 2, None)
        except Exception:
            pass


@receiver(pre_save, sender=UserActivity)
def snapshot_activity_subjects(sender, instance, **kwargs):
    if instance.user_id:
        user = instance.user
        if not instance.actor_username:
            instance.actor_username = user.username
        if not instance.actor_full_name:
            instance.actor_full_name = (user.full_name or user.get_full_name() or user.username)[:200]
        if not instance.role:
            instance.role = user.role
    if instance.project_id:
        project = instance.project
        if instance.project_id_snapshot is None:
            instance.project_id_snapshot = project.pk
        if not instance.project_title_snapshot:
            instance.project_title_snapshot = project.title


@receiver(post_save, sender=UserActivity)
def activity_recorded(sender, instance, created, **kwargs):
    if created:
        mark_audit_record(instance.user_id, instance.pk)


@receiver(post_save, sender=SystemSetting)
def setting_changed(sender, instance, created, **kwargs):
    # You can log freeze/unfreeze actions here if needed
    # But actor context must come from the view or command that triggered it
    pass
