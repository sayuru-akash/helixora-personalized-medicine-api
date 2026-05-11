from django import forms

from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile


class RecommendationWorkspaceForm(forms.Form):
	FULL_WIDTH_FIELDS = {
		'diagnoses',
		'medications',
		'allergies',
		'clinical_notes_summary',
		'evidence_summary',
	}

	external_id = forms.CharField(max_length=100)
	date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
	sex_at_birth = forms.ChoiceField(choices=PatientProfile.SexAtBirth.choices, required=False)
	consent_status = forms.CharField(max_length=50, initial='pending_review')
	diagnoses = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
	medications = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
	allergies = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))
	clinical_notes_summary = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}))
	gene_symbol = forms.CharField(required=False, max_length=50)
	variant = forms.CharField(required=False, max_length=255)
	clinical_significance = forms.ChoiceField(
		choices=[('', '---------'), *GenomicInsight.Significance.choices],
		required=False,
	)
	is_actionable = forms.BooleanField(required=False)
	evidence_summary = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 3}))

	def _split_lines(self, value: str) -> list[str]:
		return [line.strip() for line in value.splitlines() if line.strip()]

	def get_patient_payload(self) -> dict:
		cleaned = self.cleaned_data
		return {
			'external_id': cleaned['external_id'],
			'date_of_birth': cleaned.get('date_of_birth'),
			'sex_at_birth': cleaned.get('sex_at_birth') or PatientProfile.SexAtBirth.UNKNOWN,
			'consent_status': cleaned['consent_status'],
			'diagnoses': self._split_lines(cleaned.get('diagnoses', '')),
			'medications': self._split_lines(cleaned.get('medications', '')),
			'allergies': self._split_lines(cleaned.get('allergies', '')),
			'clinical_notes_summary': cleaned.get('clinical_notes_summary', ''),
		}

	def get_genomic_payload(self) -> dict | None:
		cleaned = self.cleaned_data
		if not cleaned.get('gene_symbol') and not cleaned.get('variant'):
			return None

		return {
			'gene_symbol': cleaned.get('gene_symbol', ''),
			'variant': cleaned.get('variant', ''),
			'clinical_significance': cleaned.get('clinical_significance') or GenomicInsight.Significance.UNCERTAIN,
			'is_actionable': cleaned.get('is_actionable', False),
			'evidence_summary': cleaned.get('evidence_summary', ''),
		}