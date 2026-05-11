from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os


logger = logging.getLogger(__name__)


@dataclass
class AIProviderResult:
	summary: str
	rationale: str
	suggested_options: list[dict]
	evidence_references: list[dict]
	uncertainty_notes: str
	missing_data_flags: list[str]
	contraindication_warnings: list[str]
	model_name: str
	model_version: str


class BaseRecommendationProvider:
	provider_name = 'base'

	def generate(self, *, patient_payload: dict, genomic_payload: dict | None = None) -> AIProviderResult:
		raise NotImplementedError


class PlaceholderRecommendationProvider(BaseRecommendationProvider):
	provider_name = 'safe-placeholder-engine'

	def generate(self, *, patient_payload: dict, genomic_payload: dict | None = None) -> AIProviderResult:
		missing_data_flags = []
		contraindication_warnings = []
		evidence_references = []

		if not patient_payload.get('diagnoses'):
			missing_data_flags.append('No diagnoses recorded')
		if not patient_payload.get('medications'):
			missing_data_flags.append('No medication history recorded')
		if not patient_payload.get('allergies'):
			missing_data_flags.append('No allergy history recorded')

		for medication in patient_payload.get('medications', []):
			if isinstance(medication, str) and medication.lower() == 'warfarin':
				contraindication_warnings.append('Potential interaction risk requires specialist review')

		if genomic_payload and genomic_payload.get('is_actionable'):
			evidence_references.append(
				{
					'type': 'genomic_insight',
					'gene_symbol': genomic_payload.get('gene_symbol', ''),
					'variant': genomic_payload.get('variant', ''),
					'clinical_significance': genomic_payload.get('clinical_significance', ''),
				}
			)
		else:
			missing_data_flags.append('No actionable genomic insight available')

		rationale_parts = [
			'Patient-specific recommendation draft based on available structured clinical context.',
		]
		if genomic_payload and genomic_payload.get('is_actionable'):
			rationale_parts.append(
				f"Actionable genomic signal observed: {genomic_payload.get('gene_symbol', '')} {genomic_payload.get('variant', '')}."
			)
		if missing_data_flags:
			rationale_parts.append('Missing data limits confidence and requires explicit clinician review.')

		return AIProviderResult(
			summary='Structured recommendation draft generated from currently available clinical and genomic data. Clinician review is required before use.',
			rationale=' '.join(rationale_parts),
			suggested_options=[
				{
					'label': 'Clinician review required',
					'description': 'Review the patient profile, genomic evidence, and contraindications before any action.',
				}
			],
			evidence_references=evidence_references,
			uncertainty_notes='Recommendation generated with incomplete clinical context. Clinician review required.' if missing_data_flags else '',
			missing_data_flags=missing_data_flags,
			contraindication_warnings=contraindication_warnings,
			model_name=self.provider_name,
			model_version='rules-v2',
		)


class GeminiRecommendationProvider(BaseRecommendationProvider):
	provider_name = 'gemini'

	def __init__(self, api_key: str, model: str = 'gemini-1.5-pro'):
		self.api_key = api_key
		self.model = model

	def _build_prompt(self, *, patient_payload: dict, genomic_payload: dict | None) -> str:
		return (
			'You are generating a clinical decision support draft, not final medical advice. '
			'Return only valid JSON with fields: summary, rationale, suggested_options, evidence_references, '
			'uncertainty_notes, missing_data_flags, contraindication_warnings. '
			'Be conservative, surface uncertainty, and require clinician review. '
			f'Patient data: {json.dumps(patient_payload)}. '
			f'Genomic data: {json.dumps(genomic_payload or {})}.'
		)

	def _call_gemini(self, prompt: str) -> dict:
		try:
			import google.generativeai as genai
		except ImportError as exc:
			raise RuntimeError('google-generativeai is not installed') from exc

		genai.configure(api_key=self.api_key)
		model = genai.GenerativeModel(self.model)
		response = model.generate_content(prompt)
		text = getattr(response, 'text', '') or ''
		if not text:
			raise RuntimeError('Gemini returned an empty response')

		text = text.strip()
		if text.startswith('```'):
			text = text.strip('`')
			if text.lower().startswith('json'):
				text = text[4:].strip()

		return json.loads(text)

	def generate(self, *, patient_payload: dict, genomic_payload: dict | None = None) -> AIProviderResult:
		payload = self._call_gemini(self._build_prompt(patient_payload=patient_payload, genomic_payload=genomic_payload))

		return AIProviderResult(
			summary=payload.get('summary', 'Clinician review required.'),
			rationale=payload.get('rationale', 'AI-generated rationale unavailable.'),
			suggested_options=payload.get('suggested_options', []),
			evidence_references=payload.get('evidence_references', []),
			uncertainty_notes=payload.get('uncertainty_notes', ''),
			missing_data_flags=payload.get('missing_data_flags', []),
			contraindication_warnings=payload.get('contraindication_warnings', []),
			model_name=self.provider_name,
			model_version=self.model,
		)


def get_recommendation_provider() -> BaseRecommendationProvider:
	provider_name = os.getenv('HELIXORA_AI_PROVIDER', 'placeholder').strip().lower()
	gemini_api_key = os.getenv('GEMINI_API_KEY', '').strip()
	gemini_model = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro').strip() or 'gemini-1.5-pro'

	if provider_name == 'gemini' and gemini_api_key:
		try:
			return GeminiRecommendationProvider(api_key=gemini_api_key, model=gemini_model)
		except Exception:
			logger.exception('Failed to initialize Gemini provider, falling back to placeholder provider')

	return PlaceholderRecommendationProvider()


def get_provider_status() -> dict:
	provider_name = os.getenv('HELIXORA_AI_PROVIDER', 'placeholder').strip().lower()
	gemini_api_key_present = bool(os.getenv('GEMINI_API_KEY', '').strip())
	gemini_model = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro').strip() or 'gemini-1.5-pro'

	active_provider = 'placeholder'
	if provider_name == 'gemini' and gemini_api_key_present:
		active_provider = 'gemini'

	return {
		'configured_provider': provider_name,
		'active_provider': active_provider,
		'gemini_api_key_present': gemini_api_key_present,
		'gemini_model': gemini_model,
	}