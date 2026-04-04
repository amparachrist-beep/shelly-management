# apps/dashboard/management/commands/check_notifications.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.facturation.models import Facture
from apps.alertes.models import Alerte
from apps.dashboard.utils import create_notification


class Command(BaseCommand):
    help = 'Vérifie et envoie les notifications programmées'

    def handle(self, *args, **options):
        self.stdout.write('🔔 Vérification des notifications programmées...')

        # 1. Rappels de paiement
        self.check_invoice_reminders()

        # 2. Alertes de consommation élevée (vérifier les consommations)
        self.check_high_consumption()

        self.stdout.write(self.style.SUCCESS('✅ Notifications envoyées'))

    def check_invoice_reminders(self):
        """Vérifie les factures à échéance"""
        today = timezone.now().date()

        # Factures arrivant à échéance dans 3 jours
        upcoming = Facture.objects.filter(
            statut__in=['ÉMISE', 'PARTIELLEMENT_PAYÉE'],
            date_echeance=today + timedelta(days=3)
        )

        for facture in upcoming:
            create_notification(
                user=facture.compteur.menage.utilisateur,
                title='⏰ Rappel: Échéance approche',
                message=f'Votre facture arrive à échéance dans 3 jours. Montant: {facture.solde_du} FCFA',
                notification_type='WARNING',
                priority=1,
                action_url=f'/paiements/effectuer/?facture={facture.id}',
                action_label='Payer maintenant',
                source_module='facturation',
                source_id=str(facture.id)
            )

        if upcoming.exists():
            self.stdout.write(f"📨 Rappels envoyés pour {upcoming.count()} factures")

        # Factures en retard
        overdue = Facture.objects.filter(
            statut__in=['ÉMISE', 'PARTIELLEMENT_PAYÉE'],
            date_echeance__lt=today
        )

        for facture in overdue:
            # Vérifier si déjà notifié cette semaine
            from apps.dashboard.models import DashboardNotification
            last_notification = DashboardNotification.objects.filter(
                user=facture.compteur.menage.utilisateur,
                source_module='facturation',
                source_id=str(facture.id),
                created_at__gte=today - timedelta(days=7)
            ).exists()

            if not last_notification:
                create_notification(
                    user=facture.compteur.menage.utilisateur,
                    title='⚠️ Facture en retard',
                    message=f'Votre facture est en retard de {(today - facture.date_echeance).days} jours. Montant: {facture.solde_du} FCFA',
                    notification_type='ERROR',
                    priority=2,
                    action_url=f'/paiements/effectuer/?facture={facture.id}',
                    action_label='Régulariser',
                    source_module='facturation',
                    source_id=str(facture.id)
                )

        if overdue.exists():
            self.stdout.write(f"⚠️ Rappels envoyés pour {overdue.count()} factures en retard")

    def check_high_consumption(self):
        """Vérifie les consommations anormales"""
        # À implémenter selon votre logique métier
        pass