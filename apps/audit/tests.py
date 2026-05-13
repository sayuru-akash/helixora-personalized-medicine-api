from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.test import TestCase

from apps.audit.models import AuditEvent
from apps.audit.services import create_audit_event
from config.logging import correlation_id_var


class AuditEventIntegrityTests(TestCase):
	def test_audit_event_cannot_be_updated_after_creation(self):
		event = AuditEvent.objects.create(event_type=AuditEvent.EventType.RECOMMENDATION_CREATED)

		event.event_type = AuditEvent.EventType.RECOMMENDATION_UPDATED

		with self.assertRaises(ValidationError):
			event.save()

		event.refresh_from_db()
		self.assertEqual(event.event_type, AuditEvent.EventType.RECOMMENDATION_CREATED)

	def test_audit_event_cannot_be_deleted_after_creation(self):
		event = AuditEvent.objects.create(event_type=AuditEvent.EventType.RECOMMENDATION_CREATED)

		with self.assertRaises(ValidationError):
			event.delete()

		self.assertTrue(AuditEvent.objects.filter(pk=event.pk).exists())

	def test_audit_event_bulk_update_and_delete_are_blocked(self):
		event = AuditEvent.objects.create(event_type=AuditEvent.EventType.RECOMMENDATION_CREATED)

		with self.assertRaises(ValidationError):
			AuditEvent.objects.filter(pk=event.pk).update(event_type=AuditEvent.EventType.RECOMMENDATION_UPDATED)

		with self.assertRaises(ValidationError):
			AuditEvent.objects.filter(pk=event.pk).delete()

		event.refresh_from_db()
		self.assertEqual(event.event_type, AuditEvent.EventType.RECOMMENDATION_CREATED)

	def test_explicit_internal_escape_hatch_can_update_or_delete(self):
		event = AuditEvent.objects.create(event_type=AuditEvent.EventType.RECOMMENDATION_CREATED)
		event.event_type = AuditEvent.EventType.RECOMMENDATION_UPDATED

		event.save(allow_audit_event_mutation=True)
		event.refresh_from_db()
		self.assertEqual(event.event_type, AuditEvent.EventType.RECOMMENDATION_UPDATED)

		event.delete(allow_audit_event_mutation=True)
		self.assertFalse(AuditEvent.objects.filter(pk=event.pk).exists())


class AuditEventServiceTests(TestCase):
	def test_create_audit_event_uses_context_correlation_id_and_metadata(self):
		token = correlation_id_var.set('corr-service-001')
		try:
			event = create_audit_event(
				event_type=AuditEvent.EventType.RECOMMENDATION_CREATED,
				metadata={'source': 'unit-test', 'status': 'created'},
			)
		finally:
			correlation_id_var.reset(token)

		self.assertEqual(event.correlation_id, 'corr-service-001')
		self.assertEqual(event.metadata, {'source': 'unit-test', 'status': 'created'})


class AuditEventAdminTests(TestCase):
	def test_audit_admin_allows_view_only_access(self):
		User = get_user_model()
		user = User.objects.create_superuser(
			username='audit-admin',
			email='audit-admin@example.com',
			password='secure-pass-123',
		)
		request = RequestFactory().get('/admin/audit/auditevent/')
		request.user = user
		audit_admin = admin.site._registry[AuditEvent]

		self.assertFalse(audit_admin.has_add_permission(request))
		self.assertFalse(audit_admin.has_change_permission(request))
		self.assertFalse(audit_admin.has_delete_permission(request))
		self.assertTrue(audit_admin.has_view_permission(request))
