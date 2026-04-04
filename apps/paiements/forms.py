from django import forms
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid
from datetime import datetime
from .models import Paiement, CommissionAgent, FraisTransaction
from apps.facturation.models import FactureConsommation
from apps.users.models import CustomUser


class PaiementForm(forms.ModelForm):
    """Formulaire pour créer/modifier un paiement"""
    facture = forms.ModelChoiceField(
        queryset=FactureConsommation.objects.filter(statut__in=['EMISE', 'PARTIELLEMENT_PAYEE']),
        label="Facture",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Paiement
        fields = ['facture', 'montant', 'mode_paiement', 'statut',
                  'date_paiement', 'reference_externe', 'notes',
                  'fichier_justificatif']
        widgets = {
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'mode_paiement': forms.Select(attrs={'class': 'form-control'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'date_paiement': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'reference_externe': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'fichier_justificatif': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            # Nouveau paiement - générer référence
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            unique_id = uuid.uuid4().hex[:8].upper()
            self.initial['reference_paiement'] = f"PAY-{timestamp}-{unique_id}"

        # Limiter les factures selon le rôle
        if self.user and self.user.role == 'AGENT_TERRAIN':
            # Agents voient seulement leurs ménages
            menages_assignes = self.user.menage_set.all()
            factures_ids = FactureConsommation.objects.filter(
                menage__in=menages_assignes
            ).values_list('id', flat=True)
            self.fields['facture'].queryset = FactureConsommation.objects.filter(
                id__in=factures_ids,
                statut__in=['EMISE', 'PARTIELLEMENT_PAYEE']
            )

    def clean(self):
        cleaned_data = super().clean()
        facture = cleaned_data.get('facture')
        montant = cleaned_data.get('montant')

        if facture and montant:
            # Vérifier que le montant ne dépasse pas le reste à payer
            reste_a_payer = facture.montant_total - facture.montant_paye
            if montant > reste_a_payer:
                raise forms.ValidationError(
                    f"Montant trop élevé. Reste à payer: {reste_a_payer} FCFA"
                )

        return cleaned_data

    def save(self, commit=True):
        paiement = super().save(commit=False)

        if not paiement.pk:
            # Nouveau paiement
            if self.user:
                paiement.cree_par = self.user

            # Générer référence si non définie
            if not paiement.reference_paiement:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                unique_id = uuid.uuid4().hex[:8].upper()
                paiement.reference_paiement = f"PAY-{timestamp}-{unique_id}"

        if commit:
            paiement.save()

            # Mettre à jour le statut de la facture si le paiement est validé
            if paiement.statut == 'VALIDÉ':
                paiement.facture.montant_paye += paiement.montant

                # Mettre à jour le statut de la facture
                if paiement.facture.montant_paye >= paiement.facture.montant_total:
                    paiement.facture.statut = 'PAYEE'
                elif paiement.facture.montant_paye > 0:
                    paiement.facture.statut = 'PARTIELLEMENT_PAYEE'

                paiement.facture.save()

        return paiement


class MobileMoneyPaymentForm(forms.Form):
    """Formulaire spécifique pour paiement Mobile Money"""
    facture = forms.ModelChoiceField(
        queryset=FactureConsommation.objects.filter(statut__in=['EMISE', 'PARTIELLEMENT_PAYEE']),
        label="Facture",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    montant = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        label="Montant",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    operateur = forms.ChoiceField(
        choices=[
            ('ORANGE_MONEY', 'Orange Money'),
            ('MTN_MONEY', 'MTN Money'),
            ('AIRTEL_MONEY', 'Airtel Money'),
        ],
        label="Opérateur",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    numero_transaction = forms.CharField(
        max_length=50,
        label="Numéro de transaction",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    telephone_payeur = forms.CharField(
        max_length=20,
        label="Téléphone payeur",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'XX XX XX XX'})
    )
    date_paiement = forms.DateTimeField(
        label="Date du paiement",
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        initial=timezone.now
    )


class PaiementValidationForm(forms.Form):
    """Formulaire pour valider/rejeter un paiement"""
    action = forms.ChoiceField(
        choices=[('VALIDER', 'Valider'), ('REJETER', 'Rejeter')],
        label="Action",
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    raison = forms.CharField(
        required=False,
        label="Raison (obligatoire pour rejet)",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Indiquez la raison du rejet si applicable"
    )


class CommissionAgentForm(forms.ModelForm):
    """Formulaire pour les commissions des agents"""

    class Meta:
        model = CommissionAgent
        fields = ['agent', 'taux_commission', 'montant_commission', 'statut',
                  'date_paiement_commission', 'notes']
        widgets = {
            'agent': forms.Select(attrs={'class': 'form-control'}),
            'taux_commission': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'montant_commission': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'date_paiement_commission': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class FraisTransactionForm(forms.ModelForm):
    """Formulaire pour les frais de transaction"""

    class Meta:
        model = FraisTransaction
        fields = ['type_frais', 'description', 'montant', 'facture_frais']
        widgets = {
            'type_frais': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'facture_frais': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }


class RapportJournalierForm(forms.Form):
    """Formulaire pour le rapport journalier"""
    date_rapport = forms.DateField(
        label="Date du rapport",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        initial=timezone.now().date
    )


class StatsPaiementForm(forms.Form):
    """Formulaire pour les statistiques de paiement"""
    date_debut = forms.DateField(
        label="Date début",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_fin = forms.DateField(
        label="Date fin",
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        initial=timezone.now().date
    )
    mode_paiement = forms.ChoiceField(
        choices=[('', 'Tous')] + list(Paiement.MODE_PAIEMENT_CHOICES),
        required=False,
        label="Mode de paiement",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    statut = forms.ChoiceField(
        choices=[('', 'Tous')] + list(Paiement.STATUT_CHOICES),
        required=False,
        label="Statut",
        widget=forms.Select(attrs={'class': 'form-control'})
    )