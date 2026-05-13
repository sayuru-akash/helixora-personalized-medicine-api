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
from apps.reviews.models import ClinicalReview


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
		self.patient.authorized_users.add(self.reader_user)
		self.client.force_authenticate(user=self.reader_user)

		response = self.client.get(reverse('patient-profile-list'))

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data[0]['external_id'], self.patient.external_id)

	def test_clinical_reader_group_cannot_read_unassigned_patients(self):
		group = Group.objects.create(name='clinical_reader')
		self.reader_user.groups.add(group)
		self.client.force_authenticate(user=self.reader_user)

		list_response = self.client.get(reverse('patient-profile-list'))
		detail_response = self.client.get(reverse('patient-profile-detail', kwargs={'pk': self.patient.pk}))

		self.assertEqual(list_response.status_code, status.HTTP_200_OK)
		self.assertEqual(list_response.data, [])
		self.assertEqual(detail_response.status_code, status.HTTP_404_NOT_FOUND)

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
		patient = PatientProfile.objects.get(external_id='P-EDITOR')
		self.assertTrue(patient.authorized_users.filter(pk=self.reader_user.pk).exists())

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


class ClinicalReviewApiTests(APITestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='review-api-user',
			email='review-api@example.com',
			password='safe-password-123',
		)
		self.user.groups.add(Group.objects.create(name='clinical_reviewer'))
		self.patient = PatientProfile.objects.create(external_id='P-REVIEW-API', consent_status='granted')
		self.patient.authorized_users.add(self.user)
		self.recommendation = TreatmentRecommendation.objects.create(
			patient=self.patient,
			title='Accessible recommendation',
			summary='Summary',
			rationale='Rationale',
		)
		self.review = ClinicalReview.objects.create(recommendation=self.recommendation)
		self.other_patient = PatientProfile.objects.create(external_id='P-REVIEW-OTHER', consent_status='granted')
		self.other_recommendation = TreatmentRecommendation.objects.create(
			patient=self.other_patient,
			title='Inaccessible recommendation',
			summary='Summary',
			rationale='Rationale',
		)
		self.client.force_authenticate(user=self.user)

	def test_review_update_cannot_reassign_recommendation(self):
		response = self.client.patch(
			reverse('clinical-review-detail', kwargs={'pk': self.review.pk}),
			{
				'recommendation': str(self.other_recommendation.pk),
				'decision': ClinicalReview.Decision.APPROVED,
				'limitations_acknowledged': True,
				'missing_data_acknowledged': True,
			},
			format='json',
		)

		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.review.refresh_from_db()
		self.assertEqual(self.review.recommendation, self.recommendation)
		self.assertEqual(self.review.reviewer, self.user)
