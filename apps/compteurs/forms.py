from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date

from .models import Compteur, Capteur, TypeCompteur
from apps.menages.models import Menage
from apps.parametrage.models import TypeTarification, Localite


class CompteurForm(ModelForm):
    """Formulaire de création/modification de compteur"""

    class Meta:
        model = Compteur
        fields = [
            'numero_contrat', 'matricule_compteur', 'numero_client',
            'menage', 'type_tarification', 'localite',
            'type_compteur_detail', 'puissance_souscrite', 'tension', 'phase',
            'adresse_installation', 'gps_latitude', 'gps_longitude', 'reference_local',
            'date_installation', 'date_debut_contrat', 'date_fin_contrat',
            'periode_facturation', 'jour_releve', 'jour_paiement',
            'statut', 'index_initial', 'index_actuel',
            'shelly_device_id', 'shelly_ip',
        ]
        widgets = {
            'numero_contrat': forms.TextInput(attrs={'class': 'form-control'}),
            'matricule_compteur': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_client': forms.TextInput(attrs={'class': 'form-control'}),
            'menage': forms.Select(attrs={'class': 'form-control'}),
            'type_tarification': forms.Select(attrs={'class': 'form-control'}),
            'localite': forms.Select(attrs={'class': 'form-control'}),
            'type_compteur_detail': forms.Select(attrs={'class': 'form-control'}),
            'puissance_souscrite': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'tension': forms.Select(attrs={'class': 'form-control'}),
            'phase': forms.Select(attrs={'class': 'form-control'}),
            'adresse_installation': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
            'gps_latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.00000001',
                'placeholder': 'Ex: 14.692778'
            }),
            'gps_longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.00000001',
                'placeholder': 'Ex: -17.446667'
            }),
            'reference_local': forms.TextInput(attrs={'class': 'form-control'}),
            'date_installation': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'date_debut_contrat': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'date_fin_contrat': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'periode_facturation': forms.Select(attrs={'class': 'form-control'}),
            'jour_releve': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '31'
            }),
            'jour_paiement': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '31'
            }),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'index_initial': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'index_actuel': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'shelly_device_id': forms.TextInput(attrs={'class': 'form-control'}),
            'shelly_ip': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 192.168.1.100'
            }),
        }
        labels = {
            'numero_contrat': 'Numéro de contrat',
            'matricule_compteur': 'Matricule du compteur',
            'numero_client': 'Numéro client',
            'puissance_souscrite': 'Puissance souscrite (kVA)',
            'gps_latitude': 'Latitude GPS',
            'gps_longitude': 'Longitude GPS',
            'reference_local': 'Référence locale',
            'index_initial': 'Index initial (kWh)',
            'index_actuel': 'Index actuel (kWh)',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Limiter les ménages selon l'utilisateur
        if self.user:
            if self.user.is_admin:
                menages = Menage.objects.all()
            elif self.user.is_agent:
                menages = Menage.objects.all()  # ou selon assignation
            else:
                menages = Menage.objects.none()  # Client ne peut pas créer de compteurs

            self.fields['menage'].queryset = menages

            # Limiter les types de tarification et localités
            self.fields['type_tarification'].queryset = TypeTarification.objects.filter(actif=True)
            self.fields['localite'].queryset = Localite.objects.filter(actif=True)

    def clean(self):
        cleaned_data = super().clean()

        # Vérifier que l'index actuel est >= index initial
        index_initial = cleaned_data.get('index_initial')
        index_actuel = cleaned_data.get('index_actuel')

        if index_initial and index_actuel and index_actuel < index_initial:
            raise ValidationError(
                "L'index actuel ne peut pas être inférieur à l'index initial"
            )

        # Vérifier les dates
        date_installation = cleaned_data.get('date_installation')
        date_debut_contrat = cleaned_data.get('date_debut_contrat')
        date_fin_contrat = cleaned_data.get('date_fin_contrat')

        if date_installation and date_debut_contrat and date_installation > date_debut_contrat:
            raise ValidationError(
                "La date d'installation ne peut pas être postérieure à la date de début de contrat"
            )

        if date_fin_contrat and date_debut_contrat and date_fin_contrat < date_debut_contrat:
            raise ValidationError(
                "La date de fin de contrat ne peut pas être antérieure à la date de début"
            )

        # Vérifier l'unicité des numéros
        numero_contrat = cleaned_data.get('numero_contrat')
        matricule_compteur = cleaned_data.get('matricule_compteur')

        if numero_contrat:
            qs = Compteur.objects.filter(numero_contrat=numero_contrat)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    f"Un compteur avec le numéro de contrat '{numero_contrat}' existe déjà"
                )

        if matricule_compteur:
            qs = Compteur.objects.filter(matricule_compteur=matricule_compteur)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError(
                    f"Un compteur avec le matricule '{matricule_compteur}' existe déjà"
                )

        return cleaned_data


