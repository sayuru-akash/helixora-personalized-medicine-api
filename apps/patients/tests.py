from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.patients.models import PatientProfile


class PatientProfileModelTests(TestCase):
	def test_consent_status_uses_controlled_values(self):
		patient = PatientProfile(external_id='P-CONSENT-CHOICES', consent_status='unsupported')

		with self.assertRaises(ValidationError) as raised:
			patient.full_clean()

		self.assertIn('consent_status', raised.exception.message_dict)

	def test_date_of_birth_cannot_be_in_future(self):
		patient = PatientProfile(
			external_id='P-FUTURE-DOB',
			date_of_birth=timezone.localdate() + timedelta(days=1),
		)

		with self.assertRaises(ValidationError) as raised:
			patient.full_clean()

		self.assertIn('date_of_birth', raised.exception.message_dict)
