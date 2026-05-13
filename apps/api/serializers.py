from rest_framework import serializers

from apps.audit.models import AuditEvent
from apps.genomics.models import GenomicInsight
from apps.patients.models import PatientProfile
from apps.recommendations.models import TreatmentRecommendation
from apps.reviews.models import ClinicalReview


class PatientProfileSerializer(serializers.ModelSerializer):
	class Meta:
		model = PatientProfile
		fields = [
			'id',
			'external_id',
			'date_of_birth',
			'record_status',
			'sex_at_birth',
			'consent_status',
			'diagnoses',
			'comorbidities',
			'medications',
			'allergies',
			'lifestyle_factors',
			'disease_progression_summary',
			'clinical_notes_summary',
			'created_at',
			'updated_at',
		]
		read_only_fields = ['id', 'created_at', 'updated_at']


class GenomicInsightSerializer(serializers.ModelSerializer):
	class Meta:
		model = GenomicInsight
		fields = [
			'id',
			'patient',
			'gene_symbol',
			'variant',
			'biomarker_category',
			'clinical_significance',
			'review_status',
			'is_actionable',
			'evidence_summary',
			'source',
			'report_reference',
			'observed_at',
			'created_at',
		]
		read_only_fields = ['id', 'created_at']


class TreatmentRecommendationSerializer(serializers.ModelSerializer):
	class Meta:
		model = TreatmentRecommendation
		fields = [
			'id',
			'patient',
			'primary_genomic_insight',
			'title',
			'summary',
			'rationale',
			'evidence_references',
			'suggested_options',
			'contraindication_warnings',
			'missing_data_flags',
			'uncertainty_notes',
			'intended_use_notice',
			'status',
			'confidence_level',
			'risk_level',
			'clinician_review_required',
			'generated_by',
			'model_version',
			'created_at',
			'updated_at',
		]
		read_only_fields = [
			'id',
			'summary',
			'rationale',
			'evidence_references',
			'suggested_options',
			'contraindication_warnings',
			'missing_data_flags',
			'uncertainty_notes',
			'intended_use_notice',
			'status',
			'confidence_level',
			'risk_level',
			'clinician_review_required',
			'generated_by',
			'model_version',
			'created_at',
			'updated_at',
		]

	def validate(self, attrs):
		patient = attrs.get('patient', getattr(self.instance, 'patient', None))
		primary_genomic_insight = attrs.get(
			'primary_genomic_insight',
			getattr(self.instance, 'primary_genomic_insight', None),
		)
		if patient and primary_genomic_insight and primary_genomic_insight.patient_id != patient.id:
			raise serializers.ValidationError(
				{'primary_genomic_insight': 'Primary genomic insight must belong to the recommendation patient.'}
			)

		missing_data_flags = attrs.get('missing_data_flags', getattr(self.instance, 'missing_data_flags', None))
		confidence_level = attrs.get('confidence_level', getattr(self.instance, 'confidence_level', None))
		if missing_data_flags and confidence_level == TreatmentRecommendation.ConfidenceLevel.HIGH:
			raise serializers.ValidationError(
				{'confidence_level': 'High confidence is not allowed when missing data flags are present.'}
			)
		return attrs


class ClinicalReviewSerializer(serializers.ModelSerializer):
	class Meta:
		model = ClinicalReview
		fields = [
			'id',
			'recommendation',
			'reviewer',
			'decision',
			'review_notes',
			'override_reason',
			'limitations_acknowledged',
			'missing_data_acknowledged',
			'reviewed_at',
			'created_at',
			'updated_at',
		]
		read_only_fields = ['id', 'recommendation', 'reviewer', 'reviewed_at', 'created_at', 'updated_at']

	def validate(self, attrs):
		decision = attrs.get('decision', getattr(self.instance, 'decision', None))
		override_reason = attrs.get('override_reason', getattr(self.instance, 'override_reason', ''))
		limitations_acknowledged = attrs.get(
			'limitations_acknowledged',
			getattr(self.instance, 'limitations_acknowledged', False),
		)
		missing_data_acknowledged = attrs.get(
			'missing_data_acknowledged',
			getattr(self.instance, 'missing_data_acknowledged', False),
		)

		if decision == ClinicalReview.Decision.OVERRIDDEN and not override_reason:
			raise serializers.ValidationError(
				{'override_reason': 'Override reason is required when a recommendation is overridden.'}
			)

		if decision in {
			ClinicalReview.Decision.APPROVED,
			ClinicalReview.Decision.OVERRIDDEN,
			ClinicalReview.Decision.REJECTED,
		}:
			if not limitations_acknowledged:
				raise serializers.ValidationError(
					{'limitations_acknowledged': 'Reviewer must acknowledge recommendation limitations.'}
				)
			if not missing_data_acknowledged:
				raise serializers.ValidationError(
					{'missing_data_acknowledged': 'Reviewer must acknowledge missing data considerations.'}
				)

		return attrs


class AuditEventSerializer(serializers.ModelSerializer):
	class Meta:
		model = AuditEvent
		fields = [
			'id',
			'event_type',
			'patient',
			'recommendation',
			'actor',
			'correlation_id',
			'metadata',
			'created_at',
		]
		read_only_fields = fields
