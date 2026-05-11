from dataclasses import dataclass

from apps.audit.models import AuditEvent
from apps.audit.services import create_audit_event
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview


@dataclass
class RecommendationContext:
	patient: PatientProfile
	primary_genomic_insight: GenomicInsight | None
	contraindication_warnings: list[str]
	missing_data_flags: list[str]
	evidence_references: list[dict]
	confidence_level: str
	risk_level: str
	uncertainty_notes: str


def build_recommendation_context(patient: PatientProfile) -> RecommendationContext:
	genomic_insight = (
		patient.genomic_insights.filter(is_actionable=True)
		.order_by('-created_at')
		.first()
	)
	missing_data_flags = []
	contraindication_warnings = []
	evidence_references = []
	confidence_level = TreatmentRecommendation.ConfidenceLevel.MEDIUM
	risk_level = TreatmentRecommendation.RiskLevel.MEDIUM
	uncertainty_notes = ''

	if not patient.diagnoses:
		missing_data_flags.append('No diagnoses recorded')
	if not patient.medications:
		missing_data_flags.append('No medication history recorded')
	if not patient.allergies:
		missing_data_flags.append('No allergy history recorded')

	if missing_data_flags:
		confidence_level = TreatmentRecommendation.ConfidenceLevel.INSUFFICIENT_DATA
		uncertainty_notes = 'Recommendation generated with incomplete clinical context. Clinician review required.'

	if genomic_insight:
		evidence_references.append(
			{
				'type': 'genomic_insight',
				'gene_symbol': genomic_insight.gene_symbol,
				'variant': genomic_insight.variant,
				'clinical_significance': genomic_insight.clinical_significance,
			}
		)
	else:
		missing_data_flags.append('No actionable genomic insight available')

	for medication in patient.medications:
		if isinstance(medication, str) and medication.lower() == 'warfarin':
			contraindication_warnings.append('Potential interaction risk requires specialist review')

	if contraindication_warnings:
		risk_level = TreatmentRecommendation.RiskLevel.HIGH

	return RecommendationContext(
		patient=patient,
		primary_genomic_insight=genomic_insight,
		contraindication_warnings=contraindication_warnings,
		missing_data_flags=missing_data_flags,
		evidence_references=evidence_references,
		confidence_level=confidence_level,
		risk_level=risk_level,
		uncertainty_notes=uncertainty_notes,
	)


def generate_recommendation(
	*,
	patient: PatientProfile,
	actor=None,
	correlation_id: str = '',
	generated_by: str = 'safe-placeholder-engine',
	model_version: str = 'rules-v1',
) -> TreatmentRecommendation:
	context = build_recommendation_context(patient)
	title = f'Personalized treatment review for {patient.external_id}'
	summary = (
		'Structured recommendation draft generated from currently available clinical and genomic data. '
		'Clinician review is required before use.'
	)
	rationale_parts = [
		'Patient-specific recommendation draft based on available structured clinical context.',
	]
	if context.primary_genomic_insight:
		rationale_parts.append(
			f"Actionable genomic signal observed: {context.primary_genomic_insight.gene_symbol} {context.primary_genomic_insight.variant}."
		)
	if context.missing_data_flags:
		rationale_parts.append('Missing data limits confidence and requires explicit clinician review.')

	recommendation = TreatmentRecommendation.objects.create(
		patient=patient,
		primary_genomic_insight=context.primary_genomic_insight,
		title=title,
		summary=summary,
		rationale=' '.join(rationale_parts),
		evidence_references=context.evidence_references,
		suggested_options=[
			{
				'label': 'Clinician review required',
				'description': 'Review the patient profile, genomic evidence, and contraindications before any action.',
			}
		],
		contraindication_warnings=context.contraindication_warnings,
		missing_data_flags=context.missing_data_flags,
		uncertainty_notes=context.uncertainty_notes,
		status=TreatmentRecommendation.Status.NEEDS_REVIEW,
		confidence_level=context.confidence_level,
		risk_level=context.risk_level,
		clinician_review_required=True,
		generated_by=generated_by,
		model_version=model_version,
	)

	ClinicalReview.objects.create(recommendation=recommendation)

	create_audit_event(
		event_type=AuditEvent.EventType.RECOMMENDATION_CREATED,
		patient=patient,
		recommendation=recommendation,
		actor=actor,
		correlation_id=correlation_id,
		metadata={
			'generated_by': generated_by,
			'model_version': model_version,
			'missing_data_flags': context.missing_data_flags,
		},
	)
	create_audit_event(
		event_type=AuditEvent.EventType.RECOMMENDATION_REVIEW_REQUESTED,
		patient=patient,
		recommendation=recommendation,
		actor=actor,
		correlation_id=correlation_id,
		metadata={'review_required': True},
	)

	return recommendation