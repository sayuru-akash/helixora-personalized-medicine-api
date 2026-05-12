from __future__ import annotations

from dataclasses import dataclass
import logging

from apps.ai.providers import PlaceholderRecommendationProvider, get_recommendation_provider
from apps.ai.services import generate_recommendation
from apps.audit.models import AuditEvent
from apps.audit.services import create_audit_event
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


logger = logging.getLogger(__name__)


@dataclass
class RecommendationWorkflowResult:
	patient: PatientProfile
	genomic_insight: GenomicInsight | None
	recommendation: object
	provider_name: str
	used_fallback: bool


def _derive_confidence_level(provider_result) -> str:
	if provider_result.missing_data_flags:
		return TreatmentRecommendation.ConfidenceLevel.INSUFFICIENT_DATA
	if provider_result.evidence_references and provider_result.suggested_options:
		return TreatmentRecommendation.ConfidenceLevel.MEDIUM
	return TreatmentRecommendation.ConfidenceLevel.LOW


def _derive_risk_level(provider_result) -> str:
	if provider_result.contraindication_warnings:
		return TreatmentRecommendation.RiskLevel.HIGH
	if provider_result.missing_data_flags:
		return TreatmentRecommendation.RiskLevel.MEDIUM
	return TreatmentRecommendation.RiskLevel.LOW


def run_recommendation_workflow(*, patient_data: dict, genomic_data: dict | None = None, actor=None, correlation_id: str = ''):
	external_id = patient_data['external_id']
	patient, _created = PatientProfile.objects.update_or_create(
		external_id=external_id,
		defaults={key: value for key, value in patient_data.items() if key != 'external_id'},
	)
	genomic_insight = None

	if genomic_data and genomic_data.get('gene_symbol') and genomic_data.get('variant'):
		genomic_insight = GenomicInsight.objects.create(patient=patient, **genomic_data)

	provider = get_recommendation_provider()
	used_fallback = False
	try:
		provider_result = provider.generate(patient_payload=patient_data, genomic_payload=genomic_data)
	except Exception:
		logger.exception('Recommendation provider failed; using safe placeholder provider')
		used_fallback = True
		provider_result = PlaceholderRecommendationProvider().generate(
			patient_payload=patient_data,
			genomic_payload=genomic_data,
		)
		provider_result.uncertainty_notes = (
			f'{provider_result.uncertainty_notes} AI provider was unavailable; safe placeholder rules were used.'
		).strip()

	recommendation = generate_recommendation(
		patient=patient,
		actor=actor,
		correlation_id=correlation_id,
		generated_by=provider_result.model_name,
		model_version=provider_result.model_version,
	)

	recommendation.summary = provider_result.summary
	recommendation.rationale = provider_result.rationale
	recommendation.suggested_options = provider_result.suggested_options
	recommendation.evidence_references = provider_result.evidence_references
	recommendation.uncertainty_notes = provider_result.uncertainty_notes
	recommendation.missing_data_flags = provider_result.missing_data_flags
	recommendation.contraindication_warnings = provider_result.contraindication_warnings
	recommendation.primary_genomic_insight = genomic_insight
	recommendation.confidence_level = _derive_confidence_level(provider_result)
	recommendation.risk_level = _derive_risk_level(provider_result)
	recommendation.generated_by = provider_result.model_name
	recommendation.model_version = provider_result.model_version
	recommendation.status = TreatmentRecommendation.Status.NEEDS_REVIEW
	recommendation.clinician_review_required = True
	recommendation.save(
		update_fields=[
			'summary',
			'rationale',
			'suggested_options',
			'evidence_references',
			'uncertainty_notes',
			'missing_data_flags',
			'contraindication_warnings',
			'primary_genomic_insight',
			'confidence_level',
			'risk_level',
			'generated_by',
			'model_version',
			'status',
			'clinician_review_required',
			'updated_at',
		]
	)

	create_audit_event(
		event_type=AuditEvent.EventType.RECOMMENDATION_UPDATED,
		patient=patient,
		recommendation=recommendation,
		actor=actor,
		correlation_id=correlation_id,
		metadata={
			'ai_provider': provider_result.model_name,
			'model_version': provider_result.model_version,
			'used_fallback': used_fallback,
			'confidence_level': recommendation.confidence_level,
			'risk_level': recommendation.risk_level,
		},
	)

	return RecommendationWorkflowResult(
		patient=patient,
		genomic_insight=genomic_insight,
		recommendation=recommendation,
		provider_name=provider_result.model_name,
		used_fallback=used_fallback,
	)
