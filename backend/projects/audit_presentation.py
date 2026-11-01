"""Human-readable, non-destructive presentation helpers for audit records."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from django.db.models import Q


CATEGORY_LABELS = {
    "accounts_access": "Accounts & Access",
    "projects": "Projects",
    "reviews_validation": "Reviews & Validation",
    "agencies": "Agencies",
    "website_content": "Website & Content",
    "administration_security": "Administration & Security",
}

RESULT_LABELS = {
    "completed": "Completed",
    "pending": "Pending",
    "rejected": "Rejected",
    "blocked": "Blocked",
    "failed": "Failed",
}


@dataclass(frozen=True)
class AuditEventSpec:
    category: str
    action: str
    result: str = "completed"


def _specs(category: str, actions: dict[str, str], result: str = "completed") -> dict[str, AuditEventSpec]:
    return {event: AuditEventSpec(category, action, result) for event, action in actions.items()}


EVENT_SPECS: dict[str, AuditEventSpec] = {
    **_specs("accounts_access", {
        "login": "Signed in",
        "logout": "Signed out",
        "auth_password_setup": "Completed password setup",
        "registration_completed": "Completed account registration",
        "auth_reset_approve": "Approved a password reset request",
        "user_create": "Created a user account",
        "user_update": "Updated a user account",
        "user_status_changed": "Changed a user account status",
        "user_delete": "Deleted a user account",
        "profile_updated": "Updated a user profile",
        "profile_edit_approved": "Approved a profile edit request",
        "access_request_approved": "Approved an access request",
    }),
    **_specs("accounts_access", {
        "registration_invitation_sent": "Sent a registration invitation",
        "auth_reset_request": "Requested a password reset",
        "profile_edit_requested": "Requested permission to edit a profile",
    }, "pending"),
    **_specs("accounts_access", {
        "auth_reset_reject": "Rejected a password reset request",
        "profile_edit_rejected": "Rejected a profile edit request",
        "access_request_rejected": "Rejected an access request",
    }, "rejected"),
    **_specs("accounts_access", {"login_failed": "Attempted to sign in"}, "failed"),
    **_specs("projects", {
        "project_create": "Created a project",
        "project_update": "Updated a project",
        "project_delete": "Deleted a project",
        "project_archive": "Archived a project",
        "project_unarchive": "Restored an archived project",
        "project_comment": "Added a project comment",
        "project_revision_created": "Created a project revision",
        "project_revision_updated": "Updated a project revision",
        "supporting_document_uploaded": "Uploaded a supporting document",
        "supporting_document_removed": "Removed a supporting document",
        "public_summary_overridden": "Updated a project's public summary",
    }),
    **_specs("projects", {
        "project_submit": "Submitted a project for review",
        "project_revision_submitted": "Submitted a project revision for review",
    }, "pending"),
    **_specs("projects", {
        "supporting_document_extraction_failed": "Could not process a supporting document",
    }, "failed"),
    **_specs("reviews_validation", {
        "project_approve": "Approved a project",
        "validator_reviewed": "Completed a project review",
        "validator_endorsed": "Endorsed a project",
        "project_revision_reviewed": "Reviewed a project revision",
        "project_revision_endorsed": "Endorsed a project revision",
        "priority_analysis_run": "Ran a priority analysis",
        "priority_analysis_reused": "Reused a priority analysis",
        "priority_analysis_confirmed": "Confirmed a priority analysis",
        "priority_analysis_overridden": "Overrode a priority analysis",
        "document_assessment_completed": "Completed a document assessment",
        "document_assessment_overridden": "Overrode a document assessment",
    }),
    **_specs("reviews_validation", {"validator_draft": "Saved a draft project review"}, "pending"),
    **_specs("reviews_validation", {
        "project_reject": "Rejected a project",
        "project_revision_rejected": "Rejected a project revision",
    }, "rejected"),
    **_specs("website_content", {
        "cms_event_created": "Created a public event",
        "cms_event_updated": "Updated a public event",
        "cms_event_published": "Published a public event",
        "cms_event_archived": "Archived a public event",
        "cms_event_unarchived": "Restored a public event as a draft",
        "cms_event_deleted": "Deleted a public event",
        "cms_content_created": "Created website content",
        "cms_content_updated": "Updated website content",
        "cms_content_published": "Published website content",
        "cms_content_archived": "Archived website content",
        "cms_content_restored": "Restored website content as a draft",
        "cms_section_lock_acquired": "Started editing a website section",
        "cms_section_lock_released": "Stopped editing a website section",
        "cms_section_lock_overridden": "Took over a website section edit lock",
        "cms_form_lock_acquired": "Started editing a contributor form",
        "cms_form_lock_released": "Stopped editing a contributor form",
        "cms_form_lock_overridden": "Took over a contributor form edit lock",
        "chat_knowledge_approved": "Approved public chatbot knowledge",
        "chat_content_updated": "Updated public chatbot content",
    }),
    **_specs("website_content", {
        "cms_event_submitted": "Submitted a public event for review",
        "cms_content_submitted": "Submitted website content for review",
        "cms_section_access_requested": "Requested access to a website section",
        "cms_form_access_requested": "Requested access to a contributor form",
    }, "pending"),
    **_specs("website_content", {
        "cms_event_rejected": "Rejected a public event",
        "cms_content_rejected": "Rejected website content",
        "chat_knowledge_rejected": "Rejected public chatbot knowledge",
    }, "rejected"),
    **_specs("website_content", {
        "cms_section_lock_blocked": "Could not edit a locked website section",
        "cms_form_lock_blocked": "Could not edit a locked contributor form",
    }, "blocked"),
    **_specs("administration_security", {
        "encoding_window_updated": "Updated the project encoding window",
        "progress_window_updated": "Updated the progress reporting window",
        "notification_read": "Marked a notification as read",
        "notification_read_all": "Marked all notifications as read",
    }),
}


GENERIC_ACTION_SPECS: dict[str, AuditEventSpec] = {
    "project_collaborators_updated": AuditEventSpec("projects", "Updated project collaborators"),
    "batch_project_archive": AuditEventSpec("projects", "Archived a batch of projects"),
    "automatic_form_migration": AuditEventSpec("projects", "Migrated a project to the current form"),
    "contributor_form_migration": AuditEventSpec("projects", "Migrated a project form"),
    "batch_form_migration": AuditEventSpec("projects", "Migrated a batch of project forms"),
    "agency_created": AuditEventSpec("agencies", "Created an agency"),
    "agency_updated": AuditEventSpec("agencies", "Updated an agency"),
    "agency_archived": AuditEventSpec("agencies", "Archived an agency"),
    "agency_restored": AuditEventSpec("agencies", "Restored an agency"),
    "batch_registration_invitation": AuditEventSpec("accounts_access", "Sent registration invitations"),
    "password_reset_otp_verify": AuditEventSpec("accounts_access", "Verified a password reset code", "failed"),
    "password_reset_otp_verified": AuditEventSpec("accounts_access", "Verified a password reset code"),
    "otp_requested": AuditEventSpec("accounts_access", "Requested a verification code", "pending"),
    "otp_password_reset": AuditEventSpec("accounts_access", "Reset an account password"),
    "data_export": AuditEventSpec("administration_security", "Exported administrative data"),
    "ai_model_trained": AuditEventSpec("administration_security", "Trained an AI scoring model"),
    "ai_training_record_updated": AuditEventSpec("administration_security", "Updated an AI training record"),
    "publish": AuditEventSpec("website_content", "Attempted to publish website content"),
}


ROUTE_SPECS: dict[str, AuditEventSpec] = {
    "auth-activity": AuditEventSpec("accounts_access", "Refreshed an active portal session"),
    "notifications-mark-all-read": AuditEventSpec("administration_security", "Marked all notifications as read"),
    "admin-users-set-active": AuditEventSpec("accounts_access", "Changed a user account status"),
    "admin-users-detail": AuditEventSpec("accounts_access", "Updated a user profile"),
    "admin-export-download": AuditEventSpec("administration_security", "Exported administrative data"),
    "admin-cms-module-action": AuditEventSpec("website_content", "Updated a website content workflow"),
    "admin-ai-model-train": AuditEventSpec("administration_security", "Trained an AI scoring model"),
    "admin-ai-training-record": AuditEventSpec("administration_security", "Updated an AI training record"),
}


SENSITIVE_PARTS = {
    "password", "passcode", "token", "secret", "authorization", "cookie", "otp",
    "hash", "digest", "session", "request_body", "query", "api_key", "apikey",
}


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _is_sensitive_key(key: Any) -> bool:
    normalized = _normalized_key(key)
    return any(part in normalized for part in SENSITIVE_PARTS)


def sanitize_audit_details(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Return a bounded, JSON-safe copy with credentials and session data redacted."""
    if key and _is_sensitive_key(key):
        return "[redacted]"
    if depth >= 6:
        return "[truncated]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (child_key, child_value) in enumerate(value.items()):
            if index >= 50:
                result["additional_fields"] = "[truncated]"
                break
            child_key_text = str(child_key)[:120]
            if child_key_text in {"body", "payload", "query", "headers"}:
                result[child_key_text] = "[redacted]"
                continue
            if child_key_text in {"before", "after"} and _is_sensitive_key(value.get("field", "")):
                result[child_key_text] = "[redacted]"
                continue
            result[child_key_text] = sanitize_audit_details(
                child_value, key=child_key_text, depth=depth + 1,
            )
        return result
    if isinstance(value, (list, tuple)):
        result = [sanitize_audit_details(item, depth=depth + 1) for item in list(value)[:50]]
        if len(value) > 50:
            result.append("[truncated]")
        return result
    if isinstance(value, str):
        return value if len(value) <= 500 else f"{value[:497]}..."
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]


