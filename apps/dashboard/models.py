from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class DashboardWidget(models.Model):
    """Widgets configurables pour les tableaux de bord"""

    class WidgetType(models.TextChoices):
        CONSOMMATION_CHART = 'CONSOMMATION_CHART', _('Graphique consommation')
        FACTURE_STATUS = 'FACTURE_STATUS', _('Statut factures')
        PAIEMENTS_RECENTS = 'PAIEMENTS_RECENTS', _('Paiements récents')
        ALERTES_ACTIVES = 'ALERTES_ACTIVES', _('Alertes actives')
        STATS_GLOBALES = 'STATS_GLOBALES', _('Statistiques globales')
        MAP_LOCALISATION = 'MAP_LOCALISATION', _('Carte localisation')
        PERFORMANCE_AGENT = 'PERFORMANCE_AGENT', _('Performance agent')
        PREDICTION_CONSO = 'PREDICTION_CONSO', _('Prédiction consommation')
        TASKS_PENDING = 'TASKS_PENDING', _('Tâches en attente')
        REVENUE_TREND = 'REVENUE_TREND', _('Tendance revenus')

    class RoleChoices(models.TextChoices):
        ADMIN = 'ADMIN', _('Administrateur')
        AGENT = 'AGENT', _('Agent terrain')
        CLIENT = 'CLIENT', _('Client')
        ALL = 'ALL', _('Tous')

    name = models.CharField(max_length=100, verbose_name=_("Nom du widget"))
    widget_type = models.CharField(max_length=50, choices=WidgetType.choices, verbose_name=_("Type de widget"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    icon = models.CharField(max_length=50, blank=True, verbose_name=_("Icône"), default='chart-line')

    # Configuration du widget
    config = models.JSONField(default=dict, verbose_name=_("Configuration"))
    default_position = models.JSONField(
        default=dict,
        verbose_name=_("Position par défaut"),
        help_text=_("Format: {x: 0, y: 0, w: 2, h: 2}")
    )
    default_size = models.CharField(
        max_length=20,
        default='2x2',
        verbose_name=_("Taille par défaut"),
        help_text=_("1x1, 2x2, 3x2, etc.")
    )

    # Permissions
    allowed_roles = ArrayField(
        models.CharField(max_length=20, choices=RoleChoices.choices),
        default=list,
        blank=True,
        verbose_name=_("Rôles autorisés")
    )

    # Visibilité
    enabled_by_default = models.BooleanField(default=True, verbose_name=_("Activé par défaut"))
    requires_permission = models.BooleanField(default=False, verbose_name=_("Requiert permission spécifique"))
    order = models.IntegerField(default=0, verbose_name=_("Ordre d'affichage"))

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Date création"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Date modification"))

    class Meta:
        app_label = 'dashboard'
        db_table = 'dashboard_widget'
        verbose_name = _('Widget tableau de bord')
        verbose_name_plural = _('Widgets tableaux de bord')
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['widget_type']),
            models.Index(fields=['allowed_roles']),
            models.Index(fields=['enabled_by_default']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_widget_type_display()})"

    def is_allowed_for_user(self, user):
        """Vérifie si le widget est autorisé pour l'utilisateur"""
        if 'ALL' in self.allowed_roles:
            return True

        if user.role in self.allowed_roles:
            return True

        return False


