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

public_projects_list = views.PublicProjectsViewSet.as_view({"get": "list"})
public_projects_detail = views.PublicProjectsViewSet.as_view({"get": "retrieve"})

urlpatterns = [
    path("", include(router.urls)),
    path("public/projects/", public_projects_list, name="public-projects"),
    path("public/projects/<int:pk>/", public_projects_detail, name="public-project-detail"),
    path("public/projects/stats/", views.PublicProjectsStatsView.as_view(), name="public-project-stats"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("admin/activity/", views.AdminActivityView.as_view(), name="admin-activity"),
    path("agency/activity/", views.AgencyActivityView.as_view(), name="agency-activity"),
    path("encoding-window/", views.EncodingWindowView.as_view(), name="encoding-window"),
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),
    path("contact/", views.PublicContactView.as_view(), name="public-contact"),
    path("public-chat/ask/", views.PublicChatAskView.as_view(), name="public-chat-ask"),
    path("public-chat/faq/", views.PublicChatFAQView.as_view(), name="public-chat-faq"),
    path("auth/login/", views.LoginView.as_view(), name="login"),
    path("auth/setup-password/", views.SetupPasswordView.as_view(), name="setup-password"),
    path("auth/me/", views.MeView.as_view(), name="me"),
]
