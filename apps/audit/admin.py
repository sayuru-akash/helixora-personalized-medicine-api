from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
	list_display = ('event_type', 'patient', 'recommendation', 'actor', 'created_at')
	list_filter = ('event_type',)
	search_fields = ('patient__external_id', 'recommendation__title', 'actor__username')
	readonly_fields = ('created_at',)
