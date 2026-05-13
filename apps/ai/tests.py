from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.ai.services import RecommendationConsentError, generate_recommendation
from apps.audit.models import AuditEvent
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


class RecommendationServiceTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='service-user',
			email='service@example.com',
			password='safe-password-123',
		)

	def test_generate_recommendation_creates_review_and_audit_events(self):
		patient = PatientProfile.objects.create(
			external_id='P-3001',
			consent_status='granted',
			diagnoses=['Condition A'],
			medications=['Medication A'],
			allergies=['None known'],
		)
		GenomicInsight.objects.create(
			patient=patient,
			gene_symbol='EGFR',
			variant='L858R',
			clinical_significance=GenomicInsight.Significance.HIGH,
			is_actionable=True,
		)

		recommendation = generate_recommendation(
			patient=patient,
			actor=self.user,
			correlation_id='corr-123',
		)

		self.assertEqual(recommendation.status, TreatmentRecommendation.Status.NEEDS_REVIEW)
		self.assertTrue(hasattr(recommendation, 'clinical_review'))
		self.assertEqual(recommendation.clinical_review.decision, 'needs_review')
		self.assertEqual(recommendation.audit_events.count(), 2)
		self.assertTrue(
			recommendation.audit_events.filter(
				event_type=AuditEvent.EventType.RECOMMENDATION_CREATED,
				correlation_id='corr-123',
			).exists()
		)

	def test_generate_recommendation_marks_incomplete_data_as_insufficient(self):
		patient = PatientProfile.objects.create(external_id='P-3002', consent_status='granted')

		recommendation = generate_recommendation(patient=patient)

		self.assertEqual(
			recommendation.confidence_level,
			TreatmentRecommendation.ConfidenceLevel.INSUFFICIENT_DATA,
		)
		self.assertGreaterEqual(len(recommendation.missing_data_flags), 1)

	def test_generate_recommendation_blocks_without_active_consent(self):
		patient = PatientProfile.objects.create(external_id='P-3003', consent_status='revoked')

		with self.assertRaises(RecommendationConsentError):
			generate_recommendation(patient=patient)

		self.assertEqual(TreatmentRecommendation.objects.count(), 0)
