from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, timedelta

from .models import AuditLog, SecurityEvent, AuditPolicy, AuditReport, AuditArchive
from apps.users.models import CustomUser as User


class AuditLogFilterForm(forms.Form):
    """Formulaire de filtrage des logs d'audit"""
    action = forms.ChoiceField(
        choices=[('', 'Toutes les actions')] + list(AuditLog.ACTION_TYPES),
        required=False,
        label="Action",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    severity = forms.ChoiceField(
        choices=[('', 'Toutes sévérités')] + list(AuditLog.SEVERITY_LEVELS),
        required=False,
        label="Sévérité",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Utilisateur",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_debut = forms.DateField(
        required=False,
        label="Date début",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    date_fin = forms.DateField(
        required=False,
        label="Date fin",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    success = forms.ChoiceField(
        choices=[('', 'Tous'), ('true', 'Succès'), ('false', 'Échec')],
        required=False,
        label="Statut",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    entity_type = forms.CharField(
        required=False,
        label="Type d'entité",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: USER, COMPTEUR'
        })
    )
    search = forms.CharField(
        required=False,
        label="Recherche texte",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Description, IP, nom...'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limiter les utilisateurs aux derniers actifs
        self.fields['user'].queryset = User.objects.filter(
            id__in=AuditLog.objects.values_list('user_id', flat=True).distinct()
        ).order_by('username')

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_debut and date_fin and date_debut > date_fin:
            raise ValidationError("La date de début ne peut pas être postérieure à la date de fin")

        return cleaned_data


class SecurityEventFilterForm(forms.Form):
    """Formulaire de filtrage des événements de sécurité"""
    event_type = forms.ChoiceField(
        choices=[('', 'Tous les types')] + list(SecurityEvent.EVENT_TYPES),
        required=False,
        label="Type d'événement",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    severity = forms.ChoiceField(
        choices=[('', 'Toutes sévérités')] + list(SecurityEvent.SEVERITY_LEVELS),
        required=False,
        label="Sévérité",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    blocked = forms.ChoiceField(
        choices=[('', 'Tous'), ('true', 'Bloqués'), ('false', 'Non bloqués')],
        required=False,
        label="Bloqué",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_debut = forms.DateField(
        required=False,
        label="Date début",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    date_fin = forms.DateField(
        required=False,
        label="Date fin",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    source_ip = forms.CharField(
        required=False,
        label="IP source",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: 192.168.1.1'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_debut and date_fin and date_debut > date_fin:
            raise ValidationError("La date de début ne peut pas être postérieure à la date de fin")

        return cleaned_data


class AuditPolicyForm(ModelForm):
    """Formulaire pour les politiques d'audit"""

    class Meta:
        model = AuditPolicy
        fields = [
            'name', 'policy_type', 'description', 'enabled', 'retention_period',
            'included_actions', 'excluded_actions', 'included_users', 'excluded_users',
            'min_severity', 'notify_on_critical', 'notification_emails'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'policy_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'retention_period': forms.Select(attrs={'class': 'form-control'}),
            'included_actions': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 10}),
            'excluded_actions': forms.SelectMultiple(attrs={'class': 'form-control', 'size': 10}),
            'included_users': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'IDs ou noms séparés par des virgules'
            }),
            'excluded_users': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'IDs ou noms séparés par des virgules'
            }),
            'min_severity': forms.Select(attrs={'class': 'form-control'}),
            'notify_on_critical': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notification_emails': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'emails@example.com, autre@domaine.com'
            }),
        }
        labels = {
            'included_actions': 'Actions à inclure',
            'excluded_actions': 'Actions à exclure',
            'included_users': 'Utilisateurs inclus',
            'excluded_users': 'Utilisateurs exclus',
            'notification_emails': 'Emails pour notifications',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pré-remplir les choix d'actions
        self.fields['included_actions'].choices = AuditLog.ACTION_TYPES
        self.fields['excluded_actions'].choices = AuditLog.ACTION_TYPES

    def clean_notification_emails(self):
        emails = self.cleaned_data.get('notification_emails', [])
        if emails:
            # Valider les emails
            email_list = [email.strip() for email in emails if email.strip()]
            for email in email_list:
                try:
                    forms.EmailField().clean(email)
                except ValidationError:
                    raise ValidationError(f"Email invalide: {email}")
            return email_list
        return []


class AuditReportForm(ModelForm):
    """Formulaire pour générer des rapports d'audit"""

    class Meta:
        model = AuditReport
        fields = ['name', 'report_type', 'description', 'format', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'format': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
        }
        labels = {
            'start_date': 'Date/heure début',
            'end_date': 'Date/heure fin',
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("La date de début ne peut pas être postérieure à la date de fin")

            # Limiter à une période maximale (1 an)
            if (end_date - start_date).days > 365:
                raise ValidationError("La période ne peut pas dépasser 1 an")

        return cleaned_data


class ArchiveFilterForm(forms.Form):
    """Formulaire de filtrage des archives"""
    date_debut = forms.DateField(
        required=False,
        label="Date début période",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    date_fin = forms.DateField(
        required=False,
        label="Date fin période",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    storage_type = forms.ChoiceField(
        choices=[('', 'Tous')] + [('LOCAL', 'Local'), ('S3', 'S3'), ('AZURE', 'Azure')],
        required=False,
        label="Type de stockage",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class DateRangeForm(forms.Form):
    """Formulaire pour sélectionner une période"""
    start_date = forms.DateField(
        required=True,
        label="Date début",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    end_date = forms.DateField(
        required=True,
        label="Date fin",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    description = forms.CharField(
        required=False,
        label="Description (optionnel)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("La date de début ne peut pas être postérieure à la date de fin")

            # Vérifier que la période n'est pas dans le futur
            if end_date > date.today():
                raise ValidationError("La date de fin ne peut pas être dans le futur")

        return cleaned_data


class PurgeForm(forms.Form):
    """Formulaire pour purger les logs"""
    retention_days = forms.IntegerField(
        min_value=1,
        max_value=3650,
        initial=90,
        label="Conserver les logs pendant (jours)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    confirm = forms.BooleanField(
        required=True,
        label="Je confirme la suppression définitive des anciens logs",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )