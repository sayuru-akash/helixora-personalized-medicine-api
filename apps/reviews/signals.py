from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.audit.models import AuditEvent
from apps.audit.services import create_audit_event
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview


@receiver(post_save, sender=ClinicalReview)
def create_review_audit_event(sender, instance, created, **kwargs):
	status_map = {
		ClinicalReview.Decision.NEEDS_REVIEW: TreatmentRecommendation.Status.NEEDS_REVIEW,
		ClinicalReview.Decision.APPROVED: TreatmentRecommendation.Status.APPROVED,
		ClinicalReview.Decision.OVERRIDDEN: TreatmentRecommendation.Status.OVERRIDDEN,
		ClinicalReview.Decision.REJECTED: TreatmentRecommendation.Status.REJECTED,
	}
	recommendation_status = status_map.get(instance.decision)
	if recommendation_status and instance.recommendation.status != recommendation_status:
		TreatmentRecommendation.objects.filter(pk=instance.recommendation_id).update(
			status=recommendation_status,
			updated_at=instance.updated_at,
		)

	if created and instance.decision == ClinicalReview.Decision.NEEDS_REVIEW:
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
