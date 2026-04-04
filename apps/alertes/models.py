from django.db import models

# =============================================
# Modèles Alertes et Règles d’Alertes
# =============================================

class Alerte(models.Model):
    TYPE_ALERTE = (
        ('CONSOMMATION_ANORMALE', 'Consommation anormale'),
        ('CONSOMMATION_NULLE', 'Consommation nulle'),
        ('PIC_DE_CONSOMMATION', 'Pic de consommation'),
        ('CAPTEUR_DECONNECTE', 'Capteur déconnecté'),
        ('PAIEMENT_EN_RETARD', 'Paiement en retard'),
        ('ANOMALIE_TECHNIQUE', 'Anomalie technique'),
        ('DEPASSEMENT_PUISSANCE', 'Dépassement puissance'),
    )

    NIVEAU_CHOICES = (
        ('INFO', 'Information'),
        ('WARNING', 'Avertissement'),
        ('CRITIQUE', 'Critique'),
    )

    STATUT_CHOICES = (
        ('ACTIVE', 'Active'),
        ('LU', 'Lue'),
        ('TRAITEE', 'Traitée'),
        ('IGNOREE', 'Ignorée'),
    )

    DESTINATAIRE_CHOICES = (
        ('ADMIN', 'Administrateur'),
        ('AGENT', 'Agent'),
        ('CLIENT', 'Client'),
    )

    # Références
    consommation = models.ForeignKey(
        'consommation.Consommation',
        on_delete=models.CASCADE,
        related_name='alertes'
    )
    compteur = models.ForeignKey(
        'compteurs.Compteur',
        on_delete=models.CASCADE
    )

    # Détails alerte
    type_alerte = models.CharField(max_length=50, choices=TYPE_ALERTE)
    message = models.TextField()
    niveau = models.CharField(max_length=20, choices=NIVEAU_CHOICES, default='WARNING')
    valeur_mesuree = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    valeur_seuil = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    unite = models.CharField(max_length=20, blank=True)
    notifications_count = models.IntegerField(default=0, verbose_name="Nombre de notifications")

    # Destinataires
    destinataire_role = models.CharField(max_length=20, choices=DESTINATAIRE_CHOICES)
    utilisateur = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    # Statut traitement
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIVE')
    traite_par = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alertes_traitees'
    )
    notes_traitement = models.TextField(blank=True)

    # Horodatage
    date_detection = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'alerte'
        indexes = [
            models.Index(fields=['statut']),
            models.Index(fields=['type_alerte']),
            models.Index(fields=['date_detection']),
            models.Index(fields=['consommation']),
            models.Index(fields=['compteur', 'statut']),
        ]

    def __str__(self):
        return f"{self.type_alerte} - {self.compteur} ({self.statut})"


    app_label = 'alertes'
class RegleAlerte(models.Model):
    """
    Règle pour générer des alertes automatiques
    """
    TYPE_ALERTE = Alerte.TYPE_ALERTE  # référence propre

    nom = models.CharField(max_length=100)
    type_alerte = models.CharField(max_length=50, choices=TYPE_ALERTE)
    seuil = models.DecimalField(max_digits=12, decimal_places=2)
    actif = models.BooleanField(default=True)

    class Meta:
        db_table = 'regle_alerte'

    def __str__(self):
        return f"{self.nom} ({self.type_alerte})"

    app_label = 'alertes'