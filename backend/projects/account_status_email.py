"""Idempotent account status notices sent after committed lifecycle changes."""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import F
from django.utils import timezone

from .models import AccountStatusEmail


logger = logging.getLogger(__name__)

SUBJECTS = {
    "activated": "RDC-NCR Website: Your Account Has Been Activated",
    "deactivated": "RDC-NCR Website: Account Deactivation Notice",
    "reactivated": "RDC-NCR Website: Your Account Has Been Reactivated",
}

BODIES = {
    "activated": "Your RDC-NCR Website account has been activated. You may now sign in using your registered credentials.",
    "deactivated": "Your RDC-NCR Website account has been deactivated. You cannot sign in while it remains deactivated.",
    "reactivated": "Your RDC-NCR Website account has been reactivated. You may sign in using your registered credentials.",
}


def deliver_account_status_email(notice_id):
    stale_before = timezone.now() - timedelta(minutes=5)
    AccountStatusEmail.objects.filter(pk=notice_id, status="sending", updated_at__lt=stale_before).update(status="failed")
    claimed = AccountStatusEmail.objects.filter(pk=notice_id, status__in=("pending", "failed")).update(
        status="sending", attempts=F("attempts") + 1, updated_at=timezone.now(),
    )
    if not claimed:
        return False
    notice = AccountStatusEmail.objects.get(pk=notice_id)
    try:
        EmailMessage(
            subject=SUBJECTS[notice.kind],
            body=(f"Hello {notice.recipient_name or 'User'},\n\n{BODIES[notice.kind]}\n\n"
                  "If you need assistance, contact the RDC-NCR system administrator.\n\n"
                  "RDC-NCR Website Administration"),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[notice.recipient_email],
            headers={"X-RDC-Account-Notice": str(notice.pk)},
        ).send(fail_silently=False)
    except Exception as exc:
        AccountStatusEmail.objects.filter(pk=notice_id).update(
            status="failed", last_error=f"{type(exc).__name__}: email delivery was unsuccessful"[:300],
            updated_at=timezone.now(),
        )
        logger.warning("Account status notice delivery failed notice_id=%s error_type=%s", notice_id, type(exc).__name__)
        return False
    AccountStatusEmail.objects.filter(pk=notice_id).update(
        status="sent", sent_at=timezone.now(), last_error="", updated_at=timezone.now(),
    )
    return True


def dispatch_account_status_email(notice_id):
    if deliver_account_status_email(notice_id):
        return
    try:
        from .tasks import retry_account_status_email
        retry_account_status_email.delay(notice_id)
    except Exception as exc:
        logger.warning("Could not queue account status notice retry notice_id=%s error_type=%s", notice_id, type(exc).__name__)
