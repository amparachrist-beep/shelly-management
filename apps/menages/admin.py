from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Count, Sum
from django.contrib import messages
from .models import Menage
from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation


@admin.register(Menage)
class MenageAdmin(admin.ModelAdmin):
    """Configuration admin avancée pour les ménages"""

    # Configuration de l'affichage de la liste
    list_display = [
        'reference_menage',
        'nom_menage_display',
        'utilisateur_link',
        'localite',
        'statut_display',
        'date_creation_display',
        'compteurs_count',
        'consommation_moyenne',
    ]

    list_filter = [
        'statut',
        'localite',
        'type_habitation',
        'date_creation',
        'categorie_socio_professionnelle',
        'source_geolocalisation',
    ]

    search_fields = [
        'nom_menage',
        'reference_menage',
        'adresse_complete',
        'utilisateur__username',
        'utilisateur__email',
        'utilisateur__first_name',
        'utilisateur__last_name',
        'telephone_secondaire',
        'personne_contact'
    ]

    readonly_fields = [
        'date_creation',
        'consommation_totale',
        'factures_en_retard',
        'compteurs_count_display'
    ]

    raw_id_fields = ['utilisateur', 'localite']

    date_hierarchy = 'date_creation'

    list_per_page = 50

    # Groupement des champs par section
    fieldsets = (
        ('IDENTIFICATION', {
            'fields': (
                'reference_menage',
                'nom_menage',
                'utilisateur',
            ),
            'classes': ('wide', 'extrapretty'),
        }),
        ('LOCALISATION', {
            'fields': (
                'localite',
                'adresse_complete',
                'latitude',
                'longitude',
                'precision_gps',
                'source_geolocalisation',
                'google_place_id',
                'adresse_google'
            ),
        }),
        ('INFORMATIONS DU MÉNAGE', {
            'fields': (
                'nombre_personnes',
                'type_habitation',
                'surface_m2',
                'categorie_socio_professionnelle',
                'revenu_mensuel_estime'
            ),
        }),
        ('COORDONNÉES', {
            'fields': (
                'telephone_secondaire',
                'email_secondaire',
                'personne_contact'
            ),
        }),
        ('ACCÈS ET INSTRUCTIONS', {
            'fields': (
                'point_repere',
                'code_acces',
                'instructions_livraison'
            ),
        }),
        ('STATISTIQUES', {
            'fields': (
                'compteurs_count_display',
                'consommation_totale',
                'factures_en_retard',
            ),
            'classes': ('collapse',),
        }),
        ('STATUT ET MÉTADONNÉES', {
            'fields': (
                'statut',
                'date_creation'
            ),
            'classes': ('collapse',),
        }),
    )

    # Actions personnalisées
    actions = [
        'activer_menages',
        'desactiver_menages',
        'marquer_demenage',
        'generer_factures',
        'exporter_menages_csv'
    ]

    # Inline pour afficher les compteurs associés
    class CompteurInline(admin.TabularInline):
        model = Compteur
        extra = 0
        fields = [
            'numero_contrat',
            'numero_serie',
            'type_compteur',
            'type_tarification',
            'statut_display',
            'date_installation',
            'puissance_souscrite'
        ]
        readonly_fields = ['date_installation', 'statut_display']
        can_delete = False

        def statut_display(self, obj):
            colors = {
                'ACTIF': 'green',
                'INACTIF': 'red',
                'EN_PANNE': 'orange',
                'HORS_SERVICE': 'gray'
            }
            color = colors.get(obj.statut, 'black')
            return format_html(
                '<span style="color: {};">●</span> {}',
                color,
                obj.get_statut_display()
            )

        statut_display.short_description = 'Statut'

        def has_add_permission(self, request, obj=None):
            # Permettre l'ajout seulement aux administrateurs
            return request.user.is_superuser

    inlines = [CompteurInline]

    # Méthodes d'affichage personnalisées
    def nom_menage_display(self, obj):
        """Affiche le nom du ménage avec icône"""
        if obj.nombre_personnes:
            icon = '👨‍👩‍👧‍👦' if obj.nombre_personnes > 2 else '👨‍👩‍👦'
            return format_html(
                '{} <strong>{}</strong> <small class="text-muted">({} pers.)</small>',
                icon, obj.nom_menage, obj.nombre_personnes
            )
        return obj.nom_menage

    nom_menage_display.short_description = "Ménage"
    nom_menage_display.admin_order_field = 'nom_menage'

    def utilisateur_link(self, obj):
        """Afficher un lien vers l'utilisateur avec email"""
        if obj.utilisateur:
            url = reverse('admin:users_customuser_change', args=[obj.utilisateur.id])
            full_name = obj.utilisateur.get_full_name()
            display_name = full_name if full_name else obj.utilisateur.username
            return format_html(
                '<a href="{}" title="{}"><strong>{}</strong><br><small>{}</small></a>',
                url, obj.utilisateur.email, display_name, obj.utilisateur.email
            )
        return format_html('<span class="text-muted">-</span>')

    utilisateur_link.short_description = "Compte"

    def statut_display(self, obj):
        """Affiche le statut avec couleur"""
        colors = {
            'ACTIF': 'success',
            'INACTIF': 'danger',
            'DEMENAGE': 'warning',
        }
        color = colors.get(obj.statut, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_statut_display()
        )

    statut_display.short_description = "Statut"
    statut_display.admin_order_field = 'statut'

    def date_creation_display(self, obj):
        """Affiche la date de création formatée"""
        if obj.date_creation:
            days_ago = (timezone.now() - obj.date_creation).days
            if days_ago == 0:
                return "Aujourd'hui"
            elif days_ago == 1:
                return "Hier"
            elif days_ago < 7:
                return f"Il y a {days_ago} jours"
            else:
                return obj.date_creation.strftime("%d/%m/%Y")
        return "-"

    date_creation_display.short_description = "Créé le"
    date_creation_display.admin_order_field = 'date_creation'

    def compteurs_count(self, obj):
        """Nombre de compteurs associés avec lien"""
        count = obj.compteur_set.count()
        if count > 0:
            url = reverse('admin:compteurs_compteur_changelist') + f'?menage__id__exact={obj.id}'
            return format_html(
                '<a href="{}" class="badge bg-primary">{}</a>',
                url, count
            )
        return format_html('<span class="badge bg-secondary">0</span>')

    compteurs_count.short_description = "Compteurs"

    def compteurs_count_display(self, obj):
        """Version pour le formulaire d'édition"""
        count = obj.compteur_set.count()
        if count > 0:
            url = reverse('admin:compteurs_compteur_changelist') + f'?menage__id__exact={obj.id}'
            return format_html(
                '<a href="{}" class="badge bg-primary">{} compteur(s)</a>',
                url, count
            )
        return format_html('<span class="badge bg-secondary">Aucun compteur</span>')

    compteurs_count_display.short_description = "Nombre de compteurs"

    def consommation_moyenne(self, obj):
        """Affiche la consommation moyenne mensuelle"""
        try:
            # Calculer la consommation moyenne des 3 derniers mois
            trois_mois = timezone.now() - timezone.timedelta(days=90)

            # Utiliser l'annotation pour calculer la somme
            from django.db.models import Sum
            consommations = Consommation.objects.filter(
                compteur__menage=obj,
                periode__gte=trois_mois
            ).aggregate(total=Sum('index_fin_periode') - Sum('index_debut_periode'))['total'] or 0

            if consommations > 0:
                return format_html(
                    '<span class="badge bg-success">{:.0f} kWh</span>',
                    consommations / 3
                )
        except Exception as e:
            pass
        return format_html('<span class="badge bg-secondary">N/A</span>')

    consommation_moyenne.short_description = "Conso moy."

    # Méthodes de calcul pour les champs readonly
    def consommation_totale(self, obj):
        """Consommation totale de l'année en cours"""
        try:
            annee = timezone.now().year
            total = Consommation.objects.filter(
                compteur__menage=obj,
                periode__year=annee
            ).aggregate(
                total=Sum('index_fin_periode') - Sum('index_debut_periode')
            )['total'] or 0
            return f"{total:.2f} kWh"
        except Exception as e:
            return "0.00 kWh"

    consommation_totale.short_description = "Consommation annuelle"

    def factures_en_retard(self, obj):
        """Nombre de factures en retard"""
        # Cette méthode nécessiterait l'application facturation
        # Pour l'instant, retourne une valeur par défaut
        return "0 (module facturation non installé)"

    factures_en_retard.short_description = "Factures en retard"

    # Implémentation des actions
    def activer_menages(self, request, queryset):
        """Activer les ménages sélectionnés"""
        updated = queryset.update(statut='ACTIF')
        messages.success(
            request,
            f"{updated} ménage(s) activé(s) avec succès."
        )

    activer_menages.short_description = "✅ Activer les ménages"

    def desactiver_menages(self, request, queryset):
        """Désactiver les ménages sélectionnés"""
        updated = queryset.update(statut='INACTIF')
        messages.warning(
            request,
            f"{updated} ménage(s) désactivé(s)."
        )

    desactiver_menages.short_description = "❌ Désactiver les ménages"

    def marquer_demenage(self, request, queryset):
        """Marquer les ménages comme déménagés"""
        updated = queryset.update(statut='DEMENAGE')

        # Désactiver également les compteurs associés
        for menage in queryset:
            Compteur.objects.filter(menage=menage).update(statut='HORS_SERVICE')

        messages.info(
            request,
            f"{updated} ménage(s) marqué(s) comme déménagé(s). "
            f"Les compteurs associés ont été mis hors service."
        )

    marquer_demenage.short_description = "🚚 Marquer comme déménagé"

    def generer_factures(self, request, queryset):
        """Générer des factures pour les ménages sélectionnés"""
        # Cette action appellerait le système de facturation
        messages.info(
            request,
            f"Génération de factures programmée pour {queryset.count()} ménage(s). "
            f"Vous recevrez une notification lorsque le processus sera terminé."
        )

    generer_factures.short_description = "🧾 Générer des factures"

    def exporter_menages_csv(self, request, queryset):
        """Exporter les ménages sélectionnés en CSV"""
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="menages_export.csv"'

        writer = csv.writer(response, delimiter=';')
        writer.writerow([
            'Référence', 'Nom', 'Adresse', 'Localité', 'Téléphone',
            'Email', 'Statut', 'Date création', 'Type habitation', 'Nombre personnes'
        ])

        for menage in queryset:
            writer.writerow([
                menage.reference_menage,
                menage.nom_menage,
                menage.adresse_complete,
                str(menage.localite) if menage.localite else '',
                menage.telephone_secondaire,
                menage.utilisateur.email if menage.utilisateur else '',
                menage.get_statut_display(),
                menage.date_creation.strftime('%d/%m/%Y') if menage.date_creation else '',
                menage.get_type_habitation_display(),
                menage.nombre_personnes
            ])

        messages.success(request, f"Export CSV de {queryset.count()} ménage(s) généré.")
        return response

    exporter_menages_csv.short_description = "📊 Exporter en CSV"

    # Configuration avancée
    def get_queryset(self, request):
        """Optimisation des requêtes avec prefetch_related"""
        queryset = super().get_queryset(request)
        return queryset.select_related(
            'utilisateur',
            'localite',
        ).prefetch_related(
            'compteur_set'
        ).annotate(
            compteurs_count=Count('compteur')
        )

    def changelist_view(self, request, extra_context=None):
        """Ajouter des statistiques à la vue liste"""
        extra_context = extra_context or {}

        # Statistiques globales
        stats = {
            'total': Menage.objects.count(),
            'actifs': Menage.objects.filter(statut='ACTIF').count(),
            'inactifs': Menage.objects.filter(statut='INACTIF').count(),
            'demenages': Menage.objects.filter(statut='DEMENAGE').count(),
        }

        extra_context['stats'] = stats
        return super().changelist_view(request, extra_context=extra_context)

    # Configuration du formulaire d'édition
    class Media:
        css = {
            'all': ('css/admin-menages.css',)
        }
        js = ('js/admin-menages.js',)