# apps/alertes/management/commands/detecter_alertes.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from apps.alertes.models import Alerte, RegleAlerte
from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation
from apps.facturation.models import FactureConsommation


class Command(BaseCommand):
    help = 'Détecte automatiquement les anomalies (à exécuter par cron)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['all', 'capteurs', 'consommation', 'paiements', 'technique'],
            default='all',
            help='Type de détection à exécuter'
        )

    def handle(self, *args, **options):
        detection_type = options['type']

        self.stdout.write(f'🔍 Détection automatique des anomalies ({detection_type})...')

        alertes_creees = 0

        # 1. DÉTECTION DES CAPTEURS DÉCONNECTÉS
        if detection_type in ['all', 'capteurs']:
            alertes_creees += self.detecter_capteurs_deconnectes()

        # 2. DÉTECTION DES PAIEMENTS EN RETARD
        if detection_type in ['all', 'paiements']:
            alertes_creees += self.detecter_paiements_retard()

        # 3. DÉTECTION DES CONSOMMATIONS ANORMALES
        if detection_type in ['all', 'consommation']:
            alertes_creees += self.detecter_consommations_anormales()

        # 4. DÉTECTION DES DÉPASSEMENTS DE PUISSANCE
        if detection_type in ['all', 'consommation']:
            alertes_creees += self.detecter_depassements_puissance()

        # 5. DÉTECTION DES ANOMALIES TECHNIQUES
        if detection_type in ['all', 'technique']:
            alertes_creees += self.detecter_anomalies_techniques()

        # Résumé
        if alertes_creees > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Détection terminée : {alertes_creees} alerte(s) créée(s)')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Détection terminée : aucune nouvelle anomalie détectée')
            )

    def detecter_capteurs_deconnectes(self):
        """Détecte les capteurs déconnectés depuis plus d'une heure"""
        alertes_creees = 0
        date_limite = timezone.now() - timedelta(hours=1)

        compteurs_deconnectes = Compteur.objects.filter(
            shelly_status='CONNECTE',
            shelly_last_seen__lt=date_limite
        ).exclude(
            alertes__type_alerte='CAPTEUR_DECONNECTE',
            alertes__statut__in=['ACTIVE', 'LU']
        )

        for compteur in compteurs_deconnectes:
            alerte, created = Alerte.objects.get_or_create(
                compteur=compteur,
                type_alerte='CAPTEUR_DECONNECTE',
                defaults={
                    'message': f"Capteur déconnecté depuis plus d'une heure. Dernière connexion: {compteur.shelly_last_seen}",
                    'niveau': 'WARNING',
                    'destinataire_role': 'AGENT',
                    'statut': 'ACTIVE'
                }
            )
            if created:
                alertes_creees += 1
                self.stdout.write(f"  ⚠️ Alerte créée: Capteur déconnecté - {compteur.numero_contrat}")

        return alertes_creees

    def detecter_paiements_retard(self):
        """Détecte les factures impayées en retard"""
        alertes_creees = 0
        today = timezone.now().date()

        factures_retard = FactureConsommation.objects.filter(
            statut__in=['ÉMISE', 'PARTIELLEMENT_PAYÉE'],
            date_echeance__lt=today
        ).exclude(
            alertes__type_alerte='PAIEMENT_EN_RETARD',
            alertes__statut__in=['ACTIVE', 'LU']
        )

        for facture in factures_retard:
            jours_retard = (today - facture.date_echeance).days
            niveau = 'CRITIQUE' if jours_retard > 30 else 'WARNING'

            alerte, created = Alerte.objects.get_or_create(
                compteur=facture.compteur,
                type_alerte='PAIEMENT_EN_RETARD',
                defaults={
                    'message': f"Paiement en retard de {jours_retard} jours pour la facture {facture.numero_facture}",
                    'niveau': niveau,
                    'valeur_mesuree': facture.solde_du,
                    'unite': 'FCFA',
                    'destinataire_role': 'CLIENT',
                    'utilisateur': facture.compteur.menage.utilisateur,
                    'statut': 'ACTIVE'
                }
            )
            if created:
                alertes_creees += 1
                self.stdout.write(f"  💰 Alerte créée: Paiement en retard - {facture.numero_facture}")

        return alertes_creees

    def detecter_consommations_anormales(self):
        """Détecte les consommations anormales basées sur les règles"""
        alertes_creees = 0

        regles = RegleAlerte.objects.filter(
            type_alerte__in=['CONSOMMATION_ANORMALE', 'CONSOMMATION_NULLE'],
            actif=True
        )

        date_limite = timezone.now() - timedelta(days=30)
        consommations = Consommation.objects.filter(
            periode__gte=date_limite,
            statut='VALIDÉ'
        ).exclude(
            alertes__type_alerte__in=['CONSOMMATION_ANORMALE', 'CONSOMMATION_NULLE']
        )

        for consommation in consommations:
            total_kwh = consommation.consommation_kwh

            # Consommation nulle
            if total_kwh == 0:
                Alerte.objects.create(
                    consommation=consommation,
                    compteur=consommation.compteur,
                    type_alerte='CONSOMMATION_NULLE',
                    message="Consommation nulle détectée. Vérifiez le compteur.",
                    niveau='INFO',
                    valeur_mesuree=total_kwh,
                    unite='kWh',
                    destinataire_role='AGENT',
                    statut='ACTIVE'
                )
                alertes_creees += 1
                self.stdout.write(f"  📊 Alerte créée: Consommation nulle - {consommation.compteur.numero_contrat}")
                continue

            # Consommation anormale (selon les règles)
            for regle in regles:
                if regle.type_alerte == 'CONSOMMATION_ANORMALE' and total_kwh > regle.seuil:
                    Alerte.objects.create(
                        consommation=consommation,
                        compteur=consommation.compteur,
                        type_alerte='CONSOMMATION_ANORMALE',
                        message=f"Consommation anormale: {total_kwh} kWh (seuil: {regle.seuil} kWh)",
                        niveau='WARNING' if total_kwh < regle.seuil * 2 else 'CRITIQUE',
                        valeur_mesuree=total_kwh,
                        valeur_seuil=regle.seuil,
                        unite='kWh',
                        destinataire_role='CLIENT',
                        utilisateur=consommation.compteur.menage.utilisateur,
                        statut='ACTIVE'
                    )
                    alertes_creees += 1
                    self.stdout.write(
                        f"  ⚡ Alerte créée: Consommation anormale - {consommation.compteur.numero_contrat}")
                    break

        return alertes_creees

    def detecter_depassements_puissance(self):
        """Détecte les dépassements de puissance souscrite"""
        alertes_creees = 0

        regles = RegleAlerte.objects.filter(
            type_alerte='DEPASSEMENT_PUISSANCE',
            actif=True
        )

        date_limite = timezone.now() - timedelta(days=7)
        consommations = Consommation.objects.filter(
            date_releve__gte=date_limite,
            puissance_max_kw__isnull=False
        ).exclude(
            alertes__type_alerte='DEPASSEMENT_PUISSANCE'
        )

        for consommation in consommations:
            for regle in regles:
                if consommation.puissance_max_kw > regle.seuil:
                    Alerte.objects.create(
                        consommation=consommation,
                        compteur=consommation.compteur,
                        type_alerte='DEPASSEMENT_PUISSANCE',
                        message=f"Dépassement de puissance: {consommation.puissance_max_kw} kW (seuil: {regle.seuil} kW)",
                        niveau='WARNING',
                        valeur_mesuree=consommation.puissance_max_kw,
                        valeur_seuil=regle.seuil,
                        unite='kW',
                        destinataire_role='CLIENT',
                        utilisateur=consommation.compteur.menage.utilisateur,
                        statut='ACTIVE'
                    )
                    alertes_creees += 1
                    self.stdout.write(
                        f"  ⚠️ Alerte créée: Dépassement puissance - {consommation.compteur.numero_contrat}")
                    break

        return alertes_creees

    def detecter_anomalies_techniques(self):
        """Détecte les anomalies techniques"""
        alertes_creees = 0

        # Compteurs avec index négatif
        compteurs_negatifs = Compteur.objects.filter(
            index_actuel__lt=0
        ).exclude(
            alertes__type_alerte='ANOMALIE_TECHNIQUE'
        )

        for compteur in compteurs_negatifs:
            Alerte.objects.create(
                compteur=compteur,
                type_alerte='ANOMALIE_TECHNIQUE',
                message=f"Anomalie technique: index actuel négatif ({compteur.index_actuel})",
                niveau='CRITIQUE',
                valeur_mesuree=compteur.index_actuel,
                destinataire_role='ADMIN',
                statut='ACTIVE'
            )
            alertes_creees += 1
            self.stdout.write(f"  🔧 Alerte créée: Anomalie technique - {compteur.numero_contrat}")

        return alertes_creees