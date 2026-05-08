from django.contrib import admin

from .models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
	list_display = ('external_id', 'sex_at_birth', 'date_of_birth', 'updated_at')
	search_fields = ('external_id',)
	readonly_fields = ('created_at', 'updated_at')
