# apps/consommation/management/commands/sync_shelly_consommations.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import requests
from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation


class Command(BaseCommand):
    help = 'Synchronise les consommations depuis les compteurs Shelly'

    def add_arguments(self, parser):
        parser.add_argument(
            '--compteur_id',
            type=int,
            help='ID spécifique du compteur à synchroniser'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Synchronise tous les compteurs'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=1,
            help='Nombre de jours à synchroniser (défaut: 1)'
        )

    def handle(self, *args, **options):
        compteur_id = options.get('compteur_id')
        sync_all = options.get('all', False)
        days = options.get('days', 1)

        if compteur_id:
            compteurs = Compteur.objects.filter(id=compteur_id)
        elif sync_all:
            compteurs = Compteur.objects.all()
        else:
            compteurs = Compteur.objects.filter(shelly_status='CONNECTE')

        if not compteurs.exists():
            self.stdout.write(self.style.WARNING("⚠️ Aucun compteur trouvé"))
            return

        self.stdout.write(f"\n🔍 Synchronisation de {compteurs.count()} compteur(s)...")
        self.stdout.write(f"📅 Période: {days} jour(s)\n")

        for compteur in compteurs:
            self.sync_compteur(compteur, days)

        self.stdout.write(self.style.SUCCESS("\n✅ Synchronisation terminée !"))

    def sync_compteur(self, compteur, days):
        """Synchronise un compteur spécifique"""
        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(f"📡 Compteur: {compteur.numero_contrat}")
        self.stdout.write(f"📍 IP: {compteur.shelly_ip or 'Non configurée'}")

        if not compteur.shelly_ip:
            self.stdout.write(self.style.ERROR(f"  ❌ IP non configurée"))
            return

        try:
            # ✅ CORRECTION: Ajouter le paramètre id=0 dans l'URL
            url = f"http://{compteur.shelly_ip}/rpc/EM.GetStatus?id=0"
            self.stdout.write(f"  🔗 URL: {url}")

            response = requests.get(url, timeout=10)
            self.stdout.write(f"  📡 Status code: {response.status_code}")

            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"  ❌ Shelly ne répond pas (status {response.status_code})"))
                compteur.shelly_status = 'DECONNECTE'
                compteur.save(update_fields=['shelly_status'])
                return

            data = response.json()
            self.stdout.write(f"  📦 Réponse reçue")

            # Extraire les données
            result = data.get('result', {})

            # Pour Shelly Pro 3EM, les clés sont a_act_power, b_act_power, c_act_power
            phase1_w = float(result.get('a_act_power', 0) or 0)
            phase2_w = float(result.get('b_act_power', 0) or 0)
            phase3_w = float(result.get('c_act_power', 0) or 0)
            total_power_w = float(result.get('total_act_power', 0) or 0)

            # Récupérer l'énergie totale
            energie_wh = float(result.get('total_act_energy', 0) or 0)
            energie_kwh = energie_wh / 1000

            self.stdout.write(self.style.SUCCESS(f"  ✅ Connexion Shelly réussie"))
            self.stdout.write(f"  ⚡ Puissances: P1={phase1_w}W, P2={phase2_w}W, P3={phase3_w}W, Total={total_power_w}W")
            self.stdout.write(f"  📊 Énergie totale: {energie_kwh:.3f} kWh")

            # Mettre à jour le compteur
            compteur.shelly_status = 'CONNECTE'
            compteur.index_actuel = Decimal(str(energie_kwh))
            compteur.derniere_sync_shelly = timezone.now()
            compteur.save(update_fields=['shelly_status', 'index_actuel', 'derniere_sync_shelly'])

            # Mettre à jour ou créer le capteur
            capteur = compteur.capteurs.first()
            if not capteur:
                from apps.compteurs.models import Capteur
                capteur = Capteur.objects.create(
                    compteur=compteur,
                    device_id=f"SHELLY-{compteur.id}",
                    device_name=f"Capteur {compteur.numero_contrat}",
                    ip_address=compteur.shelly_ip,
                    status='ACTIF'
                )
                self.stdout.write(f"  📝 Capteur créé")

            capteur.puissance_instantanee = Decimal(str(total_power_w))
            capteur.energie_totale = Decimal(str(energie_kwh))
            capteur.derniere_communication = timezone.now()
            capteur.status = 'ACTIF'
            capteur.save(update_fields=['puissance_instantanee', 'energie_totale', 'derniere_communication', 'status'])

            # Enregistrer la consommation journalière
            self.enregistrer_consommation(compteur, phase1_w, phase2_w, phase3_w, energie_kwh)

        except requests.exceptions.Timeout:
            self.stdout.write(self.style.ERROR(f"  ❌ Timeout: Shelly injoignable"))
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])

        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR(f"  ❌ Erreur de connexion: Vérifiez l'IP {compteur.shelly_ip}"))
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Erreur: {str(e)}"))
            import traceback
            traceback.print_exc()

    def enregistrer_consommation(self, compteur, phase1_w, phase2_w, phase3_w, energie_totale_kwh):
        """Enregistre la consommation journalière"""
        today = date.today()

        # Récupérer la consommation de la veille
        hier = today - timedelta(days=1)
        conso_hier = Consommation.objects.filter(compteur=compteur, periode=hier).first()

        # Calculer la consommation du jour (différence d'index)
        index_precedent = float(conso_hier.index_fin_periode) if conso_hier else 0
        conso_jour_kwh = energie_totale_kwh - index_precedent

        if conso_jour_kwh < 0:
            conso_jour_kwh = (phase1_w + phase2_w + phase3_w) * 24 / 1000

        # Calculer la répartition par phase
        total_w = phase1_w + phase2_w + phase3_w
        if total_w > 0:
            phase1_kwh = (phase1_w / total_w) * conso_jour_kwh
            phase2_kwh = (phase2_w / total_w) * conso_jour_kwh
            phase3_kwh = (phase3_w / total_w) * conso_jour_kwh
        else:
            phase1_kwh = conso_jour_kwh / 3
            phase2_kwh = conso_jour_kwh / 3
            phase3_kwh = conso_jour_kwh / 3

        # Créer ou mettre à jour la consommation
        conso, created = Consommation.objects.update_or_create(
            compteur=compteur,
            periode=today,
            defaults={
                'phase_1_kwh': round(Decimal(str(phase1_kwh)), 2),
                'phase_2_kwh': round(Decimal(str(phase2_kwh)), 2),
                'phase_3_kwh': round(Decimal(str(phase3_kwh)), 2),
                'index_debut_periode': Decimal(str(index_precedent)),
                'index_fin_periode': Decimal(str(energie_totale_kwh)),
                'statut': 'VALIDÉ',
                'source': 'SHELLY',
                'date_releve': timezone.now(),
            }
        )

        status = "créée" if created else "mise à jour"
        self.stdout.write(self.style.SUCCESS(f"  ✅ Consommation {status} pour {today}: {conso_jour_kwh:.2f} kWh"))
        self.stdout.write(
            f"     Phase1: {phase1_kwh:.2f} kWh, Phase2: {phase2_kwh:.2f} kWh, Phase3: {phase3_kwh:.2f} kWh")