def actor_label(activity: Any) -> str:
    if getattr(activity, "actor_full_name", ""):
        full_name = activity.actor_full_name.strip()
        if full_name.casefold() == "unauthenticated":
            return "Unauthenticated user"
        return full_name
    user = getattr(activity, "user", None)
    if user is not None:
        name = (user.get_full_name() or user.username or "").strip()
        if name:
            return name
    username = (getattr(activity, "actor_username", "") or "").strip()
    if username:
        if username.casefold() == "unauthenticated":
            return "Unauthenticated user"
        return username
    if (getattr(activity, "role", "") or "").casefold() == "unauthenticated":
        return "Unauthenticated user"
    return "System"


def target_label(activity: Any) -> str:
    project_title = (getattr(activity, "project_title_snapshot", "") or "").strip()
    project = getattr(activity, "project", None)
    if not project_title and project is not None:
        project_title = str(getattr(project, "title", "") or getattr(project, "name", "") or "").strip()
    if project_title:
        return project_title[:160]

    details = activity.details if isinstance(getattr(activity, "details", None), dict) else {}
    for key in (
        "target_label", "title", "email", "attempted_email", "name", "agency_name", "agency_code",
        "slug", "key", "filename", "reference", "version",
    ):
        value = details.get(key)
        if isinstance(value, str) and value.strip() and not _is_sensitive_key(key):
            return value.strip()[:160]

    id_labels = (
        ("target_user_id", "User account"), ("agency_id", "Agency"), ("form_id", "Contributor form"),
        ("event_id", "Event"), ("training_record_id", "Training record"), ("project_id", "Project"),
        ("request_id", "Request"), ("id", "Content"),
    )
    for key, label in id_labels:
        value = details.get(key)
        if value is not None and str(value).strip():
            return f"{label} #{str(value).strip()[:40]}"

    route_parameters = details.get("route_parameters")
    if isinstance(route_parameters, dict):
        for key, label in (("user_id", "User account"), ("project_id", "Project"), ("pk", "Record"), ("id", "Record")):
            value = route_parameters.get(key)
            if value is not None and str(value).strip():
                return f"{label} #{str(value).strip()[:40]}"

    path = str(details.get("path") or "")
    path_match = re.search(r"/(?:users|projects|agencies|events|forms)/(\d+)(?:/|$)", path)
    if path_match:
        return f"Record #{path_match.group(1)}"
    return "Target not recorded"


