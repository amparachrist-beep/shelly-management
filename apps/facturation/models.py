from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import timedelta
User = get_user_model()

class FactureConsommation(models.Model):
    """Facture issue d'une consommation pour un compteur et une période donnée"""

    STATUT_CHOICES = (
        ('BROUILLON', 'Brouillon'),
        ('ÉMISE', 'Émise'),
        ('PARTIELLEMENT_PAYÉE', 'Partiellement payée'),
        ('PAYÉE', 'Payée'),
        ('EN_RETARD', 'En retard'),
        ('ANNULEE', 'Annulée'),
        ('REMBOURSEE', 'Remboursée'),
    )

    # Identification
    numero_facture = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Numéro facture"
    )

    compteur = models.ForeignKey(
        'compteurs.Compteur',
        on_delete=models.CASCADE,
        related_name='factures_consommation',
        verbose_name="Compteur"
    )

    consommation = models.OneToOneField(
        'consommation.Consommation',
        on_delete=models.PROTECT,
        related_name='facture_consommation',
        verbose_name="Consommation"
    )

    # Période facturée
    periode = models.DateField(verbose_name="Période")
    date_emission = models.DateField(verbose_name="Date émission")
    date_echeance = models.DateField(verbose_name="Date échéance")
    date_paiement = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date paiement"
    )

    # Consommation
    consommation_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Consommation (kWh)"
    )

    # Montants
    montant_consommation = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Montant consommation"
    )

    montant_abonnement = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="Montant abonnement"
    )

    # Taxes
    tva_taux = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=18.00,
        validators=[MinValueValidator(0)],
        verbose_name="Taux TVA (%)"
    )

    redevance_communale = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name="Redevance communale"
    )

    autres_taxes = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name="Autres taxes"
    )

    # Calculs
    @property
    def total_ht(self):
        return self.montant_consommation + self.montant_abonnement

    @property
    def tva_montant(self):
        return self.total_ht * self.tva_taux / 100

    @property
    def total_ttc(self):
        return (
            self.total_ht
            + self.tva_montant
            + self.redevance_communale
            + self.autres_taxes
        )

    # Paiement
    montant_paye = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(0)],
        verbose_name="Montant payé"
    )

    type_tarification = models.ForeignKey(
        'parametrage.TypeTarification',  # ou l'app où se trouve votre modèle
        on_delete=models.PROTECT,
        related_name='factures',
        verbose_name="Type de tarification appliqué",
        null=True,  # Temporairement null pour compatibilité
        help_text="La grille tarifaire utilisée pour cette facture"
    )

    taxes_appliquees = models.JSONField(
        default=dict,
        verbose_name="Taxes appliquées",
        help_text="Snapshot des taxes au moment de la facturation"
    )

    @property
    def solde_du(self):
        return self.total_ttc - self.montant_paye

    @property
    def pourcentage_paye(self):
        if self.total_ttc == 0:
            return 100
        return (self.montant_paye / self.total_ttc) * 100

    @property
    def jours_retard(self):
        if self.statut == 'EN_RETARD':
            return (timezone.now().date() - self.date_echeance).days
        return 0

    # État
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='BROUILLON',
        verbose_name="Statut"
    )

    # Traçabilité
    calcul_tranches = models.JSONField(
        default=list,
        verbose_name="Calcul par tranches"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")
    motif_annulation = models.TextField(blank=True, verbose_name="Motif annulation")

    # Documents
    fichier_pdf = models.FileField(
        upload_to='factures/pdf/',
        null=True,
        blank=True,
        verbose_name="Fichier PDF"
    )

    qr_code = models.ImageField(
        upload_to='factures/qr_codes/',
        null=True,
        blank=True,
        verbose_name="QR Code"
    )

    @classmethod
    def creer_depuis_consommation(cls, consommation, user=None):
        """
        Crée une facture à partir d'une consommation et du type de tarification du compteur
        """
        compteur = consommation.compteur
        tarif = compteur.type_tarification

        if not tarif:
            raise ValueError("Le compteur n'a pas de type de tarification associé")

        # Récupérer les taxes actives du tarif
        taxes = tarif.taxes.filter(active=True)

        # Calculer les montants
        montant_conso = tarif.calculer_montant(consommation.consommation_kwh)

        # Déterminer la période (bimestrielle si nécessaire)
        nombre_mois = 2 if tarif.periodicite == 'BIMESTRIEL' else 1
        montant_abonnement = tarif.abonnement_mensuel * nombre_mois

        # Initialiser les taxes
        redevance_communale = 0  # Pour CA
        autres_taxes = 0  # Pour RAV et Timbre
        taxes_detail = {}

        for taxe in taxes:
            montant = taxe.calculer(
                base_ht=montant_conso + montant_abonnement,
                consommation=montant_conso,
                abonnement=montant_abonnement
            )

            # Classifier les taxes
            if taxe.code == 'CA':
                redevance_communale = montant
            elif taxe.code == 'RAV':
                autres_taxes += montant
            elif taxe.code == 'TIMBRE':
                autres_taxes += montant

            taxes_detail[taxe.code] = {
                'nom': taxe.nom,
                'montant': float(montant),
                'type': taxe.type_taxe,
                'soumis_tva': taxe.soumis_tva
            }

        # Créer la facture
        facture = cls(
            numero_facture=cls.generer_numero(compteur),
            compteur=compteur,
            consommation=consommation,
            periode=consommation.periode,
            date_emission=timezone.now().date(),
            date_echeance=timezone.now().date() + timedelta(days=14),  # 14 jours
            consommation_kwh=consommation.consommation_kwh,
            montant_consommation=montant_conso,
            montant_abonnement=montant_abonnement,
            tva_taux=tarif.tva_taux,
            redevance_communale=redevance_communale,
            autres_taxes=autres_taxes,
            type_tarification=tarif,
            taxes_appliquees=taxes_detail,
            statut='BROUILLON',
            emis_par=user
        )

        facture.save()

        # Créer les lignes de facture détaillées
        facture._creer_lignes_detail(consommation, tarif)

        return facture

    def _creer_lignes_detail(self, consommation, tarif):
        """Crée les lignes détaillées de la facture"""

        # Ligne consommation
        LigneFacture.objects.create(
            facture=self,
            type_ligne='CONSOMMATION',
            description=f"Consommation {consommation.consommation_kwh} kWh",
            quantite=consommation.consommation_kwh,
            unite='kWh',
            prix_unitaire=tarif.prix_moyen_kwh(),  # À calculer
            taux_tva=self.tva_taux,
            ordre=1
        )

        # Ligne abonnement
        LigneFacture.objects.create(
            facture=self,
            type_ligne='ABONNEMENT',
            description="Abonnement mensuel",
            quantite=1,
            unite='mois',
            prix_unitaire=self.montant_abonnement,
            taux_tva=self.tva_taux,
            ordre=2
        )

        # Lignes taxes
        ordre = 3
        for code, detail in self.taxes_appliquees.items():
            LigneFacture.objects.create(
                facture=self,
                type_ligne='TAXE',
                description=detail['nom'],
                quantite=1,
                unite='-',
                prix_unitaire=detail['montant'],
                taux_tva=0,  # Les taxes sont généralement non soumises
                ordre=ordre
            )
            ordre += 1

    @staticmethod
    def generer_numero(compteur):
        """Génère un numéro de facture unique"""
        from datetime import datetime
        now = datetime.now()
        return f"F{now.strftime('%Y%m')}-{compteur.id:04d}-{now.strftime('%d%H%M')}"  # ✅ ) ajoutée

    # Historique
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date modification")

    emis_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='factures_consommation_emises',
        verbose_name="Émis par"
    )

    class Meta:
        db_table = 'facture_consommation'
        verbose_name = 'Facture de consommation'
        verbose_name_plural = 'Factures de consommation'
        ordering = ['-periode', '-date_emission']
        indexes = [
            models.Index(fields=['numero_facture']),
            models.Index(fields=['statut']),
            models.Index(fields=['date_echeance']),
            models.Index(fields=['compteur', 'periode']),
            models.Index(fields=['date_emission']),
        ]

    def __str__(self):
        return f"{self.numero_facture} - {self.compteur.numero_contrat}"

    app_label = 'facturation'
