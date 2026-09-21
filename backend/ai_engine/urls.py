from django.urls import path

from .views import (
    AdminAIModelListView,
    AdminAIModelTrainView,
    AdminAITrainingDataView,
    AdminAITrainingRecordView,
)


urlpatterns = [
    path("admin/ai/models/", AdminAIModelListView.as_view(), name="admin-ai-models"),
    path("admin/ai/models/train/", AdminAIModelTrainView.as_view(), name="admin-ai-model-train"),
    path("admin/ai/training-data/", AdminAITrainingDataView.as_view(), name="admin-ai-training-data"),
    path(
        "admin/ai/training-data/<int:pk>/",
        AdminAITrainingRecordView.as_view(),
        name="admin-ai-training-record",
    ),
]
