from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse

from apps.ai.workflow import run_recommendation_workflow
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview


class RecommendationWorkspaceTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='workspace-clinician',
			email='workspace@example.com',
			password='safe-password-123',
		)
		self.user.groups.add(Group.objects.create(name='clinical_editor'))

	def login_workspace_user(self):
		self.client.force_login(self.user)

	def test_workspace_requires_authentication(self):
		response = self.client.get(reverse('recommendation-workspace'))

		self.assertEqual(response.status_code, 302)
		self.assertIn('/admin/login/', response['Location'])

	def test_workspace_page_renders(self):
		self.login_workspace_user()

		response = self.client.get(reverse('recommendation-workspace'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Prepare a structured recommendation for clinician review.')
		self.assertContains(response, 'Review controls')

	def test_workspace_submission_creates_patient_and_recommendation(self):
		self.login_workspace_user()

		with patch.dict('os.environ', {'HELIXORA_AI_PROVIDER': 'placeholder'}, clear=False):
			response = self.client.post(
				reverse('recommendation-workspace'),
				data={
					'external_id': 'P-9001',
					'consent_status': 'granted',
					'diagnoses': 'Metastatic lung cancer',
					'medications': 'Warfarin',
					'allergies': 'None known',
					'clinical_notes_summary': 'Progressive disease after first-line therapy.',
					'gene_symbol': 'EGFR',
					'variant': 'L858R',
					'clinical_significance': 'high',
					'is_actionable': 'on',
					'evidence_summary': 'Known actionable alteration.',
				},
			)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(PatientProfile.objects.filter(external_id='P-9001').exists())
		self.assertEqual(TreatmentRecommendation.objects.count(), 1)
		self.assertContains(response, 'Personalized treatment review for P-9001')
		self.assertContains(response, 'Review report')
		self.assertContains(response, 'AI provider')
		self.assertContains(response, 'safe-placeholder-engine')
		self.assertEqual(ClinicalReview.objects.count(), 1)

	def test_workspace_submission_updates_existing_patient(self):
		self.login_workspace_user()
		patient = PatientProfile.objects.create(
			external_id='P-9002',
			consent_status='granted',
			diagnoses=['Earlier diagnosis'],
		)
		patient.authorized_users.add(self.user)

		with patch.dict('os.environ', {'HELIXORA_AI_PROVIDER': 'placeholder'}, clear=False):
			for note in ['First submission', 'Updated submission']:
				response = self.client.post(
					reverse('recommendation-workspace'),
					data={
						'external_id': 'P-9002',
						'consent_status': 'granted',
						'diagnoses': 'Metastatic lung cancer',
						'medications': 'Warfarin',
						'allergies': 'None known',
						'clinical_notes_summary': note,
						'gene_symbol': 'EGFR',
						'variant': 'L858R',
						'clinical_significance': 'high',
						'is_actionable': 'on',
						'evidence_summary': 'Known actionable alteration.',
					},
				)
				self.assertEqual(response.status_code, 200)

		self.assertEqual(PatientProfile.objects.filter(external_id='P-9002').count(), 1)
		self.assertEqual(PatientProfile.objects.get(external_id='P-9002').clinical_notes_summary, 'Updated submission')
		self.assertEqual(TreatmentRecommendation.objects.filter(patient__external_id='P-9002').count(), 2)

	def test_workspace_sidebar_only_shows_assigned_recent_recommendations(self):
		self.login_workspace_user()
		assigned_patient = PatientProfile.objects.create(external_id='P-ASSIGNED', consent_status='granted')
		assigned_patient.authorized_users.add(self.user)
		unassigned_patient = PatientProfile.objects.create(external_id='P-UNASSIGNED', consent_status='granted')
		TreatmentRecommendation.objects.create(
			patient=assigned_patient,
			title='Assigned recommendation',
			summary='Visible summary',
			rationale='Visible rationale',
		)
		TreatmentRecommendation.objects.create(
			patient=unassigned_patient,
			title='Unassigned recommendation',
			summary='Hidden summary',
			rationale='Hidden rationale',
		)

		response = self.client.get(reverse('recommendation-workspace'))

		self.assertContains(response, 'Assigned recommendation')
		self.assertContains(response, 'P-ASSIGNED')
		self.assertNotContains(response, 'Unassigned recommendation')
		self.assertNotContains(response, 'P-UNASSIGNED')

	def test_workflow_blocks_existing_patient_self_authorization_by_external_id(self):
		other_user = get_user_model().objects.create_user(
			username='other-clinician',
			email='other@example.com',
			password='safe-password-123',
		)
		patient = PatientProfile.objects.create(
			external_id='P-OWNED',
			consent_status='granted',
			diagnoses=['Earlier diagnosis'],
		)
		patient.authorized_users.add(other_user)

		with self.assertRaises(PermissionDenied):
			run_recommendation_workflow(
				patient_data={
					'external_id': 'P-OWNED',
					'consent_status': 'granted',
					'diagnoses': ['Tampered diagnosis'],
					'medications': ['Medication A'],
					'allergies': ['None known'],
				},
				actor=self.user,
			)

		patient.refresh_from_db()
		self.assertEqual(patient.diagnoses, ['Earlier diagnosis'])
		self.assertFalse(patient.authorized_users.filter(pk=self.user.pk).exists())
		self.assertEqual(TreatmentRecommendation.objects.count(), 0)
