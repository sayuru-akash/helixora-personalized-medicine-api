from django.views.generic import FormView, TemplateView

from apps.ai.providers import get_provider_status
from apps.ai.workflow import run_recommendation_workflow
from apps.api.health import get_health_status
from apps.api.forms import RecommendationWorkspaceForm
from apps.audit.models import AuditEvent
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview


class LandingPageView(TemplateView):
	template_name = 'frontend/index.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['health'] = get_health_status()
		context['experience_status'] = {
			'headline': 'Workspace available',
			'summary': 'Clinical recommendation drafting, review workflow, and audit tracking are ready.',
		}
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
		context['provider_status'] = get_provider_status()
		return context


class RecommendationWorkspaceView(FormView):
	template_name = 'frontend/workspace.html'
	form_class = RecommendationWorkspaceForm

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context['health'] = get_health_status()
		context['experience_status'] = {
			'headline': 'Ready for clinician-guided drafting',
			'summary': 'Enter patient and genomic context to generate a structured, reviewable recommendation draft.',
		}
		context['latest_recommendations'] = TreatmentRecommendation.objects.select_related(
			'patient', 'primary_genomic_insight'
		)[:5]
		context['latest_audit_events'] = AuditEvent.objects.select_related('patient', 'recommendation')[:6]
		context['provider_status'] = get_provider_status()
		context['full_width_fields'] = self.form_class.FULL_WIDTH_FIELDS
		return context

	def form_valid(self, form):
		result = run_recommendation_workflow(
			patient_data=form.get_patient_payload(),
			genomic_data=form.get_genomic_payload(),
			actor=self.request.user if self.request.user.is_authenticated else None,
			correlation_id=getattr(self.request, 'correlation_id', ''),
		)
		context = self.get_context_data(form=form)
		context['workflow_result'] = result
		return self.render_to_response(context)