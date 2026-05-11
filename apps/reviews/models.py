import uuid

from django.conf import settings
from django.db import models


class ClinicalReview(models.Model):
	class Decision(models.TextChoices):
		NEEDS_REVIEW = 'needs_review', 'Needs Review'
		APPROVED = 'approved', 'Approved'
		OVERRIDDEN = 'overridden', 'Overridden'
		REJECTED = 'rejected', 'Rejected'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	recommendation = models.OneToOneField(
		'recommendations.TreatmentRecommendation',
		on_delete=models.CASCADE,
		related_name='clinical_review',
	)
	reviewer = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		related_name='clinical_reviews',
	)
	decision = models.CharField(
		max_length=20,
		choices=Decision.choices,
		default=Decision.NEEDS_REVIEW,
	)
	review_notes = models.TextField(blank=True)
	override_reason = models.TextField(blank=True)
	limitations_acknowledged = models.BooleanField(default=False)
	missing_data_acknowledged = models.BooleanField(default=False)
	reviewed_at = models.DateTimeField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-updated_at']

	def __str__(self):
		return f'Review for {self.recommendation.title}'
