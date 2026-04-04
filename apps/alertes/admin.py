from django.contrib import admin
from django.utils.html import format_html
from .models import Alerte, RegleAlerte


@admin.register(Alerte)
class AlerteAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'type_alerte_display', 'compteur_display', 'niveau_display',
        'statut_display', 'date_detection', 'utilisateur_display'
    ]
    list_filter = [
        'type_alerte', 'niveau', 'statut', 'destinataire_role',
        'date_detection'
    ]
    search_fields = [
        'message', 'compteur__numero_serie', 'compteur__menage__nom_menage',
        'utilisateur__email'
    ]
    readonly_fields = ['date_detection', 'date_traitement']
    fieldsets = (
        ('Informations Générales', {
            'fields': ('type_alerte', 'consommation', 'compteur')
        }),
        ('Détails de l\'Alerte', {
            'fields': ('message', 'niveau', 'valeur_mesuree', 'valeur_seuil', 'unite')
        }),
        ('Destinataires', {
            'fields': ('destinataire_role', 'utilisateur')
        }),
        ('Traitement', {
            'fields': ('statut', 'traite_par', 'notes_traitement')
        }),
        ('Horodatage', {
            'fields': ('date_detection', 'date_traitement'),
            'classes': ('collapse',)
        }),
    )
    actions = ['marquer_comme_lues', 'marquer_comme_traitees']

    def type_alerte_display(self, obj):
        return obj.get_type_alerte_display()

    type_alerte_display.short_description = 'Type'

    def compteur_display(self, obj):
        if obj.compteur:
            menage_info = f" - {obj.compteur.menage.nom_menage}" if obj.compteur.menage else ""
            return f"{obj.compteur.numero_serie}{menage_info}"
        return "-"

    compteur_display.short_description = 'Compteur/Ménage'

    def niveau_display(self, obj):
        color = {
            'INFO': 'blue',
            'WARNING': 'orange',
            'CRITIQUE': 'red'
        }.get(obj.niveau, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_niveau_display()
        )

    niveau_display.short_description = 'Niveau'

    def statut_display(self, obj):
        color = {
            'ACTIVE': 'red',
            'LU': 'blue',
            'TRAITEE': 'green',
            'IGNOREE': 'gray'
        }.get(obj.statut, 'black')
        return format_html(
            '<span style="color: {};">{}</span>',
            color,
            obj.get_statut_display()
        )

    statut_display.short_description = 'Statut'

    def utilisateur_display(self, obj):
        return obj.utilisateur.email if obj.utilisateur else "-"

    utilisateur_display.short_description = 'Utilisateur'

    def marquer_comme_lues(self, request, queryset):
        updated = queryset.update(statut='LU')
        self.message_user(request, f"{updated} alertes marquées comme lues.")

    marquer_comme_lues.short_description = "Marquer comme lues"

    def marquer_comme_traitees(self, request, queryset):
        updated = queryset.update(statut='TRAITEE', traite_par=request.user)
        self.message_user(request, f"{updated} alertes marquées comme traitées.")

    marquer_comme_traitees.short_description = "Marquer comme traitées"


@admin.register(RegleAlerte)
class RegleAlerteAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_alerte_display', 'seuil', 'actif']
    list_filter = ['type_alerte', 'actif']
    search_fields = ['nom', 'type_alerte']
    list_editable = ['actif']

    def type_alerte_display(self, obj):
        return dict(Alerte.TYPE_ALERTE).get(obj.type_alerte, obj.type_alerte)

    type_alerte_display.short_description = 'Type d\'alerte'