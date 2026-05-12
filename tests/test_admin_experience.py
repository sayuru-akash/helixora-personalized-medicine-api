from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview


class AdminExperienceTests(TestCase):
	def setUp(self):
		User = get_user_model()
		self.admin_user = User.objects.create_superuser(
			username='admin',
			email='admin@example.com',
			password='secure-pass-123',
		)
		self.client.force_login(self.admin_user)

		self.patient = PatientProfile.objects.create(external_id='P-ADMIN-001', consent_status='granted')
		self.genomic_insight = GenomicInsight.objects.create(
			patient=self.patient,
			gene_symbol='EGFR',
			variant='L858R',
			clinical_significance=GenomicInsight.Significance.HIGH,
		)
		self.recommendation = TreatmentRecommendation.objects.create(
			patient=self.patient,
			primary_genomic_insight=self.genomic_insight,
			title='Targeted EGFR strategy',
			summary='Decision support summary',
			rationale='Clinical rationale with explainability notes.',
		)
		self.review = ClinicalReview.objects.create(
			recommendation=self.recommendation,
			reviewer=self.admin_user,
			review_notes='Needs confirmation in tumor board.',
		)
		self.audit_event = AuditEvent.objects.create(
			event_type=AuditEvent.EventType.RECOMMENDATION_CREATED,
			patient=self.patient,
			recommendation=self.recommendation,
			actor=self.admin_user,
			correlation_id='corr-admin-001',
		)

	def test_admin_site_branding_visible_on_index(self):
		response = self.client.get(reverse('admin:index'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Helixora Clinical Operations')
		self.assertContains(response, 'Clinical Decision Support Administration')
		self.assertContains(response, 'admin/helixora_admin.css')

	def test_key_domain_admin_changelists_are_accessible(self):
		urls = [
			reverse('admin:patients_patientprofile_changelist'),
			reverse('admin:genomics_genomicinsight_changelist'),
			reverse('admin:recommendations_treatmentrecommendation_changelist'),
			reverse('admin:reviews_clinicalreview_changelist'),
			reverse('admin:audit_auditevent_changelist'),
		]

		for url in urls:
			response = self.client.get(url)
			self.assertEqual(response.status_code, 200)

	def test_audit_admin_is_read_only(self):
		audit_admin = admin.site._registry[AuditEvent]
		request = self.client.request().wsgi_request
		request.user = self.admin_user

		self.assertFalse(audit_admin.has_add_permission(request))
		self.assertFalse(audit_admin.has_delete_permission(request, self.audit_event))
		self.assertIn('correlation_id', audit_admin.search_fields)
