from django.contrib import admin

from .models import GenomicInsight


@admin.register(GenomicInsight)
class GenomicInsightAdmin(admin.ModelAdmin):
	list_display = ('gene_symbol', 'variant', 'clinical_significance', 'patient', 'created_at')
	list_filter = ('clinical_significance', 'biomarker_category')
	search_fields = ('gene_symbol', 'variant', 'patient__external_id')
