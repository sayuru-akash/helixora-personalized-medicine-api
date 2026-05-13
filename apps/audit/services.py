from apps.audit.models import AuditEvent
from config.logging import correlation_id_var


def create_audit_event(
	*,
	event_type,
	patient=None,
	recommendation=None,
	actor=None,
	correlation_id='',
	metadata=None,
):
	if not correlation_id:
		correlation_id = correlation_id_var.get() or ''

	return AuditEvent.objects.create(
		event_type=event_type,
		patient=patient,
		recommendation=recommendation,
		actor=actor,
		correlation_id=correlation_id,
		metadata=metadata or {},
	)
