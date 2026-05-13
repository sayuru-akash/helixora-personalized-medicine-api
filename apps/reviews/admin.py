from django.contrib import admin

from .models import ClinicalReview


@admin.register(ClinicalReview)
class ClinicalReviewAdmin(admin.ModelAdmin):
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
	readonly_fields = ('id', 'created_at', 'updated_at', 'reviewed_at')
	autocomplete_fields = ('recommendation', 'reviewer')
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
