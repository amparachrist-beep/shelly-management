from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal

User = get_user_model()


class Paiement(models.Model):
    MODE_PAIEMENT_CHOICES = (
        ('ESPECES', 'Espèces'),
        ('VIREMENT', 'Virement bancaire'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CARTE_BANCAIRE', 'Carte bancaire'),
        ('CHEQUE', 'Chèque'),
        ('AUTRE', 'Autre'),
    )

    STATUT_CHOICES = (
        ('EN_ATTENTE', 'En attente'),
        ('VALIDÉ', 'Validé'),
        ('REJETÉ', 'Rejeté'),
        ('ANNULE', 'Annulé'),
    )

    # Référence à la facture (maintenant FactureConsommation)
    facture = models.ForeignKey(
        'facturation.FactureConsommation',  # <-- Changé ici
        on_delete=models.CASCADE,
        related_name='paiements',
        verbose_name="Facture"
    )

    # Informations de paiement
    reference_paiement = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Référence paiement"
    )
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Montant"
    )
    mode_paiement = models.CharField(
        max_length=20,
        choices=MODE_PAIEMENT_CHOICES,
        verbose_name="Mode de paiement"
    )

    # Statut et validation
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='EN_ATTENTE',
        verbose_name="Statut"
    )
    date_paiement = models.DateTimeField(verbose_name="Date paiement")
    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date validation"
    )

    # Informations supplémentaires
    reference_externe = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence externe"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    # Fichier justificatif
    fichier_justificatif = models.FileField(
        upload_to='paiements/justificatifs/',
        null=True,
        blank=True,
        verbose_name="Fichier justificatif"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date modification")
    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='paiements_crees',
        verbose_name="Créé par"
    )
    valide_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paiements_valides',
        verbose_name="Validé par"
    )

    class Meta:
        db_table = 'paiement'
        app_label = 'paiements'  # <-- Ajouté ici
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-date_paiement']
        indexes = [
            models.Index(fields=['reference_paiement']),
            models.Index(fields=['statut']),
            models.Index(fields=['date_paiement']),
            models.Index(fields=['facture']),
        ]

    def __str__(self):
        return f"{self.reference_paiement} - {self.montant} FCFA"

    def save(self, *args, **kwargs):
        # Si le paiement est validé et que la date de validation n'est pas définie
        if self.statut == 'VALIDÉ' and not self.date_validation:
            from django.utils import timezone
            self.date_validation = timezone.now()

        # Si c'est un nouveau paiement et qu'aucune référence n'est définie
        if not self.reference_paiement and not self.pk:
            from datetime import datetime
            import uuid
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            unique_id = uuid.uuid4().hex[:8].upper()
            self.reference_paiement = f"PAY-{timestamp}-{unique_id}"

        super().save(*args, **kwargs)

        # Mettre à jour le montant payé sur la facture
        if self.statut == 'VALIDÉ':
            self.facture.montant_paye += self.montant
            self.facture.save()


class CommissionAgent(models.Model):
    """Commission des agents sur les paiements encaissés"""
    agent = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='commissions',
        verbose_name="Agent"
    )
    paiement = models.OneToOneField(
        Paiement,
        on_delete=models.CASCADE,
        related_name='commission',
        verbose_name="Paiement"
    )

    taux_commission = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name="Taux commission (%)"
    )
    montant_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant commission"
    )

    # Statut paiement commission
    STATUT_COMMISSION = (
        ('DUE', 'Due'),
        ('PAYEE', 'Payée'),
        ('ANNULEE', 'Annulée'),
    )
    statut = models.CharField(
        max_length=20,
        choices=STATUT_COMMISSION,
        default='DUE',
        verbose_name="Statut commission"
    )

    date_paiement_commission = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date paiement commission"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'commission_agent'
        app_label = 'paiements'  # <-- Ajouté ici
        verbose_name = 'Commission agent'
        verbose_name_plural = 'Commissions agents'
        indexes = [
            models.Index(fields=['agent']),
            models.Index(fields=['statut']),
        ]


class FraisTransaction(models.Model):
    """Frais associés aux transactions de paiement"""
    paiement = models.ForeignKey(
        Paiement,
        on_delete=models.CASCADE,
        related_name='frais',
        verbose_name="Paiement"
    )

    TYPE_FRAIS = (
        ('COMMISSION_BANCAIRE', 'Commission bancaire'),
        ('FRAIS_MOBILE_MONEY', 'Frais Mobile Money'),
        ('TAXE_GOUVERNEMENTALE', 'Taxe gouvernementale'),
        ('FRAIS_PLATEFORME', 'Frais plateforme'),
        ('AUTRE', 'Autre'),
    )

    type_frais = models.CharField(
        max_length=50,
        choices=TYPE_FRAIS,
        verbose_name="Type frais"
    )
    description = models.CharField(
        max_length=200,
        verbose_name="Description"
    )
    montant = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Montant"
    )

    facture_frais = models.FileField(
        upload_to='paiements/frais/',
        blank=True,
        null=True,
        verbose_name="Facture frais"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'frais_transaction'
        app_label = 'paiements'  # <-- Ajouté ici
        verbose_name = 'Frais transaction'
        verbose_name_plural = 'Frais transactions'


class HistoriqueStatutPaiement(models.Model):
    """Historique des changements de statut d'un paiement"""
    paiement = models.ForeignKey(
        Paiement,
        on_delete=models.CASCADE,
        related_name='historique_statuts',
        verbose_name="Paiement"
    )

    ancien_statut = models.CharField(max_length=20, verbose_name="Ancien statut")
    nouveau_statut = models.CharField(max_length=20, verbose_name="Nouveau statut")

    utilisateur = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Utilisateur"
    )

    raison = models.TextField(blank=True, verbose_name="Raison")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date changement")

    class Meta:
        db_table = 'historique_statut_paiement'
        app_label = 'paiements'  # <-- Déplacé et ajouté ici
        verbose_name = 'Historique statut paiement'
        verbose_name_plural = 'Historiques statut paiement'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['paiement']),
            models.Index(fields=['created_at']),
        ]