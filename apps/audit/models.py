from django.db import models

# Create your models here.

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField  # Pour PostgreSQL

User = get_user_model()


class AuditLog(models.Model):
    """Journal d'audit pour toutes les actions importantes"""
    ACTION_TYPES = (
        # Utilisateurs
        ('USER_CREATE', 'Création utilisateur'),
        ('USER_UPDATE', 'Modification utilisateur'),
        ('USER_DELETE', 'Suppression utilisateur'),
        ('USER_LOGIN', 'Connexion utilisateur'),
        ('USER_LOGOUT', 'Déconnexion utilisateur'),
        ('USER_PASSWORD_CHANGE', 'Changement mot de passe'),

        # Ménages
        ('MENAGE_CREATE', 'Création ménage'),
        ('MENAGE_UPDATE', 'Modification ménage'),
        ('MENAGE_DELETE', 'Suppression ménage'),
        ('MENAGE_ACTIVATE', 'Activation ménage'),
        ('MENAGE_DEACTIVATE', 'Désactivation ménage'),

        # Compteurs
        ('COMPTEUR_CREATE', 'Création compteur'),
        ('COMPTEUR_UPDATE', 'Modification compteur'),
        ('COMPTEUR_DELETE', 'Suppression compteur'),
        ('COMPTEUR_ACTIVATE', 'Activation compteur'),
        ('COMPTEUR_DEACTIVATE', 'Désactivation compteur'),
        ('COMPTEUR_ASSOCIER_CAPTEUR', 'Association capteur'),

        # Factures
        ('FACTURE_CREATE', 'Création facture'),
        ('FACTURE_UPDATE', 'Modification facture'),
        ('FACTURE_DELETE', 'Suppression facture'),
        ('FACTURE_EMETTRE', 'Émission facture'),
        ('FACTURE_ANNULER', 'Annulation facture'),
        ('FACTURE_PAYER', 'Paiement facture'),

        # Paiements
        ('PAIEMENT_CREATE', 'Création paiement'),
        ('PAIEMENT_UPDATE', 'Modification paiement'),
        ('PAIEMENT_VALIDER', 'Validation paiement'),
        ('PAIEMENT_REJETER', 'Rejet paiement'),

        # Système
        ('SYSTEM_CONFIG_UPDATE', 'Modification configuration système'),
        ('TARIF_UPDATE', 'Modification tarif'),
        ('DATABASE_BACKUP', 'Sauvegarde base de données'),
        ('SECURITY_EVENT', 'Événement sécurité'),

        # Autres
        ('DATA_EXPORT', 'Export données'),
        ('DATA_IMPORT', 'Import données'),
        ('REPORT_GENERATE', 'Génération rapport'),
    )

    SEVERITY_LEVELS = (
        ('LOW', 'Faible'),
        ('MEDIUM', 'Moyen'),
        ('HIGH', 'Élevé'),
        ('CRITICAL', 'Critique'),
    )

    # Informations sur l'action
    action = models.CharField(max_length=100, choices=ACTION_TYPES, verbose_name="Action")
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='LOW', verbose_name="Sévérité")
    description = models.TextField(verbose_name="Description")

    # Utilisateur responsable
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Utilisateur"
    )
    user_role = models.CharField(max_length=20, blank=True, verbose_name="Rôle utilisateur")
    user_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP utilisateur")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")

    # Entité concernée
    entity_type = models.CharField(max_length=100, blank=True, verbose_name="Type d'entité")
    entity_id = models.IntegerField(null=True, blank=True, verbose_name="ID entité")
    entity_name = models.CharField(max_length=200, blank=True, verbose_name="Nom entité")

    # Données avant/après
    old_values = models.JSONField(null=True, blank=True, verbose_name="Anciennes valeurs")
    new_values = models.JSONField(null=True, blank=True, verbose_name="Nouvelles valeurs")
    changed_fields = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        verbose_name="Champs modifiés"
    )

    # Contexte
    request_method = models.CharField(max_length=10, blank=True, verbose_name="Méthode HTTP")
    request_path = models.CharField(max_length=500, blank=True, verbose_name="Chemin requête")
    query_params = models.JSONField(null=True, blank=True, verbose_name="Paramètres requête")

    # Statut
    success = models.BooleanField(default=True, verbose_name="Succès")
    error_message = models.TextField(blank=True, verbose_name="Message d'erreur")
    error_traceback = models.TextField(blank=True, verbose_name="Traceback erreur")

    # Métadonnées
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Horodatage")
    session_id = models.CharField(max_length=100, blank=True, verbose_name="ID session")
    correlation_id = models.UUIDField(null=True, blank=True, verbose_name="ID corrélation")

    # Archivage
    archived = models.BooleanField(default=False, verbose_name="Archivé")
    archive_date = models.DateTimeField(null=True, blank=True, verbose_name="Date archivage")

    class Meta:
        db_table = 'audit_log'
        verbose_name = 'Log audit'
        verbose_name_plural = 'Logs audit'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['action']),
            models.Index(fields=['user']),
            models.Index(fields=['severity']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['success']),
            models.Index(fields=['user_ip']),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.user} - {self.timestamp}"


    app_label = 'audit'
