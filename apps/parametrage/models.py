# apps/parametrage/models.py
"""
Modèles géographiques et tarifaires pour le paramétrage du système
Compatible GeoDjango + Windows/Conda avec GDAL 3.4.3
"""
from django.db import models
from django.contrib.gis.db import models as gis_models
from django.db.models import JSONField  # ✅ Portable (Django 3.1+)
from decimal import Decimal

class Departement(models.Model):
    """Départements administratifs du Congo"""

    nom = models.CharField(max_length=100)
    code_departement = models.CharField(max_length=10, unique=True)
    region = models.CharField(max_length=100, blank=True, null=True)

    # === CHAMPS GÉOGRAPHIQUES GEOJANGO ===
    geom = gis_models.MultiPolygonField(srid=4326, null=True, blank=True)  # Frontières réelles
    centre = gis_models.PointField(srid=4326, null=True, blank=True)  # Point central

    # Champs de compatibilité
    centre_latitude = models.DecimalField(
        max_digits=10, decimal_places=8, null=True, blank=True
    )
    centre_longitude = models.DecimalField(
        max_digits=10, decimal_places=8, null=True, blank=True
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'departement'
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.code_departement})"

    def save(self, *args, **kwargs):
        # Créer automatiquement le point si on a les coordonnées
        if self.centre_latitude and self.centre_longitude and not self.centre:
            self.centre = gis_models.Point(
                float(self.centre_longitude),
                float(self.centre_latitude),
                srid=4326
            )
        super().save(*args, **kwargs)

    @property
    def centroid(self):
        """Retourne le centroïde du polygone si disponible"""
        if self.geom:
            return self.geom.centroid
        return self.centre

    def contains_point(self, lat, lon):
        """Vérifie si un point est dans le département"""
        from django.contrib.gis.geos import Point

        if not self.geom:
            return False

        point = Point(lon, lat, srid=4326)
        return self.geom.contains(point)


class Localite(models.Model):
    """Localités (villes, quartiers, villages) du Congo"""

    TYPE_LOCALITE = (
        ('VILLE', 'Ville'),
        ('COMMUNE', 'Commune'),
        ('QUARTIER', 'Quartier'),
        ('VILLAGE', 'Village'),
    )

    nom = models.CharField(max_length=100)
    code_postal = models.CharField(max_length=10, blank=True, null=True)
    actif = models.BooleanField(default=True)
    departement = models.ForeignKey(
        Departement,
        on_delete=models.CASCADE,
        related_name='localites'
    )
    type_localite = models.CharField(
        max_length=20,
        choices=TYPE_LOCALITE,
        default='QUARTIER'
    )

    # === CHAMPS GÉOGRAPHIQUES GEOJANGO ===
    geom = gis_models.MultiPolygonField(srid=4326, null=True, blank=True)  # Frontières
    point = gis_models.PointField(srid=4326, null=True, blank=True)  # Point central

    # Coordonnées de compatibilité
    latitude = models.DecimalField(
        max_digits=10, decimal_places=8, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=8, null=True, blank=True
    )

    # Google Maps
    google_place_id = models.CharField(max_length=255, blank=True, null=True)

    # Périmètre de validité (rayon en km autour du point)
    zone_rayon_km = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=5.00,
        null=True, blank=True
    )

    class Meta:
        db_table = 'localite'
        ordering = ['nom']
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['google_place_id']),
        ]

    def __str__(self):
        return f"{self.nom} ({self.get_type_localite_display()})"

    def save(self, *args, **kwargs):
        # Créer automatiquement le point si on a les coordonnées
        if self.latitude and self.longitude and not self.point:
            self.point = gis_models.Point(
                float(self.longitude),
                float(self.latitude),
                srid=4326
            )
        super().save(*args, **kwargs)

    @property
    def centroid(self):
        """Retourne le centroïde"""
        if self.geom:
            return self.geom.centroid
        return self.point

    def contains_point(self, lat, lon):
        """Vérifie si un point est dans la localité"""
        from django.contrib.gis.geos import Point

        if not self.geom:
            return False

        point = Point(lon, lat, srid=4326)
        return self.geom.contains(point)

    def distance_to_point(self, lat, lon):
        """Calcule la distance en km entre cette localité et un point"""
        from django.contrib.gis.geos import Point

        target_point = Point(lon, lat, srid=4326)
        if self.point:
            # Conversion degrés → km (approximation)
            return self.point.distance(target_point) * 111.32
        return None


