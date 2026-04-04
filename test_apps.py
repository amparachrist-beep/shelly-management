# test_apps.py
import os
import sys
import django

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Initialisation Django
django.setup()

# Tests
from django.apps import apps
from django.conf import settings

print("=" * 60)
print("DIAGNOSTIC DJANGO APPS")
print("=" * 60)

print("\n1. INSTALLED_APPS dans settings:")
for app in settings.INSTALLED_APPS:
    print(f"   - {app}")

print("\n2. Apps chargées par Django:")
for app_config in apps.get_app_configs():
    print(f"   - label: {app_config.label:20} | name: {app_config.name}")

print("\n3. Recherche de 'parametrage':")
try:
    app = apps.get_app_config('parametrage')
    print(f"   ✅ Trouvée : {app}")
except LookupError as e:
    print(f"   ❌ Non trouvée : {e}")

print("\n4. Recherche de 'apps.parametrage':")
try:
    # Note: app_label est dérivé du dernier segment du name
    # Mais essayons quand même
    for app in apps.get_app_configs():
        if 'parametrage' in app.name:
            print(f"   ✅ Trouvée : label={app.label}, name={app.name}")
except Exception as e:
    print(f"   ❌ Erreur : {e}")

print("\n5. sys.path:")
for path in sys.path[:5]:  # Premiers 5 éléments
    print(f"   - {path}")