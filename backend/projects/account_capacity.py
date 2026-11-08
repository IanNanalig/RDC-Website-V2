"""Transactional account-capacity checks shared by every account workflow."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .agency_catalog import primary_system_agency, validate_contributor_agency
from .models import AccountCapacityLock, Agency, User, UserInvitation


ADMIN_LOCK_KEY = "global-admin"
RESERVING_INVITATION_STATUSES = (
    UserInvitation.STATUS_PENDING,
    UserInvitation.STATUS_SENT,
)
RESERVING_ACCOUNT_STATES = (
    User.ACCOUNT_ACTIVE,
    User.ACCOUNT_PENDING_ACTIVATION,
)


@dataclass
class AccountCapacityError(Exception):
    detail: str
    limit: int
    agency_code: str = ""

    @property
    def payload(self):
        payload = {
            "code": "account_capacity_reached",
            "detail": self.detail,
            "limit": self.limit,
        }
        if self.agency_code:
            payload["agency"] = self.agency_code
        return payload


def _reserved_users(role, *, agency=None, exclude_user_id=None):
    queryset = User.objects.filter(
        role=role,
        account_state__in=RESERVING_ACCOUNT_STATES,
    )
    if agency is not None:
        queryset = queryset.filter(agency_record=agency)
    if exclude_user_id:
        queryset = queryset.exclude(pk=exclude_user_id)
    return queryset


def _reserved_invitations(role, *, agency=None, exclude_invitation_ids=(), now=None):
    now = now or timezone.now()
    queryset = UserInvitation.objects.filter(
        role=role,
        status__in=RESERVING_INVITATION_STATUSES,
        expires_at__gte=now,
    )
    if agency is not None:
        queryset = queryset.filter(agency_record=agency)
    if exclude_invitation_ids:
        queryset = queryset.exclude(pk__in=tuple(exclude_invitation_ids))
    return queryset


def _lock_global_admin_capacity():
    # The migration seeds this row. get_or_create keeps new/test databases safe.
    AccountCapacityLock.objects.get_or_create(key=ADMIN_LOCK_KEY)
    return AccountCapacityLock.objects.select_for_update().get(key=ADMIN_LOCK_KEY)


def _lock_agencies(agency_ids):
    ids = sorted({int(value) for value in agency_ids if value})
    if not ids:
        return {}
    rows = list(Agency.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
    return {row.pk: row for row in rows}


def lock_capacity_rows(role_agencies):
    """Lock capacity rows in one stable order; caller must be in atomic()."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Account capacity locks require an atomic transaction.")
    pairs = list(role_agencies)
    if any(role == "admin" for role, _agency in pairs):
        _lock_global_admin_capacity()
    return _lock_agencies(
        agency.pk for role, agency in pairs if role == "staff" and agency is not None
    )


def assert_capacity(
    role,
    *,
    agency=None,
    exclude_user_id=None,
    exclude_invitation_ids=(),
    additional=1,
    now=None,
):
    """Raise a structured error if `additional` reservations would exceed capacity."""
    if role == "admin":
        limit = int(getattr(settings, "MAX_ACTIVE_ADMIN_ACCOUNTS", 2))
        used = _reserved_users("admin", exclude_user_id=exclude_user_id).count()
        used += _reserved_invitations(
            "admin", exclude_invitation_ids=exclude_invitation_ids, now=now
        ).count()
        if used + additional > limit:
            raise AccountCapacityError(
                f"The system already has {limit} active or reserved Administrator accounts.",
                limit,
            )
        return

    if role != "staff" or agency is None:
        return
    limit = int(getattr(settings, "MAX_ACTIVE_CONTRIBUTORS_PER_AGENCY", 5))
    used = _reserved_users("staff", agency=agency, exclude_user_id=exclude_user_id).count()
    used += _reserved_invitations(
        "staff",
        agency=agency,
        exclude_invitation_ids=exclude_invitation_ids,
        now=now,
    ).count()
    if used + additional > limit:
        raise AccountCapacityError(
            f"{agency.code} already has {limit} active or reserved Contributor accounts.",
            limit,
            agency.code,
        )


def reserve_invitation(
    *,
    email,
    role,
    agency,
    agency_locked,
    token_digest,
    invited_by,
    batch_key,
    expires_at,
):
    """Replace an email's live invitation and reserve its capacity atomically."""
    now = timezone.now()
    with transaction.atomic():
        previous = list(
            UserInvitation.objects.select_for_update().filter(
                email__iexact=email,
                status__in=RESERVING_INVITATION_STATUSES,
                expires_at__gte=now,
            )
        )
        pairs = [(role, agency)] + [
            (item.role, item.agency_record) for item in previous
        ]
        locked_agencies = lock_capacity_rows(pairs)
        if role == "staff" and agency is not None:
            agency = locked_agencies.get(agency.pk)
            validate_contributor_agency(agency)
        previous_ids = [item.pk for item in previous]
        if previous_ids:
            UserInvitation.objects.filter(pk__in=previous_ids).update(
                status=UserInvitation.STATUS_REVOKED,
                revoked_at=now,
            )
        assert_capacity(role, agency=agency, now=now)
        return UserInvitation.objects.create(
            email=email,
            role=role,
            agency=agency.code if agency else "",
            agency_record=agency,
            agency_locked=agency_locked,
            token_digest=token_digest,
            status=UserInvitation.STATUS_PENDING,
            invited_by=invited_by,
            batch_key=str(batch_key or "")[:64],
            expires_at=expires_at,
        )


