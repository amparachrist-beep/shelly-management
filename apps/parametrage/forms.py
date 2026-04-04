from django import forms
from .models import Departement, Localite,  Zone,TypeTarification, TrancheTarifaire, TaxeTarifaire, ConfigurationTarifaire
import json


class DepartementForm(forms.ModelForm):
    """Formulaire pour les départements"""

    class Meta:
        model = Departement
        fields = ['nom', 'code_departement', 'region',
                  'centre_latitude', 'centre_longitude']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'code_departement': forms.TextInput(attrs={'class': 'form-control'}),
            'region': forms.TextInput(attrs={'class': 'form-control'}),
            'centre_latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.00000001',
                'min': '-90',
                'max': '90'
            }),
            'centre_longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.00000001',
                'min': '-180',
                'max': '180'
            }),
        }

    def clean_code_departement(self):
        code = self.cleaned_data.get('code_departement')
        if Departement.objects.filter(code_departement=code).exists():
            if self.instance and self.instance.code_departement != code:
                raise forms.ValidationError("Ce code département existe déjà.")
        return code


class LocaliteForm(forms.ModelForm):
    """Formulaire pour les localités"""

    class Meta:
        model = Localite
        fields = ['nom', 'code_postal', 'departement', 'type_localite',
                  'latitude', 'longitude', 'google_place_id', 'zone_rayon_km']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'code_postal': forms.TextInput(attrs={'class': 'form-control'}),
            'departement': forms.Select(attrs={'class': 'form-control'}),
            'type_localite': forms.Select(attrs={'class': 'form-control'}),
            'latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.00000001',
                'min': '-90',
                'max': '90'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.00000001',
                'min': '-180',
                'max': '180'
            }),
            'google_place_id': forms.TextInput(attrs={'class': 'form-control'}),
            'zone_rayon_km': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
        }


import json
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone


class TrancheTarifaireForm(forms.ModelForm):
    """Formulaire pour une tranche individuelle"""

    class Meta:
        model = TrancheTarifaire
        fields = ['ordre', 'borne_inferieure', 'borne_superieure', 'prix_kwh']
        widgets = {
            'ordre': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'readonly': True,
                'style': 'background-color: #f8f9fa;'
            }),
            'borne_inferieure': forms.NumberInput(attrs={
                'class': 'form-control borne-inf',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Borne inférieure (kWh)'
            }),
            'borne_superieure': forms.NumberInput(attrs={
                'class': 'form-control borne-sup',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Borne supérieure (kWh) - Laissez vide si illimité'
            }),
            'prix_kwh': forms.NumberInput(attrs={
                'class': 'form-control prix-kwh',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Prix du kWh (FCFA)'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        borne_inf = cleaned_data.get('borne_inferieure')
        borne_sup = cleaned_data.get('borne_superieure')

        if borne_inf is not None and borne_inf < 0:
            raise ValidationError("La borne inférieure ne peut pas être négative")

        if borne_sup and borne_sup <= borne_inf:
            raise ValidationError({
                'borne_superieure': "La borne supérieure doit être supérieure à la borne inférieure"
            })

        return cleaned_data


class TaxeTarifaireForm(forms.ModelForm):
    """Formulaire pour une taxe individuelle"""

    class Meta:
        model = TaxeTarifaire
        fields = [
            'code', 'nom', 'type_taxe', 'montant_fixe', 'pourcentage',
            'base_calcul', 'soumis_tva', 'ordre_application',
            'date_debut', 'date_fin', 'active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: RAV, CA, TIMBRE'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la taxe'
            }),
            'type_taxe': forms.Select(attrs={
                'class': 'form-control taxe-type'
            }),
            'montant_fixe': forms.NumberInput(attrs={
                'class': 'form-control montant-fixe',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Montant en FCFA'
            }),
            'pourcentage': forms.NumberInput(attrs={
                'class': 'form-control pourcentage',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': 'Pourcentage (%)'
            }),
            'base_calcul': forms.Select(attrs={'class': 'form-control'}),
            'soumis_tva': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordre_application': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'date_debut': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'date_fin': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        type_taxe = cleaned_data.get('type_taxe')
        montant_fixe = cleaned_data.get('montant_fixe')
        pourcentage = cleaned_data.get('pourcentage')

        if type_taxe == 'FIXE' and not montant_fixe:
            raise ValidationError({
                'montant_fixe': "Le montant fixe est requis pour une taxe de type 'Montant fixe'"
            })

        if type_taxe == 'POURCENTAGE' and not pourcentage:
            raise ValidationError({
                'pourcentage': "Le pourcentage est requis pour une taxe de type 'Pourcentage'"
            })

        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_fin and date_fin < date_debut:
            raise ValidationError({
                'date_fin': "La date de fin doit être postérieure à la date de début"
            })

        return cleaned_data


class TypeTarificationBaseForm(forms.ModelForm):
    """Formulaire de base pour TypeTarification"""

    class Meta:
        model = TypeTarification
        fields = [
            'code', 'nom', 'categorie', 'periodicite',
            'abonnement_mensuel', 'devise', 'tva_taux',
            'reference_arrete', 'date_effet', 'date_fin',
            'description', 'conditions', 'actif'
        ]
        widgets = {
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: CONGO_RES_5KVA'
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Tarif Résidentiel Congo 5kVA'
            }),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'periodicite': forms.Select(attrs={'class': 'form-control'}),
            'abonnement_mensuel': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Montant abonnement mensuel'
            }),
            'devise': forms.TextInput(attrs={
                'class': 'form-control',
                'value': 'FCFA',
                'readonly': True
            }),
            'tva_taux': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'value': '18.00'
            }),
            'reference_arrete': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Loi N°16-2001 du 31 Décembre'
            }),
            'date_effet': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'date_fin': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description détaillée du tarif'
            }),
            'conditions': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Conditions particulières d\'application'
            }),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if TypeTarification.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ce code de tarification existe déjà.")
        return code.upper()

    def clean(self):
        cleaned_data = super().clean()
        date_effet = cleaned_data.get('date_effet')
        date_fin = cleaned_data.get('date_fin')

        if date_fin and date_fin <= date_effet:
            raise ValidationError({
                'date_fin': "La date de fin doit être postérieure à la date d'effet"
            })

        return cleaned_data


