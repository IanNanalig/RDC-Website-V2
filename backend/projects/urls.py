from django.urls import include, path
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register(r"projects", views.ProjectViewSet, basename="project")
router.register(r"employee/projects", views.EmployeeProjectViewSet, basename="employee-projects")
router.register(r"validator/projects", views.ValidatorProjectViewSet, basename="validator-projects")
router.register(r"admin/projects", views.AdminProjectViewSet, basename="admin-projects")
router.register(r"admin/users", views.AdminUserViewSet, basename="admin-users")
router.register(r"access-requests", views.AccessRequestViewSet, basename="access-requests")
router.register(r"password-reset-requests", views.PasswordResetRequestViewSet, basename="password-reset-requests")
router.register(r"project-revisions", views.ProjectRevisionViewSet, basename="project-revisions")
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
    path("public/events/", public_events_list, name="public-events"),
    path("public/events/<int:pk>/", public_events_detail, name="public-event-detail"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("admin/activity/", views.AdminActivityView.as_view(), name="admin-activity"),
    path("agency/activity/", views.AgencyActivityView.as_view(), name="agency-activity"),
    path("encoding-window/", views.EncodingWindowView.as_view(), name="encoding-window"),
    path("progress-update-window/", views.ProgressUpdateWindowView.as_view(), name="progress-update-window"),
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path("contact/", views.PublicContactView.as_view(), name="public-contact"),
    path("public-chat/ask/", views.PublicChatAskView.as_view(), name="public-chat-ask"),
    path("public-chat/feedback/", views.PublicChatFeedbackView.as_view(), name="public-chat-feedback"),
    path("public-chat/faq/", views.PublicChatFAQView.as_view(), name="public-chat-faq"),
    path("admin/chat/knowledge-gaps/", views.AdminChatKnowledgeGapView.as_view(), name="admin-chat-knowledge-gaps"),
    path("admin/chat/knowledge-gaps/<int:pk>/approve/", views.AdminChatKnowledgeGapApproveView.as_view(), name="admin-chat-knowledge-gap-approve"),
    path("admin/chat/knowledge-gaps/<int:pk>/reject/", views.AdminChatKnowledgeGapRejectView.as_view(), name="admin-chat-knowledge-gap-reject"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/setup-password/", views.SetupPasswordView.as_view(), name="setup-password"),
    path("auth/me/", views.MeView.as_view(), name="me"),
]
