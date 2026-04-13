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
            self.stdout.write(self.style.WARNING("Aucun compteur trouve"))
            return

        self.stdout.write(f"\nSynchronisation de {compteurs.count()} compteur(s)...\n")

        for compteur in compteurs:
            self.sync_compteur(compteur)

        self.stdout.write(self.style.SUCCESS("\nSynchronisation terminee !"))

    def sync_compteur(self, compteur):
        self.stdout.write(f"\n{'=' * 50}")
        self.stdout.write(f"Compteur: {compteur.numero_contrat}")

        if not compteur.shelly_ip:
            self.stdout.write(self.style.ERROR("IP non configuree"))
            return

        try:
            payload = {"id": 1, "method": "EM.GetStatus", "params": {"id": 0}}
            response = requests.post(
                f"http://{compteur.shelly_ip}/rpc", json=payload, timeout=10
            )

            if response.status_code != 200:
                raise Exception("Shelly ne repond pas")

            data = response.json().get('result', {})
            phase1_w      = float(data.get('a_act_power', 0) or 0)
            phase2_w      = float(data.get('b_act_power', 0) or 0)
            phase3_w      = float(data.get('c_act_power', 0) or 0)
            total_power_w = float(data.get('total_act_power', 0) or 0)

            try:
                payload_energy = {"id": 2, "method": "EMData.GetStatus", "params": {"id": 0}}
                r = requests.post(
                    f"http://{compteur.shelly_ip}/rpc", json=payload_energy, timeout=10
                )
                result_energy = r.json().get('result', {})
                energie_wh = result_energy.get('total_act', 0) or 0
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Erreur recuperation energie: {e}"))
                energie_wh = 0

            energie_kwh = float(energie_wh) / 1000

            self.stdout.write(self.style.SUCCESS("Shelly OK"))
            self.stdout.write(f"Total: {total_power_w} W | {energie_kwh:.3f} kWh")

            # ── Detection reset Shelly ────────────────────────────────────────
            if compteur.dernier_index_shelly is not None:
                if energie_kwh < float(compteur.dernier_index_shelly) - 1:
                    self.stdout.write(self.style.WARNING("Reset detecte"))
                    compteur.shelly_offset += compteur.dernier_index_shelly
                    compteur.date_reset_shelly = timezone.now()
                    self.stdout.write(f"Nouvel offset: {compteur.shelly_offset} kWh")

            # ── Mise a jour du compteur ───────────────────────────────────────
            compteur.shelly_status        = 'CONNECTE'
            compteur.dernier_index_shelly = Decimal(str(energie_kwh))
            compteur.index_actuel         = Decimal(str(float(compteur.index_initial) + energie_kwh))
            compteur.derniere_sync_shelly = timezone.now()

            compteur.save(update_fields=[
                'shelly_status',
                'dernier_index_shelly',
                'shelly_offset',
                'index_actuel',
                'date_reset_shelly',
                'derniere_sync_shelly',
            ])

            self.stdout.write(f"Index reel: {compteur.index_actuel} kWh")

            # ── Mise a jour du capteur ────────────────────────────────────────
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
                self.stdout.write("Capteur cree")

            capteur.puissance_instantanee  = Decimal(str(total_power_w))
            capteur.energie_totale         = Decimal(str(energie_kwh))
            capteur.derniere_communication = timezone.now()
            capteur.status                 = 'ACTIF'
            capteur.save()

            self.enregistrer_consommation(
                compteur, phase1_w, phase2_w, phase3_w, energie_kwh
            )

        except requests.exceptions.Timeout:
            self.stdout.write(self.style.ERROR("Timeout: Shelly injoignable"))
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])

        except requests.exceptions.ConnectionError:
            self.stdout.write(self.style.ERROR(f"Erreur connexion: {compteur.shelly_ip}"))
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erreur: {e}"))
            import traceback
            traceback.print_exc()
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])

    def enregistrer_consommation(self, compteur, phase1_w, phase2_w, phase3_w, energie_kwh):
        from apps.consommation.models import ConsommationJournaliere
        from django.db.models import Sum

        today = timezone.now().date()
        hier  = today - timedelta(days=1)

        # Index reel cumule = index_initial + energie mesure par Shelly
        index_actuel_reel = float(compteur.index_initial) + energie_kwh

        # ── Index de reference : fin d'HIER en priorite ───────────────────────
        conso_hier = Consommation.objects.filter(
            compteur=compteur,
            periode=hier,
        ).exclude(source='SHELLY_MENSUEL').first()

        if conso_hier:
            index_precedent = float(conso_hier.index_fin_periode)
            self.stdout.write(f"  Index precedent (hier {hier}): {index_precedent} kWh")
        else:
            # Fallback : derniere journee reelle disponible avant aujourd'hui
            derniere_conso = Consommation.objects.filter(
                compteur=compteur,
                periode__lt=today,
            ).exclude(source='SHELLY_MENSUEL').order_by('-periode').first()

            if derniere_conso:
                index_precedent = float(derniere_conso.index_fin_periode)
                self.stdout.write(
                    f"  Index precedent (derniere: {derniere_conso.periode}): {index_precedent} kWh"
                )
            else:
                index_precedent = float(compteur.index_initial)
                self.stdout.write(f"  Index initial: {index_precedent} kWh")

        # ── Consommation du jour ──────────────────────────────────────────────
        conso_jour_kwh = index_actuel_reel - index_precedent
        self.stdout.write(f"  Index actuel reel: {index_actuel_reel} kWh")
        self.stdout.write(f"  Consommation du jour: {conso_jour_kwh:.2f} kWh")

        # Sanity check : entre 0 et 100 kWh/jour
        if conso_jour_kwh < 0 or conso_jour_kwh > 100:
            self.stdout.write(self.style.WARNING("  Consommation incoherente, estimation utilisee"))
            conso_jour_kwh = (phase1_w + phase2_w + phase3_w) * 24 / 1000
            self.stdout.write(f"  Consommation estimee: {conso_jour_kwh:.2f} kWh")

        # ── Repartition par phase ─────────────────────────────────────────────
        total_w = phase1_w + phase2_w + phase3_w
        if total_w > 0:
            phase1_kwh = round((phase1_w / total_w) * conso_jour_kwh, 2)
            phase2_kwh = round((phase2_w / total_w) * conso_jour_kwh, 2)
            phase3_kwh = round((phase3_w / total_w) * conso_jour_kwh, 2)
        else:
            phase1_kwh = 0
            phase2_kwh = 0
            phase3_kwh = round(conso_jour_kwh, 2)

        # ── Enregistrement journalier dans Consommation (source=SHELLY) ───────
        conso, created = Consommation.objects.update_or_create(
            compteur=compteur,
            periode=today,
            defaults={
                'phase_1_kwh':         Decimal(str(phase1_kwh)),
                'phase_2_kwh':         Decimal(str(phase2_kwh)),
                'phase_3_kwh':         Decimal(str(phase3_kwh)),
                'index_debut_periode': Decimal(str(index_precedent)),
                'index_fin_periode':   Decimal(str(index_actuel_reel)),
                'statut':              'VALIDE',
                'source':              'SHELLY',
                'date_releve':         timezone.now(),
            }
        )
        status = "creee" if created else "mise a jour"
        self.stdout.write(
            self.style.SUCCESS(f"  Consommation {status} pour {today}: {conso_jour_kwh:.2f} kWh")
        )

        # ── Enregistrement dans ConsommationJournaliere ───────────────────────
        ConsommationJournaliere.objects.update_or_create(
            compteur=compteur,
            date=today,
            defaults={'consommation_kwh': Decimal(str(conso_jour_kwh))}
        )

        # ── Mise a jour de l'agregat mensuel (pour facturation) ───────────────
        self.mettre_a_jour_conso_mensuelle(compteur)

    def mettre_a_jour_conso_mensuelle(self, compteur):
        """
        Cree/met a jour UN enregistrement mensuel agrege (source='SHELLY_MENSUEL')
        sur la periode = 1er du mois en cours.

        Utilise par GenererFacturesView qui filtre sur source='SHELLY_MENSUEL'
        pour ne facturer qu'une seule fois par mois et par compteur.

        Regles :
          - Ne s'execute pas le 1er du mois (risque d'ecraser la journee reelle)
          - N'ecrase jamais une journee reelle (source='SHELLY') du 1er du mois
          - Somme les phases depuis les journees source='SHELLY' du mois
        """
        from apps.consommation.models import ConsommationJournaliere
        from django.db.models import Sum

        today         = timezone.now().date()
        current_month = today.replace(day=1)

        # Pas de mensuel le 1er du mois : la journee reelle et le mensuel
        # auraient la meme cle (compteur, periode) => conflit
        if today == current_month:
            self.stdout.write(
                f"  Mensuel {current_month.strftime('%b %Y')}: ignore (on est le 1er du mois)"
            )
            return

        # ── Calculer le total mensuel depuis les journees reelles ─────────────
        agg = Consommation.objects.filter(
            compteur=compteur,
            periode__year=today.year,
            periode__month=today.month,
            source='SHELLY',
        ).aggregate(
            p1=Sum('phase_1_kwh'),
            p2=Sum('phase_2_kwh'),
            p3=Sum('phase_3_kwh'),
        )

        phase1_total = Decimal(str(agg['p1'] or 0))
        phase2_total = Decimal(str(agg['p2'] or 0))
        phase3_total = Decimal(str(agg['p3'] or 0))
        total_mois   = phase1_total + phase2_total + phase3_total

        if total_mois == 0:
            self.stdout.write(
                f"  Mensuel {current_month.strftime('%b %Y')}: aucune donnee journaliere"
            )
            return

        # ── Index debut du mois = index_fin de la derniere journee du mois precedent ──
        mois_precedent_fin = current_month - timedelta(days=1)
        derniere_conso_prec = Consommation.objects.filter(
            compteur=compteur,
            periode__year=mois_precedent_fin.year,
            periode__month=mois_precedent_fin.month,
            source='SHELLY',
        ).order_by('-periode').first()

        if derniere_conso_prec:
            index_debut = Decimal(str(derniere_conso_prec.index_fin_periode))
        else:
            index_debut = Decimal(str(compteur.index_initial))

        index_fin = index_debut + total_mois

        # ── Verifier qu'aucune journee reelle n'existe pour le 1er du mois ────
        # (cas ou le 1er du mois a deja ete enregistre comme journee SHELLY)
        journee_du_1er = Consommation.objects.filter(
            compteur=compteur,
            periode=current_month,
            source='SHELLY',
        ).first()

        if journee_du_1er:
            # On ne peut pas ecraser — le mensuel sera calcule a la volee
            # par GenererFacturesView via aggregation directe
            self.stdout.write(
                f"  Mensuel {current_month.strftime('%b %Y')}: journee du 1er presente "
                f"(source=SHELLY), agregat = {total_mois:.2f} kWh (calcul a la volee)"
            )
            return

        # ── Creer/mettre a jour l'enregistrement mensuel ──────────────────────
        _, created = Consommation.objects.update_or_create(
            compteur=compteur,
            periode=current_month,
            defaults={
                'phase_1_kwh':         phase1_total,
                'phase_2_kwh':         phase2_total,
                'phase_3_kwh':         phase3_total,
                'index_debut_periode': index_debut,
                'index_fin_periode':   index_fin,
                'statut':              'VALIDE',
                'source':              'SHELLY_MENSUEL',
                'date_releve':         timezone.now(),
            }
        )
        action = "cree" if created else "mis a jour"
        self.stdout.write(
            self.style.SUCCESS(
                f"  Mensuel {current_month.strftime('%b %Y')} {action}: {total_mois:.2f} kWh"
            )
        )