class LigneFacture(models.Model):
    """Ligne détaillée d'une facture (pour affichage détaillé)"""
    TYPE_LIGNE_CHOICES = (
        ('CONSOMMATION', 'Consommation'),
        ('ABONNEMENT', 'Abonnement'),
        ('TAXE', 'Taxe'),
        ('PENALITE', 'Pénalité'),
        ('REMISE', 'Remise'),
        ('AUTRE', 'Autre'),
    )

    facture = models.ForeignKey(
        'FactureConsommation',
        on_delete=models.CASCADE,
        related_name='lignes',
        verbose_name="Facture"
    )
    type_ligne = models.CharField(max_length=20, choices=TYPE_LIGNE_CHOICES, verbose_name="Type ligne")
    description = models.CharField(max_length=200, verbose_name="Description")

    # Quantité et prix
    quantite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1,
        verbose_name="Quantité"
    )
    unite = models.CharField(max_length=20, default='kWh', verbose_name="Unité")
    prix_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Prix unitaire"
    )
    taux_tva = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=18.00,
        verbose_name="Taux TVA (%)"
    )

    # Calculs
    @property
    def montant_ht(self):
        return self.quantite * self.prix_unitaire

    @property
    def montant_tva(self):
        return self.montant_ht * self.taux_tva / 100

    @property
    def montant_ttc(self):
        return self.montant_ht + self.montant_tva

    # Pour les tranches de consommation
    tranche_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Tranche min (kWh)"
    )
    tranche_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Tranche max (kWh)"
    )

    # Ordre d'affichage
    ordre = models.IntegerField(default=0, verbose_name="Ordre")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")

    class Meta:
        db_table = 'ligne_facture'
        verbose_name = 'Ligne facture'
        verbose_name_plural = 'Lignes facture'
        ordering = ['ordre', 'id']
        indexes = [
            models.Index(fields=['facture']),
            models.Index(fields=['type_ligne']),
        ]

    def __str__(self):
        return f"{self.description} - {self.facture.numero_facture}"


    app_label = 'facturation'
