import uuid
import re

from config.logging import correlation_id_var


CORRELATION_ID_PATTERN = re.compile(r'^[A-Za-z0-9_.:-]{1,100}$')


def normalize_correlation_id(value):
	if value and CORRELATION_ID_PATTERN.fullmatch(value):
		return value
	return str(uuid.uuid4())


class CorrelationIdMiddleware:
	HEADER_NAME = 'HTTP_X_CORRELATION_ID'
	RESPONSE_HEADER = 'X-Correlation-ID'

	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		correlation_id = normalize_correlation_id(request.META.get(self.HEADER_NAME, ''))
		token = correlation_id_var.set(correlation_id)
		request.correlation_id = correlation_id
		try:
			response = self.get_response(request)
		finally:
			correlation_id_var.reset(token)

		response[self.RESPONSE_HEADER] = correlation_id
		return response