class TypeTarificationFullForm(TypeTarificationBaseForm):
    """Formulaire complet avec gestion JSON des tranches et taxes"""

    tranches_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    taxes_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Initialiser les données JSON si l'instance existe
        if self.instance.pk:
            # Tranches
            tranches = self.instance.tranches.all().order_by('ordre')
            tranches_list = []
            for t in tranches:
                tranches_list.append({
                    'id': t.id,
                    'ordre': t.ordre,
                    'borne_inferieure': float(t.borne_inferieure),
                    'borne_superieure': float(t.borne_superieure) if t.borne_superieure else None,
                    'prix_kwh': float(t.prix_kwh)
                })
            self.initial['tranches_data'] = json.dumps(tranches_list)

            # Taxes
            taxes = self.instance.taxes.filter(active=True).order_by('ordre_application')
            taxes_list = []
            for tax in taxes:
                taxes_list.append({
                    'id': tax.id,
                    'code': tax.code,
                    'nom': tax.nom,
                    'type_taxe': tax.type_taxe,
                    'montant_fixe': float(tax.montant_fixe) if tax.montant_fixe else None,
                    'pourcentage': float(tax.pourcentage) if tax.pourcentage else None,
                    'base_calcul': tax.base_calcul,
                    'soumis_tva': tax.soumis_tva,
                    'ordre_application': tax.ordre_application
                })
            self.initial['taxes_data'] = json.dumps(taxes_list)

    def save(self, commit=True):
        instance = super().save(commit=False)

        if commit:
            instance.save()

            # Sauvegarder les tranches
            if self.cleaned_data.get('tranches_data'):
                self._save_tranches(instance, self.cleaned_data['tranches_data'])

            # Sauvegarder les taxes
            if self.cleaned_data.get('taxes_data'):
                self._save_taxes(instance, self.cleaned_data['taxes_data'])

        return instance

    def _save_tranches(self, tarification, tranches_data):
        """Sauvegarde les tranches depuis les données JSON"""
        try:
            tranches = json.loads(tranches_data)

            # Supprimer les anciennes tranches
            tarification.tranches.all().delete()

            # Créer les nouvelles tranches
            for tranche in tranches:
                TrancheTarifaire.objects.create(
                    tarification=tarification,
                    ordre=tranche.get('ordre', 0),
                    borne_inferieure=tranche.get('borne_inferieure', 0),
                    borne_superieure=tranche.get('borne_superieure'),
                    prix_kwh=tranche.get('prix_kwh', 0)
                )
        except json.JSONDecodeError as e:
            raise ValidationError(f"Erreur de format JSON pour les tranches: {e}")

    def _save_taxes(self, tarification, taxes_data):
        """Sauvegarde les taxes depuis les données JSON"""
        try:
            taxes = json.loads(taxes_data)

            # Mettre à jour ou créer les taxes
            for tax_data in taxes:
                tax_id = tax_data.get('id')
                if tax_id:
                    # Mettre à jour une taxe existante
                    TaxeTarifaire.objects.filter(id=tax_id).update(
                        code=tax_data.get('code'),
                        nom=tax_data.get('nom'),
                        type_taxe=tax_data.get('type_taxe'),
                        montant_fixe=tax_data.get('montant_fixe'),
                        pourcentage=tax_data.get('pourcentage'),
                        base_calcul=tax_data.get('base_calcul'),
                        soumis_tva=tax_data.get('soumis_tva', False),
                        ordre_application=tax_data.get('ordre_application', 0)
                    )
                else:
                    # Créer une nouvelle taxe
                    TaxeTarifaire.objects.create(
                        tarification=tarification,
                        code=tax_data.get('code'),
                        nom=tax_data.get('nom'),
                        type_taxe=tax_data.get('type_taxe'),
                        montant_fixe=tax_data.get('montant_fixe'),
                        pourcentage=tax_data.get('pourcentage'),
                        base_calcul=tax_data.get('base_calcul'),
                        soumis_tva=tax_data.get('soumis_tva', False),
                        ordre_application=tax_data.get('ordre_application', 0),
                        date_debut=timezone.now().date(),
                        active=True
                    )
        except json.JSONDecodeError as e:
            raise ValidationError(f"Erreur de format JSON pour les taxes: {e}")


