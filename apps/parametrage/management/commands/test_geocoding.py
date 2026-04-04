# apps/parametrage/management/commands/test_geocoding.py
"""
Commande pour tester la détection géographique après correction
"""
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from apps.parametrage.models import Departement, Localite
from math import radians, cos, sin, asin, sqrt


class Command(BaseCommand):
    help = 'Teste la détection géographique sur plusieurs points'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('TEST DE GÉOLOCALISATION'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        # Points de test
        test_points = [
            {
                'name': 'Centre de Brazzaville',
                'lat': -4.2634,
                'lon': 15.2429,
                'expected_dept': 'Brazzaville'
            },
            {
                'name': 'Poto-Poto (Brazzaville)',
                'lat': -4.2500,
                'lon': 15.2700,
                'expected_dept': 'Brazzaville'
            },
            {
                'name': 'Point problématique (ex-Ngamaba)',
                'lat': -4.167114,
                'lon': 15.264038,
                'expected_dept': 'Brazzaville'
            },
            {
                'name': 'Bacongo (Brazzaville)',
                'lat': -4.2800,
                'lon': 15.2700,
                'expected_dept': 'Brazzaville'
            },
            {
                'name': 'Pointe-Noire',
                'lat': -4.7773,
                'lon': 11.8650,
                'expected_dept': 'Pointe-Noire'
            },
        ]

        self.stdout.write('\n')

        for i, test in enumerate(test_points, 1):
            self.stdout.write(f"\n📍 TEST {i}: {test['name']}")
            self.stdout.write(f"   Coordonnées: {test['lat']}, {test['lon']}")
            self.stdout.write(f"   Attendu: {test['expected_dept']}")

            point = Point(test['lon'], test['lat'], srid=4326)

            # Détection par polygone
            dept = Departement.objects.filter(geom__contains=point).first()

            if dept:
                if test['expected_dept'].lower() in dept.nom.lower():
                    self.stdout.write(self.style.SUCCESS(f"   ✅ Détecté: {dept.nom} (CORRECT)"))
                else:
                    self.stdout.write(self.style.ERROR(f"   ❌ Détecté: {dept.nom} (INCORRECT)"))

                # Chercher la localité
                localite = Localite.objects.filter(
                    departement=dept,
                    geom__contains=point
                ).first()

                if not localite:
                    # Fallback par proximité
                    localites = Localite.objects.filter(
                        departement=dept,
                        latitude__isnull=False,
                        longitude__isnull=False
                    ).exclude(latitude=0, longitude=0)

                    meilleure = None
                    dist_min = float('inf')

                    for loc in localites:
                        try:
                            dist = self.haversine(
                                test['lat'], test['lon'],
                                float(loc.latitude), float(loc.longitude)
                            )
                            if dist < dist_min:
                                dist_min = dist
                                meilleure = loc
                        except:
                            continue

                    if meilleure and dist_min < 5.0:
                        localite = meilleure
                        self.stdout.write(f"      → Localité: {localite.nom} ({dist_min:.2f} km)")
                    else:
                        self.stdout.write(f"      → Aucune localité proche trouvée")
                else:
                    self.stdout.write(f"      → Localité: {localite.nom} (polygone)")
            else:
                self.stdout.write(self.style.ERROR(f"   ❌ Aucun département détecté"))

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('✅ TESTS TERMINÉS'))
        self.stdout.write('=' * 80)

    def haversine(self, lat1, lon1, lat2, lon2):
        """Calcule la distance en km entre deux points GPS"""
        R = 6371.0
        phi1 = radians(lat1)
        phi2 = radians(lat2)
        delta_phi = radians(lat2 - lat1)
        delta_lambda = radians(lon2 - lon1)
        a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
        return R * 2 * asin(sqrt(a))