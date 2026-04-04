"""
Script de diagnostic pour vérifier les quartiers de Brazzaville
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from apps.parametrage.models import Localite, Departement

print("=" * 80)
print("DIAGNOSTIC DES DONNÉES GÉOGRAPHIQUES - BRAZZAVILLE")
print("=" * 80)

# 1. Vérifier le département Brazzaville
brazza = Departement.objects.filter(nom__icontains='brazza').first()

if not brazza:
    print("\n❌ DÉPARTEMENT BRAZZAVILLE NON TROUVÉ !")
    print("Liste des départements disponibles:")
    for dept in Departement.objects.all():
        print(f"  - {dept.nom} ({dept.code_departement})")
else:
    print(f"\n✅ Département trouvé: {brazza.nom}")
    print(f"   Code: {brazza.code_departement}")
    print(f"   Centre: {brazza.centre_latitude}, {brazza.centre_longitude}")
    print(f"   Polygone: {'Oui' if brazza.geom else 'Non'}")

    # 2. Vérifier les quartiers
    print("\n" + "=" * 80)
    print("QUARTIERS DE BRAZZAVILLE")
    print("=" * 80)

    quartiers = Localite.objects.filter(
        departement=brazza,
        type_localite='QUARTIER'
    )

    print(f"\nTotal: {quartiers.count()} quartiers")

    # Quartiers avec coordonnées
    avec_coords = quartiers.exclude(latitude__isnull=True).exclude(longitude__isnull=True)
    print(f"Avec coordonnées: {avec_coords.count()}")

    # Quartiers sans coordonnées
    sans_coords = quartiers.filter(latitude__isnull=True) | quartiers.filter(longitude__isnull=True)
    print(f"Sans coordonnées: {sans_coords.count()}")

    # Lister les quartiers avec coordonnées
    if avec_coords.exists():
        print("\n📍 QUARTIERS AVEC COORDONNÉES:")
        for q in avec_coords.order_by('nom'):
            print(f"   ✅ {q.nom:<30} ({q.latitude}, {q.longitude})")

    # Lister les quartiers sans coordonnées
    if sans_coords.exists():
        print("\n⚠️  QUARTIERS SANS COORDONNÉES:")
        for q in sans_coords.order_by('nom')[:10]:
            print(f"   ❌ {q.nom}")
        if sans_coords.count() > 10:
            print(f"   ... et {sans_coords.count() - 10} autres")

    # 3. Test avec les coordonnées fournies
    print("\n" + "=" * 80)
    print("TEST AVEC VOS COORDONNÉES")
    print("=" * 80)

    test_lat = -4.167114
    test_lon = 15.264038

    print(f"\nPoint test: {test_lat}, {test_lon}")

    # Chercher le quartier le plus proche
    from math import radians, cos, sin, asin, sqrt


    def haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        phi1 = radians(lat1)
        phi2 = radians(lat2)
        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)
        a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
        return R * 2 * asin(sqrt(a))


    print("\nDistances aux quartiers:")
    distances = []

    for q in avec_coords:
        try:
            dist = haversine(test_lat, test_lon, float(q.latitude), float(q.longitude))
            distances.append((q.nom, dist))
        except:
            continue

    # Trier par distance
    distances.sort(key=lambda x: x[1])

    # Afficher les 10 plus proches
    print("\n🎯 10 QUARTIERS LES PLUS PROCHES:")
    for i, (nom, dist) in enumerate(distances[:10], 1):
        print(f"   {i}. {nom:<30} {dist:.3f} km ({int(dist * 1000)} m)")

    # Recommandations
    print("\n" + "=" * 80)
    print("RECOMMANDATIONS")
    print("=" * 80)

    if sans_coords.exists():
        print(f"\n⚠️  Vous avez {sans_coords.count()} quartiers sans coordonnées GPS.")
        print("   Pour améliorer la précision, il faut ajouter les coordonnées GPS de ces quartiers.")
        print("\n   Quartiers prioritaires à géolocaliser:")
        for q in sans_coords.order_by('nom')[:5]:
            print(f"   - {q.nom}")

    if avec_coords.count() < 10:
        print(f"\n⚠️  Seulement {avec_coords.count()} quartiers géolocalisés.")
        print("   Brazzaville compte plus de 30 quartiers. Importez les données complètes.")

    if distances and distances[0][1] > 2:
        print(f"\n⚠️  Le quartier le plus proche ({distances[0][0]}) est à {distances[0][1]:.1f} km.")
        print("   Les coordonnées du point test ne correspondent à aucun quartier connu.")
        print("   Vérifiez que les données de quartiers sont complètes.")

print("\n" + "=" * 80)
print("FIN DU DIAGNOSTIC")
print("=" * 80)