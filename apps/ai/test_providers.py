import json
from unittest.mock import patch

from django.test import TestCase

from apps.ai.providers import AIProviderResult, GeminiRecommendationProvider, get_recommendation_provider
from apps.ai.workflow import RecommendationConsentError, run_recommendation_workflow
from apps.audit.models import AuditEvent
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


class GeminiProviderTests(TestCase):
	def test_provider_status_selects_gemini_when_configured(self):
		with patch.dict(
			'os.environ',
			{
				'HELIXORA_AI_PROVIDER': 'gemini',
				'GEMINI_API_KEY': 'test-key',
				'GEMINI_MODEL': 'gemini-test-model',
			},
			clear=False,
		):
			provider = get_recommendation_provider()

		self.assertIsInstance(provider, GeminiRecommendationProvider)
		self.assertEqual(provider.model, 'gemini-test-model')

	def test_gemini_json_extraction_handles_fenced_response(self):
		provider = GeminiRecommendationProvider(api_key='test-key', model='gemini-test-model')
		payload = {
			'summary': 'Summary',
			'rationale': 'Rationale',
			'suggested_options': [],
			'evidence_references': [],
			'uncertainty_notes': '',
			'missing_data_flags': [],
			'contraindication_warnings': [],
		}

		extracted = provider._extract_json_text(f"```json\n{json.dumps(payload)}\n```")

		self.assertEqual(json.loads(extracted), payload)

	def test_gemini_malformed_json_is_safely_normalized(self):
		provider = GeminiRecommendationProvider(api_key='test-key', model='gemini-test-model')
		payload = provider._payload_from_malformed_json(
			'{"summary":"Partial AI summary","rationale":"Partial AI rationale","suggested_options":[{"label":"Review"}'
		)

		self.assertEqual(payload['summary'], 'Partial AI summary')
		self.assertEqual(payload['rationale'], 'Partial AI rationale')
		self.assertIn('AI response normalization incomplete', payload['missing_data_flags'])

	def test_workflow_falls_back_when_provider_fails(self):
		class FailingProvider:
			provider_name = 'failing'

			def generate(self, *, patient_payload, genomic_payload=None):
				raise RuntimeError('provider unavailable for sensitive patient payload')

		with patch('apps.ai.workflow.get_recommendation_provider', return_value=FailingProvider()):
			with self.assertLogs('apps.ai.workflow', level='WARNING') as logs:
				result = run_recommendation_workflow(
					patient_data={
						'external_id': 'P-GEMINI-FALLBACK',
						'consent_status': 'granted',
						'diagnoses': ['Condition A'],
						'medications': ['Medication A'],
						'allergies': ['None known'],
						'clinical_notes_summary': 'Stable presentation.',
					},
					genomic_data={
						'gene_symbol': 'EGFR',
						'variant': 'L858R',
						'clinical_significance': 'high',
						'is_actionable': True,
						'evidence_summary': 'Known actionable alteration.',
					},
				)

		self.assertEqual(result.recommendation.generated_by, 'safe-placeholder-engine')
		self.assertIn('safe placeholder rules were used', result.recommendation.uncertainty_notes)
		self.assertTrue(result.used_fallback)
		self.assertIn('Recommendation provider failed; using safe placeholder provider', logs.output[0])
		self.assertNotIn('sensitive patient payload', logs.output[0])

	def test_workflow_persists_successful_ai_provider_output(self):
		class SuccessfulProvider:
			provider_name = 'test-ai'

			def generate(self, *, patient_payload, genomic_payload=None):
				return AIProviderResult(
					summary='AI-generated review summary.',
					rationale='AI-generated rationale with clinician review requirement.',
					suggested_options=[{'label': 'Review option', 'description': 'Clinician review required.'}],
					evidence_references=[{'type': 'genomic_insight', 'gene_symbol': 'EGFR'}],
					uncertainty_notes='AI output requires validation by a qualified clinician.',
					missing_data_flags=[],
					contraindication_warnings=[],
					model_name='test-ai',
					model_version='test-model-v1',
				)

		with patch('apps.ai.workflow.get_recommendation_provider', return_value=SuccessfulProvider()):
			result = run_recommendation_workflow(
				patient_data={
					'external_id': 'P-AI-SUCCESS',
					'consent_status': 'granted',
					'diagnoses': ['Condition A'],
					'medications': ['Medication A'],
					'allergies': ['None known'],
					'clinical_notes_summary': 'Stable presentation.',
				},
				genomic_data={
					'gene_symbol': 'EGFR',
					'variant': 'L858R',
					'clinical_significance': 'high',
					'is_actionable': True,
					'evidence_summary': 'Known actionable alteration.',
				},
			)

		recommendation = result.recommendation
		self.assertFalse(result.used_fallback)
		self.assertEqual(recommendation.generated_by, 'test-ai')
		self.assertEqual(recommendation.model_version, 'test-model-v1')
		self.assertEqual(recommendation.summary, 'AI-generated review summary.')
		self.assertEqual(recommendation.confidence_level, TreatmentRecommendation.ConfidenceLevel.MEDIUM)
		self.assertEqual(recommendation.risk_level, TreatmentRecommendation.RiskLevel.LOW)
		self.assertTrue(
			recommendation.audit_events.filter(
				event_type=AuditEvent.EventType.RECOMMENDATION_UPDATED,
				metadata__ai_provider='test-ai',
				metadata__used_fallback=False,
			).exists()
		)

	def test_workflow_blocks_denied_consent_before_provider_call_or_recommendation(self):
		class UnexpectedProvider:
			provider_name = 'unexpected'

			def generate(self, *, patient_payload, genomic_payload=None):
				raise AssertionError('provider should not be called without consent')

		with patch('apps.ai.workflow.get_recommendation_provider', return_value=UnexpectedProvider()):
			with self.assertRaises(RecommendationConsentError) as raised:
				run_recommendation_workflow(
					patient_data={
						'external_id': 'P-CONSENT-DENIED',
						'consent_status': 'denied',
						'diagnoses': ['Condition A'],
						'medications': ['Medication A'],
						'allergies': ['None known'],
					},
				)

		self.assertIn('consent', str(raised.exception).lower())
		self.assertEqual(TreatmentRecommendation.objects.count(), 0)
		self.assertFalse(PatientProfile.objects.filter(external_id='P-CONSENT-DENIED').exists())

	def test_workflow_blocks_missing_consent_before_provider_call_or_recommendation(self):
		with patch('apps.ai.workflow.get_recommendation_provider') as get_provider:
			with self.assertRaises(RecommendationConsentError):
				run_recommendation_workflow(
					patient_data={
						'external_id': 'P-CONSENT-MISSING',
						'diagnoses': ['Condition A'],
						'medications': ['Medication A'],
						'allergies': ['None known'],
					},
				)

		get_provider.assert_not_called()
		self.assertEqual(TreatmentRecommendation.objects.count(), 0)
		self.assertFalse(PatientProfile.objects.filter(external_id='P-CONSENT-MISSING').exists())

	def test_workflow_normalizes_empty_provider_options_to_review_required_output(self):
		class EmptyOptionsProvider:
			provider_name = 'empty-output-ai'

			def generate(self, *, patient_payload, genomic_payload=None):
				return AIProviderResult(
					summary='',
					rationale='',
					suggested_options=[],
					evidence_references=[],
					uncertainty_notes='',
					missing_data_flags=[],
					contraindication_warnings=[],
					model_name='empty-output-ai',
					model_version='test-model-v1',
				)

		with patch('apps.ai.workflow.get_recommendation_provider', return_value=EmptyOptionsProvider()):
			result = run_recommendation_workflow(
				patient_data={
					'external_id': 'P-AI-EMPTY',
					'consent_status': 'active',
					'diagnoses': ['Condition A'],
					'medications': ['Medication A'],
					'allergies': ['None known'],
				},
			)

		recommendation = result.recommendation
		self.assertEqual(recommendation.status, TreatmentRecommendation.Status.NEEDS_REVIEW)
		self.assertTrue(recommendation.clinician_review_required)
		self.assertEqual(recommendation.confidence_level, TreatmentRecommendation.ConfidenceLevel.INSUFFICIENT_DATA)
		self.assertGreaterEqual(len(recommendation.suggested_options), 1)
		self.assertIn('Clinician review required', recommendation.suggested_options[0]['label'])
		self.assertIn('AI provider output omitted suggested options', recommendation.missing_data_flags)

	def test_workflow_normalizes_malformed_provider_result_to_safe_lists(self):
		class MalformedProvider:
			provider_name = 'malformed-output-ai'

			def generate(self, *, patient_payload, genomic_payload=None):
				return AIProviderResult(
					summary='Malformed provider summary',
					rationale='Malformed provider rationale',
					suggested_options='Take direct action',
					evidence_references={'type': 'unsupported'},
					uncertainty_notes='',
					missing_data_flags={'missing': 'renal function'},
					contraindication_warnings=[{'warning': 'nested object'}],
					model_name='malformed-output-ai',
					model_version='test-model-v1',
				)

		with patch('apps.ai.workflow.get_recommendation_provider', return_value=MalformedProvider()):
			result = run_recommendation_workflow(
				patient_data={
					'external_id': 'P-AI-MALFORMED',
					'consent_status': 'consented',
					'diagnoses': ['Condition A'],
					'medications': ['Medication A'],
					'allergies': ['None known'],
				},
			)

		recommendation = result.recommendation
		self.assertEqual(
			recommendation.suggested_options,
			[
				{
					'label': 'Clinician review required',
					'description': 'AI provider output was incomplete or malformed; review the patient profile and source evidence before action.',
				}
			],
		)
		self.assertEqual(recommendation.evidence_references, [])
		self.assertIn('AI provider output contained invalid suggested options', recommendation.missing_data_flags)
		self.assertIn('AI provider output contained invalid evidence references', recommendation.missing_data_flags)
		self.assertEqual(recommendation.risk_level, TreatmentRecommendation.RiskLevel.HIGH)
