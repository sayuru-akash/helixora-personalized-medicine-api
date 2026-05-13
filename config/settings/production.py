from .base import *  # noqa: F403,F401

DEBUG = False

SECURE_SSL_REDIRECT = get_bool_env('DJANGO_SECURE_SSL_REDIRECT', True)
SESSION_COOKIE_SECURE = get_bool_env('DJANGO_SESSION_COOKIE_SECURE', True)
CSRF_COOKIE_SECURE = get_bool_env('DJANGO_CSRF_COOKIE_SECURE', True)
SECURE_HSTS_SECONDS = get_int_env('DJANGO_SECURE_HSTS_SECONDS', 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_bool_env('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', True)
SECURE_HSTS_PRELOAD = get_bool_env('DJANGO_SECURE_HSTS_PRELOAD', True)
SECURE_REFERRER_POLICY = get_env('DJANGO_SECURE_REFERRER_POLICY', 'same-origin')

if get_bool_env('DJANGO_USE_X_FORWARDED_PROTO', True):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


def validate_production_settings() -> None:
    unsafe_secret_keys = {
        DEFAULT_SECRET_KEY,
        'change-me-before-production',
    }
    if not SECRET_KEY or SECRET_KEY in unsafe_secret_keys:
        raise RuntimeError('Production requires a non-default DJANGO_SECRET_KEY.')
    if SECRET_KEY.startswith('django-insecure-') or len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5:
        raise RuntimeError('Production requires a strong DJANGO_SECRET_KEY.')

    if not ALLOWED_HOSTS:
        raise RuntimeError('Production requires DJANGO_ALLOWED_HOSTS to be configured.')
    if '*' in ALLOWED_HOSTS:
        raise RuntimeError('Production DJANGO_ALLOWED_HOSTS must not contain wildcard hosts.')

    if not CSRF_TRUSTED_ORIGINS:
        raise RuntimeError('Production requires DJANGO_CSRF_TRUSTED_ORIGINS to be configured.')
    insecure_csrf_origins = [
        origin
        for origin in CSRF_TRUSTED_ORIGINS
        if not origin.startswith('https://')
    ]
    if insecure_csrf_origins:
        raise RuntimeError('Production DJANGO_CSRF_TRUSTED_ORIGINS must use https:// origins.')

    required_true_settings = {
        'DJANGO_SECURE_SSL_REDIRECT': SECURE_SSL_REDIRECT,
        'DJANGO_SESSION_COOKIE_SECURE': SESSION_COOKIE_SECURE,
        'DJANGO_CSRF_COOKIE_SECURE': CSRF_COOKIE_SECURE,
    }
    for env_name, value in required_true_settings.items():
        if not value:
            raise RuntimeError(f'Production requires {env_name}=true.')

    if SECURE_HSTS_SECONDS <= 0:
        raise RuntimeError('Production requires DJANGO_SECURE_HSTS_SECONDS to be greater than 0.')


validate_production_settings()