class CapteurForm(ModelForm):
    """Formulaire de création/modification de capteur"""

    class Meta:
        model = Capteur
        fields = [
            'compteur',
            'device_id', 'device_name', 'mac_address', 'ip_address',
            'nombre_phase', 'calibre_courant', 'calibration_factor',
            'status',
        ]
        widgets = {
            'compteur': forms.Select(attrs={
                'class': 'form-control',
            }),
            'device_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: shellypro3em-e08cfe95b16c'
            }),
            'device_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Shelly Pro 3EM - Tableau Général'
            }),
            'mac_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: E0:8C:FE:95:B1:6C'
            }),
            'ip_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 192.168.11.234'
            }),
            'nombre_phase': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '3'
            }),
            'calibre_courant': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Ex: 63'
            }),
            'calibration_factor': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'compteur': 'Compteur associé',
            'device_id': 'ID du dispositif',
            'device_name': 'Nom du capteur',
            'mac_address': 'Adresse MAC',
            'ip_address': 'Adresse IP',
            'nombre_phase': 'Nombre de phases',
            'calibre_courant': 'Calibre courant (A)',
            'calibration_factor': 'Facteur de calibration',
            'status': 'Statut',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dropdown uniquement les compteurs actifs
        self.fields['compteur'].queryset = Compteur.objects.filter(
            statut='ACTIF'
        ).select_related('menage').order_by('numero_contrat')

        # Affichage lisible : "CONT-001 — Famille Dupont"
        self.fields['compteur'].label_from_instance = lambda c: (
            f"{c.numero_contrat} — {c.menage.nom_menage}"
        )

        # Rendre compteur obligatoire explicitement
        self.fields['compteur'].empty_label = "— Sélectionner un compteur —"
        self.fields['compteur'].required = True

    def clean_mac_address(self):
        """Valider le format de l'adresse MAC"""
        mac = self.cleaned_data.get('mac_address', '').strip().upper()
        if mac:
            import re
            if not re.match(r'^([0-9A-F]{2}:){5}[0-9A-F]{2}$', mac):
                raise forms.ValidationError(
                    "Format MAC invalide. Utilisez le format AA:BB:CC:DD:EE:FF"
                )
        return mac

    def clean_device_id(self):
        """Vérifier l'unicité du device_id (sauf en modification)"""
        device_id = self.cleaned_data.get('device_id', '').strip().lower()
        qs = Capteur.objects.filter(device_id=device_id)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f"Un capteur avec l'ID '{device_id}' existe déjà."
            )
        return device_id

    def clean_nombre_phase(self):
        """Valider que le nombre de phases est 1 ou 3"""
        phases = self.cleaned_data.get('nombre_phase')
        if phases not in [1, 3]:
            raise forms.ValidationError(
                "Le nombre de phases doit être 1 (monophasé) ou 3 (triphasé)."
            )
        return phases

    def clean(self):
        cleaned_data = super().clean()

        # Vérifier cohérence phases / compteur
        compteur = cleaned_data.get('compteur')
        nombre_phase = cleaned_data.get('nombre_phase')

        if compteur and nombre_phase:
            if compteur.phase == 'TRIPHASE' and nombre_phase != 3:
                self.add_error(
                    'nombre_phase',
                    "Le compteur est triphasé — le capteur doit avoir 3 phases."
                )
            elif compteur.phase == 'MONOPHASE' and nombre_phase != 1:
                self.add_error(
                    'nombre_phase',
                    "Le compteur est monophasé — le capteur doit avoir 1 phase."
                )

        return cleaned_data


