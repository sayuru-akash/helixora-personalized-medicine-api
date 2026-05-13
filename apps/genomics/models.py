import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


class GenomicInsight(models.Model):
	class ReviewStatus(models.TextChoices):
		PENDING = 'pending', 'Pending'
		REVIEWED = 'reviewed', 'Reviewed'
		FLAGGED = 'flagged', 'Flagged'

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
	gene_symbol = models.CharField(
		max_length=50,
		validators=[
			RegexValidator(
				regex=r'^[A-Za-z0-9][A-Za-z0-9_.-]*$',
				message='Gene symbol must contain only letters, numbers, underscores, periods, or hyphens.',
			)
		],
	)
	variant = models.CharField(max_length=255)
	biomarker_category = models.CharField(max_length=100, blank=True)
	clinical_significance = models.CharField(
		max_length=20,
		choices=Significance.choices,
		default=Significance.UNCERTAIN,
	)
	review_status = models.CharField(
		max_length=20,
		choices=ReviewStatus.choices,
		default=ReviewStatus.PENDING,
	)
	is_actionable = models.BooleanField(default=False)
	evidence_summary = models.TextField(blank=True)
	source = models.CharField(max_length=255, blank=True)
	report_reference = models.CharField(max_length=255, blank=True)
	observed_at = models.DateField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']
		indexes = [
			models.Index(fields=['patient', 'gene_symbol', 'variant']),
			models.Index(fields=['patient', 'is_actionable', '-created_at']),
		]

	def __str__(self):
		return f'{self.gene_symbol} {self.variant}'

	def clean(self):
		super().clean()
		if not self.variant.strip():
			raise ValidationError({'variant': 'Variant is required.'})
		if self.report_reference and not self.source:
			raise ValidationError({'source': 'Source is required when a report reference is provided.'})
