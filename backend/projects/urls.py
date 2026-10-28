from django.urls import include, path
from rest_framework import routers
from . import views
from .admin_exports import AdminExportCountView, AdminExportDownloadView, AdminExportOptionsView
from .project_concerns import (
    AdminProjectConcernDetailView,
    AdminProjectConcernEvidenceDownloadView,
    AdminProjectConcernListView,
    AdminProjectConcernRetryView,
    PublicProjectConcernOptionsView,
    PublicProjectConcernSubmitView,
)

router = routers.DefaultRouter()
router.register(r"projects", views.ProjectViewSet, basename="project")
router.register(r"employee/projects", views.EmployeeProjectViewSet, basename="employee-projects")
router.register(r"validator/projects", views.ValidatorProjectViewSet, basename="validator-projects")
router.register(r"admin/projects", views.AdminProjectViewSet, basename="admin-projects")
router.register(r"admin/users", views.AdminUserViewSet, basename="admin-users")
router.register(r"admin/agencies", views.AdminAgencyViewSet, basename="admin-agencies")
router.register(r"access-requests", views.AccessRequestViewSet, basename="access-requests")
router.register(r"project-revisions", views.ProjectRevisionViewSet, basename="project-revisions")
router.register(r"project-supporting-documents", views.ProjectSupportingDocumentViewSet, basename="project-supporting-documents")
router.register(r"notifications", views.NotificationViewSet, basename="notifications")
router.register(r"admin/events", views.AdminEventViewSet, basename="admin-events")

public_projects_list = views.PublicProjectsViewSet.as_view({"get": "list"})
public_projects_detail = views.PublicProjectsViewSet.as_view({"get": "retrieve"})
public_events_list = views.PublicEventViewSet.as_view({"get": "list"})
public_events_detail = views.PublicEventViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("", include(router.urls)),
    path("health/", views.HealthCheckView.as_view(), name="health-check"),
    path("public/projects/", public_projects_list, name="public-projects"),
    path("public/projects/<int:pk>/", public_projects_detail, name="public-project-detail"),
    path("public/projects/stats/", views.PublicProjectsStatsView.as_view(), name="public-project-stats"),
    path("public/project-concerns/options/", PublicProjectConcernOptionsView.as_view(), name="public-project-concern-options"),
    path("public/project-concerns/", PublicProjectConcernSubmitView.as_view(), name="public-project-concern-submit"),
    path("public/events/", public_events_list, name="public-events"),
    path("public/events/<int:pk>/", public_events_detail, name="public-event-detail"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("admin/activity/", views.AdminActivityView.as_view(), name="admin-activity"),
    path("admin/users/batch-invitations/options/", views.BatchInvitationOptionsView.as_view(), name="batch-invitation-options"),
    path("admin/users/batch-invitations/preview/", views.BatchInvitationPreviewView.as_view(), name="batch-invitation-preview"),
    path("admin/users/batch-invitations/send/", views.BatchInvitationSendView.as_view(), name="batch-invitation-send"),
    path("admin/exports/options/", AdminExportOptionsView.as_view(), name="admin-export-options"),
    path("admin/exports/count/", AdminExportCountView.as_view(), name="admin-export-count"),
    path("admin/exports/download/", AdminExportDownloadView.as_view(), name="admin-export-download"),
    path("admin/project-concerns/", AdminProjectConcernListView.as_view(), name="admin-project-concern-list"),
    path("admin/project-concerns/<str:reference>/", AdminProjectConcernDetailView.as_view(), name="admin-project-concern-detail"),
    path("admin/project-concerns/<str:reference>/retry/", AdminProjectConcernRetryView.as_view(), name="admin-project-concern-retry"),
    path("admin/project-concerns/<str:reference>/evidence/<int:evidence_id>/download/", AdminProjectConcernEvidenceDownloadView.as_view(), name="admin-project-concern-evidence-download"),
    path("agency/activity/", views.AgencyActivityView.as_view(), name="agency-activity"),
    path("encoding-window/", views.EncodingWindowView.as_view(), name="encoding-window"),
    path("progress-update-window/", views.ProgressUpdateWindowView.as_view(), name="progress-update-window"),
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path("contact/", views.PublicContactView.as_view(), name="public-contact"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/logout/", views.LogoutView.as_view(), name="logout"),
    path("auth/activity/", views.PortalSessionActivityView.as_view(), name="auth-activity"),
    path("auth/setup-password/", views.SetupPasswordView.as_view(), name="setup-password"),
    path("auth/password-reset/request/", views.PasswordResetOTPRequestView.as_view(), name="password-reset-request"),
    path("auth/password-reset/verify/", views.PasswordResetOTPVerifyView.as_view(), name="password-reset-verify"),
    path("auth/password-reset/complete/", views.PasswordResetOTPCompleteView.as_view(), name="password-reset-complete"),
    path("auth/me/", views.MeView.as_view(), name="me"),
    path("profile/", views.ProfileView.as_view(), name="profile-self"),
    path("profile/edit-requests/", views.ProfileEditRequestView.as_view(), name="profile-edit-requests"),
    path("admin/profiles/<int:user_id>/", views.ProfileView.as_view(), name="admin-profile-detail"),
    path("admin/profile-edit-requests/", views.AdminProfileEditRequestView.as_view(), name="admin-profile-edit-requests"),
    path("admin/profile-edit-requests/<int:request_id>/<str:decision>/", views.AdminProfileEditDecisionView.as_view(), name="admin-profile-edit-decision"),
]
