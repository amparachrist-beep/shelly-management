"""
Script pour diagnostiquer et corriger le problème de détection Pool vs Brazzaville
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.parametrage.models import Departement, Localite
from django.contrib.gis.geos import Point

print("=" * 80)
print("DIAGNOSTIC DU CONFLIT POOL vs BRAZZAVILLE")
print("=" * 80)

# Coordonnées du point problématique
test_lat = -4.167114
test_lon = 15.264038
test_point = Point(test_lon, test_lat, srid=4326)

print(f"\n📍 Point test: {test_lat}, {test_lon}")

# 1. Vérifier quel département contient ce point
print("\n" + "=" * 80)
print("DÉTECTION PAR POLYGONE")
print("=" * 80)

depts_contains = Departement.objects.filter(geom__contains=test_point)

print(f"\nDépartements contenant ce point: {depts_contains.count()}")
for dept in depts_contains:
    print(f"  ✅ {dept.nom} ({dept.code_departement})")

# 2. Vérifier Brazzaville spécifiquement
brazza = Departement.objects.filter(nom__icontains='brazza').first()
pool = Departement.objects.filter(nom__icontains='pool').first()

if brazza:
    print(f"\n🔍 Brazzaville:")
    print(f"   - A un polygone: {'Oui' if brazza.geom else 'Non'}")
    if brazza.geom:
        contains_brazza = brazza.geom.contains(test_point)
        print(f"   - Contient le point: {'Oui' if contains_brazza else 'Non'}")

if pool:
    print(f"\n🔍 Pool:")
    print(f"   - A un polygone: {'Oui' if pool.geom else 'Non'}")
    if pool.geom:
        contains_pool = pool.geom.contains(test_point)
        print(f"   - Contient le point: {'Oui' if contains_pool else 'Non'}")

# 3. Vérifier les localités de Pool
print("\n" + "=" * 80)
print("LOCALITÉS DU DÉPARTEMENT POOL")
print("=" * 80)

if pool:
    localites_pool = Localite.objects.filter(departement=pool)
    print(f"\nTotal: {localites_pool.count()} localités dans Pool")

    # Chercher "Ngamaba"
    ngamaba = localites_pool.filter(nom__icontains='ngamaba').first()
    if ngamaba:
        print(f"\n📌 Ngamaba trouvé:")
        print(f"   - Coordonnées: {ngamaba.latitude}, {ngamaba.longitude}")
        print(f"   - A un polygone: {'Oui' if ngamaba.geom else 'Non'}")
        if ngamaba.geom:
            contains_ngamaba = ngamaba.geom.contains(test_point)
            print(f"   - Contient le point: {'Oui' if contains_ngamaba else 'Non'}")

# 4. Calcul des distances
print("\n" + "=" * 80)
print("CALCUL DES DISTANCES")
print("=" * 80)

from math import radians, cos, sin, asin, sqrt


def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1 = radians(lat1)
    phi2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lon2 - lon1)
    a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return R * 2 * asin(sqrt(a))


# Distance au centre de Brazzaville (approximatif: -4.2634, 15.2429)
brazza_center_lat = -4.2634
brazza_center_lon = 15.2429
dist_to_brazza = haversine(test_lat, test_lon, brazza_center_lat, brazza_center_lon)

print(f"\nDistance au centre de Brazzaville: {dist_to_brazza:.2f} km")

# Distance à Ngamaba si elle a des coordonnées
if pool and ngamaba and ngamaba.latitude and ngamaba.longitude:
    dist_to_ngamaba = haversine(
        test_lat, test_lon,
        float(ngamaba.latitude),
        float(ngamaba.longitude)
    )
    print(f"Distance au centre de Ngamaba: {dist_to_ngamaba:.2f} km")

print("\n" + "=" * 80)
print("CONCLUSION & RECOMMANDATIONS")
print("=" * 80)

if pool and pool.geom and pool.geom.contains(test_point):
    print("\n❌ PROBLÈME IDENTIFIÉ:")
    print("   Le polygone du département POOL déborde sur Brazzaville.")
    print("   C'est pour cela que votre point est détecté comme 'Ngamaba (Pool)'")
    print("   alors qu'il est à seulement 10 km du centre de Brazzaville.")

    print("\n✅ SOLUTIONS POSSIBLES:")
    print("   1. SOLUTION IMMÉDIATE (contournement):")
    print("      - Modifier la logique de détection pour privilégier la distance")
    print("      - Si distance < 15 km de Brazzaville → forcer Brazzaville")

    print("\n   2. SOLUTION PROPRE (recommandée):")
    print("      - Corriger les données géographiques du département Pool")
    print("      - Importer des polygones précis depuis OpenStreetMap ou GADM")

    print("\n   3. SOLUTION ALTERNATIVE:")
    print("      - Désactiver temporairement la détection par polygone pour Pool")
    print("      - Utiliser uniquement la détection par proximité")

else:
    print("\n✅ Les polygones semblent corrects.")
    print("   Le problème vient peut-être d'autre chose.")
    print("   Il faut augmenter le rayon de détection pour Brazzaville.")

print("\n" + "=" * 80)