# apps/dashboard/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from apps.alertes.models import Alerte
from apps.facturation.models import Facture
from apps.paiements.models import Paiement
from .models import DashboardNotification
from .utils import create_notification


@receiver(post_save, sender=Alerte)
def alerte_vers_notification(sender, instance, created, **kwargs):
    """
    🔔 Transforme une alerte en notification dashboard
    Cette fonction est appelée automatiquement quand une alerte est créée
    """
    if created and instance.statut == 'ACTIVE':
        print(f"🔄 Traitement de l'alerte #{instance.id}: {instance.type_alerte}")

        # 1. Déterminer le type de notification et l'icône
        notification_type = 'ALERT'
        icon = 'bell'

        # 2. Déterminer la priorité en fonction du niveau
        priority_map = {
            'INFO': 0,  # Normal
            'WARNING': 1,  # Important
            'CRITIQUE': 2  # Urgent
        }
        priority = priority_map.get(instance.niveau, 0)

        # 3. Déterminer l'utilisateur destinataire
        users_to_notify = []

        if instance.destinataire_role == 'CLIENT':
            # Client spécifique
            if instance.utilisateur:
                users_to_notify.append(instance.utilisateur)
            else:
                # Sinon, l'utilisateur propriétaire du compteur
                users_to_notify.append(instance.compteur.menage.utilisateur)

        elif instance.destinataire_role == 'AGENT':
            # Tous les agents
            from apps.users.models import CustomUser
            agents = CustomUser.objects.filter(role='AGENT_TERRAIN')
            users_to_notify.extend(agents)

        elif instance.destinataire_role == 'ADMIN':
            # Tous les administrateurs
            from apps.users.models import CustomUser
            admins = CustomUser.objects.filter(role='ADMIN')
            users_to_notify.extend(admins)

        # 4. Créer une notification pour chaque destinataire
        for user in users_to_notify:
            if user:
                # Générer le titre selon le type d'alerte
                titles = {
                    'CONSOMMATION_ANORMALE': '⚠️ Consommation anormale détectée',
                    'CONSOMMATION_NULLE': '📉 Consommation nulle',
                    'PIC_DE_CONSOMMATION': '⚡ Pic de consommation',
                    'CAPTEUR_DECONNECTE': '🔌 Capteur déconnecté',
                    'PAIEMENT_EN_RETARD': '💰 Paiement en retard',
                    'ANOMALIE_TECHNIQUE': '🔧 Anomalie technique',
                    'DEPASSEMENT_PUISSANCE': '📊 Dépassement de puissance'
                }
                title = titles.get(instance.type_alerte, f'Alerte: {instance.type_alerte}')

                # Personnaliser le message
                message = instance.message
                if instance.valeur_mesuree and instance.valeur_seuil:
                    message += f" (Valeur: {instance.valeur_mesuree} {instance.unite} | Seuil: {instance.valeur_seuil} {instance.unite})"

                # Créer la notification
                create_notification(
                    user=user,
                    title=title,
                    message=message,
                    notification_type=notification_type,
                    icon=icon,
                    priority=priority,
                    action_url=f'/alertes/{instance.id}/',
                    action_label='Voir l\'alerte',
                    source_module='alertes',
                    source_id=str(instance.id),
                    # Données supplémentaires
                    data={
                        'alerte_id': instance.id,
                        'type_alerte': instance.type_alerte,
                        'niveau': instance.niveau,
                        'valeur_mesuree': str(instance.valeur_mesuree) if instance.valeur_mesuree else None,
                        'valeur_seuil': str(instance.valeur_seuil) if instance.valeur_seuil else None,
                        'compteur_id': instance.compteur.id,
                        'compteur_numero': instance.compteur.numero_serie
                    }
                )
                print(f"✅ Notification créée pour {user.email}: {title}")

        # 5. Mettre à jour l'alerte avec le nombre de notifications créées
        instance.notifications_count = len(users_to_notify)
        # Note: Vous pouvez ajouter un champ dans Alerte pour suivre les notifications


@receiver(post_save, sender=Facture)
def facture_vers_notification(sender, instance, created, **kwargs):
    """Créer une notification lors de l'émission d'une facture"""
    if created and instance.statut == 'ÉMISE':
        create_notification(
            user=instance.compteur.menage.utilisateur,
            title='📄 Nouvelle facture disponible',
            message=f'Votre facture de {instance.periode.strftime("%B %Y")} est disponible. Montant: {instance.total_ttc} FCFA',
            notification_type='INFO',
            priority=1,
            action_url=f'/facturation/factures/{instance.id}/',
            action_label='Voir ma facture',
            source_module='facturation',
            source_id=str(instance.id)
        )


@receiver(post_save, sender=Paiement)
def paiement_vers_notification(sender, instance, created, **kwargs):
    """Créer une notification lors de la confirmation d'un paiement"""
    if created and instance.statut == 'CONFIRMÉ':
        create_notification(
            user=instance.facture.compteur.menage.utilisateur,
            title='✅ Paiement confirmé',
            message=f'Votre paiement de {instance.montant} FCFA a été confirmé.',
            notification_type='SUCCESS',
            priority=0,
            action_url=f'/facturation/factures/{instance.facture.id}/',
            action_label='Voir le détail',
            source_module='paiements',
            source_id=str(instance.id)
        )