from django.contrib import admin

from apps.api.admin_scoping import PatientScopedAdminMixin

from .models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(PatientScopedAdminMixin, admin.ModelAdmin):
	patient_scope_filter = 'authorized_users'
	list_display = (
		'external_id',
		'record_status',
		'consent_status',
		'sex_at_birth',
		'date_of_birth',
		'updated_at',
	)
	list_filter = ('record_status', 'consent_status', 'sex_at_birth', 'updated_at')
	search_fields = ('external_id', 'clinical_notes_summary')
	readonly_fields = ('id', 'created_at', 'updated_at')
	filter_horizontal = ('authorized_users',)
	ordering = ('-updated_at',)
	date_hierarchy = 'updated_at'
	list_per_page = 30
	actions = None
	fieldsets = (
		('Identity', {'fields': ('id', 'external_id', 'record_status', 'consent_status', 'authorized_users')}),
		('Clinical Profile', {'fields': ('date_of_birth', 'sex_at_birth', 'clinical_notes_summary')}),
		(
			'Structured Medical Context',
			{
					'fields': (
						'diagnoses',
						'comorbidities',
						'medications',
						'allergies',
						'lifestyle_factors',
						'disease_progression_summary',
					)
				},
			),
			('Audit Timestamps', {'fields': ('created_at', 'updated_at')}),
		)

	def has_delete_permission(self, request, obj=None):
		return False
