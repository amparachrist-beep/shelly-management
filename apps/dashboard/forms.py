from django import forms
from django.forms import ModelForm, Form
from django.utils.translation import gettext_lazy as _
from .models import (
    UserDashboardLayout, DashboardWidget, DashboardNotification,
    DashboardQuickAction, DashboardAnalytics
)


class DashboardLayoutForm(ModelForm):
    """Formulaire de configuration du layout"""

    class Meta:
        model = UserDashboardLayout
        fields = ['theme', 'density', 'auto_refresh', 'refresh_interval', 'default_view']
        widgets = {
            'theme': forms.Select(attrs={'class': 'form-select'}),
            'density': forms.Select(attrs={'class': 'form-select'}),
            'auto_refresh': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'refresh_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 30,
                'max': 3600,
                'step': 30
            }),
            'default_view': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'theme': _('Thème visuel'),
            'density': _('Densité d\'affichage'),
            'auto_refresh': _('Rafraîchissement automatique'),
            'refresh_interval': _('Intervalle (secondes)'),
            'default_view': _('Vue par défaut'),
        }
        help_texts = {
            'refresh_interval': _('Intervalle en secondes (30s minimum, 3600s maximum)'),
            'default_view': _('Vue affichée lors de l\'ouverture du dashboard'),
        }


class WidgetConfigurationForm(Form):
    """Formulaire générique de configuration de widget"""
    # Champs communs à tous les widgets
    titre = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label=_("Titre personnalisé"),
        max_length=100
    )

    periode = forms.ChoiceField(
        choices=[
            ('7j', _('7 derniers jours')),
            ('30j', _('30 derniers jours')),
            ('3m', _('3 derniers mois')),
            ('6m', _('6 derniers mois')),
            ('1a', _('1 an')),
            ('personnalise', _('Personnalisée')),
        ],
        initial='30j',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Période")
    )

    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_("Date début")
    )

    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_("Date fin")
    )

    taille = forms.ChoiceField(
        choices=[
            ('small', _('Petit (1x1)')),
            ('medium', _('Moyen (2x2)')),
            ('large', _('Large (3x3)')),
            ('xlarge', _('Très large (4x4)')),
        ],
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Taille")
    )

    auto_refresh = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Rafraîchissement automatique")
    )

    refresh_interval = forms.IntegerField(
        required=False,
        initial=60,
        min_value=10,
        max_value=3600,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label=_("Intervalle rafraîchissement (secondes)")
    )

    def __init__(self, *args, **kwargs):
        widget_type = kwargs.pop('widget_type', None)
        super().__init__(*args, **kwargs)

        # Ajouter des champs spécifiques selon le type de widget
        if widget_type == 'CONSOMMATION_CHART':
            self.fields['type_graphique'] = forms.ChoiceField(
                choices=[
                    ('line', _('Ligne')),
                    ('bar', _('Barres')),
                    ('area', _('Aire')),
                    ('pie', _('Camembert')),
                ],
                initial='line',
                widget=forms.Select(attrs={'class': 'form-select'}),
                label=_("Type de graphique")
            )
            self.fields['afficher_moyenne'] = forms.BooleanField(
                required=False,
                initial=True,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                label=_("Afficher la moyenne")
            )

        elif widget_type == 'STATS_GLOBALES':
            self.fields['show_percentages'] = forms.BooleanField(
                required=False,
                initial=True,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                label=_("Afficher les pourcentages")
            )
            self.fields['show_comparison'] = forms.BooleanField(
                required=False,
                initial=True,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
                label=_("Afficher la comparaison")
            )

        elif widget_type == 'ALERTES_ACTIVES':
            self.fields['niveau_alerte'] = forms.MultipleChoiceField(
                choices=[
                    ('INFO', _('Information')),
                    ('WARNING', _('Avertissement')),
                    ('CRITIQUE', _('Critique')),
                ],
                initial=['WARNING', 'CRITIQUE'],
                widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
                label=_("Niveaux d'alerte")
            )
            self.fields['max_elements'] = forms.IntegerField(
                required=False,
                initial=10,
                min_value=1,
                max_value=50,
                widget=forms.NumberInput(attrs={'class': 'form-control'}),
                label=_("Nombre maximum d'éléments")
            )


