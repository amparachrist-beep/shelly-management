from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import FactureConsommation, LigneFacture, BatchFacturation, Relance


class LigneFactureInline(admin.TabularInline):
    """Inline pour les lignes de facture"""
    model = LigneFacture
    extra = 0
    fields = ['type_ligne', 'description', 'quantite', 'unite',
              'prix_unitaire', 'montant_ht', 'montant_tva', 'montant_ttc']
    readonly_fields = ['montant_ht', 'montant_tva', 'montant_ttc']


class RelanceInline(admin.TabularInline):
    """Inline pour les relances"""
    model = Relance
    extra = 0
    fields = ['type_relance', 'numero_relance', 'sujet', 'date_envoi_prevue', 'statut']
    readonly_fields = ['numero_relance']


@admin.register(FactureConsommation)
class FactureConsommationAdmin(admin.ModelAdmin):
    """Configuration admin pour les factures de consommation"""
    list_display = ['numero_facture', 'compteur_link', 'periode',
                    'total_ttc', 'montant_paye', 'solde_du_display',
                    'statut_display', 'date_echeance', 'jours_retard_display']
    list_filter = ['statut', 'periode', 'date_emission', 'compteur__menage__localite']
    search_fields = ['numero_facture', 'compteur__numero_contrat',
                     'compteur__menage__nom_menage', 'compteur__menage__utilisateur__email']
    readonly_fields = ['total_ht', 'tva_montant', 'total_ttc', 'solde_du',
                       'pourcentage_paye', 'jours_retard', 'created_at', 'updated_at']
    date_hierarchy = 'date_emission'

    fieldsets = (
        ('Identification', {
            'fields': ('numero_facture', 'compteur', 'consommation', 'periode')
        }),
        ('Dates', {
            'fields': ('date_emission', 'date_echeance', 'date_paiement')
        }),
        ('Consommation', {
            'fields': ('consommation_kwh', 'montant_consommation', 'montant_abonnement')
        }),
        ('Taxes', {
            'fields': ('tva_taux', 'redevance_communale', 'autres_taxes')
        }),
        ('Calculs', {
            'fields': ('total_ht', 'tva_montant', 'total_ttc', 'montant_paye',
                       'solde_du', 'pourcentage_paye', 'jours_retard')
        }),
        ('Statut et documents', {
            'fields': ('statut', 'fichier_pdf', 'qr_code', 'calcul_tranches')
        }),
        ('Informations', {
            'fields': ('notes', 'motif_annulation', 'emis_par')
        }),
        ('Dates système', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    inlines = [LigneFactureInline, RelanceInline]

    def compteur_link(self, obj):
        """Lien vers le compteur"""
        url = reverse('admin:compteurs_compteur_change', args=[obj.compteur.id])
        return format_html('<a href="{}">{}</a>', url, obj.compteur.numero_contrat)

    compteur_link.short_description = "Compteur"

    def solde_du_display(self, obj):
        """Affichage coloré du solde dû"""
        color = 'success' if obj.solde_du == 0 else 'warning' if obj.solde_du < obj.total_ttc else 'danger'
        return format_html(
            '<span class="badge bg-{}">{:.2f} FCFA</span>',
            color, obj.solde_du
        )

    solde_du_display.short_description = "Solde dû"

    def statut_display(self, obj):
        """Affichage coloré du statut"""
        colors = {
            'BROUILLON': 'secondary',
            'ÉMISE': 'info',
            'PARTIELLEMENT_PAYÉE': 'warning',
            'PAYÉE': 'success',
            'EN_RETARD': 'danger',
            'ANNULEE': 'dark',
            'REMBOURSEE': 'light'
        }
        color = colors.get(obj.statut, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_statut_display()
        )

    statut_display.short_description = "Statut"

    def jours_retard_display(self, obj):
        """Affichage des jours de retard"""
        if obj.jours_retard > 0:
            return format_html(
                '<span class="badge bg-danger">{} jours</span>',
                obj.jours_retard
            )
        return "-"

    jours_retard_display.short_description = "Retard"

    actions = ['emettre_factures', 'marquer_payees', 'marquer_annulees']

    def emettre_factures(self, request, queryset):
        """Émettre les factures sélectionnées"""
        updated = queryset.filter(statut='BROUILLON').update(statut='ÉMISE')
        self.message_user(request, f"{updated} facture(s) émise(s).")

    emettre_factures.short_description = "Émettre les factures"

    def marquer_payees(self, request, queryset):
        """Marquer comme payées"""
        for facture in queryset:
            facture.montant_paye = facture.total_ttc
            facture.statut = 'PAYÉE'
            facture.save()
        self.message_user(request, f"{queryset.count()} facture(s) marquée(s) comme payée(s).")

    marquer_payees.short_description = "Marquer comme payées"

    def marquer_annulees(self, request, queryset):
        """Marquer comme annulées"""
        updated = queryset.filter(statut__in=['BROUILLON', 'ÉMISE']).update(statut='ANNULEE')
        self.message_user(request, f"{updated} facture(s) annulée(s).")

    marquer_annulees.short_description = "Annuler les factures"


@admin.register(LigneFacture)
class LigneFactureAdmin(admin.ModelAdmin):
    """Configuration admin pour les lignes de facture"""
    list_display = ['facture', 'type_ligne', 'description', 'quantite',
                    'unite', 'prix_unitaire', 'montant_ht', 'montant_ttc']
    list_filter = ['type_ligne', 'facture__periode']
    search_fields = ['description', 'facture__numero_facture']
    readonly_fields = ['montant_ht', 'montant_tva', 'montant_ttc']

    fieldsets = (
        ('Identification', {
            'fields': ('facture', 'type_ligne', 'description')
        }),
        ('Quantité et prix', {
            'fields': ('quantite', 'unite', 'prix_unitaire', 'taux_tva')
        }),
        ('Tranches (si applicable)', {
            'fields': ('tranche_min', 'tranche_max', 'ordre')
        }),
        ('Calculs', {
            'fields': ('montant_ht', 'montant_tva', 'montant_ttc')
        }),
        ('Date', {
            'fields': ('created_at',)
        }),
    )

@admin.register(BatchFacturation)
class BatchFacturationAdmin(admin.ModelAdmin):
    """Configuration admin pour les batches de facturation"""
    list_display = ['reference', 'periode', 'statut', 'progression',
                    'total_factures', 'factures_generees', 'total_ttc',
                    'date_generation', 'cree_par']
    list_filter = ['statut', 'periode']
    search_fields = ['reference', 'description']
    readonly_fields = ['progression', 'total_ttc', 'total_consommation_kwh',
                       'logs', 'erreurs', 'started_at', 'completed_at', 'created_at']

    fieldsets = (
        ('Identification', {
            'fields': ('reference', 'description', 'cree_par')
        }),
        ('Période', {
            'fields': ('periode', 'date_generation', 'parametres')
        }),
        ('Statistiques', {
            'fields': ('total_factures', 'factures_generees', 'factures_erreur',
                       'total_ttc', 'total_consommation_kwh')
        }),
        ('Statut', {
            'fields': ('statut', 'progression')
        }),
        ('Documents', {
            'fields': ('fichier_rapport',)
        }),
        ('Logs', {
            'fields': ('logs', 'erreurs')
        }),
        ('Dates', {
            'fields': ('started_at', 'completed_at', 'created_at')
        }),
    )


@admin.register(Relance)
class RelanceAdmin(admin.ModelAdmin):
    """Configuration admin pour les relances"""
    list_display = ['facture', 'type_relance', 'numero_relance', 'sujet',
                    'date_envoi_prevue', 'date_envoi_reelle', 'statut', 'agent']
    list_filter = ['type_relance', 'statut', 'date_envoi_prevue']
    search_fields = ['sujet', 'facture__numero_facture', 'destinataire_email']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Identification', {
            'fields': ('facture', 'type_relance', 'numero_relance')
        }),
        ('Contenu', {
            'fields': ('sujet', 'message')
        }),
        ('Destinataire', {
            'fields': ('destinataire_email', 'destinataire_telephone', 'destinataire_adresse')
        }),
        ('Envoi', {
            'fields': ('date_envoi_prevue', 'date_envoi_reelle', 'cout_envoi')
        }),
        ('Statut', {
            'fields': ('statut', 'statut_delivrance')
        }),
        ('Réponse', {
            'fields': ('date_reponse', 'reponse_client', 'engagement_paiement', 'agent')
        }),
        ('Dates système', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    actions = ['envoyer_relances', 'marquer_envoyees']

    def envoyer_relances(self, request, queryset):
        """Simuler l'envoi des relances"""
        updated = queryset.filter(statut='EN_ATTENTE').update(
            statut='ENVOYEE',
            date_envoi_reelle=timezone.now()
        )
        self.message_user(request, f"{updated} relance(s) envoyée(s).")

    envoyer_relances.short_description = "Envoyer les relances"

    def marquer_envoyees(self, request, queryset):
        """Marquer comme envoyées"""
        updated = queryset.filter(statut='EN_ATTENTE').update(statut='ENVOYEE')
        self.message_user(request, f"{updated} relance(s) marquée(s) comme envoyée(s).")

    marquer_envoyees.short_description = "Marquer comme envoyées"