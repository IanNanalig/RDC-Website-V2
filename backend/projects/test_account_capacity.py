import threading
from datetime import timedelta
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from .account_capacity import agency_capacity
from .models import Agency, User, UserInvitation


class AccountCapacityApiTests(APITestCase):
    def setUp(self):
        self.rdc, _ = Agency.objects.get_or_create(code="RDC-NCR", defaults={"name": "RDC-NCR"})
        self.denr, _ = Agency.objects.get_or_create(code="DENR", defaults={"name": "DENR"})
        self.doh, _ = Agency.objects.get_or_create(code="DOH", defaults={"name": "DOH"})
        self.admin = User.objects.create_user(
            username="capacity-admin",
            email="capacity-admin@example.test",
            password="StrongPassword123!",
            role="admin",
            agency_record=self.rdc,
            agency=self.rdc.code,
            is_staff=True,
        )
        self.client.force_authenticate(self.admin)

    def create_staff(self, agency, index, *, active=True, state=None):
        return User.objects.create_user(
            username=f"staff-{agency.code}-{index}",
            email=f"staff-{agency.code}-{index}@example.test",
            password="StrongPassword123!",
            role="staff",
            agency=agency.code,
            agency_record=agency,
            is_active=active,
            account_state=state or (User.ACCOUNT_ACTIVE if active else User.ACCOUNT_DISABLED),
        )

    def invite_with_token(self, email, *, role="contributor", agency=""):
        captured = {}

        def deliver(address, token):
            captured["token"] = token

        payload = {"email": email, "role": role}
        if agency:
            payload["agency"] = agency
        with patch("projects.views._send_registration_invitation", side_effect=deliver):
            response = self.client.post("/api/admin/users/", payload, format="json")
        return response, captured.get("token")

    @staticmethod
    def setup_payload(token, agency="DENR"):
        return {
            "token": token,
            "new_password": "ValidSetup123!",
            "first_name": "Capacity",
            "last_name": "Tester",
            "agency": agency,
            "division": "Planning",
            "position": "Officer",
            "contact_number": "0212345678",
            "phone_number": "09170000000",
        }

    def test_second_admin_reservation_is_allowed_and_third_is_rejected(self):
        second, _ = self.invite_with_token("second-admin@example.test", role="admin")
        self.assertEqual(second.status_code, 202, second.data)
        third, _ = self.invite_with_token("third-admin@example.test", role="admin")
        self.assertEqual(third.status_code, 409, third.data)
        self.assertEqual(third.data["code"], "account_capacity_reached")
        self.assertEqual(third.data["limit"], 2)

    def test_fifth_contributor_reservation_is_allowed_and_sixth_is_rejected(self):
        for index in range(4):
            self.create_staff(self.denr, index)
        fifth, _ = self.invite_with_token("fifth@example.test", agency="DENR")
        self.assertEqual(fifth.status_code, 202, fifth.data)
        sixth, _ = self.invite_with_token("sixth@example.test", agency="DENR")
        self.assertEqual(sixth.status_code, 409, sixth.data)
        self.assertEqual(sixth.data["agency"], "DENR")
        self.assertEqual(sixth.data["limit"], 5)

    def test_open_invitation_reserves_chosen_agency_only_at_setup(self):
        for index in range(5):
            self.create_staff(self.denr, index)
        invited, token = self.invite_with_token("open@example.test")
        self.assertEqual(invited.status_code, 202, invited.data)
        self.client.force_authenticate(None)
        full = self.client.post(
            "/api/auth/setup-password/", self.setup_payload(token, "DENR"), format="json"
        )
        self.assertEqual(full.status_code, 409, full.data)
        self.assertFalse(User.objects.filter(email="open@example.test").exists())
        available = self.client.post(
            "/api/auth/setup-password/", self.setup_payload(token, "DOH"), format="json"
        )
        self.assertEqual(available.status_code, 200, available.data)
        user = User.objects.get(email="open@example.test")
        self.assertEqual(user.account_state, User.ACCOUNT_PENDING_ACTIVATION)
        self.assertFalse(user.is_active)

    def test_pending_activation_reserves_slot_and_activation_does_not_double_count(self):
        for index in range(4):
            self.create_staff(self.denr, index)
        pending = self.create_staff(
            self.denr,
            5,
            active=False,
            state=User.ACCOUNT_PENDING_ACTIVATION,
        )
        activated = self.client.post(
            f"/api/admin/users/{pending.pk}/set_active/", {"active": True}, format="json"
        )
        self.assertEqual(activated.status_code, 200, activated.data)
        pending.refresh_from_db()
        self.assertEqual(pending.account_state, User.ACCOUNT_ACTIVE)
        self.assertTrue(pending.is_active)

    @skipUnless(connection.vendor == "postgresql", "requires PostgreSQL row locking")
    def test_activation_locks_only_user_when_agency_relation_is_nullable(self):
        """PostgreSQL must not attempt FOR UPDATE on the nullable agency join."""
        pending = self.create_staff(
            self.denr,
            6,
            active=False,
            state=User.ACCOUNT_PENDING_ACTIVATION,
        )
        response = self.client.post(
            f"/api/admin/users/{pending.pk}/set_active/", {"active": True}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        pending.refresh_from_db()
        self.assertTrue(pending.is_active)

    def test_disabled_reactivation_and_full_agency_reassignment_are_rejected_atomically(self):
        disabled = self.create_staff(self.denr, 99, active=False)
        moving = self.create_staff(self.denr, 100)
        for index in range(5):
            self.create_staff(self.doh, index)
        reactivation = self.client.post(
            f"/api/admin/users/{disabled.pk}/set_active/", {"active": True}, format="json"
        )
        self.assertEqual(reactivation.status_code, 200, reactivation.data)
        reassignment = self.client.patch(
            f"/api/admin/users/{moving.pk}/", {"agency_code": "DOH"}, format="json"
        )
        self.assertEqual(reassignment.status_code, 409, reassignment.data)
        moving.refresh_from_db()
        self.assertEqual(moving.agency_record_id, self.denr.pk)

    def test_reactivation_is_rejected_when_own_agency_is_full(self):
        disabled = self.create_staff(self.denr, 99, active=False)
        for index in range(5):
            self.create_staff(self.denr, index)
        response = self.client.post(
            f"/api/admin/users/{disabled.pk}/set_active/", {"active": True}, format="json"
        )
        self.assertEqual(response.status_code, 409, response.data)
        disabled.refresh_from_db()
        self.assertEqual(disabled.account_state, User.ACCOUNT_DISABLED)
        self.assertFalse(disabled.is_active)

    def test_archived_agency_rejects_assignment(self):
        user = self.create_staff(self.denr, 1)
        self.doh.is_active = False
        self.doh.save(update_fields=["is_active"])
        response = self.client.patch(
            f"/api/admin/users/{user.pk}/", {"agency_code": "DOH"}, format="json"
        )
        self.assertEqual(response.status_code, 400, response.data)
        user.refresh_from_db()
        self.assertEqual(user.agency_record_id, self.denr.pk)

    def test_protected_rdc_rejects_new_contributor_assignment_in_every_admin_flow(self):
        invited, token = self.invite_with_token(
            "protected-invite@example.test",
            agency=self.rdc.code,
        )
        self.assertEqual(invited.status_code, 400, invited.data)
        self.assertEqual(invited.data["code"], "agency_not_eligible_for_contributor")
        self.assertIsNone(token)

        contributor = self.create_staff(self.denr, 44)
        reassigned = self.client.patch(
            f"/api/admin/users/{contributor.pk}/",
            {"agency_code": self.rdc.code},
            format="json",
        )
        self.assertEqual(reassigned.status_code, 400, reassigned.data)
        self.assertEqual(reassigned.data["code"], "agency_not_eligible_for_contributor")
        contributor.refresh_from_db()
        self.assertEqual(contributor.agency_record_id, self.denr.pk)

        preview = self.client.post(
            "/api/admin/users/batch-invitations/preview/",
            {"entries": [{
                "email": "protected-batch@example.test",
                "role": "contributor",
                "agency": self.rdc.code,
            }]},
            format="json",
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["rows"][0]["status"], "invalid")
        self.assertIn("cannot be selected", preview.data["rows"][0]["reason"])

    def test_existing_rdc_contributor_can_be_reactivated_without_reassignment(self):
        existing = self.create_staff(self.rdc, 55, active=False)
        response = self.client.post(
            f"/api/admin/users/{existing.pk}/set_active/",
            {"active": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        existing.refresh_from_db()
        self.assertTrue(existing.is_active)
        self.assertEqual(existing.agency_record_id, self.rdc.pk)

    def test_batch_preview_marks_rows_that_exceed_remaining_capacity(self):
        response = self.client.post(
            "/api/admin/users/batch-invitations/preview/",
            {
                "entries": [
                    {"email": "admin-two@example.test", "role": "admin"},
                    {"email": "admin-three@example.test", "role": "admin"},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["rows"][0]["status"], "valid")
        self.assertEqual(response.data["rows"][1]["status"], "capacity_reached")

    def test_delivery_failure_releases_the_reserved_slot(self):
        for index in range(4):
            self.create_staff(self.denr, index)
        with patch(
            "projects.views._send_registration_invitation",
            side_effect=RuntimeError("SMTP unavailable"),
        ):
            failed = self.client.post(
                "/api/admin/users/",
                {"email": "failed-delivery@example.test", "role": "contributor", "agency": "DENR"},
                format="json",
            )
        self.assertEqual(failed.status_code, 500, failed.data)
        self.assertEqual(
            UserInvitation.objects.get(email="failed-delivery@example.test").status,
            UserInvitation.STATUS_DELIVERY_FAILED,
        )
        replacement, _ = self.invite_with_token("replacement@example.test", agency="DENR")
        self.assertEqual(replacement.status_code, 202, replacement.data)

    def test_replacing_an_invitation_keeps_only_one_reservation(self):
        for index in range(4):
            self.create_staff(self.denr, index)
        first, _ = self.invite_with_token("replace-me@example.test", agency="DENR")
        self.assertEqual(first.status_code, 202, first.data)
        second, _ = self.invite_with_token("replace-me@example.test", agency="DENR")
        self.assertEqual(second.status_code, 202, second.data)
        statuses = list(
            UserInvitation.objects.filter(email="replace-me@example.test")
            .order_by("id")
            .values_list("status", flat=True)
        )
        self.assertEqual(statuses, [UserInvitation.STATUS_REVOKED, UserInvitation.STATUS_SENT])
        self.assertEqual(agency_capacity(self.denr)["used"], 5)

    def test_expired_invitation_does_not_reserve_capacity(self):
        for index in range(4):
            self.create_staff(self.denr, index)
        UserInvitation.objects.create(
            email="expired@example.test",
            role="staff",
            agency="DENR",
            agency_record=self.denr,
            agency_locked=True,
            token_digest="e" * 64,
            status=UserInvitation.STATUS_SENT,
            expires_at=timezone.now() - timedelta(minutes=1),
            invited_by=self.admin,
        )
        response, _ = self.invite_with_token("current@example.test", agency="DENR")
        self.assertEqual(response.status_code, 202, response.data)

    def test_role_promotion_failure_preserves_role_and_agency(self):
        User.objects.create_user(
            username="second-admin",
            email="second-admin@example.test",
            password="StrongPassword123!",
            role="admin",
            agency="RDC-NCR",
            agency_record=self.rdc,
            is_staff=True,
        )
        contributor = self.create_staff(self.denr, 77)
        response = self.client.patch(
            f"/api/admin/users/{contributor.pk}/", {"role": "admin"}, format="json"
        )
        self.assertEqual(response.status_code, 409, response.data)
        contributor.refresh_from_db()
        self.assertEqual(contributor.role, "staff")
        self.assertEqual(contributor.agency_record_id, self.denr.pk)

    def test_capacity_metadata_and_account_state_are_returned(self):
        pending = self.create_staff(
            self.denr,
            8,
            active=False,
            state=User.ACCOUNT_PENDING_ACTIVATION,
        )
        users = self.client.get("/api/admin/users/")
        self.assertEqual(users.status_code, 200, users.data)
        serialized = next(item for item in users.data if item["id"] == pending.pk)
        self.assertEqual(serialized["account_state"], User.ACCOUNT_PENDING_ACTIVATION)

        options = self.client.get("/api/admin/users/batch-invitations/options/")
        self.assertEqual(options.data["administrator_capacity"]["active"], 1)
        self.assertEqual(options.data["administrator_capacity"]["available"], 1)
        denr = next(item for item in options.data["agencies"] if item["code"] == "DENR")
        self.assertEqual(denr["contributor_capacity"]["reserved"], 1)
        self.assertEqual(denr["contributor_capacity"]["available"], 4)
        self.assertTrue(denr["accepting_contributors"])

    def test_user_manager_keeps_new_account_state_and_is_active_synchronized(self):
        pending = User.objects.create_user(
            username="manager-pending",
            email="manager-pending@example.test",
            password="StrongPassword123!",
            role="staff",
            agency="DENR",
            agency_record=self.denr,
            account_state=User.ACCOUNT_PENDING_ACTIVATION,
        )
        self.assertFalse(pending.is_active)
        with self.assertRaisesMessage(ValueError, "same lifecycle state"):
            User.objects.create_user(
                username="manager-inconsistent",
                email="manager-inconsistent@example.test",
                password="StrongPassword123!",
                role="staff",
                account_state=User.ACCOUNT_DISABLED,
                is_active=True,
            )


@skipUnless(connection.vendor == "postgresql", "Requires a disposable PostgreSQL database")
class AccountCapacityConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_two_simultaneous_admin_reservations_cannot_take_one_slot(self):
        from projects.account_capacity import AccountCapacityError, reserve_invitation
        from django.utils import timezone
        from datetime import timedelta

        rdc, _ = Agency.objects.get_or_create(code="RDC-NCR", defaults={"name": "RDC-NCR"})
        admin = User.objects.create_user(
            username="existing-admin",
            email="existing-admin@example.test",
            password="StrongPassword123!",
            role="admin",
            agency_record=rdc,
            agency=rdc.code,
        )
        barrier = threading.Barrier(2)
        results = []

        def worker(index):
            connections["default"].close()
            barrier.wait()
            try:
                reserve_invitation(
                    email=f"candidate-{index}@example.test",
                    role="admin",
                    agency=Agency.objects.get(pk=rdc.pk),
                    agency_locked=True,
                    token_digest=f"{index:064d}",
                    invited_by=User.objects.get(pk=admin.pk),
                    batch_key="",
                    expires_at=timezone.now() + timedelta(hours=1),
                )
                results.append("created")
            except AccountCapacityError:
                results.append("blocked")
            finally:
                connections["default"].close()

        threads = [threading.Thread(target=worker, args=(index,)) for index in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertCountEqual(results, ["created", "blocked"])
