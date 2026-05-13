import logging
from contextvars import ContextVar


correlation_id_var = ContextVar('correlation_id', default='')

SENSITIVE_LOG_KEY_PARTS = (
	'patient',
	'person',
	'name',
	'email',
	'phone',
	'address',
	'mrn',
	'medical_record',
	'phi',
	'pii',
	'genomic',
	'genome',
	'gene',
	'variant',
	'dna',
	'sequence',
	'prompt',
	'response',
)


def _is_sensitive_key(key):
	key_text = str(key).lower()
	return any(part in key_text for part in SENSITIVE_LOG_KEY_PARTS)


def _redact_sensitive_values(value):
	if isinstance(value, dict):
		return {
			key: '[REDACTED]' if _is_sensitive_key(key) else _redact_sensitive_values(item)
			for key, item in value.items()
		}
	if isinstance(value, tuple):
		return tuple(_redact_sensitive_values(item) for item in value)
	if isinstance(value, list):
		return [_redact_sensitive_values(item) for item in value]
	return value


class CorrelationIdFilter(logging.Filter):
	def filter(self, record):
		try:
			record.correlation_id = correlation_id_var.get() or 'n/a'
		except Exception:
			record.correlation_id = 'n/a'

		try:
			if record.args:
				record.args = _redact_sensitive_values(record.args)
			record.msg = _redact_sensitive_values(record.msg)
		except Exception:
			record.msg = '[LOG REDACTION FAILED]'
			record.args = ()

		return True
