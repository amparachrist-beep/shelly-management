# apps/parametrage/management/commands/import_geojson.py

import json
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import GEOSGeometry, Point, MultiPolygon, Polygon
from apps.parametrage.models import Departement, \
    Localite  # ⚠️ L'IDE peut souligner en rouge, mais ça fonctionne avec manage.py !


class Command(BaseCommand):
    help = 'Importe les données géographiques depuis un fichier GeoJSON'

    def add_arguments(self, parser):
        parser.add_argument(
            'file_path',
            type=str,
            help='Chemin vers le fichier GeoJSON'
        )
        parser.add_argument(
            '--level',
            type=str,
            choices=['departement', 'localite'],
            default='departement',
            help='Niveau administratif à importer (département ou localité)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simuler l\'import sans sauvegarder'
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Écraser les données existantes'
        )
        parser.add_argument(
            '--encoding',
            type=str,
            default='utf-8',
            help='Encodage du fichier (défaut: utf-8)'
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        level = options['level']
        dry_run = options['dry_run']
        overwrite = options['overwrite']
        encoding = options['encoding']

        # Vérifier que le fichier existe
        if not os.path.exists(file_path):
            raise CommandError(f'Fichier non trouvé : {file_path}')

        self.stdout.write(self.style.SUCCESS(f'Lecture du fichier : {file_path}'))

        # Lire le GeoJSON
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f'Erreur de lecture JSON : {e}')
        except Exception as e:
            raise CommandError(f'Erreur : {e}')

        # Vérifier la structure - CORRIGÉ ICI ⬇️
        if 'features' not in data:
            raise CommandError('Format GeoJSON invalide : champ "features" manquant')

        features = data['features']
        self.stdout.write(f'{len(features)} entités trouvées')

        imported = 0
        skipped = 0
        updated = 0
        errors = []

        for i, feature in enumerate(features, 1):
            try:
                properties = feature.get('properties', {})
                geometry = feature.get('geometry')

                if not geometry:
                    errors.append(f'Entité {i}: géométrie manquante')
                    skipped += 1
                    continue

                # Normaliser la géométrie
                geom = self._normalize_geometry(geometry)

                if level == 'departement':
                    result = self._import_departement(properties, geom, overwrite, dry_run)
                else:
                    result = self._import_localite(properties, geom, overwrite, dry_run)

                if result == 'imported':
                    imported += 1
                elif result == 'updated':
                    updated += 1
                elif result == 'skipped':
                    skipped += 1

                if i % 10 == 0:
                    self.stdout.write(f'Traitement {i}/{len(features)}...')

            except Exception as e:
                errors.append(f'Entité {i}: {str(e)}')
                skipped += 1

        # Résumé
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS(f'Import terminé :'))
        self.stdout.write(f'  ✓ Importés : {imported}')
        self.stdout.write(f'  🔄 Mis à jour : {updated}')
        self.stdout.write(f'  ⚠ Ignorés : {skipped}')
        self.stdout.write(f'  ✗ Erreurs : {len(errors)}')

        if errors and not dry_run:
            self.stdout.write('\nErreurs détaillées (premières 10) :')
            for error in errors[:10]:
                self.stdout.write(f'  - {error}')
            if len(errors) > 10:
                self.stdout.write(f'  ... et {len(errors) - 10} autres erreurs')

    def _normalize_geometry(self, geometry):
        """Normalise la géométrie pour être compatible avec GeoDjango"""
        geom_type = geometry.get('type')

        if geom_type in ['Polygon', 'MultiPolygon']:
            # Convertir en MultiPolygon si nécessaire
            if geom_type == 'Polygon':
                geometry = {
                    'type': 'MultiPolygon',
                    'coordinates': [geometry['coordinates']]
                }
            return GEOSGeometry(json.dumps(geometry), srid=4326)

        elif geom_type == 'Point':
            return GEOSGeometry(json.dumps(geometry), srid=4326)

        else:
            raise ValueError(f'Type de géométrie non supporté : {geom_type}')

    def _import_departement(self, properties, geom, overwrite, dry_run):
        """Importe un département (compatible GADM)"""
        # Extraire le nom (supporte GADM: NAME_1, HDX: name_1, OSM: name)
        nom = (
                properties.get('NAME_1') or
                properties.get('name_1') or
                properties.get('NAME') or
                properties.get('name') or
                properties.get('nom') or
                'Inconnu'
        )

        # Extraire le code (GADM: HASC_1, ISO: ISO_1, etc.)
        code = (
                properties.get('HASC_1') or
                properties.get('ISO_1') or
                properties.get('GID_1') or
                properties.get('code') or
                properties.get('CODE') or
                f'COG_{nom.replace(" ", "_")}'
        )

        # Extraire la région (souvent le pays pour niveau 1)
        region = (
                properties.get('NAME_0') or  # Pays
                properties.get('region') or
                'Congo-Brazzaville'
        )

        # Vérifier si le département existe déjà
        existing = Departement.objects.filter(code_departement=code).first()

        if existing and not overwrite:
            return 'skipped'

        if not dry_run:
            if existing:
                # Mise à jour
                existing.nom = nom
                existing.region = region
                existing.geom = geom

                if isinstance(geom, (MultiPolygon, Polygon)):
                    existing.centre = geom.centroid

                existing.save()
                self.stdout.write(self.style.WARNING(f'🔄 Mis à jour : {nom}'))
                return 'updated'
            else:
                # Création - CORRIGÉ: utiliser _get_float_property ⬇️
                dept = Departement.objects.create(
                    nom=nom,
                    code_departement=code,
                    region=region,
                    geom=geom,
                    centre=geom.centroid if isinstance(geom, (MultiPolygon, Polygon)) else None,
                    centre_latitude=self._get_float_property(properties, ['LAT', 'latitude', 'Latitude', 'y', 'Y']),
                    centre_longitude=self._get_float_property(properties, ['LON', 'longitude', 'Longitude', 'x', 'X'])
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Créé : {dept.nom}'))
                return 'imported'

        return 'skipped'

    def _import_localite(self, properties, geom, overwrite, dry_run):
        """Importe une localité (compatible GADM niveau 2)"""
        # Extraire le nom de l'arrondissement/commune
        nom = (
                properties.get('NAME_2') or
                properties.get('name_2') or
                properties.get('NAME') or
                properties.get('name') or
                properties.get('nom') or
                'Inconnu'
        )

        # Type de localité selon le niveau GADM
        type_localite = 'ARRONDISSEMENT'  # Niveau 2 = arrondissements au Congo

        # Trouver le département parent via HASC_1 ou NAME_1
        dept_code = (
                properties.get('HASC_1') or
                properties.get('GID_1') or
                properties.get('ISO_1')
        )
        dept_name = properties.get('NAME_1') or properties.get('name_1')

        departement = None

        if dept_code:
            departement = Departement.objects.filter(
                code_departement__iexact=dept_code
            ).first()

        if not departement and dept_name:
            departement = Departement.objects.filter(
                nom__iexact=dept_name
            ).first()

        if not departement:
            # Fallback : prendre le premier département si non trouvé
            departement = Departement.objects.first()
            if not departement:
                self.stdout.write(self.style.ERROR(f'❌ Aucun département trouvé pour {nom}'))
                return 'skipped'

        # Vérifier si la localité existe déjà
        existing = Localite.objects.filter(
            nom__iexact=nom,
            departement=departement,
            type_localite=type_localite
        ).first()

        if existing and not overwrite:
            return 'skipped'

        if not dry_run:
            if existing:
                existing.geom = geom
                existing.point = geom.centroid if isinstance(geom, (MultiPolygon, Polygon)) else None
                existing.save()
                self.stdout.write(self.style.WARNING(f'🔄 Mis à jour : {nom}'))
                return 'updated'
            else:
                # Création - CORRIGÉ: utiliser _get_float_property ⬇️
                localite = Localite.objects.create(
                    nom=nom,
                    code_postal='',
                    departement=departement,
                    type_localite=type_localite,
                    geom=geom,
                    point=geom.centroid if isinstance(geom, (MultiPolygon, Polygon)) else None,
                    latitude=self._get_float_property(properties, ['LAT', 'latitude', 'Latitude', 'y', 'Y']),
                    longitude=self._get_float_property(properties, ['LON', 'longitude', 'Longitude', 'x', 'X']),
                    zone_rayon_km=2.0  # Rayon par défaut pour arrondissements
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Créé : {localite.nom}'))
                return 'imported'

        return 'skipped'

    def _map_type_localite(self, type_value):
        """Mappe le type de localité aux choix définis"""
        mapping = {
            'ville': 'VILLE',
            'Ville': 'VILLE',
            'city': 'VILLE',
            'commune': 'COMMUNE',
            'Commune': 'COMMUNE',
            'arrondissement': 'ARRONDISSEMENT',
            'Arrondissement': 'ARRONDISSEMENT',
            'quartier': 'QUARTIER',
            'Quartier': 'QUARTIER',
            'village': 'VILLAGE',
            'Village': 'VILLAGE',
            'secteur': 'SECTEUR',
            'Secteur': 'SECTEUR',
        }
        return mapping.get(type_value, 'QUARTIER')

    def _get_float_property(self, properties, keys):
        """Récupère une propriété flottante - MÉTHODE AJOUTÉE ⬇️"""
        for key in keys:
            value = properties.get(key)
            if value is not None:
                try:
                    # Gérer les valeurs comme "4.2634" ou "-4.2634"
                    return float(str(value).strip())
                except (ValueError, TypeError, AttributeError):
                    continue
        return None