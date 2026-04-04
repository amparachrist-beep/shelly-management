# ========================================
# apps/compteurs/apps.py
# ========================================
from django.apps import AppConfig

class CompteursConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.compteurs'
    verbose_name = 'Compteurs'