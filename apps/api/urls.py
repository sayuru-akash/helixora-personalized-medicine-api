from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AuditEventViewSet,
    ClinicalReviewViewSet,
    GenomicInsightViewSet,
    HealthCheckView,
    OperationsHealthCheckView,
    PatientProfileViewSet,
    TreatmentRecommendationViewSet,
)


router = DefaultRouter()
router.register('patients', PatientProfileViewSet, basename='patient-profile')
router.register('genomics', GenomicInsightViewSet, basename='genomic-insight')
router.register('recommendations', TreatmentRecommendationViewSet, basename='treatment-recommendation')
router.register('reviews', ClinicalReviewViewSet, basename='clinical-review')
router.register('audit-events', AuditEventViewSet, basename='audit-event')


urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health-check'),
    path('ops/health/', OperationsHealthCheckView.as_view(), name='operations-health-check'),
    path('', include(router.urls)),
]