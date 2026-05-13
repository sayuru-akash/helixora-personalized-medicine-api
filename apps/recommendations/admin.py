from django.contrib import admin

from .models import TreatmentRecommendation


@admin.register(TreatmentRecommendation)
class TreatmentRecommendationAdmin(admin.ModelAdmin):
	list_display = (
		'title',
		'patient',
		'status',
		'confidence_level',
		'risk_level',
		'clinician_review_required',
		'generated_by',
		'updated_at',
	)
	list_filter = ('status', 'confidence_level', 'risk_level', 'clinician_review_required', 'generated_by', 'updated_at')
	search_fields = ('title', 'patient__external_id', 'summary')
	readonly_fields = ('id', 'intended_use_notice', 'created_at', 'updated_at')
	autocomplete_fields = ('patient', 'primary_genomic_insight')
	list_select_related = ('patient', 'primary_genomic_insight')
	ordering = ('-updated_at',)
	date_hierarchy = 'updated_at'
	list_per_page = 30
	actions = None
	fieldsets = (
		('Identity', {'fields': ('id', 'patient', 'primary_genomic_insight', 'title')}),
		('Recommendation Narrative', {'fields': ('summary', 'rationale', 'suggested_options', 'evidence_references')}),
		(
			'Risk and Uncertainty',
			{'fields': ('risk_level', 'contraindication_warnings', 'missing_data_flags', 'uncertainty_notes')},
		),
		(
			'Governance',
			{'fields': ('status', 'confidence_level', 'clinician_review_required', 'intended_use_notice')},
		),
		('Provenance and Timestamps', {'fields': ('generated_by', 'model_version', 'created_at', 'updated_at')}),
	)
