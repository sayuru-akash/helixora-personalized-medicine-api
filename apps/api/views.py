from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditEvent
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview

from .health import get_operations_health_status, get_public_health_status
from .permissions import IsClinicalApiAuthorized
from .serializers import (
	AuditEventSerializer,
	ClinicalReviewSerializer,
	GenomicInsightSerializer,
	PatientProfileSerializer,
	TreatmentRecommendationSerializer,
)


class HealthCheckView(APIView):
	permission_classes = []
	authentication_classes = []

	def get(self, request):
		return Response(get_public_health_status())


class OperationsHealthCheckView(APIView):
	permission_classes = [IsAdminUser]

	def get(self, request):
		return Response(get_operations_health_status())


class PatientProfileViewSet(viewsets.ModelViewSet):
	queryset = PatientProfile.objects.all()
	serializer_class = PatientProfileSerializer
	permission_classes = [IsClinicalApiAuthorized]
	clinical_write_roles = {'clinical_editor', 'clinical_admin'}


class GenomicInsightViewSet(viewsets.ModelViewSet):
	queryset = GenomicInsight.objects.select_related('patient').all()
	serializer_class = GenomicInsightSerializer
	permission_classes = [IsClinicalApiAuthorized]
	clinical_write_roles = {'clinical_editor', 'clinical_admin'}


class TreatmentRecommendationViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = TreatmentRecommendation.objects.select_related('patient', 'primary_genomic_insight').all()
	serializer_class = TreatmentRecommendationSerializer
	permission_classes = [IsClinicalApiAuthorized]


class ClinicalReviewViewSet(
	mixins.ListModelMixin,
	mixins.RetrieveModelMixin,
	mixins.UpdateModelMixin,
	viewsets.GenericViewSet,
):
	queryset = ClinicalReview.objects.select_related('recommendation', 'reviewer').all()
	serializer_class = ClinicalReviewSerializer
	permission_classes = [IsClinicalApiAuthorized]
	clinical_write_roles = {'clinical_reviewer', 'clinical_admin'}

	def perform_update(self, serializer):
		serializer.save(reviewer=self.request.user)


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = AuditEvent.objects.select_related('patient', 'recommendation', 'actor').all()
	serializer_class = AuditEventSerializer
	permission_classes = [IsClinicalApiAuthorized]
