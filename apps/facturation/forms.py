from django import forms
from django.core.validators import MinValueValidator
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import uuid
from .models import FactureConsommation, LigneFacture, BatchFacturation, Relance
from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation


class FactureConsommationForm(forms.ModelForm):
    """Formulaire pour créer/modifier une facture"""
    compteur = forms.ModelChoiceField(
        queryset=Compteur.objects.filter(statut='ACTIF'),
        label="Compteur",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    consommation = forms.ModelChoiceField(
        queryset=Consommation.objects.filter(statut='VALIDÉ'),
        label="Consommation",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = FactureConsommation
        fields = [
            'numero_facture', 'compteur', 'consommation', 'periode',
            'date_emission', 'date_echeance', 'consommation_kwh',
            'montant_consommation', 'montant_abonnement', 'tva_taux',
            'redevance_communale', 'autres_taxes', 'montant_paye', 'statut',
            'notes'
        ]
        widgets = {
            'numero_facture': forms.TextInput(attrs={'class': 'form-control'}),
            'periode': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_emission': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_echeance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'consommation_kwh': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'montant_consommation': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'montant_abonnement': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'tva_taux': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'redevance_communale': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'autres_taxes': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'montant_paye': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Si c'est une nouvelle facture, générer un numéro
        if not self.instance.pk:
            timestamp = datetime.now().strftime('%Y%m%d')
            unique_id = uuid.uuid4().hex[:6].upper()
            self.initial['numero_facture'] = f"FAC-{timestamp}-{unique_id}"
            self.initial['date_emission'] = timezone.now().date()
            self.initial['date_echeance'] = timezone.now().date() + timedelta(days=15)

    def clean_numero_facture(self):
        numero = self.cleaned_data.get('numero_facture')
        if FactureConsommation.objects.filter(numero_facture=numero).exists():
            if self.instance and self.instance.numero_facture != numero:
                raise forms.ValidationError("Ce numéro de facture existe déjà.")
        return numero

    def clean(self):
        cleaned_data = super().clean()

        # Vérifier que le montant payé ne dépasse pas le total
        montant_consommation = cleaned_data.get('montant_consommation', Decimal('0'))
        montant_abonnement = cleaned_data.get('montant_abonnement', Decimal('0'))
        tva_taux = cleaned_data.get('tva_taux', Decimal('18'))
        redevance_communale = cleaned_data.get('redevance_communale', Decimal('0'))
        autres_taxes = cleaned_data.get('autres_taxes', Decimal('0'))
        montant_paye = cleaned_data.get('montant_paye', Decimal('0'))

        # Calculer le total TTC
        total_ht = montant_consommation + montant_abonnement
        tva_montant = total_ht * tva_taux / 100
        total_ttc = total_ht + tva_montant + redevance_communale + autres_taxes

        if montant_paye > total_ttc:
            raise forms.ValidationError(
                f"Le montant payé ({montant_paye}) ne peut pas dépasser le total TTC ({total_ttc:.2f})"
            )

        return cleaned_data


class LigneFactureForm(forms.ModelForm):
    """Formulaire pour les lignes de facture"""

    class Meta:
        model = LigneFacture
        fields = ['type_ligne', 'description', 'quantite', 'unite',
                  'prix_unitaire', 'taux_tva', 'tranche_min', 'tranche_max', 'ordre']
        widgets = {
            'type_ligne': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'quantite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'unite': forms.TextInput(attrs={'class': 'form-control'}),
            'prix_unitaire': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'taux_tva': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'tranche_min': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'tranche_max': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'ordre': forms.NumberInput(attrs={'class': 'form-control'}),
        }



class BatchFacturationForm(forms.ModelForm):
    """Formulaire pour les batches de facturation"""

    class Meta:
        model = BatchFacturation
        fields = ['reference', 'description', 'periode', 'parametres']
        widgets = {
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'periode': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class RelanceForm(forms.ModelForm):
    """Formulaire pour les relances"""

    class Meta:
        model = Relance
        fields = ['type_relance', 'sujet', 'message', 'destinataire_email',
                  'destinataire_telephone', 'destinataire_adresse',
                  'date_envoi_prevue', 'cout_envoi', 'statut']
        widgets = {
            'type_relance': forms.Select(attrs={'class': 'form-control'}),
            'sujet': forms.TextInput(attrs={'class': 'form-control'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'destinataire_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'destinataire_telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'destinataire_adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'date_envoi_prevue': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'cout_envoi': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
        }


class FactureSearchForm(forms.Form):
    """Formulaire de recherche de factures"""
    q = forms.CharField(
        required=False,
        label="Recherche",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Numéro facture, client...'
        })
    )
    statut = forms.ChoiceField(
        choices=[('', 'Tous')] + list(FactureConsommation.STATUT_CHOICES),
        required=False,
        label="Statut",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    date_debut = forms.DateField(
        required=False,
        label="Date début",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_fin = forms.DateField(
        required=False,
        label="Date fin",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    periode = forms.CharField(
        required=False,
        label="Période (YYYY-MM)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '2024-01'
        })
    )


class GenererFacturesForm(forms.Form):
    """Formulaire pour générer des factures"""
    periode = forms.DateField(
        label="Période",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'month'  # Pour sélectionner mois/année
        }),
        help_text="Mois/année pour lequel générer les factures"
    )
    date_echeance_jours = forms.IntegerField(
        initial=15,
        min_value=1,
        max_value=60,
        label="Jours avant échéance",
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Nombre de jours après l'émission pour l'échéance"
    )
    inclure_tous_compteurs = forms.BooleanField(
        initial=True,
        required=False,
        label="Inclure tous les compteurs",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    generer_pdf = forms.BooleanField(
        initial=False,
        required=False,
        label="Générer automatiquement les PDF",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


# apps/facturation/forms.py
from django import forms
from django.utils import timezone
from .models import DossierImpaye, PeriodeFacturation, Relance


# ==================== FORMULAIRES POUR DOSSIERS IMPAYÉS ====================

class DossierImpayeForm(forms.ModelForm):
    """Formulaire pour la création/modification d'un dossier d'impayé"""

    class Meta:
        model = DossierImpaye
        fields = ['facture', 'client', 'montant_du', 'motif', 'notes']
        widgets = {
            'facture': forms.Select(attrs={'class': 'form-input'}),
            'client': forms.Select(attrs={'class': 'form-input'}),
            'montant_du': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'motif': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }
        labels = {
            'facture': 'Facture',
            'client': 'Client',
            'montant_du': 'Montant dû (FCFA)',
            'motif': 'Motif',
            'notes': 'Notes',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les factures impayées
        self.fields['facture'].queryset = self.fields['facture'].queryset.filter(
            statut__in=['ÉMISE', 'EN_RETARD', 'PARTIELLEMENT_PAYÉE']
        )

        # Ajouter des classes CSS
        for field in self.fields:
            if not hasattr(self.fields[field].widget, 'attrs'):
                self.fields[field].widget.attrs = {}
            if 'class' not in self.fields[field].widget.attrs:
                self.fields[field].widget.attrs['class'] = 'form-input'

    def clean_montant_du(self):
        montant = self.cleaned_data.get('montant_du')
        facture = self.cleaned_data.get('facture')

        if montant and facture:
            if montant <= 0:
                raise forms.ValidationError("Le montant dû doit être supérieur à 0.")
            if montant > facture.solde_du:
                raise forms.ValidationError(
                    f"Le montant dû ne peut pas dépasser le solde de la facture ({facture.solde_du} FCFA)."
                )
        return montant


class TraiterDossierImpayeForm(forms.Form):
    """Formulaire pour traiter un dossier d'impayé"""

    ACTION_CHOICES = (
        ('resoudre', 'Résoudre'),
        ('relancer', 'Relancer'),
        ('cloturer', 'Clôturer'),
    )

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
        label='Action'
    )
    motif = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        label='Motif / Notes'
    )
    date_engagement = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        label="Date d'engagement de paiement"
    )
    montant_engage = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
        label="Montant engagé (FCFA)"
    )

    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')

        if action == 'relancer':
            if not cleaned_data.get('motif'):
                self.add_error('motif', "Le motif est requis pour une relance.")

        return cleaned_data


# ==================== FORMULAIRES POUR PÉRIODES DE FACTURATION ====================

class PeriodeFacturationForm(forms.ModelForm):
    """Formulaire pour la création/modification d'une période de facturation"""

    class Meta:
        model = PeriodeFacturation
        fields = [
            'libelle', 'date_debut', 'date_fin', 'actif', 'description',
            'date_generation_factures', 'date_echeance_default'
        ]
        widgets = {
            'libelle': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Ex: Janvier 2024'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'date_generation_factures': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'date_echeance_default': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 90}),
        }
        labels = {
            'libelle': 'Libellé',
            'date_debut': 'Date début',
            'date_fin': 'Date fin',
            'actif': 'Actif',
            'description': 'Description',
            'date_generation_factures': 'Date génération des factures',
            'date_echeance_default': 'Échéance par défaut (jours)',
        }
        help_texts = {
            'date_echeance_default': 'Nombre de jours après l\'émission pour l\'échéance',
            'date_generation_factures': 'Laissez vide pour utiliser la date de fin + 1 jour',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajouter des classes CSS pour tous les champs
        for field in self.fields:
            if hasattr(self.fields[field], 'widget') and not isinstance(self.fields[field].widget, forms.CheckboxInput):
                if 'class' not in self.fields[field].widget.attrs:
                    self.fields[field].widget.attrs['class'] = 'form-input'

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')

        if date_debut and date_fin:
            if date_debut > date_fin:
                self.add_error('date_fin', "La date de fin doit être postérieure à la date de début.")

        return cleaned_data


class PeriodeFacturationSearchForm(forms.Form):
    """Formulaire de recherche pour les périodes de facturation"""

    libelle = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'filter-input', 'placeholder': 'Rechercher par libellé...'}),
        label='Libellé'
    )
    actif = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous'), ('1', 'Actif'), ('0', 'Inactif')],
        widget=forms.Select(attrs={'class': 'filter-input'}),
        label='Statut'
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'filter-input', 'type': 'date'}),
        label='À partir du'
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'filter-input', 'type': 'date'}),
        label='Jusqu\'au'
    )


