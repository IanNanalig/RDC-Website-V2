"""Request-scoped fallback for meaningful authenticated actions without a domain audit event."""

import logging
from contextvars import ContextVar


_current_request = ContextVar("rdc_audit_request", default=None)
_recorded_users = ContextVar("rdc_audit_recorded_users", default=None)
logger = logging.getLogger(__name__)

ROLE_NAMES = {"admin", "validator", "staff", "employee", "content_editor"}
PASSIVE_POST_PATHS = {"/api/analytics/", "/api/token/refresh/"}


def current_audit_request():
    return _current_request.get()


def mark_audit_record(user_id, activity_id):
    recorded = _recorded_users.get()
    if recorded is not None and user_id is not None:
        recorded.setdefault(user_id, set()).add(activity_id)


class AuditActionMiddleware:
    """Record one safe fallback event for uncovered authenticated write requests.

    Specific UserActivity events take precedence. Bodies, query strings, tokens, and
    passwords are deliberately never copied into audit details. Automatic heartbeat
    and analytics requests are excluded to avoid filling the audit log with polling.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_token = _current_request.set(request)
        users_token = _recorded_users.set({})
        try:
            response = self.get_response(request)
            self._audit_uncovered_action(request, response)
            return response
        finally:
            _recorded_users.reset(users_token)
            _current_request.reset(request_token)

    def _audit_uncovered_action(self, request, response):
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return
        if not (request.path.startswith("/api/") or request.path.startswith("/admin/")):
            return
        if request.path in PASSIVE_POST_PATHS or request.path.rstrip("/").endswith("/heartbeat"):
            return
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return
        role = getattr(user, "role", "") or ("admin" if getattr(user, "is_superuser", False) else "")
        if role not in ROLE_NAMES:
            return
        from .models import UserActivity

        activity_ids = (_recorded_users.get() or {}).get(user.pk, set())
        route = getattr(request, "resolver_match", None)
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip_address = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR", "")
        try:
            if activity_ids and UserActivity.objects.filter(pk__in=activity_ids).exists():
                return
            UserActivity.objects.create(
                user=user,
                role=role,
                event="api_action_failed" if response.status_code >= 400 else "api_action",
                ip_address=ip_address[:64],
                details={
                    "method": request.method,
                    "path": request.path[:512],
                    "route": (getattr(route, "url_name", "") or "")[:120],
                    "status_code": response.status_code,
                },
            )
        except Exception:
            # An audit-storage problem must not turn a successful workflow into a 500.
            logger.exception("Could not record audit fallback for %s", request.path[:512])
