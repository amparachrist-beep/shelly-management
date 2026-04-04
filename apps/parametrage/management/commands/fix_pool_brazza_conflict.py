# apps/parametrage/management/commands/fix_pool_brazza_conflict.py
"""
Commande pour corriger le conflit entre Pool et Brazzaville
✅ Redéfinit les limites géographiques précises
✅ Empêche le chevauchement des départements
"""
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Polygon, MultiPolygon, Point
from apps.parametrage.models import Departement, Localite


class Command(BaseCommand):
    help = 'Corrige le conflit géographique entre Pool et Brazzaville'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('CORRECTION DU CONFLIT POOL vs BRAZZAVILLE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        # ============================================
        # ÉTAPE 1 : CORRIGER BRAZZAVILLE
        # ============================================
        self.stdout.write('\n📍 ÉTAPE 1 : Redéfinition de Brazzaville...')

        brazza = Departement.objects.filter(nom__icontains='brazza').first()

        if brazza:
            # Polygone de Brazzaville (zone urbaine stricte)
            # Coordonnées approximatives basées sur la vraie zone urbaine
            brazza_coords = [
                (15.180, -4.330),  # Sud-Ouest
                (15.180, -4.160),  # Nord-Ouest
                (15.350, -4.160),  # Nord-Est
                (15.350, -4.330),  # Sud-Est
                (15.180, -4.330),  # Retour au début
            ]

            brazza_polygon = Polygon(brazza_coords, srid=4326)
            brazza.geom = MultiPolygon([brazza_polygon], srid=4326)
            brazza.centre = Point(15.2429, -4.2634, srid=4326)
            brazza.centre_latitude = -4.2634
            brazza.centre_longitude = 15.2429
            brazza.save()

            self.stdout.write(self.style.SUCCESS(f'   ✅ Brazzaville redéfini'))
            self.stdout.write(f'      - Superficie: ~{self.calculate_area(brazza_polygon):.2f} km²')
        else:
            self.stdout.write(self.style.WARNING('   ⚠️  Département Brazzaville non trouvé'))

        # ============================================
        # ÉTAPE 2 : CORRIGER POOL (exclure Brazzaville)
        # ============================================
        self.stdout.write('\n📍 ÉTAPE 2 : Redéfinition de Pool (sans Brazzaville)...')

        pool = Departement.objects.filter(code_departement='CG.PO').first()
        if not pool:
            pool = Departement.objects.filter(nom__icontains='pool').first()

        if pool:
            # Polygone de Pool SANS la zone de Brazzaville
            # Zone Nord de Pool
            pool_nord_coords = [
                (15.180, -4.160),  # Limite sud (juste au nord de Brazza)
                (15.180, -3.800),  # Nord
                (15.500, -3.800),  # Nord-Est
                (15.500, -4.160),  # Sud-Est
                (15.180, -4.160),  # Retour
            ]

            # Zone Sud de Pool
            pool_sud_coords = [
                (15.180, -4.330),  # Limite nord (juste au sud de Brazza)
                (15.180, -4.800),  # Sud
                (15.500, -4.800),  # Sud-Est
                (15.500, -4.330),  # Nord-Est
                (15.180, -4.330),  # Retour
            ]

            # Créer MultiPolygon avec les deux zones
            pool_polygon_nord = Polygon(pool_nord_coords, srid=4326)
            pool_polygon_sud = Polygon(pool_sud_coords, srid=4326)

            pool.geom = MultiPolygon([pool_polygon_nord, pool_polygon_sud], srid=4326)
            pool.centre = Point(15.340, -4.300, srid=4326)
            pool.centre_latitude = -4.300
            pool.centre_longitude = 15.340
            pool.save()

            self.stdout.write(self.style.SUCCESS(f'   ✅ Pool redéfini (2 zones distinctes)'))
            self.stdout.write(f'      - Zone Nord: ~{self.calculate_area(pool_polygon_nord):.2f} km²')
            self.stdout.write(f'      - Zone Sud: ~{self.calculate_area(pool_polygon_sud):.2f} km²')
        else:
            self.stdout.write(self.style.WARNING('   ⚠️  Département Pool non trouvé'))

        # ============================================
        # ÉTAPE 3 : DÉSACTIVER NGAMABA (localité de Pool dans Brazza)
        # ============================================
        self.stdout.write('\n📍 ÉTAPE 3 : Correction des localités problématiques...')

        ngamaba = Localite.objects.filter(nom__iexact='ngamaba').first()

        if ngamaba and ngamaba.departement == pool:
            # Option 1 : Déplacer Ngamaba vers Pool (hors Brazzaville)
            ngamaba.latitude = -4.350
            ngamaba.longitude = 15.280
            ngamaba.point = Point(15.280, -4.350, srid=4326)
            ngamaba.geom = None  # Retirer le polygone problématique
            ngamaba.save()

            self.stdout.write(self.style.SUCCESS('   ✅ Ngamaba déplacé hors de Brazzaville'))
            self.stdout.write(f'      - Nouvelles coordonnées: {ngamaba.latitude}, {ngamaba.longitude}')
        else:
            self.stdout.write(self.style.WARNING('   ⚠️  Localité Ngamaba non trouvée'))

        # ============================================
        # ÉTAPE 4 : VÉRIFICATION
        # ============================================
        self.stdout.write('\n📍 ÉTAPE 4 : Vérification...')

        # Point de test (celui qui posait problème)
        test_point = Point(15.264038, -4.167114, srid=4326)

        dept_brazza = Departement.objects.filter(
            geom__contains=test_point,
            nom__icontains='brazza'
        ).first()

        dept_pool = Departement.objects.filter(
            geom__contains=test_point,
            code_departement='CG.PO'
        ).first()

        if dept_brazza and not dept_pool:
            self.stdout.write(self.style.SUCCESS('   ✅ Point test détecté dans Brazzaville uniquement'))
        elif dept_pool and not dept_brazza:
            self.stdout.write(self.style.WARNING('   ⚠️  Point test détecté dans Pool (attendu: Brazzaville)'))
        elif dept_brazza and dept_pool:
            self.stdout.write(self.style.ERROR('   ❌ CONFLIT: Point détecté dans les DEUX départements !'))
        else:
            self.stdout.write(self.style.WARNING('   ⚠️  Point test non détecté'))

        # ============================================
        # STATISTIQUES FINALES
        # ============================================
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('STATISTIQUES FINALES'))
        self.stdout.write('=' * 80)

        if brazza:
            nb_quartiers_brazza = Localite.objects.filter(
                departement=brazza,
                type_localite='QUARTIER'
            ).count()
            self.stdout.write(f'📊 Brazzaville: {nb_quartiers_brazza} quartiers')

        if pool:
            nb_localites_pool = Localite.objects.filter(departement=pool).count()
            self.stdout.write(f'📊 Pool: {nb_localites_pool} localités')

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('✅ CORRECTION TERMINÉE'))
        self.stdout.write('=' * 80)

        self.stdout.write('\n💡 PROCHAINES ÉTAPES:')
        self.stdout.write('   1. Testez la détection avec: python manage.py test_geocoding')
        self.stdout.write('   2. Vérifiez sur la carte que les quartiers sont bien placés')
        self.stdout.write('   3. Si nécessaire, ajustez les coordonnées des polygones')

    def calculate_area(self, polygon):
        """
        Calcule approximativement la superficie d'un polygone en km²
        (méthode simplifiée pour estimation)
        """
        try:
            # Transformation en projection appropriée pour calcul de surface
            from django.contrib.gis.geos import GEOSGeometry
            from pyproj import Geod

            geod = Geod(ellps='WGS84')
            area, _ = geod.geometry_area_perimeter(polygon.wkt)
            return abs(area) / 1_000_000  # Conversion m² → km²
        except:
            # Fallback : estimation approximative
            bounds = polygon.extent
            width = (bounds[2] - bounds[0]) * 111  # 1 degré ≈ 111 km
            height = (bounds[3] - bounds[1]) * 111
            return width * height