from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import json


# ==================== TARIFICATION ====================

class TypeTarification(models.Model):
    """Types de tarification pour la facturation"""

    CATEGORIE_CHOICES = (
        ('RESIDENTIEL', 'Résidentiel'),
        ('COMMERCIAL', 'Commercial'),
        ('INDUSTRIEL', 'Industriel'),
        ('ADMINISTRATIF', 'Administratif'),
        ('SPECIAL', 'Spécial'),
    )

    PERIODICITE_CHOICES = (
        ('MENSUEL', 'Mensuel'),
        ('BIMESTRIEL', 'Bimestriel'),
        ('TRIMESTRIEL', 'Trimestriel'),
        ('SEMESTRIEL', 'Semestriel'),
    )

    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, verbose_name="Catégorie")

    periodicite = models.CharField(
        max_length=20,
        choices=PERIODICITE_CHOICES,
        default='BIMESTRIEL',
        verbose_name="Périodicité de facturation"
    )

    abonnement_mensuel = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Abonnement mensuel (FCFA)"
    )
    devise = models.CharField(max_length=10, default='FCFA', verbose_name="Devise")

    tva_taux = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=18.00,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Taux TVA (%)"
    )

    reference_arrete = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Référence arrêté/loi"
    )
    date_effet = models.DateField(verbose_name="Date d'effet")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de fin")

    description = models.TextField(blank=True, null=True, verbose_name="Description")
    conditions = models.TextField(blank=True, null=True, verbose_name="Conditions d'application")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_modification = models.DateTimeField(auto_now=True, verbose_name="Dernière modification")

    class Meta:
        db_table = 'type_tarification'
        ordering = ['-date_effet', 'nom']
        verbose_name = "Type de tarification"
        verbose_name_plural = "Types de tarification"
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['categorie', 'actif']),
            models.Index(fields=['date_effet', 'date_fin']),
        ]

    def __str__(self):
        return f"{self.nom} ({self.code}) - {self.get_categorie_display()}"

    # ──────────────────────────────────────────────
    # PROPRIÉTÉS
    # ──────────────────────────────────────────────

    @property
    def est_active(self):
        """Vérifie si la tarification est active aujourd'hui"""
        today = timezone.now().date()
        if not self.actif:
            return False
        if self.date_fin and today > self.date_fin:
            return False
        return today >= self.date_effet

    # ──────────────────────────────────────────────
    # MÉTHODES UTILITAIRES
    # ──────────────────────────────────────────────

    def get_tranches_ordonnees(self):
        """Retourne les tranches triées par ordre puis par borne inférieure"""
        return self.tranches.all().order_by('ordre', 'borne_inferieure')

    def to_json(self):
        """Exporte la configuration en JSON"""
        return {
            'id': self.id,
            'code': self.code,
            'nom': self.nom,
            'categorie': self.categorie,
            'periodicite': self.periodicite,
            'abonnement_mensuel': float(self.abonnement_mensuel),
            'devise': self.devise,
            'tva_taux': float(self.tva_taux),
            'tranches': [
                {
                    'ordre': t.ordre,
                    'borne_inferieure': float(t.borne_inferieure),
                    'borne_superieure': float(t.borne_superieure) if t.borne_superieure else None,
                    'prix_kwh': float(t.prix_kwh)
                }
                for t in self.get_tranches_ordonnees()
            ]
        }

    # ──────────────────────────────────────────────
    # CALCUL TARIFAIRE
    # ──────────────────────────────────────────────

    def calculer_montant(self, consommation_kwh):
        """
        Calcule le montant HT de la consommation selon les tranches tarifaires.

        Args:
            consommation_kwh (float | Decimal): Consommation à facturer en kWh

        Returns:
            Decimal: Montant HT de la consommation (hors abonnement, hors taxes)

        Raises:
            ValueError: Si aucune tranche n'est configurée
        """
        montant, _ = self.calculer_montant_avec_detail(consommation_kwh)
        return montant

    def calculer_montant_avec_detail(self, consommation_kwh):
        """
        Calcule le montant HT avec le détail par tranche.

        Args:
            consommation_kwh (float | Decimal): Consommation à facturer en kWh

        Returns:
            tuple: (Decimal montant_total, list detail_tranches)
            Chaque élément de detail_tranches est un dict :
                {
                    'borne_inferieure': Decimal,
                    'borne_superieure': Decimal | None,
                    'kwh_factures': Decimal,
                    'prix_kwh': Decimal,
                    'montant': Decimal,
                }

        Raises:
            ValueError: Si aucune tranche n'est configurée
        """
        tranches = self.get_tranches_ordonnees()

        if not tranches.exists():
            raise ValueError(
                f"Aucune tranche tarifaire configurée pour '{self.nom}' ({self.code})"
            )

        conso_restante = Decimal(str(consommation_kwh))
        montant_total = Decimal('0.00')
        detail_tranches = []

        for tranche in tranches:
            if conso_restante <= 0:
                break

            borne_inf = tranche.borne_inferieure
            borne_sup = tranche.borne_superieure  # None = tranche illimitée

            # Largeur de cette tranche
            if borne_sup is not None:
                largeur_tranche = borne_sup - borne_inf
            else:
                largeur_tranche = conso_restante  # illimitée : consomme tout le reste

            kwh_dans_tranche = min(conso_restante, largeur_tranche)

            if kwh_dans_tranche <= 0:
                continue

            montant_tranche = kwh_dans_tranche * tranche.prix_kwh
            montant_total += montant_tranche
            conso_restante -= kwh_dans_tranche

            detail_tranches.append({
                'borne_inferieure': borne_inf,
                'borne_superieure': borne_sup,
                'kwh_factures': kwh_dans_tranche,
                'prix_kwh': tranche.prix_kwh,
                'montant': montant_tranche,
            })

        # Protection : consommation dépasse toutes les tranches définies
        # → on applique le prix de la dernière tranche sur le solde
        if conso_restante > 0:
            derniere_tranche = tranches.last()
            montant_reste = conso_restante * derniere_tranche.prix_kwh
            montant_total += montant_reste
            detail_tranches.append({
                'borne_inferieure': derniere_tranche.borne_inferieure,
                'borne_superieure': None,
                'kwh_factures': conso_restante,
                'prix_kwh': derniere_tranche.prix_kwh,
                'montant': montant_reste,
            })

        return montant_total, detail_tranches

    def prix_moyen_kwh(self, consommation_kwh=None):
        """
        Calcule le prix moyen par kWh pour une consommation donnée.
        Utilisé dans LigneFacture pour l'affichage du prix unitaire.

        Args:
            consommation_kwh: Si None, retourne le prix de la première tranche.

        Returns:
            Decimal: Prix moyen par kWh arrondi à 4 décimales
        """
        if consommation_kwh is None or Decimal(str(consommation_kwh)) == 0:
            premiere_tranche = self.tranches.order_by('ordre', 'borne_inferieure').first()
            return premiere_tranche.prix_kwh if premiere_tranche else Decimal('0.00')

        montant, _ = self.calculer_montant_avec_detail(consommation_kwh)
        return (montant / Decimal(str(consommation_kwh))).quantize(Decimal('0.0001'))