class PenaliteRetard(models.Model):
    """Pénalités pour retard de paiement"""
    TYPE_PENALITE_CHOICES = (
        ('POURCENTAGE', 'Pourcentage'),
        ('MONTANT_FIXE', 'Montant fixe'),
        ('ECHELONNEE', 'Échelonnée'),
    )

    nom = models.CharField(max_length=100, verbose_name="Nom")
    type_penalite = models.CharField(max_length=20, choices=TYPE_PENALITE_CHOICES, verbose_name="Type pénalité")
    description = models.TextField(blank=True, verbose_name="Description")

    # Configuration
    delai_jours = models.IntegerField(default=30, verbose_name="Délai jours")
    taux_penalite = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        verbose_name="Taux pénalité (%)"
    )
    montant_fixe = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Montant fixe"
    )

    # Échelonnage (si type échelonné)
    echelons = models.JSONField(
        default=list,
        verbose_name="Échelons"
    )  # Format: [{"jours_min": 30, "jours_max": 60, "taux": 5}, ...]

    # Application
    applicable = models.BooleanField(default=True, verbose_name="Applicable")
    date_debut = models.DateField(verbose_name="Date début application")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date fin application")

    # Maximum
    penalite_maximum = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Pénalité maximum"
    )
    pourcentage_maximum = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Pourcentage maximum"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date modification")

    class Meta:
        db_table = 'penalite_retard'
        verbose_name = 'Pénalité retard'
        verbose_name_plural = 'Pénalités retard'
        ordering = ['delai_jours']
        indexes = [
            models.Index(fields=['applicable']),
            models.Index(fields=['date_debut', 'date_fin']),
        ]

    def __str__(self):
        return f"{self.nom} ({self.get_type_penalite_display()})"


    app_label = 'facturation'
class Remise(models.Model):
    """Remises applicables sur les factures"""
    TYPE_REMISE_CHOICES = (
        ('POURCENTAGE', 'Pourcentage'),
        ('MONTANT_FIXE', 'Montant fixe'),
        ('EXONERATION', 'Exonération'),
    )

    APPLICABLE_SUR_CHOICES = (
        ('CONSOMMATION', 'Consommation'),
        ('ABONNEMENT', 'Abonnement'),
        ('TOTAL_HT', 'Total HT'),
        ('TOTAL_TTC', 'Total TTC'),
    )

    code = models.CharField(max_length=50, unique=True, verbose_name="Code remise")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    type_remise = models.CharField(max_length=20, choices=TYPE_REMISE_CHOICES, verbose_name="Type remise")
    applicable_sur = models.CharField(max_length=20, choices=APPLICABLE_SUR_CHOICES, verbose_name="Applicable sur")

    # Valeur
    pourcentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Pourcentage (%)"
    )
    montant_fixe = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Montant fixe"
    )

    # Conditions
    montant_minimum = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Montant minimum"
    )
    montant_maximum = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Montant maximum"
    )
    consommation_min_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Consommation minimum (kWh)"
    )
    consommation_max_kwh = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Consommation maximum (kWh)"
    )

    # Validité
    date_debut = models.DateField(verbose_name="Date début")
    date_fin = models.DateField(null=True, blank=True, verbose_name="Date fin")
    utilisations_max = models.IntegerField(null=True, blank=True, verbose_name="Utilisations maximum")
    utilisations_actuelles = models.IntegerField(default=0, verbose_name="Utilisations actuelles")

    # Clientèle cible
    pour_tous = models.BooleanField(default=True, verbose_name="Pour tous")
    categories_clients = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Catégories clients"
    )  # IDs ou codes de catégories

    # Statut
    active = models.BooleanField(default=True, verbose_name="Active")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date modification")
    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Créé par"
    )

    class Meta:
        db_table = 'remise'
        verbose_name = 'Remise'
        verbose_name_plural = 'Remises'
        ordering = ['-date_debut', 'code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['active']),
            models.Index(fields=['date_debut', 'date_fin']),
        ]

    def __str__(self):
        return f"{self.code} - {self.nom}"


    app_label = 'facturation'
