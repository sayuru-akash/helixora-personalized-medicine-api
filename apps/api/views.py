from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit.models import AuditEvent
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview

from .permissions import IsAuthenticatedReadWrite
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
		return Response(
			{
				'status': 'ok',
				'service': 'helixora-api',
				'framework': 'django-drf-celery',
			}
		)


class PatientProfileViewSet(viewsets.ModelViewSet):
	queryset = PatientProfile.objects.all()
	serializer_class = PatientProfileSerializer
	permission_classes = [IsAuthenticatedReadWrite]


class GenomicInsightViewSet(viewsets.ModelViewSet):
	queryset = GenomicInsight.objects.select_related('patient').all()
	serializer_class = GenomicInsightSerializer
	permission_classes = [IsAuthenticatedReadWrite]


class TreatmentRecommendationViewSet(viewsets.ModelViewSet):
	queryset = TreatmentRecommendation.objects.select_related('patient', 'primary_genomic_insight').all()
	serializer_class = TreatmentRecommendationSerializer
	permission_classes = [IsAuthenticatedReadWrite]


class ClinicalReviewViewSet(viewsets.ModelViewSet):
	queryset = ClinicalReview.objects.select_related('recommendation', 'reviewer').all()
	serializer_class = ClinicalReviewSerializer
	permission_classes = [IsAuthenticatedReadWrite]


class AuditEventViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = AuditEvent.objects.select_related('patient', 'recommendation', 'actor').all()
	serializer_class = AuditEventSerializer
	permission_classes = [IsAuthenticatedReadWrite]