class TrancheTarifaire(models.Model):
    """Tranches de consommation pour un type de tarification"""

    tarification = models.ForeignKey(
        TypeTarification,
        on_delete=models.CASCADE,
        related_name='tranches'
    )

    # Bornes de la tranche
    borne_inferieure = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Borne inférieure (kWh)"
    )
    borne_superieure = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Borne supérieure (kWh)"
    )

    # Prix
    prix_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Prix du kWh (FCFA)"
    )

    # Ordre d'application
    ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre d'application")

    class Meta:
        db_table = 'tranche_tarifaire'
        ordering = ['tarification', 'ordre', 'borne_inferieure']
        verbose_name = "Tranche tarifaire"
        verbose_name_plural = "Tranches tarifaires"
        unique_together = [
            ['tarification', 'ordre'],
            ['tarification', 'borne_inferieure']
        ]
        indexes = [
            models.Index(fields=['tarification', 'ordre']),
        ]

    def __str__(self):
        if self.borne_superieure:
            return f"{self.borne_inferieure} - {self.borne_superieure} kWh: {self.prix_kwh} FCFA/kWh"
        else:
            return f"≥ {self.borne_inferieure} kWh: {self.prix_kwh} FCFA/kWh"

    def clean(self):
        """Validation personnalisée"""
        from django.core.exceptions import ValidationError

        if self.borne_superieure and self.borne_superieure <= self.borne_inferieure:
            raise ValidationError({
                'borne_superieure': "La borne supérieure doit être supérieure à la borne inférieure"
            })

