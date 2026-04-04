#!/usr/bin/env python
"""
manage.py - Version CORRIGÉE
✅ Ne pas ajouter apps/ à sys.path pour éviter les conflits
"""
import os
import sys

# ============================================
# ÉTAPE 0 : CONFIGURATION DU PATH
# ============================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ✅ SEULEMENT ajouter BASE_DIR (pas APPS_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ============================================
# ÉTAPE 1 : CONFIGURATION GÉOSPATIALE
# ============================================
if sys.platform == 'win32':
    conda_prefix = os.environ.get('CONDA_PREFIX', '')
    if conda_prefix:
        bin_dir = os.path.join(conda_prefix, 'Library', 'bin')
        if os.path.exists(bin_dir) and bin_dir not in os.environ['PATH']:
            os.environ['PATH'] = bin_dir + os.pathsep + os.environ['PATH']
        try:
            import ctypes
            ctypes.CDLL(os.path.join(bin_dir, 'gdal304.dll'))
            ctypes.CDLL(os.path.join(bin_dir, 'geos_c.dll'))
        except:
            pass

# ============================================
# ÉTAPE 2 : INITIALISATION DJANGO
# ============================================
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')


def main():
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()