def _generic_spec(activity: Any) -> AuditEventSpec | None:
    details = activity.details if isinstance(getattr(activity, "details", None), dict) else {}
    for key in ("action", "operation"):
        value = _normalized_key(details.get(key))
        if value in GENERIC_ACTION_SPECS:
            return GENERIC_ACTION_SPECS[value]
    route = str(details.get("route") or "").strip()
    return ROUTE_SPECS.get(route)


def presentation_for(activity: Any) -> dict[str, str]:
    event = str(getattr(activity, "event", "") or "")
    if event in {"api_action", "api_action_failed"}:
        spec = _generic_spec(activity) or AuditEventSpec(
            "administration_security",
            "Performed an administrative action" if event == "api_action" else "Could not complete an administrative action",
            "completed" if event == "api_action" else "failed",
        )
        if event == "api_action_failed" and spec.result not in {"blocked", "rejected"}:
            details = activity.details if isinstance(getattr(activity, "details", None), dict) else {}
            result = "blocked" if details.get("status_code") in {401, 403, 423} else "failed"
            spec = AuditEventSpec(spec.category, spec.action, result)
    else:
        spec = EVENT_SPECS.get(event) or AuditEventSpec(
            "administration_security", "Recorded a system activity",
        )

    actor = actor_label(activity)
    target = target_label(activity)
    description = f"{actor} {spec.action[0].lower() + spec.action[1:]}"
    if target != "Target not recorded":
        description += f" — {target}"
    description += "."
    return {
        "category": spec.category,
        "category_label": CATEGORY_LABELS[spec.category],
        "action_label": spec.action,
        "description": description,
        "target_label": target,
        "result": spec.result,
        "result_label": RESULT_LABELS[spec.result],
    }