# ==================== TAXES TARIFAIRES ====================

class TaxeTarifaire(models.Model):
    """Taxes applicables à un type de tarification"""

    TYPE_TAXE_CHOICES = (
        ('FIXE', 'Montant fixe'),
        ('POURCENTAGE', 'Pourcentage'),
    )

    BASE_CALCUL_CHOICES = (
        ('HT', 'Sur le total HT'),
        ('CONSO', 'Sur la consommation'),
        ('ABONNEMENT', "Sur l'abonnement"),
        ('TTC', 'Sur le total TTC'),
    )

    tarification = models.ForeignKey(
        TypeTarification,
        on_delete=models.CASCADE,
        related_name='taxes'
    )

    code = models.CharField(
        max_length=20,
        verbose_name="Code taxe",
        help_text="Ex: RAV, CA, TIMBRE"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom de la taxe")

    type_taxe = models.CharField(
        max_length=20,
        choices=TYPE_TAXE_CHOICES,
        default='FIXE',
        verbose_name="Type de taxe"
    )

    montant_fixe = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        verbose_name="Montant fixe (FCFA)"
    )

    pourcentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Pourcentage (%)"
    )

    base_calcul = models.CharField(
        max_length=20,
        choices=BASE_CALCUL_CHOICES,
        default='HT',
        verbose_name="Base de calcul"
    )

    soumis_tva = models.BooleanField(
        default=False,
        verbose_name="Soumis à TVA",
        help_text="Cette taxe est-elle incluse dans l'assiette de la TVA ?"
    )

    ordre_application = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'application"
    )

    date_debut = models.DateField(default=timezone.now, verbose_name="Date de début")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de fin")
    active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        db_table = 'taxe_tarifaire'
        ordering = ['tarification', 'ordre_application']
        verbose_name = "Taxe tarifaire"
        verbose_name_plural = "Taxes tarifaires"
        unique_together = ['tarification', 'code']

    def __str__(self):
        if self.type_taxe == 'FIXE':
            return f"{self.code} - {self.montant_fixe} FCFA"
        return f"{self.code} - {self.pourcentage}% sur {self.get_base_calcul_display()}"

    def calculer(self, base_ht, base_ttc=None, consommation=None, abonnement=None):
        """Calcule le montant de la taxe selon sa configuration"""
        if self.base_calcul == 'HT':
            base = base_ht
        elif self.base_calcul == 'TTC':
            base = base_ttc or base_ht
        elif self.base_calcul == 'CONSO':
            base = consommation or 0
        elif self.base_calcul == 'ABONNEMENT':
            base = abonnement or 0
        else:
            base = 0

        if self.type_taxe == 'FIXE':
            return Decimal(str(self.montant_fixe or 0))
        else:  # POURCENTAGE
            return Decimal(str(base)) * (Decimal(str(self.pourcentage or 0)) / 100)



