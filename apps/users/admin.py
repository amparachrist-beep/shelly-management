from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserUpdateForm


class CustomUserAdmin(UserAdmin):
    """Configuration admin pour CustomUser"""
    add_form = CustomUserCreationForm
    form = CustomUserUpdateForm
    model = CustomUser

    # Champs en lecture seule (IMPORTANT pour les champs auto_now)
    readonly_fields = ('date_modification', 'last_login', 'date_joined')

    # Liste des utilisateurs
    list_display = ('username', 'email', 'telephone', 'role', 'statut',
                    'is_active', 'date_joined', 'last_login', 'date_modification')
    list_filter = ('role', 'statut', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'telephone', 'first_name', 'last_name',
                     'matricule_agent')

    # Détail de l'utilisateur - Modifié pour regrouper les champs en lecture seule
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {
            'fields': ('first_name', 'last_name', 'email', 'telephone')
        }),
        ('Informations professionnelles', {
            'fields': ('role', 'statut', 'matricule_agent', 'poste_agent')
        }),
        ('Géolocalisation', {
            'fields': ('derniere_position_lat', 'derniere_position_lng'),
            'classes': ('collapse',)  # Peut être réduit par défaut
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser',
                       'groups', 'user_permissions')
        }),
        ('Dates et audit', {
            'fields': ('last_login', 'date_joined', 'date_modification', 'cree_par')
        }),
    )

    # Formulaire d'ajout
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'telephone', 'password1', 'password2',
                       'role', 'first_name', 'last_name', 'statut')
        }),
    )

    # Filtrage hiérarchique
    filter_horizontal = ('groups', 'user_permissions',)

    # Ordre des champs
    ordering = ('-date_joined',)

    # Actions personnalisées
    actions = ['activate_users', 'deactivate_users', 'make_agents', 'make_clients']

    def activate_users(self, request, queryset):
        """Activer les utilisateurs sélectionnés"""
        updated = queryset.update(is_active=True, statut='ACTIF')
        self.message_user(request, f'{updated} utilisateur(s) activé(s).')

    activate_users.short_description = "Activer les utilisateurs sélectionnés"

    def deactivate_users(self, request, queryset):
        """Désactiver les utilisateurs sélectionnés"""
        updated = queryset.update(is_active=False, statut='INACTIF')
        self.message_user(request, f'{updated} utilisateur(s) désactivé(s).')

    deactivate_users.short_description = "Désactiver les utilisateurs sélectionnés"

    def make_agents(self, request, queryset):
        """Transformer en agents"""
        updated = queryset.update(role='AGENT_TERRAIN')
        self.message_user(request, f'{updated} utilisateur(s) transformé(s) en agents.')

    make_agents.short_description = "Transformer en agents"

    def make_clients(self, request, queryset):
        """Transformer en clients"""
        updated = queryset.update(role='CLIENT')
        self.message_user(request, f'{updated} utilisateur(s) transformé(s) en clients.')

    make_clients.short_description = "Transformer en clients"

    def get_form(self, request, obj=None, **kwargs):
        """S'assurer que le formulaire exclut les champs non éditable"""
        form = super().get_form(request, obj, **kwargs)

        # Si c'est un formulaire d'édition (pas d'ajout)
        if obj:
            # date_modification est déjà en readonly_fields
            pass

        return form

    def get_readonly_fields(self, request, obj=None):
        """Déterminer les champs en lecture seule selon le contexte"""
        readonly_fields = list(super().get_readonly_fields(request, obj))

        # Pour un objet existant, ajouter des champs supplémentaires en lecture seule
        if obj:
            readonly_fields.extend(['date_modification', 'last_login', 'date_joined'])
        else:
            # Pour la création, date_modification n'existe pas encore
            readonly_fields = ['last_login', 'date_joined']

        return tuple(set(readonly_fields))


# Enregistrement
admin.site.register(CustomUser, CustomUserAdmin)