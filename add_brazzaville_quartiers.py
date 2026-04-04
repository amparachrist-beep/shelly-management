#!/usr/bin/env python
"""
Script pour ajouter manuellement les quartiers de Brazzaville
"""
import os
import sys
import django

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.parametrage.models import Departement, Localite
from django.contrib.gis.geos import Point, Polygon, MultiPolygon


def add_brazzaville_quartiers():
    """
    Ajoute les principaux quartiers de Brazzaville avec leurs coordonnées approximatives
    """
    print("=" * 70)
    print("AJOUT DES QUARTIERS DE BRAZZAVILLE")
    print("=" * 70)

    # Récupérer ou créer le département de Brazzaville
    dept, created = Departement.objects.get_or_create(
        code_departement='BZV',
        defaults={
            'nom': 'Brazzaville',
            'region': 'Sud',
            'centre_latitude': -4.2634,
            'centre_longitude': 15.2429
        }
    )

    if created:
        dept.centre = Point(15.2429, -4.2634, srid=4326)
        dept.save()
        print(f"✅ Département créé: {dept.nom}")
    else:
        print(f"✅ Département existant: {dept.nom}")

    # Liste des quartiers avec coordonnées approximatives
    # Format: (nom, lat, lon, rayon_km)
    quartiers = [
        # Centre-ville
        ("Centre-ville", -4.2634, 15.2829, 2.0),
        ("Plateau", -4.2600, 15.2900, 1.5),
        ("Poto-Poto", -4.2500, 15.2700, 2.0),
        ("Moungali", -4.2700, 15.2600, 2.0),
        ("Ouenzé", -4.2400, 15.2500, 2.5),

        # Arrondissements nord
        ("Talangaï", -4.2300, 15.2800, 3.0),
        ("Mfilou", -4.3000, 15.3000, 3.0),
        ("Madibou", -4.2800, 15.3100, 2.5),  # Celui détecté

        # Arrondissements sud
        ("Bacongo", -4.2800, 15.2700, 2.0),
        ("Makélékélé", -4.2900, 15.2500, 2.5),
        ("Mpi", -4.3200, 15.2400, 3.0),

        # Autres quartiers
        ("M'Pila", -4.2567, 15.2872, 1.8),
        ("OCH", -4.2456, 15.2934, 1.5),
        ("Djiri", -4.2789, 15.2534, 2.0),
        ("Nkombo", -4.2345, 15.2678, 1.5),
    ]

    added = 0
    updated = 0

    for nom, lat, lon, rayon in quartiers:
        # Créer un polygone carré approximatif autour du point
        # (pour une meilleure détection)
        offset = rayon / 111.0  # Approximation: 1 degré ≈ 111 km

        polygon = Polygon([
            (lon - offset, lat - offset),
            (lon + offset, lat - offset),
            (lon + offset, lat + offset),
            (lon - offset, lat + offset),
            (lon - offset, lat - offset),
        ], srid=4326)

        multi_polygon = MultiPolygon([polygon], srid=4326)

        # Créer ou mettre à jour
        localite, created = Localite.objects.get_or_create(
            nom=nom,
            departement=dept,
            defaults={
                'type_localite': 'QUARTIER',
                'latitude': lat,
                'longitude': lon,
                'zone_rayon_km': rayon,
                'geom': multi_polygon,
                'point': Point(lon, lat, srid=4326)
            }
        )

        if created:
            print(f"   ✅ Créé: {nom} ({lat}, {lon})")
            added += 1
        else:
            # Mettre à jour les coordonnées
            localite.latitude = lat
            localite.longitude = lon
            localite.zone_rayon_km = rayon
            localite.geom = multi_polygon
            localite.point = Point(lon, lat, srid=4326)
            localite.save()
            print(f"   🔄 Mis à jour: {nom}")
            updated += 1

    print(f"\n📊 Résumé:")
    print(f"   Créés: {added}")
    print(f"   Mis à jour: {updated}")
    print(f"   Total: {Localite.objects.filter(departement=dept).count()}")

    # Test de géolocalisation
    print(f"\n🧪 Test avec votre position (-4.256800, 15.287200):")
    test_point = Point(15.287200, -4.256800, srid=4326)

    localite = Localite.objects.filter(
        geom__contains=test_point,
        departement=dept
    ).first()

    if localite:
        print(f"   ✅ Quartier détecté: {localite.nom}")
    else:
        print(f"   ⚠️  Aucun quartier trouvé")
        # Chercher le plus proche
        from math import radians, cos, sin, asin, sqrt

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371
            dlat = radians(lat2 - lat1)
            dlon = radians(lon2 - lon1)
            a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
            return R * 2 * asin(sqrt(a))

        quartiers_proches = []
        for q in Localite.objects.filter(departement=dept):
            if q.latitude and q.longitude:
                dist = haversine(-4.256800, 15.287200, float(q.latitude), float(q.longitude))
                quartiers_proches.append((q.nom, dist))

        quartiers_proches.sort(key=lambda x: x[1])
        print(f"\n   📍 Quartiers les plus proches:")
        for nom, dist in quartiers_proches[:5]:
            print(f"      - {nom}: {dist:.2f} km")


if __name__ == '__main__':
    add_brazzaville_quartiers()

    print("\n" + "=" * 70)
    print("✅ TERMINÉ")
    print("=" * 70)
    print("\n💡 Prochaines étapes:")
    print("   1. Rechargez votre page web")
    print("   2. Testez en cliquant sur la carte à votre position")
    print("   3. Si le quartier n'est toujours pas bon, ajustez les coordonnées")
    print()