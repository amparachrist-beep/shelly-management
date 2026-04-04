#!/usr/bin/env python
"""
Script pour vérifier les imports dans le fichier de commande
"""
import os

file_path = 'apps/parametrage/management/commands/corriger_quartiers_brazza.py'

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    print("=" * 80)
    print("VÉRIFICATION DES IMPORTS")
    print("=" * 80)

    # Vérifier les imports
    imports_ok = True

    if 'from django.contrib.gis.geos import' in content:
        if 'Point' in content.split('from django.contrib.gis.geos import')[1].split('\n')[0]:
            print("✅ Point est importé depuis django.contrib.gis.geos")
        else:
            print("❌ Point n'est PAS importé depuis django.contrib.gis.geos")
            imports_ok = False
    else:
        print("❌ Import geos manquant")
        imports_ok = False

    # Afficher les 10 premières lignes
    print("\n" + "=" * 80)
    print("PREMIÈRES LIGNES DU FICHIER:")
    print("=" * 80)
    for i, line in enumerate(content.split('\n')[:15], 1):
        print(f"{i:3}: {line}")

    if not imports_ok:
        print("\n" + "=" * 80)
        print("⚠️  LES IMPORTS SONT INCORRECTS")
        print("=" * 80)
        print("\nCODE CORRECT À UTILISER:")
        print("-" * 80)
        print("""from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Polygon, MultiPolygon, Point
from apps.parametrage.models import Departement, Localite
from math import radians, cos, sin, asin, sqrt""")
        print("-" * 80)
else:
    print(f"❌ Fichier non trouvé: {file_path}")