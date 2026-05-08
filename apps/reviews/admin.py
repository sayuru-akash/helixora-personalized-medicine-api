from django.contrib import admin

from .models import ClinicalReview


@admin.register(ClinicalReview)
class ClinicalReviewAdmin(admin.ModelAdmin):
	list_display = ('recommendation', 'decision', 'reviewer', 'reviewed_at', 'updated_at')
	list_filter = ('decision',)
	search_fields = ('recommendation__title', 'recommendation__patient__external_id')
	readonly_fields = ('created_at', 'updated_at')
