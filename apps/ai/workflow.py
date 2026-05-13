from __future__ import annotations

from dataclasses import dataclass
import logging

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.ai.providers import PlaceholderRecommendationProvider, get_recommendation_provider
from apps.ai.services import RecommendationConsentError, ensure_ai_consent_status, ensure_patient_ai_consent, generate_recommendation
from apps.audit.models import AuditEvent
from apps.audit.services import create_audit_event
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation


logger = logging.getLogger(__name__)


__all__ = ['RecommendationConsentError', 'RecommendationWorkflowResult', 'run_recommendation_workflow']


@dataclass
class RecommendationWorkflowResult:
	patient: PatientProfile
	genomic_insight: GenomicInsight | None
	recommendation: object
	provider_name: str
	used_fallback: bool


SAFE_REVIEW_OPTION = {
	'label': 'Clinician review required',
	'description': 'AI provider output was incomplete or malformed; review the patient profile and source evidence before action.',
}
DEFAULT_SAFE_SUMMARY = 'Clinical decision-support draft requires clinician review before action.'
DEFAULT_SAFE_RATIONALE = 'Provider output was incomplete or malformed; qualified clinician review is required.'
DEFAULT_SAFE_UNCERTAINTY = 'Output is clinical decision support only and must be reviewed by a qualified clinician.'


def _derive_input_missing_data_flags(*, patient_data: dict, genomic_data: dict | None) -> list[str]:
	missing_data_flags = []
	if not patient_data.get('diagnoses'):
		missing_data_flags.append('No diagnoses recorded')
	if not patient_data.get('medications'):
		missing_data_flags.append('No medication history recorded')
	if not patient_data.get('allergies'):
		missing_data_flags.append('No allergy history recorded')
	if not genomic_data or not genomic_data.get('is_actionable'):
		missing_data_flags.append('No actionable genomic insight available')
	return missing_data_flags


def _append_unique(items: list[str], value: str) -> None:
	if value and value not in items:
		items.append(value)


def _normalize_text(value, fallback: str) -> str:
	if isinstance(value, str):
		value = value.strip()
		return value or fallback
	return fallback


def _normalize_string_list(value) -> tuple[list[str], bool]:
	if value is None:
		return [], False
	if not isinstance(value, list):
		return [], True

	normalized = []
	invalid = False
	for item in value:
		if isinstance(item, str):
			item = item.strip()
			if item:
				normalized.append(item)
		else:
			invalid = True
	return normalized, invalid


def _normalize_dict_list(value) -> tuple[list[dict], bool]:
	if value is None:
		return [], False
	if not isinstance(value, list):
		return [], True

	normalized = []
	invalid = False
	for item in value:
		if isinstance(item, dict):
			clean_item = {str(key): value for key, value in item.items() if value not in (None, '')}
			if clean_item:
				normalized.append(clean_item)
			else:
				invalid = True
		else:
			invalid = True
	return normalized, invalid


def _normalize_provider_result(provider_result, *, patient_data: dict, genomic_data: dict | None):
	provider_result.summary = _normalize_text(provider_result.summary, DEFAULT_SAFE_SUMMARY)
	provider_result.rationale = _normalize_text(provider_result.rationale, DEFAULT_SAFE_RATIONALE)
	provider_result.uncertainty_notes = _normalize_text(provider_result.uncertainty_notes, DEFAULT_SAFE_UNCERTAINTY)

	missing_data_flags, missing_invalid = _normalize_string_list(provider_result.missing_data_flags)
	contraindication_warnings, contraindication_invalid = _normalize_string_list(
		provider_result.contraindication_warnings
	)
	suggested_options, suggested_options_invalid = _normalize_dict_list(provider_result.suggested_options)
	evidence_references, evidence_references_invalid = _normalize_dict_list(provider_result.evidence_references)

	for missing_flag in _derive_input_missing_data_flags(patient_data=patient_data, genomic_data=genomic_data):
		_append_unique(missing_data_flags, missing_flag)
	if missing_invalid:
		_append_unique(missing_data_flags, 'AI provider output contained invalid missing data flags')
	if contraindication_invalid:
		_append_unique(missing_data_flags, 'AI provider output contained invalid contraindication warnings')
		_append_unique(
			contraindication_warnings,
			'AI provider contraindication output was malformed; clinician safety review required',
		)
	if suggested_options_invalid:
		_append_unique(missing_data_flags, 'AI provider output contained invalid suggested options')
	if evidence_references_invalid:
		_append_unique(missing_data_flags, 'AI provider output contained invalid evidence references')
	if not suggested_options:
		suggested_options = [SAFE_REVIEW_OPTION.copy()]
		_append_unique(missing_data_flags, 'AI provider output omitted suggested options')

	provider_result.missing_data_flags = missing_data_flags
	provider_result.contraindication_warnings = contraindication_warnings
	provider_result.suggested_options = suggested_options
	provider_result.evidence_references = evidence_references
	provider_result.model_name = _normalize_text(provider_result.model_name, 'unknown-ai-provider')
	provider_result.model_version = _normalize_text(provider_result.model_version, 'unknown')
	return provider_result


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


