from celery import current_app as celery_app
from django.conf import settings


def get_public_health_status():
	return {
		'status': 'ok',
		'service': 'helixora-api',
	}


def get_operations_health_status():
	broker_url = getattr(settings, 'CELERY_BROKER_URL', '')
	return {
		'status': 'ok',
		'service': 'helixora-api',
		'framework': 'django-drf-celery',
		'environment': getattr(settings, 'ENVIRONMENT', 'local'),
		'celery': {
			'broker_configured': bool(broker_url),
			'task_always_eager': getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False),
			'app_name': celery_app.main,
		},
	}


def get_health_status():
	return get_operations_health_status()
