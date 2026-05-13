from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile


class GenomicInsightModelTests(TestCase):
	def setUp(self):
		self.patient = PatientProfile.objects.create(external_id='P-GENOMIC-VALIDATION')

	def test_gene_symbol_rejects_unsupported_characters(self):
		insight = GenomicInsight(
			patient=self.patient,
			gene_symbol='EGFR<script>',
			variant='L858R',
		)

		with self.assertRaises(ValidationError) as raised:
			insight.full_clean()

		self.assertIn('gene_symbol', raised.exception.message_dict)

	def test_report_reference_requires_source(self):
		insight = GenomicInsight(
			patient=self.patient,
			gene_symbol='EGFR',
			variant='L858R',
			report_reference='REPORT-001',
		)

		with self.assertRaises(ValidationError) as raised:
			insight.full_clean()

		self.assertIn('source', raised.exception.message_dict)