class ConfigurationTarifaire(models.Model):
    """Configuration complète pour un pays/période"""

    pays = models.CharField(
        max_length=100,
        default='Congo-Brazzaville',
        verbose_name="Pays"
    )

    tarification = models.ForeignKey(
        TypeTarification,
        on_delete=models.CASCADE,
        related_name='configurations'
    )

    # Paramètres généraux
    timbre_electronique = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=50.00,
        verbose_name="Timbre électronique (FCFA)"
    )

    # Période de validité de cette configuration
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date de fin")

    # Version
    version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name="Version"
    )

    class Meta:
        db_table = 'configuration_tarifaire'
        verbose_name = "Configuration tarifaire"
        verbose_name_plural = "Configurations tarifaires"
        ordering = ['pays', '-date_debut']

    def __str__(self):
        return f"{self.pays} - {self.tarification.nom} v{self.version}"


class Zone(models.Model):
    """Zones géographiques pour l'organisation territoriale"""

    nom = models.CharField(max_length=100)
    departement = models.ForeignKey(
        Departement,
        on_delete=models.CASCADE,
        related_name='zones'
    )
    actif = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'zone'
        ordering = ['nom']
        verbose_name = 'Zone'
        verbose_name_plural = 'Zones'

    def __str__(self):
        return f"{self.nom} ({self.departement.nom})"

    @property
    def nombre_menages(self):
        """Nombre de ménages dans cette zone"""
        # ⚠️ ATTENTION: 'menage_set' suppose que le modèle Menage a une FK vers Zone
        # Si ce n'est pas le cas, adaptez selon votre modèle réel
        from apps.menages.models import Menage
        return Menage.objects.filter(zone=self, statut='ACTIF').count()


class TypeHabitation(models.Model):
    """Types d'habitation pour la classification des ménages au Congo-Brazzaville"""

    CATEGORIE_CHOICES = (
        ('VILLA', 'Villa'),
        ('APPARTEMENT', 'Appartement'),
        ('STUDIO', 'Studio'),
        ('MAISON_TRADITIONNELLE', 'Maison traditionnelle'),
        ('IMMEUBLE', 'Immeuble'),
        ('COMMERCE', 'Commerce'),
        ('MIXTE', 'Mixte (Habitation + Commerce)'),
    )

    STANDING_CHOICES = (
        ('ECONOMIQUE', 'Économique'),
        ('MOYEN', 'Moyen'),
        ('STANDING', 'Standing'),
        ('HAUT_STANDING', 'Haut standing'),
    )

    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    categorie = models.CharField(max_length=30, choices=CATEGORIE_CHOICES, default='APPARTEMENT')
    standing = models.CharField(max_length=20, choices=STANDING_CHOICES, default='MOYEN')

    surface_moyenne_m2 = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    nombre_pieces_moyen = models.IntegerField(null=True, blank=True)
    consommation_estimee_kwh = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    type_tarification_recommande = models.ForeignKey(
        'TypeTarification', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='types_habitation'
    )

    description = models.TextField(blank=True, null=True)
    caracteristiques = JSONField(default=dict, blank=True)

    actif = models.BooleanField(default=True)
    ordre_affichage = models.IntegerField(default=0)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'type_habitation'
        ordering = ['ordre_affichage', 'nom']
        verbose_name = 'Type d\'habitation'
        verbose_name_plural = 'Types d\'habitation'

    def __str__(self):
        return f"{self.nom} ({self.code})"