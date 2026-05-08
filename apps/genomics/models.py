import uuid

from django.db import models


class GenomicInsight(models.Model):
	class Significance(models.TextChoices):
		HIGH = 'high', 'High'
		MODERATE = 'moderate', 'Moderate'
		LOW = 'low', 'Low'
		UNCERTAIN = 'uncertain', 'Uncertain'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	patient = models.ForeignKey(
		'patients.PatientProfile',
		on_delete=models.CASCADE,
		related_name='genomic_insights',
	)
	gene_symbol = models.CharField(max_length=50)
	variant = models.CharField(max_length=255)
	biomarker_category = models.CharField(max_length=100, blank=True)
	clinical_significance = models.CharField(
		max_length=20,
		choices=Significance.choices,
		default=Significance.UNCERTAIN,
	)
	evidence_summary = models.TextField(blank=True)
	source = models.CharField(max_length=255, blank=True)
	observed_at = models.DateField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.gene_symbol} {self.variant}'
