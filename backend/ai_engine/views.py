from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from projects.permissions import IsAdmin

from .models import AIModelVersion, AITrainingRecord
from .serializers import AIModelVersionSerializer, AITrainingRecordSerializer
from .services import (
    set_training_record_eligibility,
    sync_all_training_records,
    train_new_model,
    training_dataset_summary,
)


class AdminAIModelListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        models = AIModelVersion.objects.select_related("trained_by").all()[:50]
        return Response({
            "results": AIModelVersionSerializer(models, many=True).data,
            "dataset": training_dataset_summary(sync=True),
        })


class AdminAIModelTrainView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request):
        try:
            model = train_new_model(request.user)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "detail": (
                    f"Model {model.version} is now active. It learned from {model.sample_count} "
                    "distinct validator-confirmed projects."
                ),
                "model": AIModelVersionSerializer(model).data,
                "dataset": training_dataset_summary(),
            },
            status=status.HTTP_201_CREATED,
        )


class AdminAITrainingDataView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def get(self, request):
        sync_all_training_records()
        records = AITrainingRecord.objects.select_related(
            "project", "rule_set", "confirmation__validator"
        ).order_by("-confirmation__created_at", "-id")[:500]
        return Response({
            "results": AITrainingRecordSerializer(records, many=True).data,
            "summary": training_dataset_summary(),
        })


class AdminAITrainingRecordView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def patch(self, request, pk):
        try:
            record = AITrainingRecord.objects.select_related(
                "project", "rule_set", "confirmation__validator"
            ).get(pk=pk)
        except AITrainingRecord.DoesNotExist:
            return Response({"detail": "Training record not found."}, status=status.HTTP_404_NOT_FOUND)
        if "is_eligible" not in request.data:
            return Response({"detail": "is_eligible is required."}, status=status.HTTP_400_BAD_REQUEST)
        raw_eligible = request.data.get("is_eligible")
        if not isinstance(raw_eligible, bool):
            return Response({"detail": "is_eligible must be true or false."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            set_training_record_eligibility(
                record,
                request.user,
                raw_eligible,
                request.data.get("exclusion_reason"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            "record": AITrainingRecordSerializer(record).data,
            "summary": training_dataset_summary(),
        })
