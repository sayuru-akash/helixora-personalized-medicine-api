from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.views.generic import FormView, TemplateView

from apps.ai.workflow import run_recommendation_workflow
from apps.api.forms import RecommendationWorkspaceForm
from apps.audit.models import AuditEvent
from apps.recommendations.models import TreatmentRecommendation


CLINICAL_WORKSPACE_ROLES = {'clinical_editor', 'clinical_admin'}


def user_can_access_clinical_workspace(user) -> bool:
	if not user or not user.is_authenticated:
		return False
	if user.is_superuser:
		return True
	if user.groups.filter(name__in=CLINICAL_WORKSPACE_ROLES).exists():
		return True
	return user.has_perm('patients.add_patientprofile') and user.has_perm('recommendations.view_treatmentrecommendation')


def user_has_clinical_admin_scope(user) -> bool:
	return bool(
		user
		and user.is_authenticated
		and (user.is_superuser or user.groups.filter(name='clinical_admin').exists())
	)


class LandingPageView(TemplateView):
	template_name = 'frontend/index.html'


class RecommendationWorkspaceView(LoginRequiredMixin, UserPassesTestMixin, FormView):
	template_name = 'frontend/workspace.html'
	form_class = RecommendationWorkspaceForm
	raise_exception = False

	def test_func(self):
		return user_can_access_clinical_workspace(self.request.user)

	def handle_no_permission(self):
		if self.request.user.is_authenticated:
			raise PermissionDenied('Clinical workspace access requires an authorized clinical role.')
		return super().handle_no_permission()

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		latest_recommendations = TreatmentRecommendation.objects.select_related(
			'patient', 'primary_genomic_insight'
		)
		latest_audit_events = AuditEvent.objects.select_related('patient', 'recommendation')
		if not user_has_clinical_admin_scope(self.request.user):
			latest_recommendations = latest_recommendations.filter(patient__authorized_users=self.request.user)
			latest_audit_events = latest_audit_events.filter(
				patient__authorized_users=self.request.user
			)
		context['latest_recommendations'] = latest_recommendations[:5]
		context['latest_audit_events'] = latest_audit_events[:6]
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
