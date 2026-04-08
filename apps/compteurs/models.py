from django.db import models

# Create your models here.
# compteurs/models.py
# Dans apps/compteurs/models.py

from django.db import models # J'ai corrigé l'import pour un modèle standard, mais gardez le vôtre si nécessaire

class Compteur(models.Model):
    # Le tuple TYPE_COMPTEUR a été supprimé car les types sont maintenant gérés
    # dans le modèle 'TypeCompteur' de cette même application.

    TENSION_CHOICES = (
        ('BT_220V', 'BT 220V'),
        ('BT_380V', 'BT 380V'),
        ('MT', 'Moyenne Tension'),
        ('HT', 'Haute Tension'),
    )

    PHASE_CHOICES = (
        ('MONOPHASE', 'Monophasé'),
        ('TRIPHASE', 'Triphasé'),
    )

    STATUT_CHOICES = (
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
        ('SUSPENDU', 'Suspendu'),
        ('COUPE', 'Coupé'),
        ('RESILIE', 'Résilié'),
        ('EN_PANNE', 'En panne'),
    )

    # Identification unique
    numero_contrat = models.CharField(max_length=30, unique=True)
    matricule_compteur = models.CharField(max_length=30, unique=True)
    numero_client = models.CharField(max_length=20, blank=True)

    # Références
    menage = models.ForeignKey('menages.Menage', on_delete=models.CASCADE, related_name='compteurs')
    type_tarification = models.ForeignKey('parametrage.TypeTarification', on_delete=models.PROTECT)
    localite = models.ForeignKey('parametrage.Localite', on_delete=models.PROTECT)

    # Caractéristiques techniques
    # Champ modifié : ForeignKey vers la table TypeCompteur
    type_compteur_detail = models.ForeignKey(
        'TypeCompteur',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='compteurs',
        help_text="Type de compteur détaillé"
    )
    puissance_souscrite = models.DecimalField(max_digits=8, decimal_places=2)  # kVA
    tension = models.CharField(max_length=20, choices=TENSION_CHOICES, default='BT_220V')
    phase = models.CharField(max_length=20, choices=PHASE_CHOICES, default='MONOPHASE')

    # Localisation précise
    adresse_installation = models.TextField(blank=True)
    gps_latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    gps_longitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    reference_local = models.CharField(max_length=100, blank=True)

    # Informations contrat
    date_installation = models.DateField()
    date_debut_contrat = models.DateField()
    date_fin_contrat = models.DateField(null=True, blank=True)

    PERIODE_FACTURATION = (
        ('MENSUEL', 'Mensuel'),
        ('BIMENSUEL', 'Bimensuel'),
    )
    periode_facturation = models.CharField(max_length=20, choices=PERIODE_FACTURATION, default='MENSUEL')
    jour_releve = models.IntegerField(default=25)  # Jour du mois
    jour_paiement = models.IntegerField(default=10)

    # État
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF')
    index_initial = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    index_actuel = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Capteur Shelly EM
    shelly_device_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    shelly_ip = models.GenericIPAddressField(blank=True, null=True)

    SHELLY_STATUS = (
        ('CONNECTE', 'Connecté'),
        ('DECONNECTE', 'Déconnecté'),
        ('ERREUR', 'Erreur'),
    )
    shelly_status = models.CharField(max_length=20, choices=SHELLY_STATUS, default='DECONNECTE')
    derniere_sync_shelly = models.DateTimeField(null=True, blank=True)
    # Gestion avancée Shelly (IMPORTANT)
    # Gestion avancée Shelly (IMPORTANT)
    shelly_offset = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0.000
    )

    dernier_index_shelly = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True
    )

    date_reset_shelly = models.DateTimeField(
        null=True,
        blank=True
    )
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compteur'
        indexes = [
            models.Index(fields=['numero_contrat']),
            models.Index(fields=['matricule_compteur']),
            models.Index(fields=['statut']),
            models.Index(fields=['menage']),
            models.Index(fields=['shelly_status']),
        ]

    def __str__(self):
        return f"{self.numero_contrat} - {self.matricule_compteur}"

    app_label = 'compteurs'


class TypeCompteur(models.Model):
    """Types de compteurs électriques disponibles au Congo-Brazzaville"""

    TECHNOLOGIE_CHOICES = (
        ('ELECTRONIQUE', 'Électronique'),
        ('MECANIQUE', 'Mécanique'),
        ('INTELLIGENT', 'Intelligent (Smart Meter)'),
        ('PREPAYE', 'Prépayé'),
        ('HYBRIDE', 'Hybride'),
    )

    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    marque = models.CharField(max_length=50, blank=True, null=True)
    modele = models.CharField(max_length=50, blank=True, null=True)

    technologie = models.CharField(max_length=20, choices=TECHNOLOGIE_CHOICES, default='ELECTRONIQUE')
    tension_compatibilite = models.CharField(max_length=20, default='BT_220V')
    nombre_phases = models.IntegerField(choices=((1, 'Monophasé'), (3, 'Triphasé')), default=1)

    compatible_shelly = models.BooleanField(default=True)
    prix_unitaire_fcfa = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    actif = models.BooleanField(default=True)
    en_stock = models.BooleanField(default=True)
    stock_disponible = models.IntegerField(default=0)
    ordre_affichage = models.IntegerField(default=0)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'type_compteur'
        ordering = ['ordre_affichage', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.code})"


class Capteur(models.Model):
    STATUS_CHOICES = (
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
        ('ERREUR', 'Erreur'),
    )

    compteur = models.ForeignKey(Compteur, on_delete=models.CASCADE, related_name='capteurs')

    # Identification Shelly
    device_id = models.CharField(max_length=100, unique=True)
    device_name = models.CharField(max_length=100, blank=True)
    mac_address = models.CharField(max_length=17, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    # Configuration
    nombre_phase = models.IntegerField(default=1)
    calibre_courant = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    calibration_factor = models.DecimalField(max_digits=6, decimal_places=3, default=1.000)

    # État
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIF')
    derniere_communication = models.DateTimeField(null=True, blank=True)
    puissance_instantanee = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    energie_totale = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Métadonnées
    date_installation = models.DateTimeField(auto_now_add=True)
    firmware_version = models.CharField(max_length=20, blank=True)
    derniere_mise_a_jour = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'capteur'
        indexes = [
            models.Index(fields=['device_id']),
            models.Index(fields=['compteur']),
            models.Index(fields=['status']),
        ]
    app_label = 'compteurs'