class UserDashboardLayout(models.Model):
    """Configuration du tableau de bord par utilisateur"""

    class ThemeChoices(models.TextChoices):
        LIGHT = 'light', _('Clair')
        DARK = 'dark', _('Sombre')
        AUTO = 'auto', _('Automatique')

    class DensityChoices(models.TextChoices):
        COMPACT = 'compact', _('Compact')
        COMFORTABLE = 'comfortable', _('Confortable')
        SPACIOUS = 'spacious', _('Spacieux')

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_layout',
        verbose_name=_("Utilisateur")
    )

    # Layout personnalisé (stockage des positions des widgets)
    layout_config = models.JSONField(
        default=list,
        verbose_name=_("Configuration layout"),
        help_text=_("Configuration JSON des positions des widgets")
    )

    # Préférences d'affichage
    theme = models.CharField(
        max_length=50,
        choices=ThemeChoices.choices,
        default='light',
        verbose_name=_("Thème")
    )
    density = models.CharField(
        max_length=20,
        choices=DensityChoices.choices,
        default='comfortable',
        verbose_name=_("Densité")
    )
    auto_refresh = models.BooleanField(default=True, verbose_name=_("Rafraîchissement automatique"))
    refresh_interval = models.IntegerField(
        default=300,
        verbose_name=_("Intervalle rafraîchissement (secondes)"),
        help_text=_("En secondes, 300 = 5 minutes")
    )
    default_view = models.CharField(
        max_length=50,
        default='overview',
        verbose_name=_("Vue par défaut"),
        help_text=_("Vue affichée par défaut lors de l'ouverture")
    )

    # Widgets activés/désactivés
    enabled_widgets = models.ManyToManyField(
        DashboardWidget,
        blank=True,
        related_name='user_preferences',
        verbose_name=_("Widgets activés")
    )

    # Métadonnées
    last_accessed = models.DateTimeField(auto_now=True, verbose_name=_("Dernier accès"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Date création"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Date modification"))

    class Meta:
        app_label = 'dashboard'
        db_table = 'user_dashboard_layout'
        verbose_name = _('Layout tableau de bord utilisateur')
        verbose_name_plural = _('Layouts tableaux de bord utilisateurs')
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['last_accessed']),
        ]

    def __str__(self):
        return f"Dashboard de {self.user.email}"

    def get_widgets_for_role(self):
        """Récupère les widgets disponibles pour le rôle de l'utilisateur"""
        return DashboardWidget.objects.filter(
            allowed_roles__contains=[self.user.role] if self.user.role != 'ALL' else 'ALL'
        )



class DashboardNotification(models.Model):
    """Notifications pour le tableau de bord"""

    class NotificationType(models.TextChoices):
        INFO = 'INFO', _('Information')
        SUCCESS = 'SUCCESS', _('Succès')
        WARNING = 'WARNING', _('Avertissement')
        ERROR = 'ERROR', _('Erreur')
        SYSTEM = 'SYSTEM', _('Système')
        ALERT = 'ALERT', _('Alerte')

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_notifications',
        verbose_name=_("Utilisateur")
    )
    title = models.CharField(max_length=200, verbose_name=_("Titre"))
    message = models.TextField(verbose_name=_("Message"))
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default='INFO',
        verbose_name=_("Type")
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Icône"),
        help_text=_("Nom de l'icône FontAwesome (sans le préfixe fa-)")
    )
    priority = models.IntegerField(
        default=0,
        verbose_name=_("Priorité"),
        help_text=_("0=Normal, 1=Important, 2=Urgent")
    )

    # Actions
    action_url = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("URL action")
    )
    action_label = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Libellé action")
    )
    action_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Données d'action")
    )

    # Statut
    read = models.BooleanField(default=False, verbose_name=_("Lu"))
    archived = models.BooleanField(default=False, verbose_name=_("Archivé"))
    acknowledged = models.BooleanField(default=False, verbose_name=_("Accusé réception"))

    # Données supplémentaires
    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Données supplémentaires")
    )

    # Expiration
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Expire le")
    )

    # Source de la notification
    source_module = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Module source")
    )
    source_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("ID source")
    )

    # Métadonnées
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notifications',
        verbose_name=_("Créé par")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Date création"))

    class Meta:
        app_label = 'dashboard'
        db_table = 'dashboard_notification'
        verbose_name = _('Notification tableau de bord')
        verbose_name_plural = _('Notifications tableaux de bord')
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['user', 'read', 'created_at']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['priority']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['source_module', 'source_id']),
        ]

    def __str__(self):
        return f"{self.title} - {self.user.email}"

    def mark_as_read(self):
        """Marquer la notification comme lue"""
        self.read = True
        self.save(update_fields=['read'])

    def is_expired(self):
        """Vérifier si la notification est expirée"""
        if self.expires_at:
            from django.utils import timezone
            return timezone.now() > self.expires_at
        return False




class DashboardQuickAction(models.Model):
    """Actions rapides pour le dashboard"""

    class ActionType(models.TextChoices):
        CREATE_MENAGE = 'CREATE_MENAGE', _('Créer ménage')
        CREATE_COMPTEUR = 'CREATE_COMPTEUR', _('Créer compteur')
        ENREGISTRER_PAIEMENT = 'ENREGISTRER_PAIEMENT', _('Enregistrer paiement')
        GENERER_FACTURE = 'GENERER_FACTURE', _('Générer facture')
        CONSULTER_CONSO = 'CONSULTER_CONSO', _('Consulter consommation')
        ENVOYER_RELANCE = 'ENVOYER_RELANCE', _('Envoyer relance')
        GENERER_RAPPORT = 'GENERER_RAPPORT', _('Générer rapport')
        DIAGNOSTIC_SHELLY = 'DIAGNOSTIC_SHELLY', _('Diagnostic Shelly')
        CREER_ALERTE = 'CREER_ALERTE', _('Créer alerte')
        ASSIGNER_AGENT = 'ASSIGNER_AGENT', _('Assigner agent')
        IMPORTER_DATA = 'IMPORTER_DATA', _('Importer données')

    class RoleChoices(models.TextChoices):
        ADMIN = 'ADMIN', _('Administrateur')
        AGENT = 'AGENT', _('Agent terrain')
        CLIENT = 'CLIENT', _('Client')
        ALL = 'ALL', _('Tous')

    name = models.CharField(max_length=100, verbose_name=_("Nom"))
    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        verbose_name=_("Type d'action")
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    icon = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Icône"),
        help_text=_("Nom de l'icône FontAwesome (sans le préfixe fa-)")
    )
    color = models.CharField(
        max_length=20,
        default='primary',
        verbose_name=_("Couleur"),
        help_text=_("Couleur Bootstrap: primary, success, warning, etc.")
    )
    badge_text = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Texte badge"),
        help_text=_("Texte affiché sur le badge (ex: 'New', 'Hot', etc.)")
    )
    badge_color = models.CharField(
        max_length=20,
        default='danger',
        verbose_name=_("Couleur badge")
    )

    # Configuration
    url = models.CharField(
        max_length=500,
        verbose_name=_("URL"),
        help_text=_("URL de l'action, peut inclure des variables: {user_id}, {today}, etc.")
    )
    method = models.CharField(
        max_length=10,
        default='GET',
        verbose_name=_("Méthode HTTP")
    )
    requires_confirmation = models.BooleanField(
        default=False,
        verbose_name=_("Requiert confirmation")
    )
    confirmation_message = models.TextField(
        blank=True,
        verbose_name=_("Message confirmation")
    )
    shortcut_key = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Raccourci clavier"),
        help_text=_("Ex: 'Ctrl+Shift+A'")
    )

    # Permissions
    allowed_roles = ArrayField(
        models.CharField(max_length=20, choices=RoleChoices.choices),
        default=list,
        blank=True,
        verbose_name=_("Rôles autorisés")
    )
    required_permission = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Permission requise")
    )

    # Visibilité
    enabled = models.BooleanField(default=True, verbose_name=_("Activé"))
    visible = models.BooleanField(default=True, verbose_name=_("Visible"))
    order = models.IntegerField(default=0, verbose_name=_("Ordre"))
    category = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Catégorie"),
        help_text=_("Pour regrouper les actions")
    )

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Date création"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Date modification"))

    class Meta:
        app_label = 'dashboard'
        db_table = 'dashboard_quick_action'
        verbose_name = _('Action rapide dashboard')
        verbose_name_plural = _('Actions rapides dashboard')
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['action_type']),
            models.Index(fields=['allowed_roles']),
            models.Index(fields=['enabled', 'visible']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.name

    def is_allowed_for_user(self, user):
        """Vérifie si l'action est autorisée pour l'utilisateur"""
        if not self.enabled or not self.visible:
            return False

        if 'ALL' in self.allowed_roles:
            return True

        if user.role in self.allowed_roles:
            return True

        return False


