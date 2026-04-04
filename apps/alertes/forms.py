from django import forms
from django.core.exceptions import ValidationError
from .models import Alerte, RegleAlerte
from apps.users.models import CustomUser
from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation




class TraiterAlerteForm(forms.ModelForm):
    class Meta:
        model = Alerte
        fields = ['statut', 'notes_traitement']
        widgets = {
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'notes_traitement': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Notes sur le traitement...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limiter les choix de statut pour le traitement
        self.fields['statut'].choices = [
            ('LU', 'Lue'),
            ('TRAITEE', 'Traitée'),
            ('IGNOREE', 'Ignorée'),
        ]


class RegleAlerteForm(forms.ModelForm):
    class Meta:
        model = RegleAlerte
        fields = ['nom', 'type_alerte', 'seuil', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={
                'placeholder': 'Ex: Consommation anormale supérieure à 500 kWh'
            }),
            'type_alerte': forms.Select(attrs={'class': 'form-select'}),
            'seuil': forms.NumberInput(attrs={
                'step': '0.01',
                'placeholder': 'Seuil de déclenchement'
            }),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'actif': 'Règle active',
        }

    def clean_seuil(self):
        seuil = self.cleaned_data.get('seuil')
        if seuil <= 0:
            raise ValidationError("Le seuil doit être positif.")
        return seuil

    def clean_nom(self):
        nom = self.cleaned_data.get('nom')
        # Vérifier si une règle avec le même nom existe déjà (sauf instance actuelle)
        qs = RegleAlerte.objects.filter(nom=nom)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Une règle avec ce nom existe déjà.")
        return nom


class FiltreAlerteForm(forms.Form):
    """Formulaire de filtrage des alertes"""
    type_alerte = forms.ChoiceField(
        choices=[('', 'Tous les types')] + list(Alerte.TYPE_ALERTE),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    statut = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + list(Alerte.STATUT_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    niveau = forms.ChoiceField(
        choices=[('', 'Tous les niveaux')] + list(Alerte.NIVEAU_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )