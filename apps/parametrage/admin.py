from django.contrib import admin

# Register your models here.

from django.contrib import admin
from .models import Departement, Localite, TypeTarification, Zone
import json


class DepartementAdmin(admin.ModelAdmin):
    """Configuration admin pour les départements"""
    list_display = ['nom', 'code_departement', 'region', 'date_creation']
    list_filter = ['region']
    search_fields = ['nom', 'code_departement', 'region']
    readonly_fields = ['date_creation']
    fieldsets = (
        ('Informations de base', {
            'fields': ('nom', 'code_departement', 'region')
        }),
        ('Coordonnées géographiques', {
            'fields': ('centre_latitude', 'centre_longitude', 'polygone')
        }),
        ('Dates', {
            'fields': ('date_creation',)
        }),
    )


class LocaliteAdmin(admin.ModelAdmin):
    """Configuration admin pour les localités"""
    list_display = ['nom', 'code_postal', 'departement', 'type_localite', 'latitude', 'longitude']
    list_filter = ['type_localite', 'departement']
    search_fields = ['nom', 'code_postal', 'google_place_id']
    raw_id_fields = ['departement']

    fieldsets = (
        ('Informations de base', {
            'fields': ('nom', 'code_postal', 'departement', 'type_localite')
        }),
        ('Coordonnées géographiques', {
            'fields': ('latitude', 'longitude', 'google_place_id', 'zone_rayon_km')
        }),
    )


class TypeTarificationAdmin(admin.ModelAdmin):
    """Configuration admin pour les tarifications"""
    list_display = ['code', 'nom', 'categorie', 'abonnement_mensuel',
                    'devise', 'date_effet', 'date_fin', 'actif']
    list_filter = ['categorie', 'actif', 'date_effet']
    search_fields = ['code', 'nom', 'reference_arrete']
    readonly_fields = ['date_creation']

    fieldsets = (
        ('Informations de base', {
            'fields': ('code', 'nom', 'categorie', 'actif')
        }),
        ('Tarification', {
            'fields': ('tranches', 'abonnement_mensuel', 'devise')
        }),
        ('Informations réglementaires', {
            'fields': ('reference_arrete', 'date_effet', 'date_fin')
        }),
        ('Descriptions', {
            'fields': ('description', 'conditions')
        }),
        ('Dates', {
            'fields': ('date_creation',)
        }),
    )

    def formfield_for_dbfield(self, db_field, **kwargs):
        """Afficher les tranches JSON de manière lisible"""
        if db_field.name == 'tranches':
            kwargs['widget'] = admin.widgets.AdminTextareaWidget(
                attrs={'style': 'font-family: monospace;'}
            )
        return super().formfield_for_dbfield(db_field, **kwargs)

    actions = ['activate_tarifs', 'deactivate_tarifs']

    def activate_tarifs(self, request, queryset):
        """Activer les tarifications sélectionnées"""
        updated = queryset.update(actif=True)
        self.message_user(request, f'{updated} tarification(s) activée(s).')

    activate_tarifs.short_description = "Activer les tarifications"

    def deactivate_tarifs(self, request, queryset):
        """Désactiver les tarifications sélectionnées"""
        updated = queryset.update(actif=False)
        self.message_user(request, f'{updated} tarification(s) désactivée(s).')

    deactivate_tarifs.short_description = "Désactiver les tarifications"


class ZoneAdmin(admin.ModelAdmin):
    """Configuration admin pour les zones"""
    list_display = ['nom', 'departement', 'actif']
    list_filter = ['actif', 'departement']
    search_fields = ['nom']
    raw_id_fields = ['departement']


# Enregistrement
admin.site.register(Departement, DepartementAdmin)
admin.site.register(Localite, LocaliteAdmin)
admin.site.register(TypeTarification, TypeTarificationAdmin)
admin.site.register(Zone, ZoneAdmin)