def claim_registration_capacity(*, role, agency, invitation=None):
    """Convert an invitation reservation to a pending-activation user reservation."""
    locked_agencies = lock_capacity_rows([(role, agency)])
    if role == "staff" and agency is not None:
        agency = locked_agencies.get(agency.pk)
        validate_contributor_agency(agency)
    excluded = (invitation.pk,) if invitation is not None else ()
    assert_capacity(role, agency=agency, exclude_invitation_ids=excluded)


def update_user_account(*, user_id, role=None, agency=None, account_state=None):
    """Atomically change role, primary agency, or lifecycle state."""
    with transaction.atomic():
        # ``agency_record`` is nullable, so ``select_related`` produces a LEFT OUTER
        # JOIN. PostgreSQL rejects a plain ``FOR UPDATE`` over the nullable side of
        # that join, which made account activation fail with a 500 response. Lock
        # only the User row; the relevant agency rows are locked separately below
        # before capacity is checked or the account is saved.
        user = User.objects.select_for_update(of=("self",)).select_related(
            "agency_record"
        ).get(pk=user_id)
        prior_state = user.account_state
        target_role = role or user.role
        target_state = account_state or user.account_state
        target_agency = agency if agency is not None else user.agency_record

        if target_role in {"admin", "validator", "content_editor"}:
            target_agency = primary_system_agency()
            if target_agency is None:
                raise ValueError("The protected RDC-NCR agency is not configured.")
        if target_role == "staff":
            if target_agency is None:
                raise ValueError("A Contributor must have a primary agency.")
            existing_agency_id = user.agency_record_id if user.role == "staff" else None
            validate_contributor_agency(
                target_agency,
                existing_agency_id=existing_agency_id,
            )
            if not target_agency.is_active and target_agency.pk != user.agency_record_id:
                raise ValueError("The selected agency is archived and cannot accept new assignments.")
            if target_state in RESERVING_ACCOUNT_STATES and not target_agency.is_active:
                raise ValueError("An account cannot be activated for an archived agency.")

        unchanged = (
            target_role == user.role
            and target_state == user.account_state
            and getattr(target_agency, "pk", None) == user.agency_record_id
        )
        if unchanged:
            return user

        locked_agencies = lock_capacity_rows(
            [
                (user.role, user.agency_record),
                (target_role, target_agency),
            ]
        )
        if target_agency is not None:
            target_agency = locked_agencies.get(target_agency.pk, target_agency)
        if target_role == "staff" and target_agency is not None:
            validate_contributor_agency(
                target_agency,
                existing_agency_id=(user.agency_record_id if user.role == "staff" else None),
            )
        if target_state in RESERVING_ACCOUNT_STATES:
            assert_capacity(
                target_role,
                agency=target_agency,
                exclude_user_id=user.pk,
            )

        user.role = target_role
        user.account_state = target_state
        user.is_active = target_state == User.ACCOUNT_ACTIVE
        user.is_staff = target_role == "admin"
        user.agency_record = target_agency
        if target_agency is not None:
            user.agency = target_agency.code
            user.office = target_agency.code
            user.agency_head = target_agency.head_name
        user.save(update_fields=[
            "role",
            "account_state",
            "is_active",
            "is_staff",
            "agency_record",
            "agency",
            "office",
            "agency_head",
        ])
        transition_kind = {
            (User.ACCOUNT_PENDING_ACTIVATION, User.ACCOUNT_ACTIVE): "activated",
            (User.ACCOUNT_ACTIVE, User.ACCOUNT_DISABLED): "deactivated",
            (User.ACCOUNT_DISABLED, User.ACCOUNT_ACTIVE): "reactivated",
        }.get((prior_state, target_state))
        if transition_kind and user.email:
            from .models import AccountStatusEmail
            from .account_status_email import dispatch_account_status_email

            notice = AccountStatusEmail.objects.create(
                user=user,
                recipient_email=user.email,
                recipient_name=user.get_full_name() or user.username,
                kind=transition_kind,
            )
            transaction.on_commit(lambda notice_id=notice.pk: dispatch_account_status_email(notice_id))
        return user


def capacity_usage(role, *, agency=None, exclude_invitation_email=""):
    """Read-only capacity snapshot for previews and UI responses."""
    invitation_qs = _reserved_invitations(role, agency=agency)
    if exclude_invitation_email:
        invitation_qs = invitation_qs.exclude(email__iexact=exclude_invitation_email)
    active = User.objects.filter(role=role, account_state=User.ACCOUNT_ACTIVE)
    pending = User.objects.filter(role=role, account_state=User.ACCOUNT_PENDING_ACTIVATION)
    if agency is not None:
        active = active.filter(agency_record=agency)
        pending = pending.filter(agency_record=agency)
    active_count = active.count()
    reserved_count = pending.count() + invitation_qs.count()
    limit = int(
        getattr(settings, "MAX_ACTIVE_ADMIN_ACCOUNTS", 2)
        if role == "admin"
        else getattr(settings, "MAX_ACTIVE_CONTRIBUTORS_PER_AGENCY", 5)
    )
    used = active_count + reserved_count
    return {
        "limit": limit,
        "active": active_count,
        "reserved": reserved_count,
        "used": used,
        "available": max(0, limit - used),
    }


def agency_capacity(agency):
    return capacity_usage("staff", agency=agency)
