# apps/consommation/management/commands/sync_shelly_consommations.py

from django.core.management.base import BaseCommand
from django.utils import timezone  # ✅ Déjà importé en haut
from datetime import date
from decimal import Decimal
import requests

from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation


class Command(BaseCommand):
    help = 'Synchronise les consommations depuis les compteurs Shelly'

    def add_arguments(self, parser):
        parser.add_argument('--compteur_id', type=int)
        parser.add_argument('--all', action='store_true')
        parser.add_argument('--days', type=int, default=1)

    def handle(self, *args, **options):
        compteur_id = options.get('compteur_id')
        sync_all = options.get('all', False)

        if compteur_id:
            compteurs = Compteur.objects.filter(id=compteur_id)
        elif sync_all:
            compteurs = Compteur.objects.all()
        else:
            compteurs = Compteur.objects.filter(shelly_status='CONNECTE')

        if not compteurs.exists():
            self.stdout.write(self.style.WARNING("⚠️ Aucun compteur trouvé"))
            return

        self.stdout.write(f"\n🔍 Synchronisation de {compteurs.count()} compteur(s)...\n")

        for compteur in compteurs:
            self.sync_compteur(compteur)

        self.stdout.write(self.style.SUCCESS("\n✅ Synchronisation terminée !"))

    def sync_compteur(self, compteur):
        """Synchronise un compteur spécifique"""
        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(f"📡 Compteur: {compteur.numero_contrat}")

        if not compteur.shelly_ip:
            self.stdout.write(self.style.ERROR("❌ IP non configurée"))
            return

        try:
            # ✅ CORRECTION 1: Utiliser POST au lieu de GET
            payload = {"id": 1, "method": "EM.GetStatus", "params": {"id": 0}}
            response = requests.post(f"http://{compteur.shelly_ip}/rpc", json=payload, timeout=10)

            if response.status_code != 200:
                raise Exception("Shelly ne répond pas")

            data = response.json().get('result', {})

            phase1_w = float(data.get('a_act_power', 0) or 0)
            phase2_w = float(data.get('b_act_power', 0) or 0)
            phase3_w = float(data.get('c_act_power', 0) or 0)
            total_power_w = float(data.get('total_act_power', 0) or 0)

            # ✅ CORRECTION 2: Récupération énergie réelle avec EMData.GetStatus
            try:
                payload_energy = {"id": 2, "method": "EMData.GetStatus", "params": {"id": 0}}
                r = requests.post(f"http://{compteur.shelly_ip}/rpc", json=payload_energy, timeout=10)
                result_energy = r.json().get('result', {})
                energie_wh = result_energy.get('total_act', 0) or 0
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠️ Erreur récupération énergie: {str(e)}"))
                energie_wh = 0

            energie_kwh = float(energie_wh) / 1000

            self.stdout.write(self.style.SUCCESS("✅ Shelly OK"))
            self.stdout.write(f"⚡ Total: {total_power_w} W | 📊 {energie_kwh:.3f} kWh")

            # 🔥 DETECTION RESET
            if compteur.dernier_index_shelly is not None:
                if energie_kwh < float(compteur.dernier_index_shelly) - 1:  # Marge de 1 kWh
                    self.stdout.write(self.style.WARNING("🔄 Reset détecté"))
                    self.stdout.write(f"   Ancien: {compteur.dernier_index_shelly} kWh")
                    self.stdout.write(f"   Nouveau: {energie_kwh:.3f} kWh")

                    compteur.shelly_offset += compteur.dernier_index_shelly
                    compteur.date_reset_shelly = timezone.now()
                    self.stdout.write(f"   Nouvel offset: {compteur.shelly_offset} kWh")

            # 🔥 CALCUL INDEX REEL
            index_reel = float(compteur.shelly_offset or 0) + energie_kwh

            # 🔥 UPDATE COMPTEUR
            compteur.shelly_status = 'CONNECTE'
            compteur.dernier_index_shelly = Decimal(str(energie_kwh))
            compteur.index_actuel = Decimal(str(index_reel))
            compteur.derniere_sync_shelly = timezone.now()

            compteur.save(update_fields=[
                'shelly_status',
                'dernier_index_shelly',
                'shelly_offset',
                'index_actuel',
                'date_reset_shelly',
                'derniere_sync_shelly'
            ])

            self.stdout.write(f"📊 Index réel: {compteur.index_actuel} kWh")

            # 🔧 CAPTEUR
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
                self.stdout.write("  📝 Capteur créé")

            capteur.puissance_instantanee = Decimal(str(total_power_w))
            capteur.energie_totale = Decimal(str(energie_kwh))
            capteur.derniere_communication = timezone.now()
            capteur.status = 'ACTIF'
            capteur.save()

            # 🔥 ENREGISTRER CONSOMMATION
            self.enregistrer_consommation(
                compteur,
                phase1_w,
                phase2_w,
                phase3_w,
                float(compteur.index_actuel)
            )

        except requests.exceptions.Timeout:
            self.stdout.write(self.style.ERROR("❌ Timeout: Shelly injoignable"))
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])

        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR(f"❌ Erreur de connexion: Vérifiez l'IP {compteur.shelly_ip}"))
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Erreur: {str(e)}"))
            import traceback
            traceback.print_exc()
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])

    def enregistrer_consommation(self, compteur, phase1_w, phase2_w, phase3_w, index_actuel_reel):
        # ✅ CORRECTION : Utiliser timezone.now().date() au lieu de date.today()
        from django.utils import timezone
        today = timezone.now().date()

        conso_precedente = Consommation.objects.filter(
            compteur=compteur,
            periode__lt=today
        ).order_by('-periode').first()

        if conso_precedente:
            index_precedent = float(conso_precedente.index_fin_periode)
            self.stdout.write(f"  📌 Index précédent ({conso_precedente.periode}): {index_precedent} kWh")
        else:
            index_precedent = float(compteur.index_initial)
            self.stdout.write(f"  📌 Index initial: {index_precedent} kWh")

        conso_jour_kwh = index_actuel_reel - index_precedent
        self.stdout.write(f"  📊 Index actuel réel: {index_actuel_reel} kWh")
        self.stdout.write(f"  📊 Consommation du jour: {conso_jour_kwh:.2f} kWh")

        # Si consommation négative ou trop grande, utiliser estimation
        if conso_jour_kwh < 0 or conso_jour_kwh > 100:
            self.stdout.write(self.style.WARNING(f"  ⚠️ Consommation incohérente, utilisation estimation"))
            conso_jour_kwh = (phase1_w + phase2_w + phase3_w) * 24 / 1000
            self.stdout.write(f"  📊 Consommation estimée: {conso_jour_kwh:.2f} kWh")

        total_w = phase1_w + phase2_w + phase3_w

        if total_w > 0:
            phase1_kwh = (phase1_w / total_w) * conso_jour_kwh
            phase2_kwh = (phase2_w / total_w) * conso_jour_kwh
            phase3_kwh = (phase3_w / total_w) * conso_jour_kwh
        else:
            phase1_kwh = 0
            phase2_kwh = 0
            phase3_kwh = conso_jour_kwh

        # Arrondir à 2 décimales
        phase1_kwh = round(phase1_kwh, 2)
        phase2_kwh = round(phase2_kwh, 2)
        phase3_kwh = round(phase3_kwh, 2)

        conso, created = Consommation.objects.update_or_create(
            compteur=compteur,
            periode=today,
            defaults={
                'phase_1_kwh': Decimal(str(phase1_kwh)),
                'phase_2_kwh': Decimal(str(phase2_kwh)),
                'phase_3_kwh': Decimal(str(phase3_kwh)),
                'index_debut_periode': Decimal(str(index_precedent)),
                'index_fin_periode': Decimal(str(index_actuel_reel)),
                'statut': 'VALIDÉ',
                'source': 'SHELLY',
                'date_releve': timezone.now(),
            }
        )

        status = "créée" if created else "mise à jour"
        self.stdout.write(self.style.SUCCESS(f"  ✅ Consommation {status} pour {today}: {conso_jour_kwh:.2f} kWh"))