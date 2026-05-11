from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from django.test import TestCase

from apps.api.serializers import ClinicalReviewSerializer
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview


class ClinicalReviewSerializerTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='reviewer',
			email='reviewer@example.com',
			password='safe-password-123',
		)
		self.patient = PatientProfile.objects.create(external_id='P-2001')
		self.recommendation = TreatmentRecommendation.objects.create(
			patient=self.patient,
			title='Review candidate',
			summary='Summary',
			rationale='Rationale',
		)

	def test_override_requires_reason(self):
		serializer = ClinicalReviewSerializer(
			data={
				'recommendation': self.recommendation.id,
				'reviewer': self.user.id,
				'decision': ClinicalReview.Decision.OVERRIDDEN,
				'limitations_acknowledged': True,
				'missing_data_acknowledged': True,
				'reviewed_at': timezone.now(),
			}
		)

		with self.assertRaises(serializers.ValidationError):
			serializer.is_valid(raise_exception=True)

	def test_approval_requires_acknowledgements(self):
		serializer = ClinicalReviewSerializer(
			data={
				'recommendation': self.recommendation.id,
				'reviewer': self.user.id,
				'decision': ClinicalReview.Decision.APPROVED,
				'reviewed_at': timezone.now(),
			}
		)

		self.assertFalse(serializer.is_valid())
		self.assertIn('limitations_acknowledged', serializer.errors)
