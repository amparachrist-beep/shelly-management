#!/usr/bin/env python
"""
Script pour trouver où Point est mal utilisé
"""
import os
import re

file_path = 'apps/parametrage/management/commands/corriger_quartiers_brazza.py'

if os.path.exists(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print("=" * 80)
    print("RECHERCHE DES UTILISATIONS DE Point")
    print("=" * 80)

    problems = []

    for i, line in enumerate(lines, 1):
        # Chercher toutes les utilisations de Point
        if 'Point(' in line and not line.strip().startswith('#'):
            # Vérifier si c'est une mauvaise utilisation
            if 'gis_models.Point' in line:
                problems.append((i, line.strip(), 'ERREUR: gis_models.Point'))
            elif 'models.Point' in line:
                problems.append((i, line.strip(), 'ERREUR: models.Point'))
            else:
                # C'est probablement correct (juste Point)
                print(f"✅ Ligne {i:3}: {line.strip()}")

    if problems:
        print("\n" + "=" * 80)
        print("⚠️  PROBLÈMES DÉTECTÉS:")
        print("=" * 80)
        for line_num, line_content, error in problems:
            print(f"\n❌ Ligne {line_num}: {error}")
            print(f"   {line_content}")
            print(
                f"   Devrait être: {line_content.replace('gis_models.Point', 'Point').replace('models.Point', 'Point')}")
    else:
        print("\n✅ Aucun problème détecté avec les utilisations de Point")

    # Chercher aussi dans models.py
    print("\n" + "=" * 80)
    print("VÉRIFICATION DE models.py")
    print("=" * 80)

    models_path = 'apps/parametrage/models.py'
    if os.path.exists(models_path):
        with open(models_path, 'r', encoding='utf-8') as f:
            models_content = f.read()

        if 'gis_models.Point' in models_content:
            print("⚠️  models.py utilise 'gis_models.Point'")
            print("   Ceci est NORMAL dans models.py")
        else:
            print("✅ models.py n'utilise pas gis_models.Point")

else:
    print(f"❌ Fichier non trouvé: {file_path}")