def category_events(category: str) -> set[str]:
    return {event for event, spec in EVENT_SPECS.items() if spec.category == category}


def generic_values_for_category(category: str) -> tuple[set[str], set[str]]:
    actions = {value for value, spec in GENERIC_ACTION_SPECS.items() if spec.category == category}
    routes = {value for value, spec in ROUTE_SPECS.items() if spec.category == category}
    return actions, routes


def category_query(category: str) -> Q:
    if category not in CATEGORY_LABELS:
        return Q(pk__in=[])
    events = category_events(category)
    actions, routes = generic_values_for_category(category)
    query = Q(event__in=events)
    if actions:
        query |= Q(event__in={"api_action", "api_action_failed"}, details__action__in=actions)
        query |= Q(event__in={"api_action", "api_action_failed"}, details__operation__in=actions)
    if routes:
        query |= Q(event__in={"api_action", "api_action_failed"}, details__route__in=routes)
    if category == "administration_security":
        known_actions = set(GENERIC_ACTION_SPECS)
        known_routes = set(ROUTE_SPECS)
        query |= (
            Q(event__in={"api_action", "api_action_failed"})
            & (Q(details__action__isnull=True) | ~Q(details__action__in=known_actions))
            & (Q(details__operation__isnull=True) | ~Q(details__operation__in=known_actions))
            & (Q(details__route__isnull=True) | ~Q(details__route__in=known_routes))
        )
    return query


def result_query(result: str) -> Q:
    if result not in RESULT_LABELS:
        return Q(pk__in=[])
    events = {event for event, spec in EVENT_SPECS.items() if spec.result == result}
    query = Q(event__in=events)
    if result == "failed":
        query |= Q(event="api_action_failed") & (
            Q(details__status_code__isnull=True) | ~Q(details__status_code__in={401, 403, 423})
        )
    elif result == "blocked":
        query |= Q(event="api_action_failed", details__status_code__in={401, 403, 423})
    generic_actions = {value for value, spec in GENERIC_ACTION_SPECS.items() if spec.result == result}
    generic_routes = {value for value, spec in ROUTE_SPECS.items() if spec.result == result}
    generic_query = Q(details__action__in=generic_actions) | Q(details__operation__in=generic_actions)
    if generic_routes:
        generic_query |= Q(details__route__in=generic_routes)
    if generic_actions or generic_routes:
        query |= Q(event="api_action") & generic_query
    if result == "completed":
        known_actions = set(GENERIC_ACTION_SPECS)
        known_routes = set(ROUTE_SPECS)
        query |= (
            Q(event="api_action")
            & (Q(details__action__isnull=True) | ~Q(details__action__in=known_actions))
            & (Q(details__operation__isnull=True) | ~Q(details__operation__in=known_actions))
            & (Q(details__route__isnull=True) | ~Q(details__route__in=known_routes))
        )
    return query


def matching_event_terms(search: str) -> tuple[set[str], set[str], set[str]]:
    needle = search.casefold().strip()
    events = {
        event for event, spec in EVENT_SPECS.items()
        if needle in spec.action.casefold() or needle in CATEGORY_LABELS[spec.category].casefold()
        or needle in RESULT_LABELS[spec.result].casefold()
    }
    actions = {
        value for value, spec in GENERIC_ACTION_SPECS.items()
        if needle in spec.action.casefold() or needle in CATEGORY_LABELS[spec.category].casefold()
    }
    routes = {
        value for value, spec in ROUTE_SPECS.items()
        if needle in spec.action.casefold() or needle in CATEGORY_LABELS[spec.category].casefold()
    }
    return events, actions, routes
