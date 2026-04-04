# apps/menages/forms.py
# ✅ VERSION FINALE OPTIMISÉE

from django import forms
from django.core.validators import MinValueValidator
from django.db.models import Q
from .models import Menage
from apps.users.models import CustomUser
from apps.parametrage.models import Localite


class MenageForm(forms.ModelForm):
    """
    ✅ Formulaire de création/modification de ménage
    Avec sélection d'utilisateur CLIENT existant (sans ménage) ou création automatique
    """

    # ✅ CHAMP POUR SÉLECTIONNER UN UTILISATEUR CLIENT EXISTANT
    utilisateur = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),  # Sera défini dans __init__
        required=False,
        empty_label="-- Créer un nouvel utilisateur CLIENT --",
        label="Lier à un utilisateur CLIENT existant",
        help_text="Sélectionnez un CLIENT déjà enregistré (sans ménage), ou laissez vide pour créer automatiquement",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white focus:outline-none focus:border-orange-500/50 focus:ring-1 focus:ring-orange-500/20',
            'id': 'id_utilisateur'  # ✅ Important pour le JavaScript
        })
    )

    # ✅ CHAMPS POUR CRÉER AUTOMATIQUEMENT UN NOUVEAU CLIENT
    telephone_principal = forms.CharField(
        required=False,
        max_length=20,
        label="Téléphone principal (si nouveau CLIENT)",
        widget=forms.TextInput(attrs={
            'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white placeholder-slate-500',
            'placeholder': '+242 XX XXX XXXX'
        })
    )

    email = forms.EmailField(
        required=False,
        label="Email (si nouveau CLIENT)",
        widget=forms.EmailInput(attrs={
            'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white placeholder-slate-500',
            'placeholder': 'email@example.com'
        })
    )

    class Meta:
        model = Menage
        fields = [
            'nom_menage',
            'reference_menage',
            'utilisateur',
            'agence', # ✅ Ajouté
            'localite',
            'adresse_complete',
            'latitude',
            'longitude',
            'type_habitation',
            'nombre_personnes',
            'personne_contact',
            'telephone_secondaire',
            'point_repere',
            'surface_m2'
        ]

        widgets = {
            'nom_menage': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white placeholder-slate-500',
                'placeholder': 'Ex: Famille MBEMBA'
            }),
            'reference_menage': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/30 border border-white/10 rounded-lg text-slate-400',
                'placeholder': 'Sera généré automatiquement',
                'readonly': 'readonly'
            }),
            'localite': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white',
                'id': 'id_localite'
            }),
            'adresse_complete': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white placeholder-slate-500',
                'placeholder': 'Numéro, rue, quartier, ville...'
            }),
            'latitude': forms.HiddenInput(attrs={'id': 'id_latitude'}),
            'longitude': forms.HiddenInput(attrs={'id': 'id_longitude'}),
            'type_habitation': forms.Select(attrs={
                'class': 'w-full px-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white'
            }),
            'nombre_personnes': forms.NumberInput(attrs={
                'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white',
                'min': '1',
                'value': '1'
            }),
            'personne_contact': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white placeholder-slate-500',
                'placeholder': 'Nom complet du contact'
            }),
            'telephone_secondaire': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white placeholder-slate-500',
                'placeholder': '+242 XX XXX XXXX'
            }),
            'point_repere': forms.TextInput(attrs={
                'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white placeholder-slate-500',
                'placeholder': 'Ex: Près de l\'église Saint-Jean'
            }),
            'surface_m2': forms.NumberInput(attrs={
                'class': 'w-full pl-10 pr-4 py-3 bg-slate-800/50 border border-white/10 rounded-lg text-white',
                'placeholder': 'Surface',
                'min': '0'
            }),

            'agence': forms.Select(attrs={
                'class': 'w-full px-4 py-3 form-input appearance-none',
                'id': 'id_agence'
            })
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # ✅ CHARGER UNIQUEMENT LES UTILISATEURS CLIENT DISPONIBLES
        if self.instance and self.instance.pk and self.instance.utilisateur:
            # MODE MODIFICATION : inclure l'utilisateur actuel + ceux disponibles
            self.fields['utilisateur'].queryset = CustomUser.objects.filter(
                Q(id=self.instance.utilisateur.id) |  # L'utilisateur actuel
                Q(role='CLIENT', statut='ACTIF', menage__isnull=True)  # Les disponibles
            ).distinct().order_by('username')

            # Pré-remplir les champs
            if self.instance.utilisateur:
                self.fields['telephone_principal'].initial = self.instance.utilisateur.telephone
                self.fields['email'].initial = self.instance.utilisateur.email
        else:
            # MODE CRÉATION : uniquement les CLIENT actifs sans ménage
            self.fields['utilisateur'].queryset = CustomUser.objects.filter(
                role='CLIENT',
                statut='ACTIF',
                menage__isnull=True
            ).order_by('username')

        # Rendre certains champs optionnels
        self.fields['reference_menage'].required = False
        self.fields['localite'].required = False  # Sera rempli par le géocodage
        # Agence obligatoire
        self.fields['agence'].required = True
        self.fields['agence'].empty_label = "— Sélectionner une agence —"

    def clean_reference_menage(self):
        """✅ Générer automatiquement une référence unique si non fournie"""
        reference = self.cleaned_data.get('reference_menage')

        if not reference or reference.strip() == '':
            # Générer une référence unique
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            reference = f"MEN-{timestamp}"

            # Vérifier l'unicité (au cas où)
            counter = 1
            base_ref = reference
            while Menage.objects.filter(reference_menage=reference).exists():
                reference = f"{base_ref}-{counter}"
                counter += 1
        else:
            # Vérifier que la référence n'existe pas déjà
            existing = Menage.objects.filter(reference_menage=reference)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise forms.ValidationError(
                    f"La référence '{reference}' existe déjà. Veuillez en choisir une autre."
                )

        return reference

    def clean_telephone_principal(self):
        """✅ Vérifier l'unicité du téléphone si création d'un nouveau CLIENT"""
        telephone = self.cleaned_data.get('telephone_principal')
        utilisateur_existant = self.cleaned_data.get('utilisateur')

        # Si un utilisateur CLIENT est sélectionné, pas besoin de vérifier
        if utilisateur_existant:
            return telephone

        # Si on crée un nouveau CLIENT, vérifier que le téléphone n'existe pas
        if telephone and telephone.strip():
            if CustomUser.objects.filter(telephone=telephone).exists():
                raise forms.ValidationError(
                    f"Un utilisateur avec le téléphone {telephone} existe déjà. "
                    f"Sélectionnez-le dans la liste ou utilisez un autre numéro."
                )

        return telephone

    def clean_email(self):
        """✅ Vérifier l'unicité de l'email si création d'un nouveau CLIENT"""
        email = self.cleaned_data.get('email')
        utilisateur_existant = self.cleaned_data.get('utilisateur')

        # Si un utilisateur CLIENT est sélectionné, pas besoin de vérifier
        if utilisateur_existant:
            return email

        # Si on crée un nouveau CLIENT, vérifier que l'email n'existe pas
        if email and email.strip():
            if CustomUser.objects.filter(email=email).exists():
                raise forms.ValidationError(
                    f"Un utilisateur avec l'email {email} existe déjà. "
                    f"Sélectionnez-le dans la liste ou utilisez un autre email."
                )

        return email

    def clean(self):
        """✅ Validation globale du formulaire"""
        cleaned_data = super().clean()

        # 1. Vérifier les coordonnées GPS
        latitude = cleaned_data.get('latitude')
        longitude = cleaned_data.get('longitude')

        if not latitude or not longitude:
            raise forms.ValidationError(
                "⚠️ Les coordonnées GPS sont obligatoires. "
                "Veuillez placer le marqueur sur la carte à l'étape 2."
            )

        # 2. Vérifier la logique utilisateur
        utilisateur = cleaned_data.get('utilisateur')
        telephone_principal = cleaned_data.get('telephone_principal')
        email = cleaned_data.get('email')
        personne_contact = cleaned_data.get('personne_contact')

        # Si aucun utilisateur CLIENT sélectionné, il faut au moins un contact
        if not utilisateur:
            if not (telephone_principal or email):
                raise forms.ValidationError(
                    "⚠️ Veuillez sélectionner un utilisateur CLIENT existant OU "
                    "fournir au moins un téléphone ou email pour créer un nouveau compte."
                )

            if not personne_contact:
                raise forms.ValidationError(
                    "⚠️ La personne de contact est obligatoire pour créer un nouveau compte CLIENT."
                )

        return cleaned_data

    def save(self, commit=True):
        """
        ✅ LOGIQUE DE SAUVEGARDE AVEC GESTION INTELLIGENTE DE L'UTILISATEUR
        """
        menage = super().save(commit=False)

        # ✅ GESTION DE L'UTILISATEUR (uniquement en création)
        if not self.instance.pk:  # Nouveau ménage uniquement
            utilisateur_existant = self.cleaned_data.get('utilisateur')

            if utilisateur_existant:
                # ═══════════════════════════════════════════════════════
                # ✅ CAS 1 : UTILISATEUR CLIENT EXISTANT SÉLECTIONNÉ
                # ═══════════════════════════════════════════════════════
                menage.utilisateur = utilisateur_existant

                print("\n" + "=" * 80)
                print("✅ UTILISATEUR CLIENT EXISTANT ASSIGNÉ AU MÉNAGE")
                print("=" * 80)
                print(f"   Username    : {utilisateur_existant.username}")
                print(f"   Nom complet : {utilisateur_existant.get_full_name()}")
                print(f"   Email       : {utilisateur_existant.email}")
                print(f"   Téléphone   : {utilisateur_existant.telephone or 'Non renseigné'}")
                print(f"   Rôle        : {utilisateur_existant.role}")
                print("=" * 80 + "\n")

            else:
                # ═══════════════════════════════════════════════════════
                # ✅ CAS 2 : CRÉER AUTOMATIQUEMENT UN NOUVEAU CLIENT
                # ═══════════════════════════════════════════════════════

                # Récupérer les données
                personne_contact = self.cleaned_data.get('personne_contact', 'Client')
                telephone = self.cleaned_data.get('telephone_principal', '').strip()
                email = self.cleaned_data.get('email', '').strip()
                nom_menage = self.cleaned_data.get('nom_menage', 'menage')

                # Générer un username unique
                base_username = nom_menage.lower().replace(' ', '_').replace('-', '_')[:20]
                username = base_username
                counter = 1

                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}_{counter}"
                    counter += 1

                # Séparer nom et prénom
                nom_parts = personne_contact.split(' ', 1)
                first_name = nom_parts[0] if len(nom_parts) > 0 else 'Client'
                last_name = nom_parts[1] if len(nom_parts) > 1 else ''

                # ✅ CRÉER LE NOUVEAU CLIENT
                nouvel_utilisateur = CustomUser.objects.create(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email=email or f"{username}@menage.local",
                    telephone=telephone if telephone else None,  # None si vide (contrainte unique)
                    role='CLIENT',  # ✅ RÔLE CLIENT
                    statut='ACTIF',  # ✅ STATUT ACTIF
                    cree_par=self.user  # ✅ Traçabilité
                )

                # Mot de passe par défaut
                nouvel_utilisateur.set_password('changeme123')
                nouvel_utilisateur.save()

                # Assigner au ménage
                menage.utilisateur = nouvel_utilisateur

                # Log de création
                print("\n" + "=" * 80)
                print("✅ NOUVEAU COMPTE CLIENT CRÉÉ AUTOMATIQUEMENT")
                print("=" * 80)
                print(f"   Username       : {username}")
                print(f"   Nom complet    : {first_name} {last_name}")
                print(f"   Email          : {nouvel_utilisateur.email}")
                print(f"   Téléphone      : {telephone or 'Non renseigné'}")
                print(f"   Rôle           : CLIENT")
                print(f"   Statut         : ACTIF")
                print(f"   Mot de passe   : changeme123 (à modifier)")
                print(f"   Créé par       : {self.user.username if self.user else 'Système'}")
                print("=" * 80 + "\n")

        # Sauvegarder le ménage
        if commit:
            menage.save()

        return menage


