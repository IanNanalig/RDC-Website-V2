from django.contrib import admin

from .models import (
    AIModelTrainingRecord,
    AIModelVersion,
    AIProjectAnalysis,
    AISimilarProject,
    AITrainingRecord,
)


admin.site.register(AITrainingRecord)
admin.site.register(AIModelVersion)
admin.site.register(AIModelTrainingRecord)
admin.site.register(AIProjectAnalysis)
admin.site.register(AISimilarProject)