class SecurityEvent(models.Model):
    """Événements de sécurité spécifiques"""
    EVENT_TYPES = (
        ('BRUTE_FORCE_ATTEMPT', 'Tentative force brute'),
        ('SUSPICIOUS_LOGIN', 'Connexion suspecte'),
        ('MULTIPLE_FAILED_LOGINS', 'Multiples échecs connexion'),
        ('UNAUTHORIZED_ACCESS', 'Accès non autorisé'),
        ('DATA_BREACH_ATTEMPT', 'Tentative fuite données'),
        ('MALICIOUS_REQUEST', 'Requête malveillante'),
        ('API_ABUSE', 'Abus API'),
        ('SESSION_HIJACKING', 'Détournement session'),
    )

    SEVERITY_LEVELS = (
        ('LOW', 'Faible'),
        ('MEDIUM', 'Moyen'),
        ('HIGH', 'Élevé'),
        ('CRITICAL', 'Critique'),
    )

    event_type = models.CharField(max_length=100, choices=EVENT_TYPES, verbose_name="Type événement")
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, verbose_name="Sévérité")
    description = models.TextField(verbose_name="Description")

    # Source
    source_ip = models.GenericIPAddressField(verbose_name="IP source")
    source_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Utilisateur source"
    )
    user_agent = models.TextField(blank=True, verbose_name="User Agent")

    # Données de l'événement
    event_data = models.JSONField(default=dict, verbose_name="Données événement")
    request_path = models.CharField(max_length=500, blank=True, verbose_name="Chemin requête")
    request_method = models.CharField(max_length=10, blank=True, verbose_name="Méthode HTTP")
    request_body = models.TextField(blank=True, verbose_name="Corps requête")

    # Statut
    blocked = models.BooleanField(default=False, verbose_name="Bloqué")
    auto_blocked = models.BooleanField(default=False, verbose_name="Auto-bloqué")
    block_reason = models.TextField(blank=True, verbose_name="Raison blocage")

    # Actions prises
    actions_taken = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        verbose_name="Actions entreprises"
    )

    # Notification
    notified_admins = models.BooleanField(default=False, verbose_name="Administrateurs notifiés")
    notification_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Notification envoyée le")

    # Métadonnées
    detected_at = models.DateTimeField(default=timezone.now, verbose_name="Détecté le")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")

    class Meta:
        db_table = 'security_event'
        verbose_name = 'Événement sécurité'
        verbose_name_plural = 'Événements sécurité'
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['detected_at']),
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['source_ip']),
            models.Index(fields=['blocked']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.source_ip} - {self.detected_at}"


    app_label = 'audit'
class AuditPolicy(models.Model):
    """Politiques d'audit configurables"""
    POLICY_TYPES = (
        ('LOG_ALL', 'Tout logger'),
        ('LOG_CRITICAL', 'Logger seulement critique'),
        ('LOG_WITH_EXCLUSIONS', 'Logger avec exclusions'),
        ('LOG_MINIMAL', 'Logger minimal'),
    )

    RETENTION_PERIODS = (
        ('30_DAYS', '30 jours'),
        ('90_DAYS', '90 jours'),
        ('180_DAYS', '180 jours'),
        ('1_YEAR', '1 an'),
        ('3_YEARS', '3 ans'),
        ('PERMANENT', 'Permanent'),
    )

    name = models.CharField(max_length=100, unique=True, verbose_name="Nom")
    policy_type = models.CharField(max_length=50, choices=POLICY_TYPES, verbose_name="Type politique")
    description = models.TextField(blank=True, verbose_name="Description")

    # Configuration
    enabled = models.BooleanField(default=True, verbose_name="Activée")
    retention_period = models.CharField(max_length=20, choices=RETENTION_PERIODS, default='90_DAYS',
                                        verbose_name="Période rétention")

    # Filtres
    included_actions = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        verbose_name="Actions incluses"
    )
    excluded_actions = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        verbose_name="Actions exclues"
    )
    included_users = ArrayField(
        models.CharField(max_length=100),  # IDs ou noms d'utilisateurs
        default=list,
        blank=True,
        verbose_name="Utilisateurs inclus"
    )
    excluded_users = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        verbose_name="Utilisateurs exclus"
    )

    # Niveaux de sévérité
    min_severity = models.CharField(
        max_length=20,
        choices=AuditLog.SEVERITY_LEVELS,
        default='LOW',
        verbose_name="Sévérité minimum"
    )

    # Notifications
    notify_on_critical = models.BooleanField(default=True, verbose_name="Notifier critique")
    notification_emails = ArrayField(
        models.EmailField(),
        default=list,
        blank=True,
        verbose_name="Emails notification"
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Date modification")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Créé par"
    )

    class Meta:
        db_table = 'audit_policy'
        verbose_name = 'Politique audit'
        verbose_name_plural = 'Politiques audit'
        ordering = ['name']

    def __str__(self):
        return self.name


    app_label = 'audit'