class CompteurSearchForm(forms.Form):
    """Formulaire de recherche de compteurs"""
    q = forms.CharField(
        required=False,
        label="Rechercher",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Numéro contrat, matricule, client...'
        })
    )
    search_type = forms.ChoiceField(
        choices=[
            ('all', 'Tout'),
            ('matricule', 'Matricule'),
            ('contrat', 'Numéro contrat'),
            ('client', 'Numéro client'),
            ('menage', 'Nom ménage'),
        ],
        initial='all',
        label="Type de recherche",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class CompteurFilterForm(forms.Form):
    """Formulaire de filtrage des compteurs"""
    statut = forms.ChoiceField(
        choices=[('', 'Tous statuts')] + list(Compteur.STATUT_CHOICES),
        required=False,
        label="Statut",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    type_compteur = forms.ModelChoiceField(
        queryset=TypeCompteur.objects.all(),
        required=False,
        label="Type de compteur",
        empty_label="Tous types",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    localite = forms.ModelChoiceField(
        queryset=Localite.objects.none(),
        required=False,
        label="Localité",
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
    shelly_status = forms.ChoiceField(
        choices=[('', 'Tous')] + list(Compteur.SHELLY_STATUS),
        required=False,
        label="Statut Shelly",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and (user.is_admin or user.is_agent):
            self.fields['localite'].queryset = Localite.objects.filter(actif=True)
        else:
            self.fields.pop('localite')


class AssocierCapteurForm(forms.Form):
    """Formulaire d'association de capteur à un compteur"""
    compteur = forms.ModelChoiceField(
        queryset=Compteur.objects.none(),
        label="Compteur à associer",
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Rechercher un compteur...'
        })
    )
    device_id = forms.CharField(
        max_length=100,
        label="ID de l'appareil Shelly",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: shellyem-123456789ABC'
        })
    )
    device_name = forms.CharField(
        max_length=100,
        required=False,
        label="Nom de l'appareil (optionnel)",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Capteur salon'
        })
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Filtrer les compteurs selon l'utilisateur
        if user:
            if user.is_admin or user.is_agent:
                queryset = Compteur.objects.filter(
                    statut='ACTIF'
                ).select_related('menage').order_by('numero_contrat')
            else:
                # Pour les clients, seulement leurs compteurs
                try:
                    menage = Menage.objects.get(utilisateur=user)
                    queryset = Compteur.objects.filter(
                        menage=menage,
                        statut='ACTIF'
                    )
                except Menage.DoesNotExist:
                    queryset = Compteur.objects.none()
        else:
            queryset = Compteur.objects.none()

        self.fields['compteur'].queryset = queryset

        # Personnaliser les labels pour afficher plus d'infos
        if queryset.exists():
            choices = [('', '--- Sélectionnez un compteur ---')]
            for compteur in queryset:
                label = f"{compteur.numero_contrat} - {compteur.menage.nom_famille} ({compteur.adresse_installation[:50]}...)"
                choices.append((compteur.id, label))
            self.fields['compteur'].choices = choices
        else:
            self.fields['compteur'].choices = [('', 'Aucun compteur disponible')]

    def clean_device_id(self):
        device_id = self.cleaned_data['device_id'].strip()

        if not device_id:
            raise ValidationError("L'ID de l'appareil est requis")

        # Vérifier si le device_id existe déjà
        if Capteur.objects.filter(device_id=device_id).exists():
            raise ValidationError("Cet ID de dispositif est déjà utilisé par un autre capteur")

        return device_id

    def clean(self):
        cleaned_data = super().clean()
        compteur = cleaned_data.get('compteur')
        device_id = cleaned_data.get('device_id')

        # Vérifier si le compteur a déjà un capteur associé
        if compteur and compteur.capteurs.exists():
            raise ValidationError(
                f"Ce compteur a déjà un capteur associé: {compteur.capteurs.first().device_id}"
            )

        # Vérifier si le compteur a déjà un shelly_device_id
        if compteur and compteur.shelly_device_id:
            raise ValidationError(
                f"Ce compteur a déjà un capteur Shelly associé: {compteur.shelly_device_id}"
            )

        return cleaned_data

class UpdateIndexForm(ModelForm):
    """Formulaire de mise à jour d'index"""

    class Meta:
        model = Compteur
        fields = ['index_actuel']
        widgets = {
            'index_actuel': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
        }
        labels = {
            'index_actuel': 'Nouvel index (kWh)',
        }

    def clean_index_actuel(self):
        index_actuel = self.cleaned_data['index_actuel']
        if self.instance and index_actuel < self.instance.index_initial:
            raise ValidationError(
                f"Le nouvel index ({index_actuel}) ne peut pas être inférieur à l'index initial ({self.instance.index_initial})"
            )
        return index_actuel


