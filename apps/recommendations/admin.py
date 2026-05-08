from django.contrib import admin

from .models import TreatmentRecommendation


@admin.register(TreatmentRecommendation)
class TreatmentRecommendationAdmin(admin.ModelAdmin):
	list_display = ('title', 'patient', 'status', 'confidence_level', 'risk_level', 'updated_at')
	list_filter = ('status', 'confidence_level', 'risk_level', 'clinician_review_required')
	search_fields = ('title', 'patient__external_id', 'summary')
	readonly_fields = ('created_at', 'updated_at')
