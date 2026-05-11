from django.views.generic import TemplateView

from apps.api.health import get_health_status
from apps.audit.models import AuditEvent
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview


class LandingPageView(TemplateView):
	template_name = 'frontend/index.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['health'] = get_health_status()
		context['stats'] = {
			'patients': PatientProfile.objects.count(),
			'recommendations': TreatmentRecommendation.objects.count(),
			'pending_reviews': ClinicalReview.objects.filter(
				decision=ClinicalReview.Decision.NEEDS_REVIEW
			).count(),
			'audit_events': AuditEvent.objects.count(),
		}
		context['latest_recommendations'] = TreatmentRecommendation.objects.select_related('patient')[:5]
		context['latest_audit_events'] = AuditEvent.objects.select_related('patient', 'recommendation')[:6]
		return context