class BatchFacturation(models.Model):
    """Batch de génération de factures"""
    STATUT_CHOICES = (
        ('EN_PREPARATION', 'En préparation'),
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('ERREUR', 'Erreur'),
        ('ANNULE', 'Annulé'),
    )

    reference = models.CharField(max_length=50, unique=True, verbose_name="Référence")
    description = models.TextField(blank=True, verbose_name="Description")

    # Période
    periode = models.DateField(verbose_name="Période")  # Mois facturé
    date_generation = models.DateField(auto_now_add=True, verbose_name="Date génération")

    # Paramètres
    parametres = models.JSONField(default=dict, verbose_name="Paramètres")

    # Statistiques
    total_factures = models.IntegerField(default=0, verbose_name="Total factures")
    factures_generees = models.IntegerField(default=0, verbose_name="Factures générées")
    factures_erreur = models.IntegerField(default=0, verbose_name="Factures en erreur")

    # Montants
    total_ttc = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name="Total TTC"
    )
    total_consommation_kwh = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        verbose_name="Total consommation (kWh)"
    )

    # Statut
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_PREPARATION', verbose_name="Statut")
    progression = models.IntegerField(default=0, verbose_name="Progression (%)")

    # Logs
    logs = models.TextField(blank=True, verbose_name="Logs")
    erreurs = models.TextField(blank=True, verbose_name="Erreurs")

    # Fichier rapport
    fichier_rapport = models.FileField(
        upload_to='batch_facturation/rapports/',
        null=True,
        blank=True,
        verbose_name="Fichier rapport"
    )

    # Métadonnées
    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Créé par"
    )
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="Débuté à")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Terminé à")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")

    class Meta:
        db_table = 'batch_facturation'
        verbose_name = 'Batch facturation'
        verbose_name_plural = 'Batches facturation'
        ordering = ['-date_generation']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['statut']),
            models.Index(fields=['periode']),
            models.Index(fields=['cree_par']),
        ]

    def __str__(self):
        return f"{self.reference} - {self.periode}"


    app_label = 'facturation'
class Relance(models.Model):
    """Relances pour factures impayées"""
    TYPE_RELANCE_CHOICES = (
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('LETTRE', 'Lettre'),
        ('APPEL', 'Appel téléphonique'),
        ('VISITE', 'Visite terrain'),
    )

    STATUT_CHOICES = (
        ('EN_ATTENTE', 'En attente'),
        ('ENVOYEE', 'Envoyée'),
        ('LU', 'Lue'),
        ('ECHEC', 'Échec'),
        ('ANNULEE', 'Annulée'),
    )

    facture = models.ForeignKey(
        'FactureConsommation',
        on_delete=models.CASCADE,
        related_name='relances',
        verbose_name="Facture"
    )
    type_relance = models.CharField(max_length=20, choices=TYPE_RELANCE_CHOICES, verbose_name="Type relance")
    numero_relance = models.IntegerField(default=1, verbose_name="Numéro relance")

    # Contenu
    sujet = models.CharField(max_length=200, verbose_name="Sujet")
    message = models.TextField(verbose_name="Message")

    # Destinataire
    destinataire_email = models.EmailField(null=True, blank=True, verbose_name="Email destinataire")
    destinataire_telephone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone destinataire")
    destinataire_adresse = models.TextField(blank=True, verbose_name="Adresse destinataire")

    # Envoi
    date_envoi_prevue = models.DateTimeField(verbose_name="Date envoi prévue")
    date_envoi_reelle = models.DateTimeField(null=True, blank=True, verbose_name="Date envoi réelle")

    # Coût
    cout_envoi = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        verbose_name="Coût envoi"
    )

    # Statut
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE', verbose_name="Statut")
    statut_delivrance = models.CharField(max_length=100, blank=True, verbose_name="Statut délivrance")

    # Réponse
    date_reponse = models.DateTimeField(null=True, blank=True, verbose_name="Date réponse")
    reponse_client = models.TextField(blank=True, verbose_name="Réponse client")
    engagement_paiement = models.DateField(null=True, blank=True, verbose_name="Engagement paiement")

    # Agent
    agent = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Agent"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date modification")

    class Meta:
        db_table = 'relance'
        verbose_name = 'Relance'
        verbose_name_plural = 'Relances'
        ordering = ['-date_envoi_prevue']
        indexes = [
            models.Index(fields=['facture']),
            models.Index(fields=['statut']),
            models.Index(fields=['type_relance']),
            models.Index(fields=['date_envoi_prevue']),
        ]
        unique_together = ['facture', 'numero_relance']

    def __str__(self):
        return f"Relance {self.numero_relance} - {self.facture.numero_facture}"


    app_label = 'facturation'
