#!/usr/bin/env python
"""
SCRIPT DE DIAGNOSTIC AUTOMATIQUE
=================================
Ce script vérifie automatiquement l'état de votre système
et identifie les problèmes potentiels.

Usage:
    python diagnostic.py
"""

import sys
import os

# Ajouter le chemin du projet Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django

django.setup()

from django.conf import settings
from apps.parametrage.models import TypeTarification
from apps.menages.models import Menage
from apps.parametrage.models import Localite, Departement


def print_section(title):
    """Afficher un titre de section"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_tarifications():
    """Vérifier les tarifications"""
    print_section("VÉRIFICATION DES TARIFICATIONS")

    try:
        total = TypeTarification.objects.count()
        actives = TypeTarification.objects.filter(statut='ACTIF').count()

        print(f"✓ Tarifications totales: {total}")
        print(f"✓ Tarifications actives: {actives}")

        if actives == 0:
            print("❌ PROBLÈME: Aucune tarification active trouvée!")
            print("   Solution: Exécutez le script de création de tarifications")
            return False

        # Afficher les détails
        print("\nDétails des tarifications actives:")
        for tarif in TypeTarification.objects.filter(statut='ACTIF'):
            print(f"  - {tarif.nom} ({tarif.code})")
            print(f"    Catégorie: {tarif.categorie}")
            print(f"    Abonnement: {tarif.abonnement_mensuel} FCFA")
            print(f"    Prix kWh: {tarif.prix_kwh} FCFA")

        return True

    except Exception as e:
        print(f"❌ ERREUR: {str(e)}")
        return False


def check_localites():
    """Vérifier les localités"""
    print_section("VÉRIFICATION DES LOCALITÉS")

    try:
        depts = Departement.objects.count()
        localites = Localite.objects.count()

        print(f"✓ Départements: {depts}")
        print(f"✓ Localités: {localites}")

        if localites == 0:
            print("⚠️  AVERTISSEMENT: Aucune localité trouvée!")
            print("   Cela peut causer des problèmes lors de la création de ménages")
            return False

        # Vérifier Brazzaville
        brazza = Departement.objects.filter(nom__icontains='brazza').first()
        if brazza:
            print(f"\n✓ Brazzaville trouvé (ID: {brazza.id})")
            quartiers = Localite.objects.filter(
                departement=brazza,
                type_localite='QUARTIER'
            ).count()
            print(f"  Quartiers: {quartiers}")
        else:
            print("\n⚠️  Brazzaville non trouvé")

        return True

    except Exception as e:
        print(f"❌ ERREUR: {str(e)}")
        return False


def check_menages():
    """Vérifier les ménages"""
    print_section("VÉRIFICATION DES MÉNAGES")

    try:
        total = Menage.objects.count()
        actifs = Menage.objects.filter(statut='ACTIF').count()

        print(f"✓ Ménages totaux: {total}")
        print(f"✓ Ménages actifs: {actifs}")

        # Vérifier le champ type_tarification
        if total > 0:
            dernier = Menage.objects.first()
            if hasattr(dernier, 'type_tarification'):
                print(f"✓ Champ 'type_tarification' existe")
            else:
                print(f"❌ PROBLÈME: Champ 'type_tarification' manquant!")
                print("   Solution: Ajouter le champ au modèle et migrer")
                return False

        return True

    except Exception as e:
        print(f"❌ ERREUR: {str(e)}")
        return False


def check_urls():
    """Vérifier les URLs"""
    print_section("VÉRIFICATION DES URLs")

    try:
        from django.urls import get_resolver

        resolver = get_resolver()
        url_patterns = [p.pattern._route for p in resolver.url_patterns
                        if hasattr(p.pattern, '_route')]

        # Vérifier les URLs importantes
        required_urls = [
            'menages/',
            'menages/create/',
            'parametrage/',
        ]

        for url in required_urls:
            if any(url in pattern for pattern in url_patterns):
                print(f"✓ URL trouvée: {url}")
            else:
                print(f"⚠️  URL manquante: {url}")

        # Vérifier l'API des tarifications
        api_url = 'parametrage/api/tarifications/actives/'
        if any(api_url in pattern for pattern in url_patterns):
            print(f"✓ API tarifications configurée")
        else:
            print(f"❌ PROBLÈME: API tarifications non configurée!")
            print(f"   Solution: Ajouter l'URL dans parametrage/urls.py")
            return False

        return True

    except Exception as e:
        print(f"❌ ERREUR: {str(e)}")
        return False


def check_settings():
    """Vérifier les settings"""
    print_section("VÉRIFICATION DES SETTINGS")

    try:
        print(f"✓ DEBUG: {settings.DEBUG}")
        print(f"✓ ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")

        # Vérifier les apps installées
        required_apps = [
            'apps.menages',
            'apps.parametrage',
            'apps.compteurs',
        ]

        for app in required_apps:
            if app in settings.INSTALLED_APPS:
                print(f"✓ App installée: {app}")
            else:
                print(f"⚠️  App manquante: {app}")

        return True

    except Exception as e:
        print(f"❌ ERREUR: {str(e)}")
        return False


def create_test_data():
    """Créer des données de test"""
    print_section("CRÉATION DE DONNÉES DE TEST")

    response = input("\nVoulez-vous créer des tarifications de test? (o/n): ")

    if response.lower() == 'o':
        tarifs = [
            {
                'nom': 'Résidentiel Standard',
                'code': 'RES-STD',
                'description': 'Tarif standard pour les ménages résidentiels',
                'categorie': 'RESIDENTIEL',
                'abonnement_mensuel': 5000,
                'prix_kwh': 125,
                'statut': 'ACTIF'
            },
            {
                'nom': 'Résidentiel Premium',
                'code': 'RES-PRE',
                'description': 'Tarif premium avec consommation élevée',
                'categorie': 'RESIDENTIEL',
                'abonnement_mensuel': 7500,
                'prix_kwh': 115,
                'statut': 'ACTIF'
            },
            {
                'nom': 'Commercial Standard',
                'code': 'COM-STD',
                'description': 'Tarif pour les petites entreprises',
                'categorie': 'COMMERCIAL',
                'abonnement_mensuel': 10000,
                'prix_kwh': 140,
                'statut': 'ACTIF'
            },
            {
                'nom': 'Social',
                'code': 'SOC',
                'description': 'Tarif social pour ménages modestes',
                'categorie': 'SOCIAL',
                'abonnement_mensuel': 3000,
                'prix_kwh': 95,
                'statut': 'ACTIF'
            }
        ]

        created = 0
        for tarif_data in tarifs:
            obj, was_created = TypeTarification.objects.get_or_create(
                code=tarif_data['code'],
                defaults=tarif_data
            )
            if was_created:
                print(f"✓ Créé: {obj.nom}")
                created += 1
            else:
                print(f"  Existe déjà: {obj.nom}")

        print(f"\n✓ {created} tarification(s) créée(s)")


def main():
    """Fonction principale"""
    print("\n" + "🔍 DIAGNOSTIC DU SYSTÈME".center(60, "="))

    results = {
        'tarifications': check_tarifications(),
        'localites': check_localites(),
        'menages': check_menages(),
        'urls': check_urls(),
        'settings': check_settings(),
    }

    # Résumé
    print_section("RÉSUMÉ")

    total = len(results)
    passed = sum(1 for v in results.values() if v)

    print(f"\nTests réussis: {passed}/{total}")

    if passed == total:
        print("\n✅ Tous les tests sont passés!")
        print("   Votre système semble correctement configuré.")
    else:
        print("\n⚠️  Certains tests ont échoué.")
        print("   Consultez les détails ci-dessus pour résoudre les problèmes.")

        # Proposer de créer des données de test
        if not results['tarifications']:
            create_test_data()

    print("\n" + "=" * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrompu par l'utilisateur.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ ERREUR FATALE: {str(e)}")
        import traceback

        traceback.print_exc()
        sys.exit(1)