from django.contrib import admin

from apps.api.admin_scoping import PatientScopedAdminMixin

from .models import ClinicalReview


@admin.register(ClinicalReview)
class ClinicalReviewAdmin(PatientScopedAdminMixin, admin.ModelAdmin):
	patient_scope_filter = 'recommendation__patient__authorized_users'
	list_display = (
		'recommendation',
		'decision',
		'reviewer',
		'limitations_acknowledged',
		'missing_data_acknowledged',
		'reviewed_at',
		'updated_at',
	)
	list_filter = ('decision', 'limitations_acknowledged', 'missing_data_acknowledged', 'reviewed_at')
	search_fields = ('recommendation__title', 'recommendation__patient__external_id')
	readonly_fields = ('id', 'reviewer', 'created_at', 'updated_at', 'reviewed_at')
	autocomplete_fields = ('recommendation',)
	list_select_related = ('recommendation', 'recommendation__patient', 'reviewer')
	date_hierarchy = 'updated_at'
	list_per_page = 30
	actions = None
	fieldsets = (
		('Linkage', {'fields': ('id', 'recommendation', 'reviewer')}),
		('Decision', {'fields': ('decision', 'review_notes', 'override_reason')}),
		('Safety Acknowledgements', {'fields': ('limitations_acknowledged', 'missing_data_acknowledged')}),
		('Timestamps', {'fields': ('reviewed_at', 'created_at', 'updated_at')}),
	)

	def has_delete_permission(self, request, obj=None):
		return False

	def save_model(self, request, obj, form, change):
		if obj.decision != ClinicalReview.Decision.NEEDS_REVIEW:
			obj.reviewer = request.user
		super().save_model(request, obj, form, change)
