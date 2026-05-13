import uuid

from django.core.exceptions import ValidationError
from django.db import models


class TreatmentRecommendation(models.Model):
	class Status(models.TextChoices):
		DRAFT = 'draft', 'Draft'
		NEEDS_REVIEW = 'needs_review', 'Needs Review'
		APPROVED = 'approved', 'Approved'
		OVERRIDDEN = 'overridden', 'Overridden'
		REJECTED = 'rejected', 'Rejected'

	class ConfidenceLevel(models.TextChoices):
		HIGH = 'high', 'High'
		MEDIUM = 'medium', 'Medium'
		LOW = 'low', 'Low'
		INSUFFICIENT_DATA = 'insufficient_data', 'Insufficient Data'

	class RiskLevel(models.TextChoices):
		HIGH = 'high', 'High'
		MEDIUM = 'medium', 'Medium'
		LOW = 'low', 'Low'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	patient = models.ForeignKey(
		'patients.PatientProfile',
		on_delete=models.CASCADE,
		related_name='recommendations',
	)
	primary_genomic_insight = models.ForeignKey(
		'genomics.GenomicInsight',
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		related_name='recommendations',
	)
	title = models.CharField(max_length=255)
	summary = models.TextField()
	rationale = models.TextField()
	evidence_references = models.JSONField(default=list, blank=True)
	suggested_options = models.JSONField(default=list, blank=True)
	contraindication_warnings = models.JSONField(default=list, blank=True)
	missing_data_flags = models.JSONField(default=list, blank=True)
	uncertainty_notes = models.TextField(blank=True)
	intended_use_notice = models.TextField(
		default='Clinical decision support only. Requires clinician review before action.'
	)
	status = models.CharField(
		max_length=20,
		choices=Status.choices,
		default=Status.DRAFT,
	)
	confidence_level = models.CharField(
		max_length=30,
		choices=ConfidenceLevel.choices,
		default=ConfidenceLevel.INSUFFICIENT_DATA,
	)
	risk_level = models.CharField(
		max_length=20,
		choices=RiskLevel.choices,
		default=RiskLevel.MEDIUM,
	)
	clinician_review_required = models.BooleanField(default=True)
	generated_by = models.CharField(max_length=100, default='system')
	model_version = models.CharField(max_length=100, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-updated_at']

	def __str__(self):
		return f'{self.title} ({self.get_status_display()})'

	def clean(self):
		super().clean()
		if (
			self.primary_genomic_insight_id
			and self.patient_id
			and self.primary_genomic_insight.patient_id != self.patient_id
		):
			raise ValidationError(
				{'primary_genomic_insight': 'Primary genomic insight must belong to the recommendation patient.'}
			)

	def save(self, *args, **kwargs):
		self.full_clean()
		super().save(*args, **kwargs)
