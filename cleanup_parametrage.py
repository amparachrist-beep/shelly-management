#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script de nettoyage des types de tarification SEULEMENT
À exécuter avec : python cleanup_tarifs_seulement.py
"""

import os
import sys
import json
import datetime
from pathlib import Path

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

import django

django.setup()

# Import des modèles Django
from django.db import connection, transaction
from django.core import serializers

# Import des modèles nécessaires
try:
    from apps.parametrage.models import TypeTarification
    from apps.compteurs.models import Compteur
    from apps.facturation.models import FactureConsommation
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    sys.exit(1)


class TarifCleaner:
    """Classe pour nettoyer uniquement les types de tarification"""

    def __init__(self):
        self.backup_dir = Path(f"backups/tarifs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.backup_dir / "cleanup.log"
        self.stats = {
            'typetarification': 0,
            'compteurs_affectes': 0,
            'factures_affectes': 0
        }

    def log(self, message, level="INFO"):
        """Enregistre un message dans le log"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"

        colors = {
            "INFO": "\033[94m", "SUCCESS": "\033[92m",
            "WARNING": "\033[93m", "ERROR": "\033[91m", "SECTION": "\033[95m"
        }
        end_color = "\033[0m"

        if level in colors:
            print(f"{colors[level]}{log_entry}{end_color}")
        else:
            print(log_entry)

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_entry + "\n")

    def print_header(self, text):
        print("\n" + "=" * 60)
        print(f" {text}")
        print("=" * 60)

    def count_objects(self):
        """Compte les objets existants"""
        self.log("SECTION", "📊 COMPTAGE DES OBJETS")

        self.stats['typetarification'] = TypeTarification.objects.count()
        self.stats['compteurs_affectes'] = Compteur.objects.filter(
            type_tarification__isnull=False
        ).count()
        self.stats['factures_affectes'] = FactureConsommation.objects.filter(
            type_tarification__isnull=False
        ).count()

        self.log("INFO", f"📈 État actuel:")
        self.log("INFO", f"   - Types de tarification: {self.stats['typetarification']}")
        self.log("INFO", f"   - Compteurs avec tarif: {self.stats['compteurs_affectes']}")
        self.log("INFO", f"   - Factures avec tarif: {self.stats['factures_affectes']}")

    def check_dependencies(self):
        """Vérifie les dépendances avant suppression"""
        self.log("SECTION", "🔗 VÉRIFICATION DES DÉPENDANCES")

        has_dependencies = False

        used_tarifs = TypeTarification.objects.filter(
            compteur__isnull=False
        ).distinct().exists()

        if used_tarifs:
            self.log("WARNING",
                     f"⚠️  {self.stats['compteurs_affectes']} types de tarification sont utilisés par des compteurs")
            has_dependencies = True

        used_in_factures = TypeTarification.objects.filter(
            factures__isnull=False
        ).distinct().exists()

        if used_in_factures:
            self.log("WARNING",
                     f"⚠️  {self.stats['factures_affectes']} types de tarification sont utilisés par des factures")
            has_dependencies = True

        if has_dependencies:
            self.log("WARNING", "⚠️  Des dépendances existent. La suppression mettra à NULL les références.")
            return True
        else:
            self.log("SUCCESS", "✅ Aucune dépendance bloquante")
            return False

    def create_backup(self):
        """Crée une sauvegarde des types de tarification"""
        self.log("SECTION", "💾 CRÉATION DE LA SAUVEGARDE")

        try:
            if self.stats['typetarification'] > 0:
                data = serializers.serialize('json', TypeTarification.objects.all())
                backup_file = self.backup_dir / 'typetarification.json'
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(data)
                self.log("SUCCESS", f"✅ {self.stats['typetarification']} types de tarification sauvegardés")

            # Sauvegarde aussi des compteurs/factures concernés (optionnel)
            if self.stats['compteurs_affectes'] > 0:
                compteurs = Compteur.objects.filter(type_tarification__isnull=False)
                data = serializers.serialize('json', compteurs)
                with open(self.backup_dir / 'compteurs_affectes.json', 'w', encoding='utf-8') as f:
                    f.write(data)
                self.log("SUCCESS", f"✅ {self.stats['compteurs_affectes']} compteurs concernés sauvegardés")

            if self.stats['factures_affectes'] > 0:
                factures = FactureConsommation.objects.filter(type_tarification__isnull=False)
                data = serializers.serialize('json', factures)
                with open(self.backup_dir / 'factures_affectes.json', 'w', encoding='utf-8') as f:
                    f.write(data)
                self.log("SUCCESS", f"✅ {self.stats['factures_affectes']} factures concernées sauvegardées")

            metadata = {
                'date': datetime.datetime.now().isoformat(),
                'stats': self.stats,
                'files': [f.name for f in self.backup_dir.glob('*.json') if f.name != 'metadata.json']
            }
            with open(self.backup_dir / 'metadata.json', 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            self.log("SUCCESS", f"✅ Sauvegarde complète dans: {self.backup_dir}")

        except Exception as e:
            self.log("ERROR", f"❌ Erreur lors de la sauvegarde: {e}")
            raise

    def confirm_deletion(self):
        """Demande confirmation"""
        self.log("SECTION", "⚠️  CONFIRMATION DE SUPPRESSION")

        print("\n\033[91m⚠️  ATTENTION ! Cette opération va SUPPRIMER définitivement :\033[0m")
        print(f"   - {self.stats['typetarification']} types de tarification")

        if self.stats['compteurs_affectes'] > 0:
            print(f"\n\033[93m⚠️  {self.stats['compteurs_affectes']} compteurs verront leur tarif mis à NULL\033[0m")
        if self.stats['factures_affectes'] > 0:
            print(f"\033[93m⚠️  {self.stats['factures_affectes']} factures verront leur tarif mis à NULL\033[0m")

        print(f"\n\033[92m💾 Une sauvegarde a été créée dans: {self.backup_dir}\033[0m")

        print("\n\033[96mNote: Les départements, localités et types d'habitation seront CONSERVÉS.\033[0m")

        response = input("\n\033[93mVoulez-vous continuer ? (non/oui) \033[0m")

        if response.lower() != 'oui':
            self.log("INFO", "❌ Opération annulée")
            return False

        return True

    @transaction.atomic
    def perform_deletion(self):
        """Supprime uniquement les types de tarification"""
        self.log("SECTION", "🗑️  SUPPRESSION DES TYPES DE TARIFICATION")

        try:
            # 1. Dissocier les compteurs
            if self.stats['compteurs_affectes'] > 0:
                compteurs_update = Compteur.objects.filter(
                    type_tarification__isnull=False
                ).update(type_tarification=None)
                self.log("INFO", f"   → {compteurs_update} compteurs dissociés de leur tarif")

            # 2. Dissocier les factures
            if self.stats['factures_affectes'] > 0:
                factures_update = FactureConsommation.objects.filter(
                    type_tarification__isnull=False
                ).update(type_tarification=None)
                self.log("INFO", f"   → {factures_update} factures dissociées de leur tarif")

            # 3. Supprimer les types de tarification
            if self.stats['typetarification'] > 0:
                TypeTarification.objects.all().delete()
                self.log("INFO", f"   → {self.stats['typetarification']} types de tarification supprimés")

            self.log("SUCCESS", "✅ Suppression terminée avec succès")

        except Exception as e:
            self.log("ERROR", f"❌ Erreur lors de la suppression: {e}")
            raise

    def verify_deletion(self):
        """Vérifie que les types de tarification sont supprimés"""
        self.log("SECTION", "🔍 VÉRIFICATION FINALE")

        remaining = TypeTarification.objects.count()

        if remaining == 0:
            self.log("SUCCESS", "✅ Tous les types de tarification ont été supprimés")
            return True
        else:
            self.log("ERROR", f"❌ Il reste {remaining} types de tarification")
            return False

    def show_summary(self):
        """Affiche le résumé"""
        self.log("SECTION", "📊 RÉSUMÉ DE L'OPÉRATION")

        print("\n\033[96m═══════════════════════════════════════════════════════════════\033[0m")
        print("\033[1mRésumé de la suppression\033[0m")
        print("\033[96m═══════════════════════════════════════════════════════════════\033[0m")
        print(f"📁 Sauvegarde créée dans: \033[92m{self.backup_dir}\033[0m")
        print(f"📝 Logs disponibles dans: \033[92m{self.log_file}\033[0m")
        print(f"\n📊 Statistiques:")
        print(f"   - Types de tarification: {self.stats['typetarification']} supprimés")
        if self.stats['compteurs_affectes'] > 0:
            print(f"   - Compteurs modifiés: {self.stats['compteurs_affectes']}")
        if self.stats['factures_affectes'] > 0:
            print(f"   - Factures modifiées: {self.stats['factures_affectes']}")

        print(f"\n\033[96mLes départements, localités et types d'habitation ont été conservés.\033[0m")

        print(f"\n\033[93mPour restaurer la sauvegarde:\033[0m")
        print(f"   python manage.py loaddata {self.backup_dir}/typetarification.json")
        print("\033[96m═══════════════════════════════════════════════════════════════\033[0m")

    def run(self):
        """Exécute le script"""
        self.print_header("NETTOYAGE DES TYPES DE TARIFICATION SEULEMENT")

        # Vérifier la connexion
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.log("SUCCESS", "✅ Connexion à la base de données OK")
        except Exception as e:
            self.log("ERROR", f"❌ Erreur de connexion: {e}")
            return

        # Compter les objets
        self.count_objects()

        # Si rien à supprimer
        if self.stats['typetarification'] == 0:
            self.log("INFO", "✅ Aucun type de tarification à supprimer")
            return

        # Vérifier les dépendances
        self.check_dependencies()

        # Créer la sauvegarde
        self.create_backup()

        # Demander confirmation
        if not self.confirm_deletion():
            return

        # Supprimer
        self.perform_deletion()

        # Vérifier
        self.verify_deletion()

        # Afficher le résumé
        self.show_summary()


if __name__ == "__main__":
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)

    print(f"📂 Répertoire de travail: {backend_dir.absolute()}")
    print(f"📁 Dossier apps: {(backend_dir / 'apps').exists()}")

    cleaner = TarifCleaner()

    try:
        cleaner.run()
    except KeyboardInterrupt:
        print("\n\n\033[93m⚠️  Interruption par l'utilisateur\033[0m")
        sys.exit(0)
    except Exception as e:
        print(f"\n\033[91m❌ Erreur: {e}\033[0m")
        import traceback

        traceback.print_exc()
        sys.exit(1)