import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
	class EventType(models.TextChoices):
		RECOMMENDATION_CREATED = 'recommendation_created', 'Recommendation Created'
		RECOMMENDATION_UPDATED = 'recommendation_updated', 'Recommendation Updated'
		RECOMMENDATION_REVIEW_REQUESTED = 'recommendation_review_requested', 'Recommendation Review Requested'
		REVIEW_SUBMITTED = 'review_submitted', 'Review Submitted'
		REVIEW_APPROVED = 'review_approved', 'Review Approved'
		REVIEW_OVERRIDDEN = 'review_overridden', 'Review Overridden'
		REVIEW_REJECTED = 'review_rejected', 'Review Rejected'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	event_type = models.CharField(max_length=50, choices=EventType.choices)
	patient = models.ForeignKey(
		'patients.PatientProfile',
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		related_name='audit_events',
	)
	recommendation = models.ForeignKey(
		'recommendations.TreatmentRecommendation',
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		related_name='audit_events',
	)
	actor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		blank=True,
		null=True,
		related_name='audit_events',
	)
	correlation_id = models.CharField(max_length=100, blank=True)
	metadata = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return self.get_event_type_display()
