# diagnostic_complet.py
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

print("=" * 70)
print("DIAGNOSTIC COMPLET - CONFIGURATION DJANGO")
print("=" * 70)

# 1. Vérifier les variables d'environnement
print("\n1. VARIABLES D'ENVIRONNEMENT:")
print(f"   DJANGO_SETTINGS_MODULE = {os.environ.get('DJANGO_SETTINGS_MODULE', 'NON DÉFINI')}")

# 2. Tester l'import du module settings
print("\n2. TEST D'IMPORT DES SETTINGS:")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

try:
    from django.conf import settings

    print("   ✅ Import réussi de django.conf.settings")

    # Vérifier si settings est configuré
    if settings.configured:
        print("   ✅ Settings configuré")
    else:
        print("   ❌ Settings NON configuré")

except Exception as e:
    print(f"   ❌ Erreur lors de l'import : {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

# 3. Vérifier INSTALLED_APPS
print("\n3. INSTALLED_APPS:")
try:
    apps_list = settings.INSTALLED_APPS
    if apps_list:
        print(f"   ✅ Nombre d'apps : {len(apps_list)}")
        for app in apps_list:
            print(f"      - {app}")
    else:
        print("   ❌ INSTALLED_APPS est vide !")
except AttributeError:
    print("   ❌ INSTALLED_APPS n'est pas défini dans settings !")
except Exception as e:
    print(f"   ❌ Erreur : {e}")

# 4. Vérifier DATABASE
print("\n4. DATABASE:")
try:
    db_config = settings.DATABASES.get('default', {})
    print(f"   ENGINE: {db_config.get('ENGINE', 'NON DÉFINI')}")
    print(f"   NAME: {db_config.get('NAME', 'NON DÉFINI')}")
except Exception as e:
    print(f"   ❌ Erreur : {e}")

# 5. Initialiser Django et vérifier les apps
print("\n5. INITIALISATION DJANGO:")
try:
    import django

    django.setup()
    print("   ✅ Django initialisé")

    from django.apps import apps

    print(f"\n6. APPS CHARGÉES PAR DJANGO ({len(list(apps.get_app_configs()))} apps):")
    for app_config in apps.get_app_configs():
        print(f"   - label: {app_config.label:25} | name: {app_config.name}")

except Exception as e:
    print(f"   ❌ Erreur lors de l'initialisation : {e}")
    import traceback

    traceback.print_exc()

# 6. Vérifier la structure des fichiers
print("\n7. VÉRIFICATION DE LA STRUCTURE:")
files_to_check = [
    'config/__init__.py',
    'config/settings/__init__.py',
    'config/settings/base.py',
    'config/settings/development.py',
    'apps/__init__.py',
    'apps/parametrage/__init__.py',
    'apps/parametrage/apps.py',
]

for file_path in files_to_check:
    full_path = os.path.join(BASE_DIR, file_path)
    exists = "✅" if os.path.exists(full_path) else "❌"
    print(f"   {exists} {file_path}")

print("\n" + "=" * 70)