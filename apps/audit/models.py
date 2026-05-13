import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


AUDIT_EVENT_MUTATION_KWARG = 'allow_audit_event_mutation'
AUDIT_EVENT_IMMUTABLE_MESSAGE = 'Audit events are append-only and cannot be modified after creation.'
AUDIT_EVENT_DELETE_MESSAGE = 'Audit events are append-only and cannot be deleted.'


class AuditEventQuerySet(models.QuerySet):
	def _allow_mutation(self):
		clone = self._chain()
		clone._audit_event_mutation_allowed = True
		return clone

	def allow_audit_event_mutation(self):
		return self._allow_mutation()

	def update(self, **kwargs):
		if not getattr(self, '_audit_event_mutation_allowed', False):
			raise ValidationError(AUDIT_EVENT_IMMUTABLE_MESSAGE)
		return super().update(**kwargs)

	def delete(self):
		if not getattr(self, '_audit_event_mutation_allowed', False):
			raise ValidationError(AUDIT_EVENT_DELETE_MESSAGE)
		return super().delete()


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

	objects = AuditEventQuerySet.as_manager()

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return self.get_event_type_display()

	def save(self, *args, **kwargs):
		allow_mutation = kwargs.pop(AUDIT_EVENT_MUTATION_KWARG, False)
		if self.pk and not allow_mutation and type(self).objects.filter(pk=self.pk).exists():
			raise ValidationError(AUDIT_EVENT_IMMUTABLE_MESSAGE)
		return super().save(*args, **kwargs)

	def delete(self, *args, **kwargs):
		allow_mutation = kwargs.pop(AUDIT_EVENT_MUTATION_KWARG, False)
		if not allow_mutation:
			raise ValidationError(AUDIT_EVENT_DELETE_MESSAGE)
		return super().delete(*args, **kwargs)
