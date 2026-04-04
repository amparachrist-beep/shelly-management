from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from .models import CustomUser
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _
from apps.menages.models import Agence  # ✅ import Agence


class CustomUserCreationForm(UserCreationForm):
    """Formulaire de création d'utilisateur"""
    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'exemple@domaine.com'})
    )
    telephone = forms.CharField(
        required=True,
        label="Téléphone",
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'XX XX XX XX'})
    )
    role = forms.ChoiceField(
        choices=CustomUser.ROLE_CHOICES,
        label="Rôle",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_role'})
    )
    agence = forms.ModelChoiceField(
        queryset=Agence.objects.filter(actif=True).order_by('nom'),
        required=False,
        empty_label="— Sélectionner une agence —",
        label="Agence",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'id_agence'})
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'telephone', 'first_name', 'last_name',
                  'role', 'matricule_agent', 'poste_agent', 'agence')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom d\'utilisateur'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom'}),
            'matricule_agent': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Matricule'}),
            'poste_agent': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Poste'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError("Cet email est déjà utilisé.")
        return email

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        if CustomUser.objects.filter(telephone=telephone).exists():
            raise forms.ValidationError("Ce numéro de téléphone est déjà utilisé.")
        return telephone

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        agence = cleaned_data.get('agence')
        if role == 'AGENT_TERRAIN' and not agence:
            self.add_error('agence', "Une agence est obligatoire pour un agent de terrain.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.telephone = self.cleaned_data['telephone']
        user.role = self.cleaned_data['role']
        user.agence = self.cleaned_data.get('agence')  # ✅
        if commit:
            user.save()
        return user


class CustomUserUpdateForm(UserChangeForm):
    """Formulaire de modification d'utilisateur"""
    password = None  # Ne pas afficher le champ password

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'telephone',
                  'role', 'statut', 'matricule_agent', 'poste_agent', 'agence')  # ✅
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control', 'id': 'id_role'}),
            'statut': forms.Select(attrs={'class': 'form-control'}),
            'matricule_agent': forms.TextInput(attrs={'class': 'form-control'}),
            'poste_agent': forms.TextInput(attrs={'class': 'form-control'}),
            'agence': forms.Select(attrs={'class': 'form-control', 'id': 'id_agence'}),  # ✅
        }

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        agence = cleaned_data.get('agence')
        if role == 'AGENT_TERRAIN' and not agence:
            self.add_error('agence', "Une agence est obligatoire pour un agent de terrain.")
        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    """Formulaire de mise à jour du profil (pour l'utilisateur connecté)"""

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'email', 'telephone')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
        }


class PasswordChangeForm(forms.Form):
    """Formulaire de changement de mot de passe"""
    old_password = forms.CharField(
        label="Ancien mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text=password_validation.password_validators_help_text_html()
    )
    new_password2 = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError("L'ancien mot de passe est incorrect.")
        return old_password

    def clean_new_password2(self):
        password1 = self.cleaned_data.get('new_password1')
        password2 = self.cleaned_data.get('new_password2')

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")

        password_validation.validate_password(password2, self.user)
        return password2

    def save(self, commit=True):
        password = self.cleaned_data['new_password1']
        self.user.set_password(password)
        if commit:
            self.user.save()
        return self.user


class CustomAuthenticationForm(AuthenticationForm):
    """Formulaire de connexion personnalisé"""
    username = forms.CharField(
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom d\'utilisateur'})
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mot de passe'})
    )