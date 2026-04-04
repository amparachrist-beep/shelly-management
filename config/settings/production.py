import os
from .base import *

# ═══════════════════════════════════════
# SÉCURITÉ
# ═══════════════════════════════════════
DEBUG = False

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

ALLOWED_HOSTS = [
    os.environ.get('RENDER_EXTERNAL_HOSTNAME', ''),
    'localhost',
    '127.0.0.1',
]

# ═══════════════════════════════════════
# BASE DE DONNÉES (PostGIS sur Supabase)
# ═══════════════════════════════════════
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': 'require',  # Obligatoire sur Supabase/Render
        },
    }
}

# ═══════════════════════════════════════
# FICHIERS STATIQUES (Whitenoise)
# ═══════════════════════════════════════
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Juste après SecurityMiddleware
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ═══════════════════════════════════════
# GDAL / GEOS (chemins Linux sur Render)
# ═══════════════════════════════════════
GDAL_LIBRARY_PATH = '/usr/lib/libgdal.so'
GEOS_LIBRARY_PATH = '/usr/lib/x86_64-linux-gnu/libgeos_c.so.1'

# ═══════════════════════════════════════
# CORS (adapter avec ton domaine Render)
# ═══════════════════════════════════════
CORS_ALLOWED_ORIGINS = [
    f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')}",
]
CORS_ALLOW_CREDENTIALS = True

# ═══════════════════════════════════════
# SÉCURITÉ HTTPS
# ═══════════════════════════════════════
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', '')}",
]

# ═══════════════════════════════════════
# EMAIL (identique à base.py)
# ═══════════════════════════════════════
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'amparachrist@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = f'Shelly SGE <{EMAIL_HOST_USER}>'

# ═══════════════════════════════════════
# LOGGING EN PRODUCTION
# ═══════════════════════════════════════
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}