# ==================== FORMULAIRES POUR LES RELANCES ====================

class RelanceForm(forms.ModelForm):
    """Formulaire pour créer une relance"""

    class Meta:
        model = Relance
        fields = [
            'type_relance', 'sujet', 'message', 'destinataire_email',
            'destinataire_telephone', 'date_envoi_prevue'
        ]
        widgets = {
            'type_relance': forms.Select(attrs={'class': 'form-input'}),
            'sujet': forms.TextInput(attrs={'class': 'form-input'}),
            'message': forms.Textarea(attrs={'class': 'form-input', 'rows': 5}),
            'destinataire_email': forms.EmailInput(attrs={'class': 'form-input'}),
            'destinataire_telephone': forms.TextInput(attrs={'class': 'form-input'}),
            'date_envoi_prevue': forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
        }
        labels = {
            'type_relance': 'Type de relance',
            'sujet': 'Sujet',
            'message': 'Message',
            'destinataire_email': 'Email destinataire',
            'destinataire_telephone': 'Téléphone destinataire',
            'date_envoi_prevue': 'Date d\'envoi prévue',
        }

    def __init__(self, *args, **kwargs):
        facture = kwargs.pop('facture', None)
        super().__init__(*args, **kwargs)

        if facture:
            # Pré-remplir avec les infos de la facture
            if not self.initial.get('destinataire_email'):
                self.initial['destinataire_email'] = facture.compteur.menage.utilisateur.email
            if not self.initial.get('destinataire_telephone'):
                self.initial['destinataire_telephone'] = facture.compteur.menage.utilisateur.telephone
            if not self.initial.get('sujet'):
                self.initial['sujet'] = f"Relance facture {facture.numero_facture}"
            if not self.initial.get('date_envoi_prevue'):
                self.initial['date_envoi_prevue'] = timezone.now() + timezone.timedelta(hours=1)

        # Ajouter des classes CSS
        for field in self.fields:
            if hasattr(self.fields[field], 'widget'):
                if 'class' not in self.fields[field].widget.attrs:
                    self.fields[field].widget.attrs['class'] = 'form-input'

    def clean(self):
        cleaned_data = super().clean()
        type_relance = cleaned_data.get('type_relance')

        if type_relance == 'EMAIL' and not cleaned_data.get('destinataire_email'):
            self.add_error('destinataire_email', "L'email est requis pour une relance par email.")
        elif type_relance == 'SMS' and not cleaned_data.get('destinataire_telephone'):
            self.add_error('destinataire_telephone', "Le téléphone est requis pour une relance par SMS.")

        return cleaned_data