class ConfigurationTarifaireForm(forms.ModelForm):
    """Formulaire pour ConfigurationTarifaire"""

    class Meta:
        model = ConfigurationTarifaire
        fields = ['pays', 'tarification', 'timbre_electronique', 'date_debut', 'date_fin', 'version']
        widgets = {
            'pays': forms.TextInput(attrs={
                'class': 'form-control',
                'value': 'Congo-Brazzaville'
            }),
            'tarification': forms.Select(attrs={'class': 'form-control'}),
            'timbre_electronique': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'value': '50.00'
            }),
            'date_debut': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'date_fin': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'version': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '1.0'
            }),
        }

class ZoneForm(forms.ModelForm):
    """Formulaire pour les zones"""

    class Meta:
        model = Zone
        fields = ['nom', 'departement', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'departement': forms.Select(attrs={'class': 'form-control'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CalculConsommationForm(forms.Form):
    """Formulaire pour calculer la consommation"""
    tarification = forms.ModelChoiceField(
        queryset=TypeTarification.objects.filter(actif=True),
        label="Tarification",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    consommation_kwh = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        label="Consommation (kWh)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'})
    )


class LocaliteSearchForm(forms.Form):
    """Formulaire de recherche de localités"""
    q = forms.CharField(
        required=False,
        label="Rechercher",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom de localité...'
        })
    )
    departement = forms.ModelChoiceField(
        queryset=Departement.objects.all(),
        required=False,
        label="Département",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    type_localite = forms.ChoiceField(
        choices=[('', 'Tous')] + list(Localite.TYPE_LOCALITE),
        required=False,
        label="Type",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ImportGeoDataForm(forms.Form):
    """Formulaire d'importation de données géographiques"""
    fichier_csv = forms.FileField(
        label="Fichier CSV",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )
    type_donnees = forms.ChoiceField(
        choices=[
            ('DEPARTEMENTS', 'Départements'),
            ('LOCALITES', 'Localités'),
            ('ZONES', 'Zones')
        ],
        label="Type de données",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    delimiter = forms.CharField(
        initial=',',
        max_length=1,
        label="Délimiteur",
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': '1'})
    )


from .models import TypeHabitation

class TypeHabitationForm(forms.ModelForm):
    class Meta:
        model = TypeHabitation
        fields = [
            'code', 'nom', 'categorie', 'standing',
            'surface_moyenne_m2', 'nombre_pieces_moyen',
            'consommation_estimee_kwh', 'type_tarification_recommande',
            'description', 'caracteristiques', 'actif', 'ordre_affichage'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'standing': forms.Select(attrs={'class': 'form-control'}),
            'surface_moyenne_m2': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'nombre_pieces_moyen': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'consommation_estimee_kwh': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'type_tarification_recommande': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'caracteristiques': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'ordre_affichage': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'code': 'Code',
            'nom': 'Nom',
            'categorie': 'Catégorie',
            'standing': 'Standing',
            'surface_moyenne_m2': 'Surface moyenne (m²)',
            'nombre_pieces_moyen': 'Nombre de pièces moyen',
            'consommation_estimee_kwh': 'Consommation estimée (kWh/mois)',
            'type_tarification_recommande': 'Tarification recommandée',
            'description': 'Description',
            'caracteristiques': 'Caractéristiques (JSON)',
            'actif': 'Actif',
            'ordre_affichage': "Ordre d'affichage",
        }
        help_texts = {
            'caracteristiques': 'Saisissez un objet JSON valide (ex: {"chauffage": "électrique", "climatisation": true})',
        }

    def clean_code(self):
        code = self.cleaned_data['code']
        if TypeHabitation.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Ce code est déjà utilisé.")
        return code

    def clean_caracteristiques(self):
        import json
        data = self.cleaned_data['caracteristiques']
        if data:
            if isinstance(data, str):
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    raise forms.ValidationError("Le format JSON n'est pas valide.")
        return data