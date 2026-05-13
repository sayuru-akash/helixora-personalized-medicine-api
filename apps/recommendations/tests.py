from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


class TreatmentRecommendationModelTests(TestCase):
	def test_primary_genomic_insight_must_belong_to_recommendation_patient(self):
		patient = PatientProfile.objects.create(external_id='P-RECOMMENDATION-1')
		other_patient = PatientProfile.objects.create(external_id='P-RECOMMENDATION-2')
		insight = GenomicInsight.objects.create(
			patient=other_patient,
			gene_symbol='EGFR',
			variant='L858R',
		)
		recommendation = TreatmentRecommendation(
			patient=patient,
			primary_genomic_insight=insight,
			title='Cross-patient recommendation',
			summary='Summary',
			rationale='Rationale',
		)

		with self.assertRaises(ValidationError) as raised:
			recommendation.full_clean()

		self.assertIn('primary_genomic_insight', raised.exception.message_dict)
