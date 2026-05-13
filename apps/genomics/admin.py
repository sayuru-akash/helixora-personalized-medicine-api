from django.contrib import admin

from apps.api.admin_scoping import PatientScopedAdminMixin

from .models import GenomicInsight


@admin.register(GenomicInsight)
class GenomicInsightAdmin(PatientScopedAdminMixin, admin.ModelAdmin):
	patient_scope_filter = 'patient__authorized_users'
	list_display = (
		'gene_symbol',
		'variant',
		'patient',
		'clinical_significance',
		'review_status',
		'is_actionable',
		'observed_at',
		'created_at',
	)
	list_filter = ('clinical_significance', 'review_status', 'is_actionable', 'biomarker_category', 'created_at')
	search_fields = ('gene_symbol', 'variant', 'patient__external_id')
	readonly_fields = ('id', 'created_at')
	autocomplete_fields = ('patient',)
	list_select_related = ('patient',)
	date_hierarchy = 'created_at'
	list_per_page = 30
	actions = None
	fieldsets = (
		('Linkage', {'fields': ('id', 'patient')}),
		('Variant Details', {'fields': ('gene_symbol', 'variant', 'biomarker_category')}),
		('Clinical Interpretation', {'fields': ('clinical_significance', 'review_status', 'is_actionable')}),
		('Evidence', {'fields': ('evidence_summary', 'source', 'report_reference')}),
		('Timeline', {'fields': ('observed_at', 'created_at')}),
	)

	def has_delete_permission(self, request, obj=None):
		return False