class AuditReport(models.Model):
    """Rapports d'audit générés"""
    REPORT_TYPES = (
        ('DAILY', 'Journalier'),
        ('WEEKLY', 'Hebdomadaire'),
        ('MONTHLY', 'Mensuel'),
        ('QUARTERLY', 'Trimestriel'),
        ('YEARLY', 'Annuel'),
        ('CUSTOM', 'Personnalisé'),
    )

    REPORT_FORMATS = (
        ('PDF', 'PDF'),
        ('EXCEL', 'Excel'),
        ('CSV', 'CSV'),
        ('JSON', 'JSON'),
    )

    name = models.CharField(max_length=200, verbose_name="Nom")
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES, verbose_name="Type rapport")
    description = models.TextField(blank=True, verbose_name="Description")

    # Configuration
    format = models.CharField(max_length=10, choices=REPORT_FORMATS, default='PDF', verbose_name="Format")
    parameters = models.JSONField(default=dict, verbose_name="Paramètres")

    # Période
    start_date = models.DateTimeField(verbose_name="Date début")
    end_date = models.DateTimeField(verbose_name="Date fin")

    # Génération
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Généré par"
    )
    generated_at = models.DateTimeField(auto_now_add=True, verbose_name="Généré le")
    generation_duration = models.DurationField(null=True, blank=True, verbose_name="Durée génération")

    # Fichier
    file_path = models.CharField(max_length=500, blank=True, verbose_name="Chemin fichier")
    file_size = models.BigIntegerField(null=True, blank=True, verbose_name="Taille fichier (bytes)")
    download_count = models.IntegerField(default=0, verbose_name="Nombre téléchargements")

    # Statut
    status = models.CharField(max_length=20, default='COMPLETED',
                              verbose_name="Statut")  # PENDING, PROCESSING, COMPLETED, FAILED
    error_message = models.TextField(blank=True, verbose_name="Message erreur")

    # Sécurité
    access_token = models.UUIDField(unique=True, null=True, blank=True, verbose_name="Token accès")
    token_expires = models.DateTimeField(null=True, blank=True, verbose_name="Token expire le")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")

    class Meta:
        db_table = 'audit_report'
        verbose_name = 'Rapport audit'
        verbose_name_plural = 'Rapports audit'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['generated_at']),
            models.Index(fields=['report_type']),
            models.Index(fields=['generated_by']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_report_type_display()}"


    app_label = 'audit'
class AuditArchive(models.Model):
    """Archive des logs d'audit anciens"""
    archive_name = models.CharField(max_length=200, unique=True, verbose_name="Nom archive")
    description = models.TextField(blank=True, verbose_name="Description")

    # Période archivée
    start_date = models.DateTimeField(verbose_name="Date début période")
    end_date = models.DateTimeField(verbose_name="Date fin période")

    # Données
    log_count = models.IntegerField(default=0, verbose_name="Nombre logs")
    total_size = models.BigIntegerField(default=0, verbose_name="Taille totale (bytes)")

    # Fichier archive
    archive_file = models.FileField(upload_to='audit_archives/', verbose_name="Fichier archive")
    compression_format = models.CharField(max_length=20, default='GZIP', verbose_name="Format compression")

    # Localisation
    storage_location = models.CharField(max_length=500, blank=True, verbose_name="Emplacement stockage")
    storage_type = models.CharField(max_length=50, default='LOCAL',
                                    verbose_name="Type stockage")  # LOCAL, S3, AZURE, etc.

    # Sécurité
    encryption_enabled = models.BooleanField(default=False, verbose_name="Chiffrement activé")
    encryption_key_hash = models.CharField(max_length=500, blank=True, verbose_name="Hash clé chiffrement")

    # Métadonnées
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Créé par"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date création")
    archived_at = models.DateTimeField(verbose_name="Date archivage")

    # Validation
    checksum = models.CharField(max_length=128, blank=True, verbose_name="Checksum")
    verified = models.BooleanField(default=False, verbose_name="Vérifié")
    verification_date = models.DateTimeField(null=True, blank=True, verbose_name="Date vérification")

    class Meta:
        db_table = 'audit_archive'
        verbose_name = 'Archive audit'
        verbose_name_plural = 'Archives audit'
        ordering = ['-archived_at']
        indexes = [
            models.Index(fields=['archived_at']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.archive_name} ({self.start_date} - {self.end_date})"

    app_label = 'audit'