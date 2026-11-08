from pathlib import Path
import sys

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = [o for o in config('CSRF_TRUSTED_ORIGINS', default='').split(',') if o]
SERVE_MEDIA = config('SERVE_MEDIA', default=False, cast=bool)

FIREBASE_CREDENTIALS = config('FIREBASE_CREDENTIALS', default='credentials.json')
FIREBASE_PROJECT_ID = config('FIREBASE_PROJECT_ID', default='')
FIREBASE_STORAGE_BUCKET = config('FIREBASE_STORAGE_BUCKET', default='')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "rest_framework",
    'core',
    "authentication.apps.AuthenticationConfig",
    'venues',
    'menus',
    'cameras',
    'ai_vision',
    'analytics',
    'chatbot',
    'api',
    'reports',
    "operations",
    "monitoring",
    "privacy",
    "assistant_chat",
    "sales.apps.SalesConfig",
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.FirstRunMiddleware',
    'core.middleware.LegalAcceptanceMiddleware',
    'core.middleware.RoleScopeMiddleware',
    'core.middleware.LoginThrottleMiddleware',
    'core.middleware.AssistantThrottleMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'assistant_chat.context_processors.assistant_widget_access',
                'assistant_chat.branding.assistant_brand',
                'core.context_role.role_scope',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DB_ENGINE = config('DB_ENGINE', default='sqlite')
SQLITE_PATH = config('SQLITE_PATH', default=str(BASE_DIR / 'db.sqlite3'))

if DB_ENGINE == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='gastroinsight_db'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='postgres'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': SQLITE_PATH,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(config("MEDIA_ROOT", default=str(BASE_DIR / "media")))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = "authentication:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "authentication:login"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

DEFAULT_FROM_EMAIL = "no-reply@gastroinsight.local"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),
    "PAGE_SIZE": 25,
}

ASSISTANT_NAME = config("ASSISTANT_NAME", default="Sazón")

DESKTOP_MODE = config('DESKTOP_MODE', default=False, cast=bool)
SERVE_STATIC = config('SERVE_STATIC', default=False, cast=bool)

LEGAL_ACCEPTANCE_REQUIRED = config('LEGAL_ACCEPTANCE_REQUIRED', default=True, cast=bool)
if len(sys.argv) > 1 and sys.argv[1] == "test":
    LEGAL_ACCEPTANCE_REQUIRED = False  # las pruebas que lo necesitan lo activan explícitamente
CONTACT_EMAIL = config('CONTACT_EMAIL', default='')
SOURCE_CODE_URL = config('SOURCE_CODE_URL', default='https://github.com/Geencuve/gastroinsight-ai')
SCENE_DETECTION = config('SCENE_DETECTION', default=True, cast=bool)
CSRF_FAILURE_VIEW = 'core.views_errors.csrf_failure'

# Permite incrustar páginas de la propia aplicación (pestañas de Visión IA); otros sitios siguen bloqueados.
X_FRAME_OPTIONS = 'SAMEORIGIN'

# Dirección pública para los códigos QR (por ejemplo, el enlace del túnel). Vacío = se detecta automáticamente.
PUBLIC_BASE_URL = config("PUBLIC_BASE_URL", default="")
if DEBUG:
    # En desarrollo, permite que los celulares de la misma red WiFi abran el servidor (runserver 0.0.0.0:8000).
    import socket as _socket

    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM) as _sock:
            _sock.connect(("10.255.255.255", 1))
            if _sock.getsockname()[0] not in ALLOWED_HOSTS:
                ALLOWED_HOSTS.append(_sock.getsockname()[0])
    except OSError:
        pass

# ---------------- Seguridad (I1) ----------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
USE_HTTPS = config("USE_HTTPS", default=False, cast=bool)
if USE_HTTPS:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
    # HSTS prudente (1 hora): súbelo cuando el dominio HTTPS sea definitivo
    SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=3600, cast=int)

# Registro público de cuentas: desactivado en el producto (las crea el administrador del local).
ALLOW_SELF_REGISTRATION = config("ALLOW_SELF_REGISTRATION", default=False, cast=bool)
