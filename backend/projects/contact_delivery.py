"""Idempotent delivery for accepted public Contact Us messages."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import F
from django.utils import timezone

from .models import PublicContactMessage


logger = logging.getLogger(__name__)


def _safe_delivery_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: email delivery was unsuccessful"[:300]


def _header_text(value: str) -> str:
    return " ".join(str(value or "").replace("\r", " ").replace("\n", " ").split())


def _receiver_message(message: PublicContactMessage) -> EmailMessage:
    receiver = str(getattr(settings, "CONTACT_RECEIVER_EMAIL", "") or "").strip()
    if not receiver:
        raise RuntimeError("Contact receiver is not configured")
    subject = _header_text(message.subject) or "Contact Form Inquiry"
    body = (
        "New contact message received via the RDC-NCR website.\n\n"
        f"Name: {message.name}\n"
        f"Email: {message.email}\n"
        f"Subject: {message.subject or '-'}\n\n"
        "Message:\n"
        f"{message.message}\n"
    )
    return EmailMessage(
        subject=f"[RDC Portal] {subject}"[:998],
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[receiver],
        reply_to=[message.email],
        headers={"X-RDC-Contact-Message": str(message.pk)},
    )


def _acknowledgement_message(message: PublicContactMessage) -> EmailMessage:
    body = (
        "Thank you for contacting the Regional Development Council – National Capital Region (RDC-NCR).\n\n"
        "This is to confirm that we have successfully received your message. Our office will review "
        "your submission and take appropriate action when necessary.\n\n"
        "Should further information be required, our office may contact you using the email address you provided.\n\n"
        "Thank you for reaching out to RDC-NCR.\n\n"
        "Regional Development Council – National Capital Region (RDC-NCR)\n\n"
        "This is an automated acknowledgement. Please do not reply directly to this email unless the "
        "system explicitly supports email replies."
    )
    return EmailMessage(
        subject="We Have Received Your Message – RDC-NCR",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[message.email],
        headers={"X-RDC-Contact-Message": str(message.pk)},
    )


def _claim_delivery(message_id: int, field: str, attempts_field: str) -> bool:
    return bool(
        PublicContactMessage.objects.filter(
            pk=message_id,
            **{f"{field}__in": [PublicContactMessage.DELIVERY_PENDING, PublicContactMessage.DELIVERY_FAILED]},
        ).update(
            **{
                field: PublicContactMessage.DELIVERY_SENDING,
                attempts_field: F(attempts_field) + 1,
                "updated_at": timezone.now(),
            }
        )
    )


def deliver_public_contact_message(message_id: int) -> dict:
    """Send receiver and acknowledgement mail at most once per successful claim."""
    stale_before = timezone.now() - timedelta(minutes=5)
    PublicContactMessage.objects.filter(
        pk=message_id,
        receiver_delivery_status=PublicContactMessage.DELIVERY_SENDING,
        updated_at__lt=stale_before,
    ).update(receiver_delivery_status=PublicContactMessage.DELIVERY_FAILED)
    PublicContactMessage.objects.filter(
        pk=message_id,
        acknowledgement_delivery_status=PublicContactMessage.DELIVERY_SENDING,
        updated_at__lt=stale_before,
    ).update(acknowledgement_delivery_status=PublicContactMessage.DELIVERY_FAILED)

    message = PublicContactMessage.objects.filter(pk=message_id).first()
    if not message:
        return {"status": "missing"}

    if _claim_delivery(message.pk, "receiver_delivery_status", "receiver_delivery_attempts"):
        message.refresh_from_db()
        try:
            _receiver_message(message).send(fail_silently=False)
        except Exception as exc:
            PublicContactMessage.objects.filter(pk=message.pk).update(
                receiver_delivery_status=PublicContactMessage.DELIVERY_FAILED,
                receiver_last_error=_safe_delivery_error(exc),
            )
        else:
            PublicContactMessage.objects.filter(pk=message.pk).update(
                receiver_delivery_status=PublicContactMessage.DELIVERY_SENT,
                receiver_sent_at=timezone.now(),
                receiver_last_error="",
            )

    message.refresh_from_db()
    if _claim_delivery(message.pk, "acknowledgement_delivery_status", "acknowledgement_delivery_attempts"):
        message.refresh_from_db()
        try:
            _acknowledgement_message(message).send(fail_silently=False)
        except Exception as exc:
            PublicContactMessage.objects.filter(pk=message.pk).update(
                acknowledgement_delivery_status=PublicContactMessage.DELIVERY_FAILED,
                acknowledgement_last_error=_safe_delivery_error(exc),
            )
        else:
            PublicContactMessage.objects.filter(pk=message.pk).update(
                acknowledgement_delivery_status=PublicContactMessage.DELIVERY_SENT,
                acknowledgement_sent_at=timezone.now(),
                acknowledgement_last_error="",
            )

    message.refresh_from_db()
    return {
        # Both messages are independently durable.  A successful staff copy
        # must not suppress retrying an acknowledgement that failed later.
        "status": (
            "complete"
            if message.receiver_delivery_status == message.DELIVERY_SENT
            and message.acknowledgement_delivery_status == message.DELIVERY_SENT
            else "pending_retry"
        ),
        "receiver": message.receiver_delivery_status,
        "acknowledgement": message.acknowledgement_delivery_status,
    }


def dispatch_public_contact_delivery(message_id: int) -> bool:
    try:
        from .tasks import retry_public_contact_delivery

        if settings.CELERY_TASK_ALWAYS_EAGER:
            retry_public_contact_delivery.run(message_id)
        else:
            retry_public_contact_delivery.delay(message_id)
        return True
    except Exception:
        logger.exception("Could not queue public contact delivery retry for message %s", message_id)
        return False