# apps/facturation/models.py
# Ajoutez cette classe à la FIN du fichier

class Facture(FactureConsommation):
    """
    Proxy model pour FactureConsommation
    Permet la compatibilité avec le code existant qui utilise 'Facture'
    """

    class Meta:
        proxy = True
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-periode', '-date_emission']

    def __str__(self):
        return f"Facture {self.numero_facture} - {self.compteur.numero_contrat}"


# apps/facturation/models.py - Ajoutez ces classes à la fin du fichier

class DossierImpaye(models.Model):
    """Dossier de suivi des impayés"""
    STATUT_CHOICES = (
        ('OUVERT', 'Ouvert'),
        ('EN_COURS', 'En cours'),
        ('RESOLU', 'Résolu'),
        ('CLOTURE', 'Clôturé'),
    )

    facture = models.ForeignKey(
        'FactureConsommation',
        on_delete=models.CASCADE,
        related_name='dossiers_impayes',
        verbose_name="Facture"
    )
    client = models.ForeignKey(
        'users.CustomUser',
        on_delete=models.CASCADE,
        related_name='dossiers_impayes',
        verbose_name="Client"
    )
    montant_du = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Montant dû"
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default='OUVERT',
        verbose_name="Statut"
    )
    motif = models.TextField(blank=True, verbose_name="Motif")
    date_resolution = models.DateTimeField(null=True, blank=True, verbose_name="Date résolution")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        db_table = 'dossier_impaye'
        verbose_name = 'Dossier impayé'
        verbose_name_plural = 'Dossiers impayés'
        ordering = ['-date_creation']
        indexes = [
            models.Index(fields=['facture']),
            models.Index(fields=['client']),
            models.Index(fields=['statut']),
        ]

    def __str__(self):
        return f"Dossier {self.id} - {self.facture.numero_facture} - {self.montant_du} FCFA"

    def generer(self):
        """Génère le dossier d'impayé"""
        self.date_creation = timezone.now()
        self.save()
        return self


class PeriodeFacturation(models.Model):
    """Période de facturation"""
    libelle = models.CharField(max_length=100, verbose_name="Libellé")
    date_debut = models.DateField(verbose_name="Date début")
    date_fin = models.DateField(verbose_name="Date fin")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    description = models.TextField(blank=True, verbose_name="Description")

    # Pour la facturation automatique
    date_generation_factures = models.DateField(null=True, blank=True, verbose_name="Date génération factures")
    date_echeance_default = models.IntegerField(
        default=14,
        help_text="Nombre de jours après l'émission pour l'échéance",
        verbose_name="Échéance par défaut (jours)"
    )

    class Meta:
        db_table = 'periode_facturation'
        verbose_name = 'Période de facturation'
        verbose_name_plural = 'Périodes de facturation'
        ordering = ['-date_debut']
        indexes = [
            models.Index(fields=['actif']),
            models.Index(fields=['date_debut', 'date_fin']),
        ]

    def __str__(self):
        return f"{self.libelle} ({self.date_debut} - {self.date_fin})"

    def est_active(self):
        """Vérifie si la période est active"""
        today = timezone.now().date()
        return self.actif and self.date_debut <= today <= self.date_fin

    def contient_date(self, date):
        """Vérifie si une date est dans la période"""
        return self.date_debut <= date <= self.date_fin