class DiagnosticForm(forms.Form):
    """Formulaire de diagnostic"""
    test_connectivite = forms.BooleanField(
        required=False,
        label="Tester la connectivité",
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    test_donnees = forms.BooleanField(
        required=False,
        label="Vérifier les données",
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    test_performance = forms.BooleanField(
        required=False,
        label="Analyser la performance",
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    test_anomalies = forms.BooleanField(
        required=False,
        label="Rechercher les anomalies",
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    notes = forms.CharField(
        required=False,
        label="Notes supplémentaires",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Observations, problèmes spécifiques...'
        })
    )


class ShellyConfigForm(forms.Form):
    """Formulaire de configuration Shelly"""
    device_id = forms.CharField(
        max_length=100,
        label="ID de l'appareil",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'readonly': 'readonly'
        })
    )
    ip_address = forms.GenericIPAddressField(
        label="Adresse IP",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '192.168.1.100'
        })
    )
    port = forms.IntegerField(
        initial=80,
        min_value=1,
        max_value=65535,
        label="Port",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    intervalle_releve = forms.IntegerField(
        initial=300,
        min_value=30,
        max_value=3600,
        label="Intervalle de relevé (secondes)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    seuil_puissance = forms.DecimalField(
        initial=5000,
        min_value=0,
        max_digits=8,
        decimal_places=2,
        label="Seuil d'alerte puissance (W)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['device_id'].required = False


from django import forms
from .models import TypeCompteur


class TypeCompteurForm(forms.ModelForm):
    class Meta:
        model = TypeCompteur
        fields = [
            'code', 'nom', 'marque', 'modele', 'technologie',
            'tension_compatibilite', 'nombre_phases', 'compatible_shelly',
            'prix_unitaire_fcfa', 'actif', 'en_stock', 'stock_disponible',
            'ordre_affichage'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CMP-CHNT-001'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Compteur CHNT DDS666'}),
            'marque': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: CHNT, Actaris, etc.'}),
            'modele': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: DDS666, A100C, etc.'}),
            'technologie': forms.Select(attrs={'class': 'form-control'}),
            'tension_compatibilite': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Ex: BT_220V, BT_110V, HT, etc.'}),
            'nombre_phases': forms.Select(attrs={'class': 'form-control'}, choices=[(1, 'Monophasé'), (3, 'Triphasé')]),
            'compatible_shelly': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'prix_unitaire_fcfa': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'en_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'stock_disponible': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': '0'}),
            'ordre_affichage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': '0'}),
        }
        labels = {
            'code': 'Code',
            'nom': 'Nom',
            'marque': 'Marque',
            'modele': 'Modèle',
            'technologie': 'Technologie',
            'tension_compatibilite': 'Tension de compatibilité',
            'nombre_phases': 'Nombre de phases',
            'compatible_shelly': 'Compatible Shelly',
            'prix_unitaire_fcfa': 'Prix unitaire (FCFA)',
            'actif': 'Actif',
            'en_stock': 'En stock',
            'stock_disponible': 'Stock disponible',
            'ordre_affichage': "Ordre d'affichage",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre certains champs optionnels
        self.fields['marque'].required = False
        self.fields['modele'].required = False
        self.fields['prix_unitaire_fcfa'].required = False
        self.fields['stock_disponible'].required = False
        self.fields['ordre_affichage'].required = False

        # Définir les valeurs par défaut pour les champs booléens
        if not self.instance.pk:
            self.fields['actif'].initial = True
            self.fields['en_stock'].initial = True
            self.fields['compatible_shelly'].initial = True
            self.fields['technologie'].initial = 'ELECTRONIQUE'
            self.fields['tension_compatibilite'].initial = 'BT_220V'
            self.fields['nombre_phases'].initial = 1
            self.fields['stock_disponible'].initial = 0
            self.fields['ordre_affichage'].initial = 0

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            if TypeCompteur.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Ce code est déjà utilisé.")
        return code

    def clean_prix_unitaire_fcfa(self):
        prix = self.cleaned_data.get('prix_unitaire_fcfa')
        if prix is not None and prix < 0:
            raise forms.ValidationError("Le prix ne peut pas être négatif.")
        return prix

    def clean_stock_disponible(self):
        stock = self.cleaned_data.get('stock_disponible')
        if stock is not None and stock < 0:
            raise forms.ValidationError("Le stock ne peut pas être négatif.")
        return stock