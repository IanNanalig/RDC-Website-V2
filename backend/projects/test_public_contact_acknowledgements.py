import uuid
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from rest_framework.test import APITestCase

from .models import PublicContactMessage


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    CONTACT_RECEIVER_EMAIL="contact@example.test",
    CELERY_TASK_ALWAYS_EAGER=False,
)
class PublicContactAcknowledgementTests(APITestCase):
    def payload(self, **overrides):
        data = {
            "submission_id": str(uuid.uuid4()),
            "name": "Public Sender",
            "email": "sender@example.test",
            "subject": "Website question",
            "message": "Please provide more information about the RDC dashboard.",
        }
        data.update(overrides)
        return data

    def test_contact_is_saved_before_receiver_and_acknowledgement_delivery(self):
        response = self.client.post("/api/contact/", self.payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["status"], "accepted")
        message = PublicContactMessage.objects.get()
        self.assertEqual(message.receiver_delivery_status, "sent")
        self.assertEqual(message.acknowledgement_delivery_status, "sent")
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(mail.outbox[0].to, ["contact@example.test"])
        self.assertEqual(mail.outbox[1].to, ["sender@example.test"])
        self.assertNotIn(message.message, mail.outbox[1].body)

    def test_repeated_submission_token_does_not_duplicate_messages_or_mail(self):
        submission_id = str(uuid.uuid4())
        first = self.client.post("/api/contact/", self.payload(submission_id=submission_id), format="json")
        second = self.client.post("/api/contact/", self.payload(submission_id=submission_id), format="json")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(PublicContactMessage.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_invalid_email_is_rejected_without_creating_a_delivery_record(self):
        response = self.client.post("/api/contact/", self.payload(email="not-an-email"), format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PublicContactMessage.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    @patch("projects.views.dispatch_public_contact_delivery", return_value=True)
    @patch("projects.contact_delivery.EmailMessage.send", side_effect=RuntimeError("smtp secret"))
    def test_delivery_failure_keeps_the_accepted_message(self, _send, dispatch):
        response = self.client.post("/api/contact/", self.payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        message = PublicContactMessage.objects.get()
        self.assertEqual(message.receiver_delivery_status, "failed")
        self.assertEqual(message.acknowledgement_delivery_status, "failed")
        self.assertNotIn("smtp secret", message.receiver_last_error)
        dispatch.assert_called_once_with(message.pk)

    @patch("projects.views.dispatch_public_contact_delivery", return_value=True)
    @patch("projects.contact_delivery.EmailMessage.send", side_effect=[1, RuntimeError("ack smtp secret")])
    def test_acknowledgement_failure_is_retried_after_receiver_delivery(self, _send, dispatch):
        response = self.client.post("/api/contact/", self.payload(), format="json")

        self.assertEqual(response.status_code, 201, response.data)
        message = PublicContactMessage.objects.get()
        self.assertEqual(message.receiver_delivery_status, "sent")
        self.assertEqual(message.acknowledgement_delivery_status, "failed")
        self.assertNotIn("ack smtp secret", message.acknowledgement_last_error)
        dispatch.assert_called_once_with(message.pk)