# ==================== FORMULAIRE POUR LA GESTION DES DOSSIERS IMPAYÉS ====================

class DossierImpayeSearchForm(forms.Form):
    """Formulaire de recherche pour les dossiers d'impayés"""

    statut = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous')] + list(DossierImpaye.STATUT_CHOICES),
        widget=forms.Select(attrs={'class': 'filter-input'}),
        label='Statut'
    )
    client = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'filter-input', 'placeholder': 'Rechercher par client...'}),
        label='Client'
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'filter-input', 'type': 'date'}),
        label='Date début'
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'filter-input', 'type': 'date'}),
        label='Date fin'
    )
    montant_min = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'filter-input', 'step': '0.01'}),
        label='Montant min (FCFA)'
    )
    montant_max = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'filter-input', 'step': '0.01'}),
        label='Montant max (FCFA)'
    )


# ==================== FORMULAIRE POUR LE SUIVI DES DOSSIERS ====================

class SuiviDossierImpayeForm(forms.Form):
    """Formulaire pour le suivi des dossiers d'impayés"""

    note = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Ajouter une note de suivi...'}),
        label='Note de suivi'
    )
    prochaine_action = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        label='Prochaine action prévue le'
    )
    contact_effectue = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        label='Contact effectué'
    )
    accord_client = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        label='Accord du client obtenu'
    )
    engagement_paiement = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
        label="Date d'engagement de paiement"
    )
    montant_engage = forms.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
        label="Montant engagé (FCFA)"
    )