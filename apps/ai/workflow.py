from __future__ import annotations

from dataclasses import dataclass

from apps.ai.providers import get_recommendation_provider
from apps.ai.services import generate_recommendation
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile


@dataclass
class RecommendationWorkflowResult:
	patient: PatientProfile
	genomic_insight: GenomicInsight | None
	recommendation: object


def run_recommendation_workflow(*, patient_data: dict, genomic_data: dict | None = None, actor=None, correlation_id: str = ''):
	patient = PatientProfile.objects.create(**patient_data)
	genomic_insight = None

	if genomic_data and genomic_data.get('gene_symbol') and genomic_data.get('variant'):
		genomic_insight = GenomicInsight.objects.create(patient=patient, **genomic_data)

	provider = get_recommendation_provider()
	provider_result = provider.generate(patient_payload=patient_data, genomic_payload=genomic_data)

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
			'updated_at',
		]
	)

	return RecommendationWorkflowResult(
		patient=patient,
		genomic_insight=genomic_insight,
		recommendation=recommendation,
	)