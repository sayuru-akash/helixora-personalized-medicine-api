from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
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

	def test_patient_related_admin_querysets_are_patient_scoped_for_non_admin_staff(self):
		User = get_user_model()
		staff_user = User.objects.create_user(
			username='scoped-staff',
			email='scoped-staff@example.com',
			password='secure-pass-123',
			is_staff=True,
		)
		for codename in (
			'view_patientprofile',
			'view_genomicinsight',
			'view_treatmentrecommendation',
			'view_clinicalreview',
			'view_auditevent',
		):
			staff_user.user_permissions.add(Permission.objects.get(codename=codename))

		assigned_patient = PatientProfile.objects.create(external_id='P-ADMIN-ASSIGNED', consent_status='granted')
		assigned_patient.authorized_users.add(staff_user)
		assigned_recommendation = TreatmentRecommendation.objects.create(
			patient=assigned_patient,
			title='Assigned admin recommendation',
			summary='Assigned',
			rationale='Assigned',
		)
		assigned_review = ClinicalReview.objects.create(recommendation=assigned_recommendation)
		assigned_audit = AuditEvent.objects.create(
			event_type=AuditEvent.EventType.RECOMMENDATION_CREATED,
			patient=assigned_patient,
			recommendation=assigned_recommendation,
		)

		request = self.client.request().wsgi_request
		request.user = staff_user

		self.assertEqual(list(admin.site._registry[PatientProfile].get_queryset(request)), [assigned_patient])
		self.assertNotIn(self.genomic_insight, admin.site._registry[GenomicInsight].get_queryset(request))
		self.assertEqual(
			list(admin.site._registry[TreatmentRecommendation].get_queryset(request)),
			[assigned_recommendation],
		)
		self.assertEqual(list(admin.site._registry[ClinicalReview].get_queryset(request)), [assigned_review])
		self.assertEqual(list(admin.site._registry[AuditEvent].get_queryset(request)), [assigned_audit])

	def test_clinical_review_admin_sets_reviewer_to_request_user(self):
		other_user = get_user_model().objects.create_user(
			username='forged-reviewer',
			email='forged@example.com',
			password='secure-pass-123',
		)
		review_admin = admin.site._registry[ClinicalReview]
		request = self.client.request().wsgi_request
		request.user = self.admin_user
		self.review.reviewer = other_user
		self.review.decision = ClinicalReview.Decision.APPROVED
		self.review.limitations_acknowledged = True
		self.review.missing_data_acknowledged = True

		review_admin.save_model(request, self.review, form=None, change=True)

		self.review.refresh_from_db()
		self.assertEqual(self.review.reviewer, self.admin_user)

	def test_final_review_created_directly_emits_review_audit_event(self):
		recommendation = TreatmentRecommendation.objects.create(
			patient=self.patient,
			title='Direct final review recommendation',
			summary='Summary',
			rationale='Rationale',
		)

		ClinicalReview.objects.create(
			recommendation=recommendation,
			reviewer=self.admin_user,
			decision=ClinicalReview.Decision.APPROVED,
			limitations_acknowledged=True,
			missing_data_acknowledged=True,
		)

		recommendation.refresh_from_db()
		self.assertEqual(recommendation.status, TreatmentRecommendation.Status.APPROVED)
		self.assertTrue(
			AuditEvent.objects.filter(
				recommendation=recommendation,
				event_type=AuditEvent.EventType.REVIEW_APPROVED,
				actor=self.admin_user,
			).exists()
		)

	def test_domain_admins_disable_delete_actions(self):
		request = self.client.request().wsgi_request
		request.user = self.admin_user
		for model in (PatientProfile, GenomicInsight, TreatmentRecommendation, ClinicalReview):
			model_admin = admin.site._registry[model]
			with self.subTest(model=model.__name__):
				self.assertFalse(model_admin.has_delete_permission(request))
				self.assertEqual(model_admin.get_actions(request), {})
