from django.db import models

# Create your models here.
# consommation/models.py
class Consommation(models.Model):
    SOURCE_CHOICES = (
        ('SHELLY_AUTO', 'Shelly automatique'),
        ('RELEVE_MANUEL', 'Relevé manuel'),
        ('ESTIMATION', 'Estimation'),
        ('CORRIGE', 'Corrigé'),
    )

    STATUT_CHOICES = (
        ('BROUILLON', 'Brouillon'),
        ('VALIDÉ', 'Validé'),
        ('FACTURÉ', 'Facturé'),
        ('ANOMALIE', 'Anomalie'),
    )

    compteur = models.ForeignKey('compteurs.Compteur', on_delete=models.CASCADE, related_name='consommations')
    periode = models.DateField()  # Premier jour du mois (YYYY-MM-01)

    # Index de consommation
    index_debut_periode = models.DecimalField(max_digits=12, decimal_places=2)
    index_fin_periode = models.DecimalField(max_digits=12, decimal_places=2)

    # Champ calculé
    @property
    def consommation_kwh(self):
        """Calcule la consommation totale à partir des phases"""
        return (self.phase_1_kwh or 0) + (self.phase_2_kwh or 0) + (self.phase_3_kwh or 0)

    # Détails par phase
    phase_1_kwh = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    phase_2_kwh = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    phase_3_kwh = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Données techniques
    puissance_max_kw = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    puissance_moyenne_kw = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    facture_charge = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    # Données journalières
    details_journaliers = models.JSONField(null=True, blank=True)

    # Source
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='SHELLY_AUTO')
    shelly_device_id = models.CharField(max_length=100, blank=True)

    # État
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    anomalie = models.TextField(blank=True)
    notes = models.TextField(blank=True, verbose_name="Notes")  # ← NOUVEAU CHAMP
    # Horodatage
    date_releve = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'consommation'
        constraints = [
            models.UniqueConstraint(
                fields=['compteur', 'periode'],
                name='uk_consommation_compteur_periode'
            )
        ]
        indexes = [
            models.Index(fields=['periode']),
            models.Index(fields=['statut']),
            models.Index(fields=['source']),
            models.Index(fields=['compteur', 'periode']),
        ]


    app_label = 'consommation'
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ConsommationQuotidienne(models.Model):
    """Détails journaliers de consommation"""
    consommation = models.ForeignKey(
        Consommation,
        on_delete=models.CASCADE,
        related_name='details_quotidiens'
    )
    date = models.DateField()
    consommation_kwh = models.DecimalField(max_digits=10, decimal_places=2)
    puissance_max_kw = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    puissance_moyenne_kw = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    heures_pleines = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    heures_creuses = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'consommation_quotidienne'
        verbose_name = 'Consommation quotidienne'
        verbose_name_plural = 'Consommations quotidiennes'
        unique_together = ['consommation', 'date']
        indexes = [
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.date} - {self.consommation_kwh} kWh"


    app_label = 'consommation'
class HistoriqueConsommation(models.Model):
    """Historique des modifications de consommation"""
    ACTION_CHOICES = (
        ('CREATE', 'Création'),
        ('UPDATE', 'Modification'),
        ('VALIDATE', 'Validation'),
        ('CORRECT', 'Correction'),
        ('MARK_ANOMALY', 'Marquage anomalie'),
    )

    consommation = models.ForeignKey(
        Consommation,
        on_delete=models.CASCADE,
        related_name='historique'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    utilisateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    ancienne_valeur = models.JSONField(null=True, blank=True)
    nouvelle_valeur = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historique_consommation'
        verbose_name = 'Historique consommation'
        verbose_name_plural = 'Historiques consommation'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.consommation} - {self.action} par {self.utilisateur}"


    app_label = 'consommation'
class AnomalieConsommation(models.Model):
    """Anomalies détectées dans les consommations"""
    TYPES_ANOMALIE = (
        ('CONSO_ABERRANTE', 'Consommation aberrante'),
        ('INDEX_NEGATIF', 'Index négatif'),
        ('DOUBLON', 'Doublon détecté'),
        ('ECART_IMPORTANT', 'Écart important avec période précédente'),
        ('FORMAT_INVALIDE', 'Format de données invalide'),
    )

    consommation = models.OneToOneField(
        Consommation,
        on_delete=models.CASCADE,
        related_name='anomalie_detail'
    )
    type_anomalie = models.CharField(max_length=50, choices=TYPES_ANOMALIE)
    severite = models.CharField(max_length=20, choices=(
        ('FAIBLE', 'Faible'),
        ('MOYENNE', 'Moyenne'),
        ('HAUTE', 'Haute'),
        ('CRITIQUE', 'Critique'),
    ))
    description = models.TextField()
    donnees_analysees = models.JSONField()
    detectee_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date_detection = models.DateTimeField(auto_now_add=True)
    resolue = models.BooleanField(default=False)
    date_resolution = models.DateTimeField(null=True, blank=True)
    resolu_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='anomalies_resolues')
    resolution_notes = models.TextField(blank=True)

    class Meta:
        db_table = 'anomalie_consommation'
        verbose_name = 'Anomalie consommation'
        verbose_name_plural = 'Anomalies consommation'
        ordering = ['-date_detection']

    def __str__(self):
        return f"Anomalie {self.get_type_anomalie_display()} - {self.consommation}"


    app_label = 'consommation'
# Ajoutez cette classe à la fin de consommation/models.py

class ConsommationJournaliere(models.Model):
    """Consommation quotidienne pour suivi détaillé"""
    compteur = models.ForeignKey(
        'compteurs.Compteur',
        on_delete=models.CASCADE,
        related_name='consommations_journalieres',
        verbose_name="Compteur"
    )
    date = models.DateField(verbose_name="Date")
    consommation_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Consommation (kWh)"
    )
    puissance_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Puissance max (W)"
    )

    # Source des données
    source = models.CharField(
        max_length=50,
        choices=[
            ('SHELLY', 'Capteur Shelly'),
            ('ESTIMATION', 'Estimation'),
            ('MANUEL', 'Saisie manuelle'),
        ],
        default='SHELLY',
        verbose_name="Source"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date modification")

    class Meta:
        db_table = 'consommation_journaliere'
        verbose_name = 'Consommation journalière'
        verbose_name_plural = 'Consommations journalières'
        ordering = ['-date']
        unique_together = ['compteur', 'date']
        indexes = [
            models.Index(fields=['compteur', 'date']),
            models.Index(fields=['date']),
        ]

    def __str__(self):
        return f"{self.date} - {self.compteur.numero_serie}: {self.consommation_kwh} kWh"
    app_label = 'consommation'
    app_label = 'consommation'