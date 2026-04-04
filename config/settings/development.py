# config/settings/development.py
"""
Configuration de développement local
Hérite de base.py et ajoute des configurations spécifiques au dev
"""
from .base import *

# Surcharges pour le développement
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '*']

# Base de données locale (héritée de base.py, mais on peut la redéfinir si nécessaire)
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'shelly-management',
        'USER': 'postgres',
        'PASSWORD': 'postgress',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# CORS pour le développement
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
]
CORS_ALLOW_CREDENTIALS = True

# Logging détaillé en développement
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Désactiver certaines sécurités en dev
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

print("✅ Development settings loaded successfully")