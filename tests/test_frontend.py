from django.test import TestCase
from django.urls import reverse

from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


class LandingPageTests(TestCase):
	def test_landing_page_renders(self):
		response = self.client.get(reverse('landing-page'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Helixora AI')
		self.assertContains(response, 'Turn patient context into a reviewable treatment support draft.')

	def test_landing_page_does_not_expose_patient_linked_records(self):
		patient = PatientProfile.objects.create(external_id='P-PUBLIC-LEAK-CHECK')
		TreatmentRecommendation.objects.create(
			patient=patient,
			title='Sensitive recommendation draft',
			summary='Summary',
			rationale='Rationale',
		)

		response = self.client.get(reverse('landing-page'))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'P-PUBLIC-LEAK-CHECK')
		self.assertNotContains(response, 'Sensitive recommendation draft')
