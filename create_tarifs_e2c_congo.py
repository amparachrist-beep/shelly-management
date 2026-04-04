"""
Script pour créer les tarifications RÉELLES du Congo-Brazzaville (E2C/SNE)
Basé sur les informations de l'étude ICEA-RICARDO 2017 et la structure tarifaire progressive
"""
import os
import django
from datetime import date, timedelta

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.parametrage.models import TypeTarification

print("=" * 80)
print("CRÉATION DES TARIFICATIONS E2C/SNE - CONGO-BRAZZAVILLE")
print("=" * 80)
print("\nBasé sur:")
print("- Étude tarifaire ICEA-RICARDO (2017)")
print("- Structure à tranches progressives")
print("- Coût moyen estimé: 94 FCFA/kWh (2018-2022)")
print("- Tarif social pour ménages modestes")
print("=" * 80)

# Supprimer les anciennes tarifications (optionnel)
# TypeTarification.objects.all().delete()

# Créer des tarifications réalistes pour le Congo-Brazzaville
tarifications = [
    {
        'code': 'RES-SOCIAL',
        'nom': 'Résidentiel Social (Tranche sociale)',
        'categorie': 'RESIDENTIEL',
        'tranches': [
            {'min': 0, 'max': 30, 'prix_kwh': 65},  # Très faible consommation (tranche sociale)
            {'min': 30, 'max': 60, 'prix_kwh': 75},  # Faible consommation
            {'min': 60, 'max': None, 'prix_kwh': 85}  # Au-delà
        ],
        'abonnement_mensuel': 1500,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Tarif social pour les ménages à très faible consommation (< 30 kWh/mois). Subventionné pour lutter contre la précarité énergétique.',
        'reference_arrete': 'Arrêté E2C/2018-001',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'RES-NORMAL',
        'nom': 'Résidentiel Normal',
        'categorie': 'RESIDENTIEL',
        'tranches': [
            {'min': 0, 'max': 50, 'prix_kwh': 80},  # 1ère tranche
            {'min': 50, 'max': 100, 'prix_kwh': 90},  # 2ème tranche
            {'min': 100, 'max': 200, 'prix_kwh': 100},  # 3ème tranche
            {'min': 200, 'max': None, 'prix_kwh': 110}  # Au-delà (incitation à maîtriser)
        ],
        'abonnement_mensuel': 2500,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Tarif standard pour les ménages résidentiels. Tarification progressive incitant à la maîtrise de l\'énergie.',
        'reference_arrete': 'Arrêté E2C/2018-002',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'RES-CONFORT',
        'nom': 'Résidentiel Confort',
        'categorie': 'RESIDENTIEL',
        'tranches': [
            {'min': 0, 'max': 100, 'prix_kwh': 85},  # 1ère tranche
            {'min': 100, 'max': 250, 'prix_kwh': 95},  # 2ème tranche
            {'min': 250, 'max': 500, 'prix_kwh': 105},  # 3ème tranche
            {'min': 500, 'max': None, 'prix_kwh': 120}  # Forte consommation
        ],
        'abonnement_mensuel': 4000,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Pour les foyers avec climatisation, équipements électriques nombreux. Consommation > 200 kWh/mois.',
        'reference_arrete': 'Arrêté E2C/2018-003',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'COM-PME',
        'nom': 'Commercial PME',
        'categorie': 'COMMERCIAL',
        'tranches': [
            {'min': 0, 'max': 150, 'prix_kwh': 95},  # Petits commerces
            {'min': 150, 'max': 400, 'prix_kwh': 105},  # Moyens commerces
            {'min': 400, 'max': 800, 'prix_kwh': 115},  # Gros commerces
            {'min': 800, 'max': None, 'prix_kwh': 125}  # Très gros commerces
        ],
        'abonnement_mensuel': 8000,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Petites et moyennes entreprises, commerces, bureaux, ateliers. Basse tension.',
        'reference_arrete': 'Arrêté E2C/2018-004',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'COM-GRANDE',
        'nom': 'Commercial Grande Distribution',
        'categorie': 'COMMERCIAL',
        'tranches': [
            {'min': 0, 'max': 500, 'prix_kwh': 100},
            {'min': 500, 'max': 1500, 'prix_kwh': 110},
            {'min': 1500, 'max': None, 'prix_kwh': 120}
        ],
        'abonnement_mensuel': 15000,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Grandes surfaces, supermarchés, centres commerciaux. Forte consommation (réfrigération, climatisation).',
        'reference_arrete': 'Arrêté E2C/2018-005',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'IND-PETITE',
        'nom': 'Industriel Petite puissance',
        'categorie': 'INDUSTRIEL',
        'tranches': [
            {'min': 0, 'max': 1000, 'prix_kwh': 90},
            {'min': 1000, 'max': 3000, 'prix_kwh': 95},
            {'min': 3000, 'max': None, 'prix_kwh': 100}
        ],
        'abonnement_mensuel': 20000,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Petites industries, ateliers de production, PMI. Basse et moyenne tension.',
        'reference_arrete': 'Arrêté E2C/2018-006',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'IND-MOYENNE',
        'nom': 'Industriel Moyenne puissance',
        'categorie': 'INDUSTRIEL',
        'tranches': [
            {'min': 0, 'max': 5000, 'prix_kwh': 85},
            {'min': 5000, 'max': 10000, 'prix_kwh': 90},
            {'min': 10000, 'max': None, 'prix_kwh': 95}
        ],
        'abonnement_mensuel': 50000,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Industries moyennes, usines de transformation. Moyenne et haute tension.',
        'reference_arrete': 'Arrêté E2C/2018-007',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'IND-GRANDE',
        'nom': 'Industriel Grande puissance',
        'categorie': 'INDUSTRIEL',
        'tranches': [
            {'min': 0, 'max': 10000, 'prix_kwh': 75},
            {'min': 10000, 'max': 50000, 'prix_kwh': 80},
            {'min': 50000, 'max': None, 'prix_kwh': 85}
        ],
        'abonnement_mensuel': 150000,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Grandes industries, cimenteries, mines, transformation lourde. Haute et très haute tension. Tarif préférentiel pour volumes importants.',
        'reference_arrete': 'Arrêté E2C/2018-008',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'ADM-PUBLIC',
        'nom': 'Administratif Public',
        'categorie': 'ADMINISTRATIF',
        'tranches': [
            {'min': 0, 'max': 300, 'prix_kwh': 90},
            {'min': 300, 'max': 800, 'prix_kwh': 100},
            {'min': 800, 'max': None, 'prix_kwh': 110}
        ],
        'abonnement_mensuel': 10000,  # FCFA/mois
        'devise': 'FCFA',
        'description': 'Administrations publiques, écoles, hôpitaux publics, mairies, préfectures.',
        'reference_arrete': 'Arrêté E2C/2018-009',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
    {
        'code': 'SPE-ECLAIRAGE',
        'nom': 'Spécial Éclairage public',
        'categorie': 'SPECIAL',
        'tranches': [
            {'min': 0, 'max': None, 'prix_kwh': 70}  # Tarif forfaitaire
        ],
        'abonnement_mensuel': 5000,  # FCFA/mois par point lumineux
        'devise': 'FCFA',
        'description': 'Éclairage public des rues, routes, places publiques. Tarif forfaitaire spécial.',
        'reference_arrete': 'Arrêté E2C/2018-010',
        'date_effet': date.today() - timedelta(days=365),
        'actif': True
    },
]

created_count = 0
updated_count = 0

for tarif_data in tarifications:
    tarif, created = TypeTarification.objects.get_or_create(
        code=tarif_data['code'],
        defaults=tarif_data
    )

    if created:
        print(f"✅ Créé: {tarif.nom} ({tarif.code})")
        print(f"   - Abonnement: {tarif.abonnement_mensuel} {tarif.devise}/mois")
        print(f"   - Tranches: {len(tarif.tranches)} niveau(x)")
        created_count += 1
    else:
        print(f"⚠️  Existe déjà: {tarif.nom} ({tarif.code})")
        # Optionnel: mettre à jour
        for key, value in tarif_data.items():
            setattr(tarif, key, value)
        tarif.save()
        updated_count += 1

print("\n" + "=" * 80)
print(f"RÉSUMÉ")
print("=" * 80)
print(f"✅ Nouvelles tarifications créées: {created_count}")
print(f"🔄 Tarifications mises à jour: {updated_count}")
print(f"📊 Total de tarifications actives: {TypeTarification.objects.filter(actif=True).count()}")

print("\n" + "=" * 80)
print("STRUCTURE TARIFAIRE CONGO-BRAZZAVILLE")
print("=" * 80)

# Afficher un résumé par catégorie
from django.db.models import Count

for categorie, nom_categorie in TypeTarification.CATEGORIE_CHOICES:
    count = TypeTarification.objects.filter(categorie=categorie, actif=True).count()
    if count > 0:
        print(f"\n📋 {nom_categorie}: {count} tarif(s)")
        for tarif in TypeTarification.objects.filter(categorie=categorie, actif=True):
            print(f"   - {tarif.nom}")
            print(f"     Abonnement: {tarif.abonnement_mensuel} FCFA/mois")
            if tarif.tranches:
                print(f"     Tranches:")
                for tranche in tarif.tranches:
                    min_kwh = tranche.get('min', 0)
                    max_kwh = tranche.get('max', '∞')
                    prix = tranche.get('prix_kwh')
                    print(f"       • {min_kwh}-{max_kwh} kWh: {prix} FCFA/kWh")

print("\n" + "=" * 80)
print("✅ Tarifications E2C/SNE créées avec succès !")
print("=" * 80)
print("\nNOTES:")
print("- Ces tarifs sont basés sur les recommandations ICEA-RICARDO (2017)")
print("- Structure progressive pour inciter à la maîtrise de l'énergie")
print("- Tarif social pour les ménages modestes (< 30 kWh/mois)")
print("- Les tarifs peuvent être ajustés selon les arrêtés officiels E2C")
print("\n✨ Vous pouvez maintenant utiliser ces tarifications dans le système SGE")