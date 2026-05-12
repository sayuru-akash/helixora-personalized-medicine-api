from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
import re
from json import JSONDecodeError


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

	def __init__(self, api_key: str, model: str = 'gemini-2.5-flash'):
		self.api_key = api_key
		self.model = model

	def _build_prompt(self, *, patient_payload: dict, genomic_payload: dict | None) -> str:
		return (
			'Generate a structured clinical decision-support draft for the supplied synthetic or de-identified data. '
			'Do not provide final medical advice, diagnosis, dosing, or autonomous treatment orders. '
			'Always surface uncertainty, missing data, contraindication considerations, and clinician review requirements. '
			f'Patient data: {json.dumps(patient_payload, default=str)}. '
			f'Genomic data: {json.dumps(genomic_payload or {}, default=str)}.'
		)

	def _coerce_list(self, value) -> list:
		if value is None:
			return []
		if isinstance(value, list):
			return value
		if isinstance(value, tuple):
			return list(value)
		if isinstance(value, str):
			return [value] if value.strip() else []
		return [value]

	def _extract_string_field(self, text: str, field_name: str) -> str:
		match = re.search(
			rf'"{re.escape(field_name)}"\s*:\s*"((?:\\.|[^"\\])*)"',
			text,
			flags=re.IGNORECASE | re.DOTALL,
		)
		if not match:
			return ''
		try:
			return json.loads(f'"{match.group(1)}"')
		except JSONDecodeError:
			return match.group(1).replace('\\n', ' ').replace('\\"', '"').strip()

	def _payload_from_malformed_json(self, text: str) -> dict:
		return {
			'summary': self._extract_string_field(text, 'summary')
			or 'AI provider returned a response that requires clinician review before use.',
			'rationale': self._extract_string_field(text, 'rationale')
			or 'AI provider response could not be fully normalized into structured rationale. Clinician review is required.',
			'suggested_options': [
				{
					'label': 'Clinician review required',
					'description': 'AI response normalization was incomplete; review source data and generated text before action.',
				}
			],
			'evidence_references': [],
			'uncertainty_notes': self._extract_string_field(text, 'uncertainty_notes')
			or 'AI response normalization was incomplete; verify all clinical assumptions before action.',
			'missing_data_flags': ['AI response normalization incomplete'],
			'contraindication_warnings': [],
		}

	def _call_gemini(self, prompt: str) -> dict:
		try:
			from google import genai
			from google.genai import types
			from pydantic import BaseModel, Field
		except ImportError as exc:
			raise RuntimeError('google-genai is not installed') from exc

		class RecommendationOption(BaseModel):
			label: str = ''
			description: str = ''

		class EvidenceReference(BaseModel):
			type: str = ''
			gene_symbol: str = ''
			variant: str = ''
			clinical_significance: str = ''

		class GeminiRecommendationPayload(BaseModel):
			summary: str = ''
			rationale: str = ''
			suggested_options: list[RecommendationOption] = Field(default_factory=list)
			evidence_references: list[EvidenceReference] = Field(default_factory=list)
			uncertainty_notes: str = ''
			missing_data_flags: list[str] = Field(default_factory=list)
			contraindication_warnings: list[str] = Field(default_factory=list)

		client = genai.Client(
			api_key=self.api_key,
			http_options=types.HttpOptions(timeout=30000),
		)
		response = client.models.generate_content(
			model=self.model,
			contents=prompt,
			config=types.GenerateContentConfig(
				systemInstruction=(
					'You are generating a clinical decision support draft, not final medical advice. '
					'Return only valid JSON with fields: summary, rationale, suggested_options, evidence_references, '
					'uncertainty_notes, missing_data_flags, contraindication_warnings. '
					'Be conservative, surface uncertainty, and require clinician review.'
				),
				responseMimeType='application/json',
				responseSchema=GeminiRecommendationPayload,
				temperature=0.2,
				maxOutputTokens=2400,
			),
		)
		parsed = getattr(response, 'parsed', None)
		if parsed:
			if hasattr(parsed, 'model_dump'):
				return parsed.model_dump()
			if isinstance(parsed, dict):
				return parsed

		text = getattr(response, 'text', '') or ''
		if not text:
			raise RuntimeError('Gemini returned an empty response')

		text = self._extract_json_text(text)

		try:
			return json.loads(text)
		except JSONDecodeError:
			logger.warning('Gemini returned malformed JSON; preserving AI response with safe normalization')
			return self._payload_from_malformed_json(text)

	def _extract_json_text(self, text: str) -> str:
		text = text.strip()
		fenced_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.IGNORECASE | re.DOTALL)
		if fenced_match:
			return fenced_match.group(1).strip()

		start = text.find('{')
		end = text.rfind('}')
		if start != -1 and end != -1 and end > start:
			return text[start : end + 1].strip()

		return text

	def generate(self, *, patient_payload: dict, genomic_payload: dict | None = None) -> AIProviderResult:
		payload = self._call_gemini(self._build_prompt(patient_payload=patient_payload, genomic_payload=genomic_payload))

		summary = (payload.get('summary') or '').strip()
		rationale = (payload.get('rationale') or '').strip()
		uncertainty_notes = (payload.get('uncertainty_notes') or '').strip()

		if not summary:
			summary = 'AI-generated clinical decision-support draft requires clinician review before action.'
		if not rationale:
			rationale = 'AI-generated rationale was incomplete; qualified clinician review is required.'
		if not uncertainty_notes:
			uncertainty_notes = 'AI output is decision support only and must be reviewed by a qualified clinician.'

		return AIProviderResult(
			summary=summary,
			rationale=rationale,
			suggested_options=self._coerce_list(payload.get('suggested_options')),
			evidence_references=self._coerce_list(payload.get('evidence_references')),
			uncertainty_notes=uncertainty_notes,
			missing_data_flags=[str(item) for item in self._coerce_list(payload.get('missing_data_flags')) if str(item).strip()],
			contraindication_warnings=[
				str(item) for item in self._coerce_list(payload.get('contraindication_warnings')) if str(item).strip()
			],
			model_name=self.provider_name,
			model_version=self.model,
		)


def get_recommendation_provider() -> BaseRecommendationProvider:
	provider_name = os.getenv('HELIXORA_AI_PROVIDER', 'placeholder').strip().lower()
	gemini_api_key = os.getenv('GEMINI_API_KEY', '').strip()
	gemini_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash').strip() or 'gemini-2.5-flash'

	if provider_name == 'gemini' and gemini_api_key:
		try:
			return GeminiRecommendationProvider(api_key=gemini_api_key, model=gemini_model)
		except Exception:
			logger.exception('Failed to initialize Gemini provider, falling back to placeholder provider')

	return PlaceholderRecommendationProvider()


def get_provider_status() -> dict:
	provider_name = os.getenv('HELIXORA_AI_PROVIDER', 'placeholder').strip().lower()
	gemini_api_key_present = bool(os.getenv('GEMINI_API_KEY', '').strip())
	gemini_model = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash').strip() or 'gemini-2.5-flash'

	active_provider = 'placeholder'
	if provider_name == 'gemini' and gemini_api_key_present:
		active_provider = 'gemini'

	return {
		'configured_provider': provider_name,
		'active_provider': active_provider,
		'gemini_api_key_present': gemini_api_key_present,
		'gemini_model': gemini_model,
	}