def _actor_has_admin_scope(actor) -> bool:
	return bool(
		actor
		and getattr(actor, 'is_authenticated', False)
		and (actor.is_superuser or actor.groups.filter(name='clinical_admin').exists())
	)


def _actor_has_patient_scope(actor, patient: PatientProfile) -> bool:
	if actor is None:
		return True
	if not getattr(actor, 'is_authenticated', False):
		return False
	if _actor_has_admin_scope(actor):
		return True
	return patient.authorized_users.filter(pk=actor.pk).exists()


def _ensure_actor_can_use_patient(actor, patient: PatientProfile) -> None:
	if not _actor_has_patient_scope(actor, patient):
		raise PermissionDenied('You do not have access to this patient record.')


def _upsert_patient(*, external_id: str, patient_data: dict, actor=None):
	patient = PatientProfile.objects.filter(external_id=external_id).first()
	defaults = {key: value for key, value in patient_data.items() if key != 'external_id'}
	if patient is None:
		patient = PatientProfile(external_id=external_id, **defaults)
	else:
		_ensure_actor_can_use_patient(actor, patient)
		for key, value in defaults.items():
			setattr(patient, key, value)

	patient.full_clean()
	patient.save()
	if actor and getattr(actor, 'is_authenticated', False):
		patient.authorized_users.add(actor)
	return patient


def _create_genomic_insight(*, patient, genomic_data: dict | None):
	if not genomic_data or not genomic_data.get('gene_symbol') or not genomic_data.get('variant'):
		return None

	genomic_insight = GenomicInsight(patient=patient, **genomic_data)
	genomic_insight.full_clean()
	genomic_insight.save()
	return genomic_insight


def run_recommendation_workflow(*, patient_data: dict, genomic_data: dict | None = None, actor=None, correlation_id: str = ''):
	external_id = patient_data['external_id']
	ensure_ai_consent_status(patient_data.get('consent_status'))
	existing_patient = PatientProfile.objects.filter(external_id=external_id).first()
	if existing_patient:
		_ensure_actor_can_use_patient(actor, existing_patient)
		ensure_patient_ai_consent(existing_patient)

	with transaction.atomic():
		patient = _upsert_patient(external_id=external_id, patient_data=patient_data, actor=actor)
		ensure_patient_ai_consent(patient)
		genomic_insight = _create_genomic_insight(patient=patient, genomic_data=genomic_data)
		provider = get_recommendation_provider()
		create_audit_event(
			event_type=AuditEvent.EventType.AI_PROVIDER_REQUESTED,
			patient=patient,
			actor=actor,
			correlation_id=correlation_id,
			metadata={
				'provider': provider.provider_name,
				'has_genomic_payload': bool(genomic_data),
			},
		)

	used_fallback = False
	try:
		provider_result = provider.generate(patient_payload=patient_data, genomic_payload=genomic_data)
		provider_result = _normalize_provider_result(
			provider_result,
			patient_data=patient_data,
			genomic_data=genomic_data,
		)
	except Exception:
		logger.warning('Recommendation provider failed; using safe placeholder provider')
		used_fallback = True
		provider_result = PlaceholderRecommendationProvider().generate(
			patient_payload=patient_data,
			genomic_payload=genomic_data,
		)
		provider_result.uncertainty_notes = (
			f'{provider_result.uncertainty_notes} AI provider was unavailable; safe placeholder rules were used.'
		).strip()
		provider_result = _normalize_provider_result(
			provider_result,
			patient_data=patient_data,
			genomic_data=genomic_data,
		)

	with transaction.atomic():
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
