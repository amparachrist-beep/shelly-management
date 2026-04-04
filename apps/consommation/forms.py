from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, datetime
from decimal import Decimal

from .models import Consommation
from apps.compteurs.models import Compteur
from apps.menages.models import Menage


class ConsommationForm(ModelForm):
    """Formulaire de création/modification de consommation"""

    class Meta:
        model = Consommation
        fields = [
            'compteur', 'periode', 'index_debut_periode', 'index_fin_periode',
            'phase_1_kwh', 'phase_2_kwh', 'phase_3_kwh',
            'puissance_max_kw', 'puissance_moyenne_kw', 'facture_charge',
            'details_journaliers', 'source', 'statut', 'anomalie', 'notes'
        ]
        widgets = {
            'periode': forms.DateInput(
                attrs={'type': 'month', 'class': 'form-control'},
                format='%Y-%m'
            ),
            'index_debut_periode': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 1500.50'
            }),
            'index_fin_periode': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 1650.75'
            }),
            'phase_1_kwh': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 45.25'
            }),
            'phase_2_kwh': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 48.30'
            }),
            'phase_3_kwh': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 56.20'
            }),
            'puissance_max_kw': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 3.5'
            }),
            'puissance_moyenne_kw': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 1.2'
            }),
            'facture_charge': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Ex: 80.00'
            }),
            'details_journaliers': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Format JSON: [{"jour": 1, "consommation": 10.5, "puissance_max": 2.3}, ...]'
            }),
            'source': forms.Select(attrs={'class': 'form-control'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'anomalie': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Décrivez l\'anomalie détectée...'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Notes, observations ou commentaires...'
            }),
        }
        labels = {
            'index_debut_periode': 'Index début période (kWh)',
            'index_fin_periode': 'Index fin période (kWh)',
            'phase_1_kwh': 'Consommation Phase 1 (kWh)',
            'phase_2_kwh': 'Consommation Phase 2 (kWh)',
            'phase_3_kwh': 'Consommation Phase 3 (kWh)',
            'puissance_max_kw': 'Puissance maximale (kW)',
            'puissance_moyenne_kw': 'Puissance moyenne (kW)',
            'facture_charge': 'Facture de charge (%)',
            'details_journaliers': 'Détails journaliers (JSON)',
            'source': 'Source des données',
            'statut': 'Statut',
            'anomalie': 'Description de l\'anomalie',
            'notes': 'Notes générales',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Format pour le champ période (affichage mois uniquement)
        if 'periode' in self.fields:
            self.fields['periode'].input_formats = ['%Y-%m']

        # Limiter les compteurs selon l'utilisateur
        if self.user:
            if self.user.is_admin:
                compteurs = Compteur.objects.all()
            elif self.user.is_agent:
                compteurs = Compteur.objects.all()  # ou selon assignation
            else:
                try:
                    menage = Menage.objects.get(utilisateur=self.user)
                    compteurs = Compteur.objects.filter(menage=menage)
                except Menage.DoesNotExist:
                    compteurs = Compteur.objects.none()

            self.fields['compteur'].queryset = compteurs
            self.fields['compteur'].widget.attrs['class'] = 'form-control'

        # Ajouter des help_text pour plus de clarté
        self.fields['consommation_kwh'] = forms.DecimalField(
            required=False,
            label='Consommation calculée (kWh)',
            widget=forms.NumberInput(attrs={
                'class': 'form-control',
                'readonly': True,
                'placeholder': 'Calculé automatiquement'
            }),
            help_text='Calculé automatiquement: index_fin - index_debut'
        )

        # Pré-remplir la consommation calculée si instance existe
        if self.instance and self.instance.pk:
            self.fields['consommation_kwh'].initial = self.instance.consommation_kwh

    def clean_periode(self):
        """Validation du champ période"""
        periode = self.cleaned_data.get('periode')
        if periode:
            # S'assurer que la période est le premier jour du mois
            if periode.day != 1:
                periode = periode.replace(day=1)

            # Valider que la période n'est pas dans le futur
            if periode > date.today():
                raise ValidationError("La période ne peut pas être dans le futur.")

        return periode

    def clean_index_debut_periode(self):
        """Validation de l'index début"""
        index = self.cleaned_data.get('index_debut_periode')
        if index is not None:
            if index < 0:
                raise ValidationError("L'index ne peut pas être négatif.")
        return index

    def clean_index_fin_periode(self):
        """Validation de l'index fin"""
        index = self.cleaned_data.get('index_fin_periode')
        if index is not None:
            if index < 0:
                raise ValidationError("L'index ne peut pas être négatif.")
        return index

    def clean(self):
        cleaned_data = super().clean()
        index_debut = cleaned_data.get('index_debut_periode')
        index_fin = cleaned_data.get('index_fin_periode')
        compteur = cleaned_data.get('compteur')
        periode = cleaned_data.get('periode')

        # Validation des index
        if index_debut and index_fin:
            if index_fin < index_debut:
                raise ValidationError({
                    'index_fin_periode': "L'index de fin doit être supérieur ou égal à l'index de début"
                })

            # Calcul et validation de la consommation
            consommation = index_fin - index_debut
            if consommation < 0:
                raise ValidationError("La consommation calculée ne peut pas être négative.")

            if consommation > 10000:  # Limite arbitraire de 10,000 kWh
                self.add_warning("consommation_kwh",
                                 "La consommation calculée semble anormalement élevée.")

            cleaned_data['_consommation_kwh'] = consommation

        # Validation d'unicité
        if compteur and periode:
            qs = Consommation.objects.filter(compteur=compteur, periode=periode)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError({
                    'compteur': f"Une consommation existe déjà pour le compteur {compteur} "
                                f"sur la période {periode.strftime('%B %Y')}",
                    'periode': "Période déjà utilisée pour ce compteur"
                })

        # Validation des phases
        phase_1 = cleaned_data.get('phase_1_kwh', 0) or 0
        phase_2 = cleaned_data.get('phase_2_kwh', 0) or 0
        phase_3 = cleaned_data.get('phase_3_kwh', 0) or 0

        if '_consommation_kwh' in cleaned_data:
            total_phases = phase_1 + phase_2 + phase_3
            consommation_totale = cleaned_data['_consommation_kwh']

            if total_phases > 0 and total_phases != consommation_totale:
                self.add_warning("phase_1_kwh",
                                 f"La somme des phases ({total_phases}) ne correspond pas "
                                 f"à la consommation totale ({consommation_totale})")

        return cleaned_data

    def add_warning(self, field, message):
        """Ajouter un avertissement sans bloquer la validation"""
        if not hasattr(self, '_warnings'):
            self._warnings = {}
        self._warnings[field] = message

    def get_warnings(self):
        """Récupérer les avertissements"""
        return getattr(self, '_warnings', {})

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Mettre à jour la date de validation si le statut passe à "VALIDÉ"
        new_statut = self.cleaned_data.get('statut')
        old_statut = instance.statut if instance.pk else None

        if new_statut == 'VALIDÉ' and old_statut != 'VALIDÉ':
            instance.date_validation = date.today()
        elif new_statut != 'VALIDÉ':
            instance.date_validation = None

        # Enregistrer automatiquement la date de relevé pour les nouvelles entrées
        if not instance.pk:
            instance.date_releve = timezone.now()

        if commit:
            instance.save()

            # Si des avertissements ont été générés, on pourrait les enregistrer
            warnings = self.get_warnings()
            if warnings and hasattr(instance, 'id'):
                # Enregistrer les avertissements dans les notes ou dans un log
                if 'notes' in self.cleaned_data:
                    notes = self.cleaned_data['notes']
                    if notes:
                        notes += "\n\nAvertissements:\n"
                        for field, message in warnings.items():
                            notes += f"- {field}: {message}\n"
                        instance.notes = notes
                        instance.save(update_fields=['notes'])

        return instance

class ReleverManuelForm(forms.Form):
    """Formulaire simplifié pour relevé manuel rapide"""
    compteur = forms.ModelChoiceField(
        queryset=Compteur.objects.none(),
        label="Compteur",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    periode = forms.DateField(
        label="Période",
        widget=forms.DateInput(
            attrs={'type': 'month', 'class': 'form-control'},
            format='%Y-%m'
        ),
        input_formats=['%Y-%m']
    )
    index_debut = forms.DecimalField(
        label="Index début (kWh)",
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    index_fin = forms.DecimalField(
        label="Index fin (kWh)",
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    notes = forms.CharField(
        label="Notes",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user:
            if self.user.is_admin:
                compteurs = Compteur.objects.all()
            elif self.user.is_agent:
                compteurs = Compteur.objects.all()  # ou selon assignation
            else:
                compteurs = Compteur.objects.none()  # Client ne peut pas faire de relevés

            self.fields['compteur'].queryset = compteurs

    def clean(self):
        cleaned_data = super().clean()
        index_debut = cleaned_data.get('index_debut')
        index_fin = cleaned_data.get('index_fin')

        if index_debut and index_fin and index_fin < index_debut:
            raise ValidationError(
                "L'index de fin doit être supérieur à l'index de début"
            )

        return cleaned_data


class CorrigerReleveForm(ModelForm):
    """Formulaire pour corriger un relevé"""

    class Meta:
        model = Consommation
        fields = ['index_debut_periode', 'index_fin_periode', 'notes']
        widgets = {
            'index_debut_periode': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'index_fin_periode': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Expliquer la raison de la correction...'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        index_debut = cleaned_data.get('index_debut_periode')
        index_fin = cleaned_data.get('index_fin_periode')

        if index_debut and index_fin and index_fin < index_debut:
            raise ValidationError(
                "L'index de fin doit être supérieur à l'index de début"
            )

        return cleaned_data


class ImportCSVForm(forms.Form):
    """Formulaire d'import CSV"""
    csv_file = forms.FileField(
        label="Fichier CSV",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv'
        })
    )
    delimiter = forms.CharField(
        label="Séparateur",
        initial=',',
        max_length=1,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'maxlength': 1,
            'size': 2
        })
    )
    overwrite = forms.BooleanField(
        label="Écraser les doublons?",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']

        if not csv_file.name.endswith('.csv'):
            raise ValidationError("Le fichier doit être au format CSV")

        if csv_file.size > 5 * 1024 * 1024:  # 5MB
            raise ValidationError("Le fichier est trop volumineux (max 5MB)")

        return csv_file


class PeriodeFilterForm(forms.Form):
    """Formulaire de filtrage par période"""
    periode_debut = forms.DateField(
        required=False,
        label="Période début",
        widget=forms.DateInput(
            attrs={'type': 'month', 'class': 'form-control'},
            format='%Y-%m'
        ),
        input_formats=['%Y-%m']
    )
    periode_fin = forms.DateField(
        required=False,
        label="Période fin",
        widget=forms.DateInput(
            attrs={'type': 'month', 'class': 'form-control'},
            format='%Y-%m'
        ),
        input_formats=['%Y-%m']
    )
    compteur = forms.ModelChoiceField(
        queryset=Compteur.objects.all(),
        required=False,
        label="Compteur",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    statut = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + list(Consommation.STATUT_CHOICES),
        required=False,
        label="Statut",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not (user.is_admin or user.is_agent):
            self.fields.pop('compteur')


class StatsFilterForm(forms.Form):
    """Formulaire de filtrage pour les statistiques"""
    annee = forms.IntegerField(
        required=False,
        label="Année",
        min_value=2000,
        max_value=2100,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: 2024'
        })
    )
    compteur = forms.ModelChoiceField(
        queryset=Compteur.objects.all(),
        required=False,
        label="Compteur spécifique",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean_annee(self):
        annee = self.cleaned_data.get('annee')
        if annee and (annee < 2000 or annee > 2100):
            raise ValidationError("L'année doit être entre 2000 et 2100")
        return annee