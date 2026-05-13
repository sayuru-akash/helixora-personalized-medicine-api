import json
import logging
import os
import subprocess
import sys
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIRequestFactory

from apps.api.health import get_health_status
from apps.api.middleware import CorrelationIdMiddleware
from config.logging import CorrelationIdFilter


def run_settings_probe(extra_env, expression, module='config.settings.production'):
	env = {
		key: value
		for key, value in os.environ.items()
		if not key.startswith('DJANGO_') and key not in {'CELERY_BROKER_URL', 'CELERY_RESULT_BACKEND'}
	}
	env.update(extra_env)

	command = (
		'import importlib, json; '
		f'settings = importlib.import_module({module!r}); '
		f'print(json.dumps({expression}))'
	)
	return subprocess.run(
		[sys.executable, '-c', command],
		cwd=os.getcwd(),
		env=env,
		text=True,
		capture_output=True,
		check=False,
	)


class HealthStatusTests(SimpleTestCase):
	@override_settings(ENVIRONMENT='production', CELERY_TASK_ALWAYS_EAGER=True)
	def test_health_status_contains_environment_and_celery_details(self):
		status = get_health_status()

		self.assertEqual(status['environment'], 'production')
		self.assertTrue(status['celery']['task_always_eager'])


class CorrelationIdMiddlewareTests(SimpleTestCase):
	def test_middleware_sets_response_header(self):
		factory = APIRequestFactory()
		request = factory.get('/api/v1/health/')

		def get_response(incoming_request):
			from django.http import JsonResponse

			return JsonResponse({'ok': True, 'correlation_id': incoming_request.correlation_id})

		middleware = CorrelationIdMiddleware(get_response)
		response = middleware(request)

		self.assertIn('X-Correlation-ID', response)
		self.assertEqual(response['X-Correlation-ID'], request.correlation_id)

	def test_middleware_replaces_invalid_correlation_id_header(self):
		factory = APIRequestFactory()
		request = factory.get('/api/v1/health/', HTTP_X_CORRELATION_ID='bad\nheader')

		def get_response(incoming_request):
			from django.http import JsonResponse

			return JsonResponse({'ok': True, 'correlation_id': incoming_request.correlation_id})

		response = CorrelationIdMiddleware(get_response)(request)

		self.assertNotEqual(response['X-Correlation-ID'], 'bad\nheader')
		self.assertEqual(response['X-Correlation-ID'], request.correlation_id)
		self.assertEqual(len(response['X-Correlation-ID']), 36)


class CorrelationIdFilterTests(SimpleTestCase):
	def test_filter_never_crashes_when_context_lookup_fails(self):
		record = logging.LogRecord('test', logging.INFO, __file__, 1, 'hello', (), None)

		with patch('config.logging.correlation_id_var') as correlation_id:
			correlation_id.get.side_effect = RuntimeError('context unavailable')
			allowed = CorrelationIdFilter().filter(record)

		self.assertTrue(allowed)
		self.assertEqual(record.correlation_id, 'n/a')

	def test_filter_redacts_sensitive_structured_values(self):
		record = logging.LogRecord(
			'test',
			logging.INFO,
			__file__,
			1,
			'payload=%s',
			({'patient_name': 'Jane Doe', 'gene_variant': 'EGFR L858R', 'status': 'ok'},),
			None,
		)

		CorrelationIdFilter().filter(record)

		self.assertNotIn('Jane Doe', record.getMessage())
		self.assertNotIn('EGFR L858R', record.getMessage())
		self.assertIn('[REDACTED]', record.getMessage())
		self.assertIn('status', record.getMessage())


class DatabaseSettingsTests(SimpleTestCase):
	def test_sqlite_database_name_resolves_under_base_dir(self):
		result = run_settings_probe(
			{
				'DJANGO_ENV': 'local',
				'DJANGO_DB_ENGINE': 'django.db.backends.sqlite3',
				'DJANGO_DB_NAME': 'local.sqlite3',
			},
			'{"name": str(settings.DATABASES["default"]["NAME"])}',
			module='config.settings.base',
		)

		self.assertEqual(result.returncode, 0, result.stderr)
		payload = json.loads(result.stdout)
		self.assertTrue(payload['name'].endswith('/local.sqlite3'))

	def test_non_sqlite_database_uses_connection_environment_without_path_joining(self):
		result = run_settings_probe(
			{
				'DJANGO_ENV': 'local',
				'DJANGO_DB_ENGINE': 'django.db.backends.postgresql',
				'DJANGO_DB_NAME': 'helixora',
				'DJANGO_DB_USER': 'helixora_user',
				'DJANGO_DB_PASSWORD': 'secret',
				'DJANGO_DB_HOST': 'db.internal',
				'DJANGO_DB_PORT': '5432',
			},
			'{"name": settings.DATABASES["default"]["NAME"], '
			'"user": settings.DATABASES["default"]["USER"], '
			'"password": settings.DATABASES["default"]["PASSWORD"], '
			'"host": settings.DATABASES["default"]["HOST"], '
			'"port": settings.DATABASES["default"]["PORT"]}',
			module='config.settings.base',
		)

		self.assertEqual(result.returncode, 0, result.stderr)
		payload = json.loads(result.stdout)
		self.assertEqual(payload['name'], 'helixora')
		self.assertEqual(payload['user'], 'helixora_user')
		self.assertEqual(payload['password'], 'secret')
		self.assertEqual(payload['host'], 'db.internal')
		self.assertEqual(payload['port'], '5432')


class ProductionSettingsValidationTests(SimpleTestCase):
	def valid_production_env(self, **overrides):
		env = {
			'DJANGO_ENV': 'production',
			'DJANGO_SECRET_KEY': 'h9Qp#4dTz!vL2s@wX8mR6nY3cB5fG7jK0aP1qE9uI4oZ2rN$6bC8',
			'DJANGO_ALLOWED_HOSTS': 'api.helixora.example',
			'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://api.helixora.example',
			'DJANGO_SECURE_SSL_REDIRECT': 'true',
			'DJANGO_SESSION_COOKIE_SECURE': 'true',
			'DJANGO_CSRF_COOKIE_SECURE': 'true',
			'DJANGO_SECURE_HSTS_SECONDS': '31536000',
		}
		env.update(overrides)
		return env

	def test_valid_production_settings_import_successfully(self):
		result = run_settings_probe(
			self.valid_production_env(),
			'{"debug": settings.DEBUG, '
			'"ssl_redirect": settings.SECURE_SSL_REDIRECT, '
			'"session_secure": settings.SESSION_COOKIE_SECURE, '
			'"csrf_secure": settings.CSRF_COOKIE_SECURE, '
			'"csrf_origins": settings.CSRF_TRUSTED_ORIGINS}',
		)

		self.assertEqual(result.returncode, 0, result.stderr)
		payload = json.loads(result.stdout)
		self.assertFalse(payload['debug'])
		self.assertTrue(payload['ssl_redirect'])
		self.assertTrue(payload['session_secure'])
		self.assertTrue(payload['csrf_secure'])
		self.assertEqual(payload['csrf_origins'], ['https://api.helixora.example'])

	def test_production_rejects_missing_csrf_trusted_origins(self):
		result = run_settings_probe(
			self.valid_production_env(DJANGO_CSRF_TRUSTED_ORIGINS=''),
			'{"loaded": True}',
		)

		self.assertNotEqual(result.returncode, 0)
		self.assertIn('DJANGO_CSRF_TRUSTED_ORIGINS', result.stderr)

	def test_production_rejects_weak_secret_key(self):
		result = run_settings_probe(
			self.valid_production_env(DJANGO_SECRET_KEY='django-insecure-not-for-production'),
			'{"loaded": True}',
		)

		self.assertNotEqual(result.returncode, 0)
		self.assertIn('DJANGO_SECRET_KEY', result.stderr)

	def test_production_rejects_insecure_cookie_and_ssl_overrides(self):
		for name in (
			'DJANGO_SECURE_SSL_REDIRECT',
			'DJANGO_SESSION_COOKIE_SECURE',
			'DJANGO_CSRF_COOKIE_SECURE',
		):
			with self.subTest(name=name):
				result = run_settings_probe(
					self.valid_production_env(**{name: 'false'}),
					'{"loaded": True}',
				)

				self.assertNotEqual(result.returncode, 0)
				self.assertIn(name, result.stderr)
