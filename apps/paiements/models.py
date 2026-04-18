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

