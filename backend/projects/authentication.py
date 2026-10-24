from datetime import timedelta

from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

from .models import PortalSession


SESSION_REPLACED_DETAIL = (
    "This session expired because this account signed in from another browser or device."
)
SESSION_REPLACED_CODE = "session_replaced"
SESSION_EXPIRED_DETAIL = "Session expired after 12 hours of inactivity. Please log in again."
SESSION_IDLE_TIMEOUT = timedelta(hours=12)
SESSION_ACTIVITY_WRITE_INTERVAL = timedelta(minutes=1)


def _coerce_session_version(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validate_token_session(user, token, *, touch=True):
    token_version = _coerce_session_version(token.get("session_version"))
    current_version = _coerce_session_version(getattr(user, "session_version", None))
    if token_version is None or current_version is None:
        raise AuthenticationFailed(SESSION_REPLACED_DETAIL, code=SESSION_REPLACED_CODE)

    session_id = token.get("portal_session_id")
    if session_id is None:
        raise AuthenticationFailed(SESSION_REPLACED_DETAIL, code=SESSION_REPLACED_CODE)
    try:
        session = PortalSession.objects.get(pk=session_id, user=user)
    except PortalSession.DoesNotExist as exc:
        raise AuthenticationFailed(SESSION_REPLACED_DETAIL, code=SESSION_REPLACED_CODE) from exc
    if session.revoked_at:
        if session.revocation_reason == "new_login":
            raise AuthenticationFailed(SESSION_REPLACED_DETAIL, code=SESSION_REPLACED_CODE)
        raise AuthenticationFailed(SESSION_EXPIRED_DETAIL, code="session_expired")
    if session.session_version != current_version or token_version != current_version:
        raise AuthenticationFailed(SESSION_REPLACED_DETAIL, code=SESSION_REPLACED_CODE)

    now = timezone.now()
    if not session.remember_me and now - session.last_activity_at >= SESSION_IDLE_TIMEOUT:
        raise AuthenticationFailed(SESSION_EXPIRED_DETAIL, code="session_expired")
    if touch and now - session.last_activity_at >= SESSION_ACTIVITY_WRITE_INTERVAL:
        PortalSession.objects.filter(pk=session.pk, revoked_at__isnull=True).update(last_activity_at=now)
    return session


class SessionVersionJWTAuthentication(JWTAuthentication):
    """
    Enforces one active portal session per account.

    SimpleJWT tokens are otherwise stateless, so a previous browser remains valid after
    a new login. This guard makes the database session_version the source of truth.
    """

    def authenticate(self, request):
        self._touch_session = (
            request.path.endswith("/auth/activity/")
            or request.META.get("HTTP_X_PORTAL_USER_ACTIVITY") == "1"
        )
        return super().authenticate(request)

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        _validate_token_session(user, validated_token, touch=getattr(self, "_touch_session", False))
        return user
