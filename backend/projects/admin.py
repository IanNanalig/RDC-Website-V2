from django.contrib import admin
from .models import AuditTrail, EditRequest, Project, SystemSetting, User, UserActivity

admin.site.register(User)
admin.site.register(Project)
admin.site.register(EditRequest)
admin.site.register(AuditTrail)
admin.site.register(SystemSetting)
admin.site.register(UserActivity)
