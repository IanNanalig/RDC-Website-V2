from django.contrib import admin
from .models import (
    AuditTrail,
    EditRequest,
    PriorityRuleSet,
    Project,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    PublicEvent,
    PublicPageContent,
    SystemSetting,
    User,
    UserActivity,
)

admin.site.register(User)
admin.site.register(Project)
admin.site.register(EditRequest)
admin.site.register(AuditTrail)
admin.site.register(SystemSetting)
admin.site.register(UserActivity)
admin.site.register(PriorityRuleSet)
admin.site.register(ProjectPriorityAnalysis)
admin.site.register(ProjectPriorityConfirmation)
admin.site.register(PublicEvent)
admin.site.register(PublicPageContent)
