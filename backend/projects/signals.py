from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import Project, AuditTrail, SystemSetting


@receiver(post_save, sender=Project)
def project_post_save(sender, instance, created, **kwargs):
    if created:
        AuditTrail.objects.create(
            actor=instance.created_by,
            action='create',
            project=instance,
            detail='Project created'
        )
    else:
        AuditTrail.objects.create(
            actor=instance.created_by,
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


@receiver(post_save, sender=SystemSetting)
def setting_changed(sender, instance, created, **kwargs):
    # You can log freeze/unfreeze actions here if needed
    # But actor context must come from the view or command that triggered it
    pass
