import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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

	class ConsentStatus(models.TextChoices):
		PENDING_REVIEW = 'pending_review', 'Pending Review'
		GRANTED = 'granted', 'Granted'
		ACTIVE = 'active', 'Active'
		CONSENTED = 'consented', 'Consented'
		DENIED = 'denied', 'Denied'
		REVOKED = 'revoked', 'Revoked'

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
	consent_status = models.CharField(
		max_length=50,
		choices=ConsentStatus.choices,
		default=ConsentStatus.PENDING_REVIEW,
	)
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

	def clean(self):
		super().clean()
		if self.date_of_birth and self.date_of_birth > timezone.localdate():
			raise ValidationError({'date_of_birth': 'Date of birth cannot be in the future.'})
