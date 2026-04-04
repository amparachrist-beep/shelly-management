"""
Script de diagnostic pour vérifier les tarifications
"""
import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.parametrage.models import TypeTarification
import json

print("=" * 80)
print("DIAGNOSTIC DES TARIFICATIONS")
print("=" * 80)

# 1. Vérifier combien de tarifications existent
total_tarifs = TypeTarification.objects.all().count()
print(f"\n✅ Total de tarifications dans la base : {total_tarifs}")

# 2. Vérifier combien sont actives
actives = TypeTarification.objects.filter(actif=True).count()
print(f"✅ Tarifications actives : {actives}")

# 3. Lister toutes les tarifications
print("\n" + "=" * 80)
print("LISTE DES TARIFICATIONS")
print("=" * 80)

for tarif in TypeTarification.objects.all():
    print(f"\n📋 {tarif.nom} ({tarif.code})")
    print(f"   - ID: {tarif.id}")
    print(f"   - Catégorie: {tarif.categorie}")
    print(f"   - Actif: {tarif.actif}")
    print(f"   - Abonnement: {tarif.abonnement_mensuel} {tarif.devise}")
    print(f"   - Date effet: {tarif.date_effet}")
    print(f"   - Date fin: {tarif.date_fin}")
    print(f"   - Tranches: {tarif.tranches}")

# 4. Simuler la réponse API
print("\n" + "=" * 80)
print("SIMULATION DE LA RÉPONSE API")
print("=" * 80)

tarifs = TypeTarification.objects.filter(actif=True)
data = []

for tarif in tarifs:
    prix_kwh = 0
    if tarif.tranches and isinstance(tarif.tranches, list) and len(tarif.tranches) > 0:
        prix_kwh = tarif.tranches[0].get('prix_kwh', 0)

    item = {
        'id': tarif.id,
        'code': tarif.code,
        'nom': tarif.nom,
        'categorie': tarif.categorie,
        'abonnement_mensuel': str(tarif.abonnement_mensuel),
        'devise': tarif.devise,
        'prix_kwh': str(prix_kwh),
        'description': tarif.description or '',
        'tranches': tarif.tranches if tarif.tranches else []
    }
    data.append(item)

print(f"\n✅ Réponse API simulée ({len(data)} tarifs):")
print(json.dumps(data, indent=2, ensure_ascii=False))

# 5. Vérifier s'il faut créer des tarifs de test
if actives == 0:
    print("\n" + "=" * 80)
    print("⚠️  AUCUNE TARIFICATION ACTIVE TROUVÉE")
    print("=" * 80)
    print("\nVoulez-vous créer des tarifications de test ?")
    print("Exécutez le script: python create_test_tarifs.py")