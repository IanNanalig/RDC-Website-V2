from django.contrib import admin
from .models import (
    AuditTrail,
    EditRequest,
    Notification,
    PriorityRuleSet,
    Project,
    ProjectPriorityAnalysis,
    ProjectPriorityConfirmation,
    PublicEvent,
    SystemSetting,
    User,
    UserActivity,
)

admin.site.register(User)
admin.site.register(Project)
admin.site.register(EditRequest)
admin.site.register(SystemSetting)
admin.site.register(Notification)
admin.site.register(PriorityRuleSet)
admin.site.register(ProjectPriorityAnalysis)
admin.site.register(ProjectPriorityConfirmation)
admin.site.register(PublicEvent)


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(UserActivity, ReadOnlyAuditAdmin)
admin.site.register(AuditTrail, ReadOnlyAuditAdmin)
