# apps/alertes/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from decimal import Decimal

from apps.consommation.models import Consommation
from apps.compteurs.models import Compteur
from apps.facturation.models import FactureConsommation
from .models import Alerte, RegleAlerte


@receiver(post_save, sender=Consommation)
def verifier_consommation_anormale(sender, instance, created, **kwargs):
    """
    Vérifie automatiquement si une consommation dépasse les seuils
    Déclenché en temps réel lors de la création d'une consommation
    """
    if not created:
        return

    regles = RegleAlerte.objects.filter(
        type_alerte__in=['CONSOMMATION_ANORMALE', 'PIC_DE_CONSOMMATION', 'CONSOMMATION_NULLE'],
        actif=True
    )

    for regle in regles:
        valeur = instance.consommation_kwh

        if regle.type_alerte == 'CONSOMMATION_ANORMALE' and valeur > regle.seuil:
            Alerte.objects.create(
                consommation=instance,
                compteur=instance.compteur,
                type_alerte='CONSOMMATION_ANORMALE',
                message=f"Consommation anormale: {valeur} kWh (seuil: {regle.seuil} kWh)",
                niveau='WARNING' if valeur < regle.seuil * 2 else 'CRITIQUE',
                valeur_mesuree=valeur,
                valeur_seuil=regle.seuil,
                unite='kWh',
                destinataire_role='CLIENT',
                utilisateur=instance.compteur.menage.utilisateur,
                statut='ACTIVE'
            )
            break

        elif regle.type_alerte == 'PIC_DE_CONSOMMATION' and valeur > regle.seuil:
            Alerte.objects.create(
                consommation=instance,
                compteur=instance.compteur,
                type_alerte='PIC_DE_CONSOMMATION',
                message=f"Pic de consommation: {valeur} kWh (seuil: {regle.seuil} kWh)",
                niveau='WARNING',
                valeur_mesuree=valeur,
                valeur_seuil=regle.seuil,
                unite='kWh',
                destinataire_role='CLIENT',
                utilisateur=instance.compteur.menage.utilisateur,
                statut='ACTIVE'
            )
            break

        elif regle.type_alerte == 'CONSOMMATION_NULLE' and valeur == 0:
            Alerte.objects.create(
                consommation=instance,
                compteur=instance.compteur,
                type_alerte='CONSOMMATION_NULLE',
                message="Consommation nulle détectée. Vérifiez le compteur.",
                niveau='INFO',
                valeur_mesuree=valeur,
                valeur_seuil=regle.seuil,
                unite='kWh',
                destinataire_role='AGENT',
                statut='ACTIVE'
            )
            break


@receiver(post_save, sender=Compteur)
def verifier_capteur_deconnecte(sender, instance, created, **kwargs):
    """
    Vérifie si le capteur est déconnecté lors de la mise à jour du compteur
    ✅ CORRIGÉ: utilise derniere_sync_shelly au lieu de shelly_last_seen
    """
    if created:
        return

    # Vérifier si le capteur est déconnecté depuis plus d'une heure
    if instance.shelly_status == 'CONNECTE' and instance.derniere_sync_shelly:
        date_limite = timezone.now() - timezone.timedelta(hours=1)

        if instance.derniere_sync_shelly < date_limite:
            # Vérifier si une alerte existe déjà
            alerte_existante = Alerte.objects.filter(
                compteur=instance,
                type_alerte='CAPTEUR_DECONNECTE',
                statut__in=['ACTIVE', 'LU']
            ).exists()

            if not alerte_existante:
                Alerte.objects.create(
                    compteur=instance,
                    type_alerte='CAPTEUR_DECONNECTE',
                    message=f"Capteur déconnecté depuis plus d'une heure. Dernière connexion: {instance.derniere_sync_shelly}",
                    niveau='WARNING',
                    destinataire_role='AGENT',
                    statut='ACTIVE'
                )


@receiver(post_save, sender=FactureConsommation)
def verifier_paiement_retard(sender, instance, created, **kwargs):
    """
    Vérifie si une facture est en retard lors de sa création ou mise à jour
    """
    today = timezone.now().date()

    if instance.statut in ['ÉMISE', 'PARTIELLEMENT_PAYÉE'] and instance.date_echeance < today:
        alerte_existante = Alerte.objects.filter(
            compteur=instance.compteur,
            type_alerte='PAIEMENT_EN_RETARD',
            statut__in=['ACTIVE', 'LU']
        ).exists()

        if not alerte_existante:
            jours_retard = (today - instance.date_echeance).days
            niveau = 'CRITIQUE' if jours_retard > 30 else 'WARNING'

            Alerte.objects.create(
                compteur=instance.compteur,
                type_alerte='PAIEMENT_EN_RETARD',
                message=f"Paiement en retard de {jours_retard} jours pour la facture {instance.numero_facture}",
                niveau=niveau,
                valeur_mesuree=instance.solde_du,
                unite='FCFA',
                destinataire_role='CLIENT',
                utilisateur=instance.compteur.menage.utilisateur,
                statut='ACTIVE'
            )