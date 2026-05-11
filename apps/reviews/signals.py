from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.audit.models import AuditEvent
from apps.audit.services import create_audit_event
from apps.reviews.models import ClinicalReview


@receiver(post_save, sender=ClinicalReview)
def create_review_audit_event(sender, instance, created, **kwargs):
	if created:
		return

	event_type_map = {
		ClinicalReview.Decision.NEEDS_REVIEW: AuditEvent.EventType.REVIEW_SUBMITTED,
		ClinicalReview.Decision.APPROVED: AuditEvent.EventType.REVIEW_APPROVED,
		ClinicalReview.Decision.OVERRIDDEN: AuditEvent.EventType.REVIEW_OVERRIDDEN,
		ClinicalReview.Decision.REJECTED: AuditEvent.EventType.REVIEW_REJECTED,
	}

	event_type = event_type_map.get(instance.decision)
	if not event_type:
		return

	create_audit_event(
		event_type=event_type,
		patient=instance.recommendation.patient,
		recommendation=instance.recommendation,
		actor=instance.reviewer,
		metadata={
			'decision': instance.decision,
			'limitations_acknowledged': instance.limitations_acknowledged,
			'missing_data_acknowledged': instance.missing_data_acknowledged,
		},
	)