# ==========================================
# AUTRES FORMULAIRES (inchangés)
# ==========================================

class MenageSearchForm(forms.Form):
    """Formulaire de recherche de ménages"""
    q = forms.CharField(
        required=False,
        label="Recherche",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nom, référence, adresse...'
        })
    )

    statut = forms.ChoiceField(
        choices=[('', 'Tous')] + list(Menage.STATUT_CHOICES),
        required=False,
        label="Statut",
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class UpdateLocalisationForm(forms.ModelForm):
    """Formulaire pour mettre à jour la localisation GPS"""

    class Meta:
        model = Menage
        fields = ['latitude', 'longitude', 'precision_gps', 'source_geolocalisation']
        widgets = {
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
            'precision_gps': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'source_geolocalisation': forms.Select(attrs={'class': 'form-control'}),
        }


class MenageImportForm(forms.Form):
    """Formulaire d'importation de ménages depuis CSV"""
    fichier_csv = forms.FileField(
        label="Fichier CSV",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'})
    )
    delimiter = forms.CharField(
        initial=',',
        max_length=1,
        label="Délimiteur",
        widget=forms.TextInput(attrs={'class': 'form-control', 'maxlength': '1'})
    )
    creer_utilisateurs = forms.BooleanField(
        required=False,
        initial=True,
        label="Créer automatiquement les utilisateurs CLIENT",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )