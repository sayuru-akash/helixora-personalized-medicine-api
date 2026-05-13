import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SECRET_KEY = 'django-insecure-change-me-before-production'


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        if line.startswith('export '):
            line = line.removeprefix('export ').strip()
        name, value = line.split('=', 1)
        name = name.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(name, value)


load_env_file(BASE_DIR / '.env')


def get_env(name: str, default=None, required: bool = False):
    value = os.getenv(name, default)
    if required and (value is None or value == ''):
        raise RuntimeError(f'Missing required environment variable: {name}')
    return value


def get_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {'1', 'true', 'yes', 'on'}:
        return True
    if normalized in {'0', 'false', 'no', 'off'}:
        return False
    raise RuntimeError(f'Invalid boolean value for {name}: {value!r}')


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == '':
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f'Invalid integer value for {name}: {value!r}') from exc


def get_list_env(name: str, default: str = '') -> list[str]:
    value = os.getenv(name, default)
    return [item.strip() for item in value.split(',') if item.strip()]


def is_sqlite_engine(engine: str) -> bool:
    return engine == 'django.db.backends.sqlite3' or engine.endswith('.sqlite3')


def build_database_config() -> dict:
    engine = get_env('DJANGO_DB_ENGINE', 'django.db.backends.sqlite3')
    sqlite = is_sqlite_engine(engine)
    name = get_env('DJANGO_DB_NAME', 'db.sqlite3' if sqlite else None, required=not sqlite)

    if sqlite and name != ':memory:':
        database_name = Path(name)
        if not database_name.is_absolute():
            database_name = BASE_DIR / database_name
    else:
        database_name = name

    config = {
        'ENGINE': engine,
        'NAME': database_name,
    }

    if not sqlite:
        optional_settings = {
            'USER': 'DJANGO_DB_USER',
            'PASSWORD': 'DJANGO_DB_PASSWORD',
            'HOST': 'DJANGO_DB_HOST',
            'PORT': 'DJANGO_DB_PORT',
        }
        for setting_name, env_name in optional_settings.items():
            value = get_env(env_name, '')
            if value != '':
                config[setting_name] = value

        config['CONN_MAX_AGE'] = get_int_env(
            'DJANGO_DB_CONN_MAX_AGE',
            60 if ENVIRONMENT == 'production' else 0,
        )

    return config


ENVIRONMENT = get_env('DJANGO_ENV', 'local').lower()

SECRET_KEY = get_env(
    'DJANGO_SECRET_KEY',
    DEFAULT_SECRET_KEY if ENVIRONMENT != 'production' else None,
    required=ENVIRONMENT == 'production',
)

DEBUG = get_bool_env('DJANGO_DEBUG', ENVIRONMENT != 'production')

ALLOWED_HOSTS: list[str] = get_list_env('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost')

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
]

LOCAL_APPS = [
    'apps.patients',
    'apps.genomics',
    'apps.recommendations',
    'apps.reviews',
    'apps.audit',
    'apps.ai',
    'apps.rules',
    'apps.api',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.api.middleware.CorrelationIdMiddleware',
]

ROOT_URLCONF = 'config.urls'
LOGIN_URL = get_env('DJANGO_LOGIN_URL', '/admin/login/')

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': build_database_config(),
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

CSRF_TRUSTED_ORIGINS = get_list_env('DJANGO_CSRF_TRUSTED_ORIGINS')

SECURE_SSL_REDIRECT = get_bool_env('DJANGO_SECURE_SSL_REDIRECT', ENVIRONMENT == 'production')
SESSION_COOKIE_SECURE = get_bool_env('DJANGO_SESSION_COOKIE_SECURE', ENVIRONMENT == 'production')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = get_env('DJANGO_SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SECURE = get_bool_env('DJANGO_CSRF_COOKIE_SECURE', ENVIRONMENT == 'production')
CSRF_COOKIE_SAMESITE = get_env('DJANGO_CSRF_COOKIE_SAMESITE', 'Lax')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
}

CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = get_env('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_BROKER_URL = get_env('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 10
CELERY_TASK_ALWAYS_EAGER = get_bool_env('CELERY_TASK_ALWAYS_EAGER', False)

LOG_LEVEL = get_env('DJANGO_LOG_LEVEL', 'INFO')

HELIXORA_AI_PROVIDER = get_env('HELIXORA_AI_PROVIDER', 'placeholder')
GEMINI_API_KEY = get_env('GEMINI_API_KEY', '')
GEMINI_MODEL = get_env('GEMINI_MODEL', 'gemini-1.5-pro')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'correlation_id': {
            '()': 'config.logging.CorrelationIdFilter',
        },
    },
    'formatters': {
        'jsonish': {
            'format': '%(asctime)s %(levelname)s %(name)s correlation_id=%(correlation_id)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'filters': ['correlation_id'],
            'formatter': 'jsonish',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
    },
}
