from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


class HealthCheckApiTests(APITestCase):
	def test_health_check_is_public(self):
		response = self.client.get(reverse('health-check'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['status'], 'ok')


class RecommendationApiTests(APITestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='clinician',
			email='clinician@example.com',
			password='safe-password-123',
			is_staff=True,
		)
		self.client.force_authenticate(user=self.user)
		self.patient = PatientProfile.objects.create(external_id='P-1001')

	def test_recommendation_rejects_high_confidence_when_missing_data_exists(self):
		payload = {
			'patient': str(self.patient.id),
			'title': 'Targeted therapy option',
			'summary': 'Candidate therapy based on available data.',
			'rationale': 'Potential benefit suggested by limited evidence.',
			'missing_data_flags': ['missing renal function'],
			'confidence_level': TreatmentRecommendation.ConfidenceLevel.HIGH,
			'risk_level': TreatmentRecommendation.RiskLevel.MEDIUM,
		}

		response = self.client.post(reverse('treatment-recommendation-list'), payload, format='json')

		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('confidence_level', response.data)


class PatientApiTests(APITestCase):
	def setUp(self):
		self.staff_user = get_user_model().objects.create_user(
			username='staff-user',
			email='staff@example.com',
			password='safe-password-123',
			is_staff=True,
		)
		self.reader_user = get_user_model().objects.create_user(
			username='reader-user',
			email='reader@example.com',
			password='safe-password-123',
		)

	def test_non_staff_user_cannot_create_patient(self):
		self.client.force_authenticate(user=self.reader_user)

		response = self.client.post(
			reverse('patient-profile-list'),
			{'external_id': 'P-READONLY'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_staff_user_can_create_patient(self):
		self.client.force_authenticate(user=self.staff_user)

		response = self.client.post(
			reverse('patient-profile-list'),
			{'external_id': 'P-STAFF'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['external_id'], 'P-STAFF')
