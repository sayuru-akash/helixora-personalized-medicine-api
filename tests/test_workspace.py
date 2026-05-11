from django.test import TestCase
from django.urls import reverse

from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


class RecommendationWorkspaceTests(TestCase):
	def test_workspace_page_renders(self):
		response = self.client.get(reverse('recommendation-workspace'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Generate a structured treatment support draft.')
		self.assertContains(response, 'Ready for clinician-guided drafting')

	def test_workspace_submission_creates_patient_and_recommendation(self):
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