class NotificationFilterForm(Form):
    """Formulaire de filtrage des notifications"""
    read_status = forms.ChoiceField(
        choices=[
            ('', _('Tous')),
            ('True', _('Lues')),
            ('False', _('Non lues')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Statut")
    )

    notification_type = forms.ChoiceField(
        choices=[
            ('', _('Tous les types')),
            ('INFO', _('Information')),
            ('SUCCESS', _('Succès')),
            ('WARNING', _('Avertissement')),
            ('ERROR', _('Erreur')),
            ('SYSTEM', _('Système')),
            ('ALERT', _('Alerte')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Type")
    )

    priority = forms.ChoiceField(
        choices=[
            ('', _('Toutes priorités')),
            ('0', _('Normale')),
            ('1', _('Importante')),
            ('2', _('Urgente')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Priorité")
    )

    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_("Date début")
    )

    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_("Date fin")
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Rechercher...')
        }),
        label=_("Recherche")
    )


class QuickActionForm(ModelForm):
    """Formulaire pour les actions rapides"""

    class Meta:
        model = DashboardQuickAction
        fields = [
            'name', 'action_type', 'description', 'icon', 'color',
            'badge_text', 'badge_color', 'url', 'method',
            'requires_confirmation', 'confirmation_message',
            'shortcut_key', 'allowed_roles', 'required_permission',
            'enabled', 'visible', 'order', 'category'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'action_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'icon': forms.TextInput(attrs={'class': 'form-control'}),
            'color': forms.Select(attrs={'class': 'form-select'}),
            'badge_text': forms.TextInput(attrs={'class': 'form-control'}),
            'badge_color': forms.Select(attrs={'class': 'form-select'}),
            'url': forms.TextInput(attrs={'class': 'form-control'}),
            'method': forms.Select(attrs={'class': 'form-select'}),
            'requires_confirmation': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'confirmation_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'shortcut_key': forms.TextInput(attrs={'class': 'form-control'}),
            'allowed_roles': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'required_permission': forms.TextInput(attrs={'class': 'form-control'}),
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'visible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': _('Nom'),
            'action_type': _('Type d\'action'),
            'description': _('Description'),
            'icon': _('Icône'),
            'color': _('Couleur'),
            'badge_text': _('Texte badge'),
            'badge_color': _('Couleur badge'),
            'url': _('URL'),
            'method': _('Méthode HTTP'),
            'requires_confirmation': _('Requiert confirmation'),
            'confirmation_message': _('Message confirmation'),
            'shortcut_key': _('Raccourci clavier'),
            'allowed_roles': _('Rôles autorisés'),
            'required_permission': _('Permission requise'),
            'enabled': _('Activé'),
            'visible': _('Visible'),
            'order': _('Ordre'),
            'category': _('Catégorie'),
        }


class WidgetCreateForm(ModelForm):
    """Formulaire de création de widget (admin)"""

    class Meta:
        model = DashboardWidget
        fields = [
            'name', 'widget_type', 'description', 'icon',
            'config', 'default_position', 'default_size',
            'allowed_roles', 'enabled_by_default', 'requires_permission', 'order'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'widget_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'icon': forms.TextInput(attrs={'class': 'form-control'}),
            'config': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': _('Configuration JSON du widget')
            }),
            'default_position': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('{"x": 0, "y": 0, "w": 2, "h": 2}')
            }),
            'default_size': forms.Select(attrs={'class': 'form-select'}),
            'allowed_roles': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'enabled_by_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'requires_permission': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': _('Nom du widget'),
            'widget_type': _('Type de widget'),
            'description': _('Description'),
            'icon': _('Icône'),
            'config': _('Configuration JSON'),
            'default_position': _('Position par défaut'),
            'default_size': _('Taille par défaut'),
            'allowed_roles': _('Rôles autorisés'),
            'enabled_by_default': _('Activé par défaut'),
            'requires_permission': _('Requiert permission'),
            'order': _('Ordre d\'affichage'),
        }


class DashboardAnalyticsForm(ModelForm):
    """Formulaire pour les analytics du dashboard"""

    class Meta:
        model = DashboardAnalytics
        fields = [
            'most_used_widgets', 'most_frequent_actions',
            'access_frequency', 'detected_preferences'
        ]
        widgets = {
            'most_used_widgets': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'readonly': True
            }),
            'most_frequent_actions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'readonly': True
            }),
            'access_frequency': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'readonly': True
            }),
            'detected_preferences': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'readonly': True
            }),
        }
        labels = {
            'most_used_widgets': _('Widgets les plus utilisés'),
            'most_frequent_actions': _('Actions les plus fréquentes'),
            'access_frequency': _('Fréquence d\'accès'),
            'detected_preferences': _('Préférences détectées'),
        }


class ExportDataForm(Form):
    """Formulaire d'export de données"""
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('excel', 'Excel'),
        ('pdf', 'PDF'),
    ]

    DATA_CHOICES = [
        ('stats', _('Statistiques')),
        ('notifications', _('Notifications')),
        ('activities', _('Activités')),
        ('consumption', _('Consommation')),
        ('payments', _('Paiements')),
    ]

    data_type = forms.ChoiceField(
        choices=DATA_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Type de données")
    )

    export_format = forms.ChoiceField(
        choices=FORMAT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Format d'export")
    )

    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_("Date début")
    )

    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label=_("Date fin")
    )

    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Inclure les graphiques")
    )

    compress = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label=_("Compresser le fichier")
    )


class DashboardSearchForm(Form):
    """Formulaire de recherche dans le dashboard"""
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _('Rechercher dans le dashboard...')
        }),
        label=_("Recherche"),
        max_length=200
    )

    search_type = forms.ChoiceField(
        choices=[
            ('all', _('Tout')),
            ('widgets', _('Widgets')),
            ('actions', _('Actions')),
            ('reports', _('Rapports')),
            ('notifications', _('Notifications')),
        ],
        initial='all',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_("Type de recherche")
    )

    def clean_query(self):
        query = self.cleaned_data.get('query', '').strip()
        if len(query) < 2 and query:
            raise forms.ValidationError(_("La recherche doit contenir au moins 2 caractères"))
        return query