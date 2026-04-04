from django.db import models

# Create your models here.
# menages/models.py
# Dans apps/menages/models.py

from django.contrib.gis.db import models
from django.core.validators import MinValueValidator

class Agence(models.Model):
    """
    Agence de la société Energie Electrique du Congo (E2C).
    Une agence supervise plusieurs ménages dans une zone géographique.
    """

    nom = models.CharField(max_length=150, verbose_name="Nom de l'agence")

    localite = models.ForeignKey(
        'parametrage.Localite',
        on_delete=models.PROTECT,
        related_name='agences',
        verbose_name="Localité"
    )
    departement = models.ForeignKey(
        'parametrage.Departement',
        on_delete=models.PROTECT,
        related_name='agences',
        verbose_name="Département"
    )
    pays = models.CharField(
        max_length=100,
        default='Congo-Brazzaville',
        verbose_name="Pays"
    )

    # Société de rattachement
    societe = models.CharField(
        max_length=100,
        default='Energie Electrique du Congo',
        editable=False,          # Toujours E2C, non modifiable via l'admin
        verbose_name="Société"
    )
    code_agence = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Code agence"
    )

    actif = models.BooleanField(default=True, verbose_name="Active")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'agence'
        ordering = ['nom']
        verbose_name = 'Agence'
        verbose_name_plural = 'Agences'

    def __str__(self):
        return f"{self.nom} ({self.code_agence}) — {self.localite}"

    @property
    def nombre_menages(self):
        return self.menages.filter(statut='ACTIF').count()

    @property
    def nombre_agents(self):
        """Nombre d'agents de terrain actifs rattachés à cette agence"""
        return self.agents.filter(statut='ACTIF', role='AGENT_TERRAIN').count()

    @property
    def agents_actifs(self):
        """Queryset des agents actifs de l'agence"""
        return self.agents.filter(statut='ACTIF', role='AGENT_TERRAIN')

class Menage(models.Model):
    # Le tuple TYPE_HABITATION a été supprimé car les types sont maintenant gérés
    # dans le modèle 'parametrage.TypeHabitation'.

    STATUT_CHOICES = (
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
        ('DEMENAGE', 'Déménagé'),
    )

    # Identification
    nom_menage = models.CharField(max_length=100)
    reference_menage = models.CharField(max_length=30, unique=True)

    agence = models.ForeignKey(
        'Agence',  # ou 'agences.Agence' si app séparée
        on_delete=models.PROTECT,
        related_name='menages',
        verbose_name="Agence",
        null=True,  # null=True pendant la migration
        blank=True  # à rendre obligatoire après peuplement
    )

    # Lien avec utilisateur
    utilisateur = models.OneToOneField('users.CustomUser', on_delete=models.CASCADE, related_name='menage', null=True,
                                       blank=True)

    # Localisation
    localite = models.ForeignKey('parametrage.Localite', on_delete=models.PROTECT)
    adresse_complete = models.TextField()

    # Coordonnées GPS
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    precision_gps = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    SOURCE_GEOLOCALISATION = (
        ('GPS_AGENT', 'GPS Agent'),
        ('GOOGLE_MAPS', 'Google Maps'),
        ('SAISIE_MANUEL', 'Saisie manuelle'),
    )
    source_geolocalisation = models.CharField(max_length=20, choices=SOURCE_GEOLOCALISATION, default='GPS_AGENT')

    # Google Maps
    google_place_id = models.CharField(max_length=255, blank=True)
    adresse_google = models.TextField(blank=True)

    # Informations ménage
    nombre_personnes = models.IntegerField(default=1, validators=[MinValueValidator(1)])

    # Champ modifié : ForeignKey vers la table de paramétrage
    type_habitation = models.ForeignKey(
        'parametrage.TypeHabitation',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='menages'
    )

    surface_m2 = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    # Contacts supplémentaires
    telephone_secondaire = models.CharField(max_length=20, blank=True)
    email_secondaire = models.EmailField(blank=True)
    personne_contact = models.CharField(max_length=100, blank=True)

    # Informations sociales (optionnel)
    categorie_socio_professionnelle = models.CharField(max_length=50, blank=True)
    revenu_mensuel_estime = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Points de repère
    point_repere = models.TextField(blank=True)
    code_acces = models.CharField(max_length=100, blank=True)
    instructions_livraison = models.TextField(blank=True)

    agent = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 'AGENT_TERRAIN'},
        related_name='menages_assignes'
    )

    # État
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'menage'
        indexes = [
            models.Index(fields=['reference_menage']),
            models.Index(fields=['statut']),
            models.Index(fields=['utilisateur']),
            models.Index(fields=['localite']),
        ]

    def __str__(self):
        return f"{self.nom_menage} ({self.reference_menage})"

    app_label = 'menages'