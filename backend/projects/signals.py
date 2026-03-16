from django.db.models.signals import post_save
from django.dispatch import receiver
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


@receiver(post_save, sender=SystemSetting)
def setting_changed(sender, instance, created, **kwargs):
    # You can log freeze/unfreeze actions here if needed
    # But actor context must come from the view or command that triggered it
    pass
