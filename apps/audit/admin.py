from django.contrib import admin

from apps.api.admin_scoping import AuditPatientScopedAdminMixin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(AuditPatientScopedAdminMixin, admin.ModelAdmin):
	list_display = ('event_type', 'patient', 'recommendation', 'actor', 'created_at')
	list_filter = ('event_type', 'created_at', 'actor')
	search_fields = ('patient__external_id', 'recommendation__title', 'actor__username', 'correlation_id')
	readonly_fields = (
		'id',
		'event_type',
		'patient',
		'recommendation',
		'actor',
		'correlation_id',
		'metadata',
		'created_at',
	)
	list_select_related = ('patient', 'recommendation', 'actor')
	date_hierarchy = 'created_at'
	list_per_page = 50

	def has_add_permission(self, request):
		return False

	def has_change_permission(self, request, obj=None):
		return False

	def has_view_permission(self, request, obj=None):
		return super().has_view_permission(request, obj)

	def has_delete_permission(self, request, obj=None):
		return False
