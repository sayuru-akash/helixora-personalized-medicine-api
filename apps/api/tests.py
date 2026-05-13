from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.audit.models import AuditEvent
from apps.api.serializers import TreatmentRecommendationSerializer
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


class HealthCheckApiTests(APITestCase):
	def test_health_check_is_public(self):
		response = self.client.get(reverse('health-check'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['status'], 'ok')
		self.assertEqual(response.data['service'], 'helixora-api')
		self.assertNotIn('environment', response.data)
		self.assertNotIn('celery', response.data)

	def test_operations_health_check_rejects_anonymous_user(self):
		response = self.client.get(reverse('operations-health-check'))

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_operations_health_check_rejects_non_staff_user(self):
		user = get_user_model().objects.create_user(
			username='ordinary-health-user',
			email='ordinary-health@example.com',
			password='safe-password-123',
		)
		self.client.force_authenticate(user=user)

		response = self.client.get(reverse('operations-health-check'))

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_operations_health_check_allows_staff_user(self):
		user = get_user_model().objects.create_user(
			username='staff-health-user',
			email='staff-health@example.com',
			password='safe-password-123',
			is_staff=True,
		)
		self.client.force_authenticate(user=user)

		response = self.client.get(reverse('operations-health-check'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('environment', response.data)
		self.assertIn('celery', response.data)


class RecommendationApiTests(APITestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_superuser(
			username='clinician',
			email='clinician@example.com',
			password='safe-password-123',
		)
		self.client.force_authenticate(user=self.user)
		self.patient = PatientProfile.objects.create(external_id='P-1001')

	def test_recommendation_create_is_not_exposed_as_raw_crud(self):
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

		self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

	def test_recommendation_rejects_cross_patient_genomic_insight(self):
		other_patient = PatientProfile.objects.create(external_id='P-1002')
		insight = GenomicInsight.objects.create(
			patient=other_patient,
			gene_symbol='EGFR',
			variant='L858R',
		)
		serializer = TreatmentRecommendationSerializer(
			data={
				'patient': str(self.patient.id),
				'primary_genomic_insight': str(insight.id),
				'title': 'Targeted therapy option',
			}
		)

		self.assertFalse(serializer.is_valid())
		self.assertIn('primary_genomic_insight', serializer.errors)


class PatientApiTests(APITestCase):
	def setUp(self):
		self.staff_user = get_user_model().objects.create_superuser(
			username='staff-user',
			email='staff@example.com',
			password='safe-password-123',
		)
		self.reader_user = get_user_model().objects.create_user(
			username='reader-user',
			email='reader@example.com',
			password='safe-password-123',
		)
		self.patient = PatientProfile.objects.create(external_id='P-EXISTING')

	def test_anonymous_user_cannot_read_patients(self):
		response = self.client.get(reverse('patient-profile-list'))

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_authenticated_user_without_role_cannot_read_patients(self):
		self.client.force_authenticate(user=self.reader_user)

		response = self.client.get(reverse('patient-profile-list'))

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_clinical_reader_group_can_read_patients(self):
		group = Group.objects.create(name='clinical_reader')
		self.reader_user.groups.add(group)
		self.client.force_authenticate(user=self.reader_user)

		response = self.client.get(reverse('patient-profile-list'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data[0]['external_id'], self.patient.external_id)

	def test_non_staff_user_cannot_create_patient(self):
		self.client.force_authenticate(user=self.reader_user)

		response = self.client.post(
			reverse('patient-profile-list'),
			{'external_id': 'P-READONLY'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

	def test_clinical_editor_group_can_create_patient(self):
		group = Group.objects.create(name='clinical_editor')
		self.reader_user.groups.add(group)
		self.client.force_authenticate(user=self.reader_user)

		response = self.client.post(
			reverse('patient-profile-list'),
			{'external_id': 'P-EDITOR'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['external_id'], 'P-EDITOR')

	def test_user_with_model_add_permission_can_create_patient(self):
		permission = Permission.objects.get(
			content_type__app_label='patients',
			codename='add_patientprofile',
		)
		self.reader_user.user_permissions.add(permission)
		self.client.force_authenticate(user=self.reader_user)

		response = self.client.post(
			reverse('patient-profile-list'),
			{'external_id': 'P-PERMISSION'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['external_id'], 'P-PERMISSION')

	def test_staff_user_can_create_patient(self):
		self.client.force_authenticate(user=self.staff_user)

		response = self.client.post(
			reverse('patient-profile-list'),
			{'external_id': 'P-STAFF'},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['external_id'], 'P-STAFF')


class AuditEventApiTests(APITestCase):
	def setUp(self):
		self.staff_user = get_user_model().objects.create_superuser(
			username='audit-staff-user',
			email='audit-staff@example.com',
			password='safe-password-123',
		)

	def test_audit_events_post_is_denied_for_staff_user(self):
		self.client.force_authenticate(user=self.staff_user)

		response = self.client.post(
			reverse('audit-event-list'),
			{'event_type': AuditEvent.EventType.RECOMMENDATION_CREATED},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
