import uuid

from django.db import models


class PatientProfile(models.Model):
	class RecordStatus(models.TextChoices):
		ACTIVE = 'active', 'Active'
		INACTIVE = 'inactive', 'Inactive'
		ARCHIVED = 'archived', 'Archived'

	class SexAtBirth(models.TextChoices):
		FEMALE = 'female', 'Female'
		MALE = 'male', 'Male'
		INTERSEX = 'intersex', 'Intersex'
		UNKNOWN = 'unknown', 'Unknown'

	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	external_id = models.CharField(max_length=100, unique=True)
	date_of_birth = models.DateField(blank=True, null=True)
	record_status = models.CharField(
		max_length=20,
		choices=RecordStatus.choices,
		default=RecordStatus.ACTIVE,
	)
	sex_at_birth = models.CharField(
		max_length=20,
		choices=SexAtBirth.choices,
		default=SexAtBirth.UNKNOWN,
	)
	consent_status = models.CharField(max_length=50, default='pending_review')
	diagnoses = models.JSONField(default=list, blank=True)
	comorbidities = models.JSONField(default=list, blank=True)
	medications = models.JSONField(default=list, blank=True)
	allergies = models.JSONField(default=list, blank=True)
	lifestyle_factors = models.JSONField(default=dict, blank=True)
	disease_progression_summary = models.JSONField(default=dict, blank=True)
	clinical_notes_summary = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-updated_at']

	def __str__(self):
		return f'Patient {self.external_id}'
