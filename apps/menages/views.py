from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.db.models import Q, Count, Sum, Avg
from django.db.models.functions import TruncMonth, TruncYear
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import date, datetime, timedelta
import csv, json
from .models import Menage, Agence
from .forms import MenageForm, MenageSearchForm, UpdateLocalisationForm, MenageImportForm
from apps.compteurs.models import Compteur
from apps.consommation.models import ConsommationJournaliere
from apps.facturation.models import FactureConsommation
from apps.paiements.models import Paiement
from apps.parametrage.models import Localite
from apps.users.models import CustomUser


# ==================== DÉCORATEURS DE PERMISSION ====================

def admin_or_agent_required(view_func):
    """Décorateur pour vérifier si l'utilisateur est admin ou agent"""

    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Veuillez vous connecter.")
            return redirect('users:login')

        if not (request.user.role == 'ADMIN' or request.user.role == 'AGENT_TERRAIN'):
            messages.error(request, "Accès refusé. Administrateur ou agent requis.")
            return redirect('dashboard:home')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def client_access(view_func):
    """Décorateur pour vérifier l'accès client à son propre ménage"""

    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Veuillez vous connecter.")
            return redirect('users:login')

        menage_id = kwargs.get('pk')
        if menage_id:
            menage = get_object_or_404(Menage, pk=menage_id)

            # Vérifier si l'utilisateur a accès à ce ménage
            if not (request.user.role == 'ADMIN' or
                    request.user.role == 'AGENT_TERRAIN' or
                    (request.user.role == 'CLIENT' and menage.utilisateur == request.user)):
                messages.error(request, "Accès refusé à ce ménage.")
                return redirect('dashboard:home')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


class AdminOrAgentRequiredMixin(UserPassesTestMixin):
    """Mixin pour vérifier si l'utilisateur est admin ou agent"""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.role == 'ADMIN' or user.role == 'AGENT_TERRAIN')


# ==================== VUES PRINCIPALES ====================
# Assurez-vous que ces imports sont présents en haut de votre fichier
 # Adaptez l'import selon votre structure


class MenageListView(LoginRequiredMixin, ListView):
    """Liste des ménages avec filtrage par rôle et recherche."""
    model = Menage
    template_name = 'gestion/menages/list.html'
    context_object_name = 'menages'
    paginate_by = 20

    def get_queryset(self):
        # Commence avec une requête optimisée
        queryset = Menage.objects.select_related('utilisateur', 'localite')

        user = self.request.user

        # ✅ MODIFICATION DE LA LOGIQUE DE RÔLE ICI
        if user.role == 'CLIENT':
            # Seuls les clients voient leur propre ménage
            queryset = queryset.filter(utilisateur=user)

        # Les utilisateurs avec les rôles ADMIN et AGENT_TERRAIN
        # voient TOUS les ménages sans restriction ici.
        # (Le filtre spécifique à AGENT_TERRAIN a été retiré)

        # --- Les autres filtres restent identiques ---

        # Recherche
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(nom_menage__icontains=search) |
                Q(reference_menage__icontains=search) |
                Q(adresse_complete__icontains=search) |
                Q(utilisateur__first_name__icontains=search) |
                Q(utilisateur__last_name__icontains=search) |
                Q(utilisateur__telephone__icontains=search) |
                Q(telephone_secondaire__icontains=search)
            )

        # Filtres supplémentaires
        localite = self.request.GET.get('localite', '')
        if localite:
            queryset = queryset.filter(localite_id=localite)

        statut = self.request.GET.get('statut', '')
        if statut:
            queryset = queryset.filter(statut=statut)

        type_habitation = self.request.GET.get('type_habitation', '')
        if type_habitation:
            queryset = queryset.filter(type_habitation=type_habitation)

        # Trier par défaut (le tri est appliqué à la fin)
        queryset = queryset.order_by('-date_creation')

        return queryset

    def get_context_data(self, **kwargs):
        # Récupère le contexte de la classe parente
        context = super().get_context_data(**kwargs)

        # Le queryset est déjà filtré et trié grâce à get_queryset()
        filtered_queryset = self.get_queryset()

        # Statistiques basées sur la liste affichée
        total = filtered_queryset.count()
        actifs = filtered_queryset.filter(statut='ACTIF').count()
        inactifs = filtered_queryset.filter(statut='INACTIF').count()

        # Ajout des données supplémentaires au contexte
        context.update({
            'title': 'Ménages',
            'form': MenageSearchForm(self.request.GET or None),
            'stats': [
                {
                    'title': 'Total Ménages',
                    'value': total,
                    'color': 'primary',
                    'icon': 'fas fa-home'
                },
                {
                    'title': 'Actifs',
                    'value': actifs,
                    'color': 'success',
                    'icon': 'fas fa-check-circle'
                },
                {
                    'title': 'Inactifs',
                    'value': inactifs,
                    'color': 'warning',
                    'icon': 'fas fa-exclamation-circle'
                },
            ],
            'localites': Localite.objects.all(),
        })
        return context


from datetime import date
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.views.generic import DetailView
import logging

logger = logging.getLogger(__name__)

class MenageDetailView(LoginRequiredMixin, DetailView):
    model = Menage
    template_name = 'gestion/menages/detail.html'
    context_object_name = 'menage'

    def get_queryset(self):
        return Menage.objects.select_related('utilisateur', 'localite')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        menage = self.object
        user = self.request.user

        # Permissions
        if not (
            user.role == 'ADMIN' or
            user.role == 'AGENT_TERRAIN' or
            (user.role == 'CLIENT' and menage.utilisateur == user)
        ):
            messages.error(self.request, "Accès refusé.")
            return context

        # ======================
        # Compteurs
        # ======================
        from apps.compteurs.models import Compteur
        compteurs = Compteur.objects.filter(
            menage=menage
        ).select_related(
            'type_tarification',
            'type_compteur_detail'
        )

        context['compteurs'] = compteurs
        context['compteurs_count'] = compteurs.count()

        # ======================
        # Factures récentes
        # ======================
        from apps.facturation.models import FactureConsommation
        factures = FactureConsommation.objects.filter(
            compteur__menage=menage
        ).select_related(
            'compteur',
        ).order_by('-date_emission')[:5]

        context['factures_recentes'] = factures

        # ======================
        # Factures impayées
        # ======================
        factures_impayees = FactureConsommation.objects.filter(
            compteur__menage=menage,
            statut__in=['EMISE', 'PARTIELLEMENT_PAYEE']
        ).select_related('compteur')

        context['factures_impayees'] = factures_impayees
        context['montant_impaye'] = sum(
            f.solde_du for f in factures_impayees
        )

        # ======================
        # Consommation du mois
        # ======================
        from apps.consommation.models import ConsommationJournaliere
        today = date.today()
        debut_mois = date(today.year, today.month, 1)

        consommation_mois = ConsommationJournaliere.objects.filter(
            compteur__menage=menage,
            date__gte=debut_mois
        ).aggregate(total=Sum('consommation_kwh'))['total'] or 0

        context['consommation_mois'] = consommation_mois

        # ======================
        # Paiements récents - COMMENTÉ TEMPORAIREMENT
        # ======================
        # La section paiements est commentée car le modèle Paiement n'existe pas
        context['paiements_recentes'] = []  # Valeur par défaut

        # ======================
        # Actions
        # ======================
        actions = []

        if user.role in ['ADMIN', 'AGENT_TERRAIN']:
            if menage.statut == 'ACTIF':
                actions.append({
                    'text': 'Désactiver',
                    'url': f'{menage.pk}/desactiver/',
                    'icon': 'ban',
                    'color': 'warning'
                })
            elif menage.statut == 'INACTIF':
                actions.append({
                    'text': 'Activer',
                    'url': f'{menage.pk}/activer/',
                    'icon': 'check-circle',
                    'color': 'success'
                })

            actions.append({
                'text': 'Ajouter Compteur',
                'url': f'/compteurs/create/?menage={menage.pk}',
                'icon': 'plus-circle',
                'color': 'primary'
            })

        context['actions'] = actions
        context['today'] = today

        return context

class MenageUpdateView(LoginRequiredMixin, AdminOrAgentRequiredMixin, UpdateView):
    """Modification d'un ménage"""
    model = Menage
    form_class = MenageForm
    template_name = 'gestion/menages/form.html'
    success_url = reverse_lazy('menages:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Modifier {self.object.nom_menage}',
            'submit_text': 'Modifier',
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Ménage {self.object.reference_menage} modifié.")
        return super().form_valid(form)


# ==================== VUES D'ACTIONS ====================

@login_required
@admin_or_agent_required
def menage_activer(request, pk):
    """Activer un ménage"""
    menage = get_object_or_404(Menage, pk=pk)

    if menage.statut != 'INACTIF':
        messages.warning(request, f"Le ménage {menage.nom_menage} n'est pas inactif.")
        return redirect('menages:detail', pk=pk)

    menage.statut = 'ACTIF'
    menage.save()

    messages.success(request, f"Ménage {menage.nom_menage} activé.")
    return redirect('menages:detail', pk=pk)


@login_required
@admin_or_agent_required
def menage_desactiver(request, pk):
    """Désactiver un ménage"""
    menage = get_object_or_404(Menage, pk=pk)

    if menage.statut != 'ACTIF':
        messages.warning(request, f"Le ménage {menage.nom_menage} n'est pas actif.")
        return redirect('menages:detail', pk=pk)

    menage.statut = 'INACTIF'
    menage.save()

    messages.warning(request, f"Ménage {menage.nom_menage} désactivé.")
    return redirect('menages:detail', pk=pk)


@login_required
@admin_or_agent_required
def menage_demenager(request, pk):
    """Marquer un ménage comme déménagé"""
    menage = get_object_or_404(Menage, pk=pk)

    menage.statut = 'DEMENAGE'
    menage.save()

    # Désactiver tous les compteurs du ménage
    Compteur.objects.filter(menage=menage).update(statut='INACTIF')

    messages.info(request, f"Ménage {menage.nom_menage} marqué comme déménagé.")
    return redirect('menages:detail', pk=pk)


@login_required
@admin_or_agent_required
def update_localisation(request, pk):
    """Mettre à jour la localisation GPS d'un ménage"""
    menage = get_object_or_404(Menage, pk=pk)

    if request.method == 'POST':
        form = UpdateLocalisationForm(request.POST, instance=menage)
        if form.is_valid():
            form.save()
            messages.success(request, "Localisation mise à jour.")
            return redirect('menages:detail', pk=pk)
    else:
        form = UpdateLocalisationForm(instance=menage)

    return render(request, 'menages/update_localisation.html', {
        'form': form,
        'menage': menage,
        'title': f'Mettre à jour localisation - {menage.nom_menage}'
    })


# ==================== VUES SPÉCIFIQUES ====================

class MenageCompteursView(LoginRequiredMixin, DetailView):
    """Liste des compteurs d'un ménage"""
    model = Menage
    template_name = 'menages/compteurs.html'
    context_object_name = 'menage'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        menage = self.object

        # Vérifier les permissions
        user = self.request.user
        if not (user.role == 'ADMIN' or
                user.role == 'AGENT_TERRAIN' or
                (user.role == 'CLIENT' and menage.utilisateur == user)):
            messages.error(self.request, "Accès refusé.")
            return context

        compteurs = Compteur.objects.filter(menage=menage).select_related(
            'type_tarification', 'capteur_shelly'
        )

        context.update({
            'compteurs': compteurs,
            'title': f'Compteurs - {menage.nom_menage}'
        })
        return context


class MenageFacturesView(LoginRequiredMixin, DetailView):
    """Liste des factures d'un ménage"""
    model = Menage
    template_name = 'menages/factures.html'
    context_object_name = 'menage'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        menage = self.object

        # Vérifier les permissions
        user = self.request.user
        if not (user.role == 'ADMIN' or
                user.role == 'AGENT_TERRAIN' or
                (user.role == 'CLIENT' and menage.utilisateur == user)):
            messages.error(self.request, "Accès refusé.")
            return context

        factures = FactureConsommation.objects.filter(
            menage=menage
        ).select_related('periode_facturation').order_by('-periode_facturation__date_fin')

        # Statistiques
        stats = factures.aggregate(
            total_factures=Count('id'),
            total_montant=Sum('montant_total'),
            montant_paye=Sum('montant_paye'),
            montant_impaye=Sum('solde_du'),
        )

        context.update({
            'factures': factures,
            'stats': stats,
            'title': f'Factures - {menage.nom_menage}'
        })
        return context


class MenageConsommationView(LoginRequiredMixin, DetailView):
    """Consommation d'un ménage"""
    model = Menage
    template_name = 'menages/consommation.html'
    context_object_name = 'menage'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        menage = self.object

        # Vérifier les permissions
        user = self.request.user
        if not (user.role == 'ADMIN' or
                user.role == 'AGENT_TERRAIN' or
                (user.role == 'CLIENT' and menage.utilisateur == user)):
            messages.error(self.request, "Accès refusé.")
            return context

        # Consommation des 30 derniers jours
        date_debut = timezone.now().date() - timedelta(days=30)
        consommations = ConsommationJournaliere.objects.filter(
            compteur__menage=menage,
            date__gte=date_debut
        ).order_by('date')

        # Données pour le graphique
        dates = []
        valeurs = []
        for conso in consommations:
            dates.append(conso.date.strftime('%d/%m'))
            valeurs.append(float(conso.valeur))

        # Statistiques
        stats = consommations.aggregate(
            total=Sum('valeur'),
            moyenne=Avg('valeur'),
            max=Max('valeur'),
            min=Min('valeur')
        )

        context.update({
            'consommations': consommations,
            'dates_json': json.dumps(dates),
            'valeurs_json': json.dumps(valeurs),
            'stats': stats,
            'title': f'Consommation - {menage.nom_menage}',
            'periode': f"{date_debut.strftime('%d/%m/%Y')} - {timezone.now().date().strftime('%d/%m/%Y')}"
        })
        return context


class MenagePaiementsView(LoginRequiredMixin, DetailView):
    """Paiements d'un ménage"""
    model = Menage
    template_name = 'menages/paiements.html'
    context_object_name = 'menage'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        menage = self.object

        # Vérifier les permissions
        user = self.request.user
        if not (user.role == 'ADMIN' or
                user.role == 'AGENT_TERRAIN' or
                (user.role == 'CLIENT' and menage.utilisateur == user)):
            messages.error(self.request, "Accès refusé.")
            return context

        paiements = Paiement.objects.filter(
            facture__menage=menage
        ).select_related('facture', 'cree_par').order_by('-date_paiement')

        # Statistiques
        stats = paiements.aggregate(
            total_paiements=Count('id'),
            total_montant=Sum('montant'),
            montant_valide=Sum('montant', filter=Q(statut='VALIDÉ')),
        )

        context.update({
            'paiements': paiements,
            'stats': stats,
            'title': f'Paiements - {menage.nom_menage}'
        })
        return context


# ==================== VUES DE STATISTIQUES ====================

class StatsMenagesView(LoginRequiredMixin, AdminOrAgentRequiredMixin, TemplateView):
    """Statistiques sur les ménages"""
    template_name = 'menages/stats.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques globales
        stats_globales = Menage.objects.aggregate(
            total=Count('id'),
            actifs=Count('id', filter=Q(statut='ACTIF')),
            inactifs=Count('id', filter=Q(statut='INACTIF')),
            demenages=Count('id', filter=Q(statut='DEMENAGE')),
        )

        # Par type d'habitation
        par_type = Menage.objects.values('type_habitation').annotate(
            nombre=Count('id'),
            pourcentage=Count('id') * 100.0 / Menage.objects.count()
        ).order_by('-nombre')

        # Évolution mensuelle des créations
        creation_mensuelle = Menage.objects.annotate(
            mois=TruncMonth('date_creation')
        ).values('mois').annotate(
            nombre=Count('id')
        ).order_by('-mois')[:12]

        # Par localité
        par_localite = Localite.objects.annotate(
            nombre_menages=Count('menage'),
            menages_actifs=Count('menage', filter=Q(menage__statut='ACTIF'))
        ).order_by('-nombre_menages')

        context.update({
            'title': 'Statistiques des Ménages',
            'stats_globales': stats_globales,
            'par_type': par_type,
            'creation_mensuelle': list(creation_mensuelle),
            'par_localite': par_localite,
        })
        return context


# ==================== VUES POUR IMPORT/EXPORT ====================

@login_required
@admin_or_agent_required
def import_menages(request):
    """Importation de ménages depuis CSV"""
    if request.method == 'POST':
        form = MenageImportForm(request.POST, request.FILES)
        if form.is_valid():
            fichier = form.cleaned_data['fichier_csv']
            delimiter = form.cleaned_data['delimiter']
            creer_utilisateurs = form.cleaned_data['creer_utilisateurs']

            try:
                decoded_file = fichier.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file, delimiter=delimiter)

                imported_count = 0
                errors = []

                for row in reader:
                    try:
                        # Récupérer la localité
                        localite_nom = row.get('localite')
                        localite = Localite.objects.filter(nom__iexact=localite_nom).first()
                        if not localite:
                            errors.append(f"Localité '{localite_nom}' non trouvée")
                            continue

                        # Vérifier si le ménage existe déjà
                        reference = row.get('reference_menage')
                        if Menage.objects.filter(reference_menage=reference).exists():
                            errors.append(f"Ménage avec référence '{reference}' existe déjà")
                            continue

                        # Créer l'utilisateur si nécessaire
                        utilisateur = None
                        if creer_utilisateurs:
                            email = row.get('email')
                            telephone = row.get('telephone')

                            if email or telephone:
                                # Vérifier si l'utilisateur existe déjà
                                if email:
                                    utilisateur = CustomUser.objects.filter(email=email).first()
                                elif telephone:
                                    utilisateur = CustomUser.objects.filter(telephone=telephone).first()

                                if not utilisateur:
                                    # Créer un nouvel utilisateur
                                    username = f"user_{reference.lower()}"
                                    utilisateur = CustomUser.objects.create(
                                        username=username,
                                        first_name=row.get('nom', ''),
                                        last_name=row.get('prenom', ''),
                                        email=email,
                                        telephone=telephone,
                                        role='CLIENT'
                                    )
                                    utilisateur.set_password('password123')  # Mot de passe temporaire
                                    utilisateur.save()

                        # Créer le ménage
                        menage = Menage.objects.create(
                            nom_menage=row.get('nom_menage', ''),
                            reference_menage=reference,
                            utilisateur=utilisateur,
                            localite=localite,
                            adresse_complete=row.get('adresse_complete', ''),
                            latitude=row.get('latitude'),
                            longitude=row.get('longitude'),
                            nombre_personnes=row.get('nombre_personnes', 1),
                            type_habitation=row.get('type_habitation', 'MAISON'),
                            statut=row.get('statut', 'ACTIF')
                        )

                        imported_count += 1

                    except Exception as e:
                        errors.append(f"Ligne {reader.line_num}: {str(e)}")

                if imported_count > 0:
                    messages.success(request, f"{imported_count} ménage(s) importé(s) avec succès.")

                if errors:
                    messages.warning(request, f"{len(errors)} erreur(s) lors de l'import.")
                    # Vous pourriez logger ces erreurs ou les afficher dans un fichier

                return redirect('menages:list')

            except Exception as e:
                messages.error(request, f"Erreur lors de la lecture du fichier: {str(e)}")

    else:
        form = MenageImportForm()

    return render(request, 'menages/import.html', {
        'form': form,
        'title': 'Importation de ménages'
    })


@login_required
@admin_or_agent_required
def export_menages_csv(request):
    """Exporter les ménages en CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="menages.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Référence', 'Nom', 'Utilisateur', 'Localité', 'Adresse',
        'Téléphone', 'Email', 'Nombre personnes', 'Type habitation',
        'Surface (m²)', 'Statut', 'Date création'
    ])

    # Récupérer les ménages selon les filtres
    menages = Menage.objects.select_related('utilisateur', 'localite')

    # Appliquer les mêmes filtres que la liste si présents
    search = request.GET.get('search', '')
    if search:
        menages = menages.filter(
            Q(nom_menage__icontains=search) |
            Q(reference_menage__icontains=search) |
            Q(adresse_complete__icontains=search)
        )

    statut = request.GET.get('statut', '')
    if statut:
        menages = menages.filter(statut=statut)

    for menage in menages:
        writer.writerow([
            menage.reference_menage,
            menage.nom_menage,
            menage.utilisateur.username if menage.utilisateur else '',
            menage.localite.nom if menage.localite else '',
            menage.adresse_complete,
            menage.utilisateur.telephone if menage.utilisateur else '',
            menage.utilisateur.email if menage.utilisateur else '',
            menage.nombre_personnes,
            menage.type_habitation,
            menage.surface_m2 or '',
            menage.statut,
            menage.date_creation.strftime('%Y-%m-%d %H:%M'),
        ])

    return response


# ==================== VUES POUR AJAX/API SIMPLE ====================

@login_required
def menage_stats_api(request, pk):
    """API pour les statistiques d'un ménage (AJAX)"""
    menage = get_object_or_404(Menage, pk=pk)

    # Vérifier les permissions
    user = request.user
    if not (user.role == 'ADMIN' or
            user.role == 'AGENT_TERRAIN' or
            (user.role == 'CLIENT' and menage.utilisateur == user)):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    # Statistiques
    compteurs_count = Compteur.objects.filter(menage=menage).count()

    today = date.today()
    debut_mois = date(today.year, today.month, 1)
    consommation_mois = ConsommationJournaliere.objects.filter(
        compteur__menage=menage,
        date__gte=debut_mois
    ).aggregate(total=Sum('valeur'))['total'] or 0

    factures_impayees = FactureConsommation.objects.filter(
        menage=menage,
        statut__in=['EMISE', 'PARTIELLEMENT_PAYEE']
    )
    montant_impaye = sum(f.solde_du for f in factures_impayees)

    return JsonResponse({
        'compteurs_count': compteurs_count,
        'consommation_mois': float(consommation_mois),
        'factures_impayees': factures_impayees.count(),
        'montant_impaye': float(montant_impaye),
        'statut': menage.statut
    })


@login_required
def menage_search_api(request):
    """Recherche de ménages (AJAX)"""
    query = request.GET.get('q', '')

    if not query:
        return JsonResponse([], safe=False)

    menages = Menage.objects.filter(
        Q(nom_menage__icontains=query) |
        Q(reference_menage__icontains=query) |
        Q(adresse_complete__icontains=query) |
        Q(utilisateur__first_name__icontains=query) |
        Q(utilisateur__last_name__icontains=query)
    ).select_related('utilisateur', 'localite')[:10]

    results = []
    for menage in menages:
        results.append({
            'id': menage.id,
            'reference': menage.reference_menage,
            'nom': menage.nom_menage,
            'utilisateur': menage.utilisateur.get_full_name() if menage.utilisateur else '',
            'localite': menage.localite.nom if menage.localite else '',
            'adresse': menage.adresse_complete,
        })

    return JsonResponse(results, safe=False)


@login_required
def menage_factures_impayees_api(request, pk):
    """Factures impayées d'un ménage (AJAX)"""
    menage = get_object_or_404(Menage, pk=pk)

    # Vérifier les permissions
    user = request.user
    if not (user.role == 'ADMIN' or
            user.role == 'AGENT_TERRAIN' or
            (user.role == 'CLIENT' and menage.utilisateur == user)):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    factures = FactureConsommation.objects.filter(
        menage=menage,
        statut__in=['EMISE', 'PARTIELLEMENT_PAYEE']
    ).order_by('periode_facturation__date_fin')

    results = []
    today = date.today()

    for facture in factures:
        jours_retard = 0
        if facture.date_echeance and facture.date_echeance < today:
            jours_retard = (today - facture.date_echeance).days

        results.append({
            'numero': facture.numero_facture,
            'periode': f"{facture.periode_facturation.date_debut} - {facture.periode_facturation.date_fin}",
            'date_echeance': facture.date_echeance.strftime('%d/%m/%Y') if facture.date_echeance else '',
            'jours_retard': jours_retard,
            'montant_total': float(facture.montant_total),
            'solde_du': float(facture.solde_du),
            'statut': facture.statut,
        })

    return JsonResponse(results, safe=False)


# apps/menages/views.py - MODIFIEZ votre fonction reverse_geocode_local

# apps/menages/views.py - VOICI LA FONCTION COMPLÈTE :
from math import radians, cos, sin, asin, sqrt  # Ajoutez cet import si ce n'est pas déjà fait


# apps/menages/views.py
# REMPLACEZ votre fonction reverse_geocode_local PAR CELLE-CI

@login_required
def reverse_geocode_local(request):
    """
    Géocodage inverse avec FIX pour le conflit Pool/Brazzaville
    ✅ Détection intelligente basée sur la distance ET les polygones
    ✅ Brazzaville : Priorité absolue dans un rayon de 20 km
    ✅ Autres zones : Détection classique
    ✅ Retourne toujours localite_id pour la sélection dans le formulaire
    """
    from apps.parametrage.models import Localite, Departement
    from django.contrib.gis.geos import Point
    from math import radians, cos, sin, asin, sqrt

    lat = request.GET.get('lat')
    lon = request.GET.get('lon')

    if not lat or not lon:
        return JsonResponse({
            'error': 'Coordonnées manquantes',
            'success': False,
            'localite': 'Non détectée',
            'localite_id': None,
            'departement': 'Non détecté',
            'departement_id': None,
            'methode': 'aucune',
            'precision': 'Coordonnées manquantes',
            'fiabilite': 'aucune'
        }, status=400)

    try:
        lat_float = float(lat)
        lon_float = float(lon)
        search_point = Point(lon_float, lat_float, srid=4326)

        # ==================== FONCTION HAVERSINE ====================
        def haversine(lat1, lon1, lat2, lon2):
            """Calcule la distance entre 2 points GPS en km"""
            R = 6371.0
            phi1 = radians(lat1)
            phi2 = radians(lat2)
            delta_phi = radians(lat2 - lat1)
            delta_lambda = radians(lon2 - lon1)
            a = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
            return R * 2 * asin(sqrt(a))

        # ==================== VÉRIFICATION PRIORITAIRE : BRAZZAVILLE ====================
        # Coordonnées approximatives du centre de Brazzaville
        BRAZZA_CENTER_LAT = -4.2634
        BRAZZA_CENTER_LON = 15.2429
        BRAZZA_RADIUS_KM = 20  # Rayon de 20 km autour du centre

        dist_to_brazza = haversine(lat_float, lon_float, BRAZZA_CENTER_LAT, BRAZZA_CENTER_LON)

        # 🔴 SI LE POINT EST À MOINS DE 20 KM DE BRAZZAVILLE → FORCER BRAZZAVILLE
        if dist_to_brazza <= BRAZZA_RADIUS_KM:
            print(f"🎯 Point dans le rayon de Brazzaville ({dist_to_brazza:.2f} km)")

            brazza = Departement.objects.filter(nom__icontains='brazza').first()

            if brazza:
                # Chercher le quartier le plus proche
                quartiers = Localite.objects.filter(
                    departement=brazza,
                    type_localite='QUARTIER',
                    latitude__isnull=False,
                    longitude__isnull=False
                ).exclude(latitude=0, longitude=0)

                meilleur_quartier = None
                distance_min = float('inf')

                for quartier in quartiers:
                    try:
                        dist = haversine(
                            lat_float, lon_float,
                            float(quartier.latitude),
                            float(quartier.longitude)
                        )
                        if dist < distance_min:
                            distance_min = dist
                            meilleur_quartier = quartier
                    except:
                        continue

                # ✅ Si on trouve un quartier dans un rayon raisonnable (5 km)
                if meilleur_quartier and distance_min <= 5.0:
                    return JsonResponse({
                        'success': True,
                        'localite': meilleur_quartier.nom,
                        'localite_id': meilleur_quartier.id,
                        'departement': brazza.nom,
                        'departement_id': brazza.id,
                        'distance_km': round(distance_min, 3),
                        'methode': 'proximite_quartier',
                        'precision': f'À {int(distance_min * 1000)} m de {meilleur_quartier.nom}',
                        'fiabilite': 'élevée' if distance_min < 1.0 else 'moyenne'
                    })

                # ✅ Sinon, retourner Brazzaville sans quartier précis
                else:
                    # Chercher une localité par défaut pour Brazzaville
                    localite_par_defaut = Localite.objects.filter(
                        departement=brazza,
                        type_localite='VILLE'
                    ).first()

                    return JsonResponse({
                        'success': True,
                        'localite': localite_par_defaut.nom if localite_par_defaut else 'Brazzaville (centre)',
                        'localite_id': localite_par_defaut.id if localite_par_defaut else None,
                        'departement': brazza.nom,
                        'departement_id': brazza.id,
                        'distance_km': round(dist_to_brazza, 2),
                        'methode': 'proximite_ville',
                        'precision': f'Zone périphérique de Brazzaville ({int(dist_to_brazza)} km du centre)',
                        'fiabilite': 'moyenne'
                    })

        # ==================== VÉRIFICATION PRIORITAIRE : POINTE-NOIRE ====================
        PNOIRE_CENTER_LAT = -4.7773
        PNOIRE_CENTER_LON = 11.8650
        PNOIRE_RADIUS_KM = 15

        dist_to_pnoire = haversine(lat_float, lon_float, PNOIRE_CENTER_LAT, PNOIRE_CENTER_LON)

        if dist_to_pnoire <= PNOIRE_RADIUS_KM:
            pnoire = Departement.objects.filter(nom__icontains='pointe').first()

            if pnoire:
                quartiers = Localite.objects.filter(
                    departement=pnoire,
                    type_localite='QUARTIER',
                    latitude__isnull=False,
                    longitude__isnull=False
                ).exclude(latitude=0, longitude=0)

                meilleur_quartier = None
                distance_min = float('inf')

                for quartier in quartiers:
                    try:
                        dist = haversine(
                            lat_float, lon_float,
                            float(quartier.latitude),
                            float(quartier.longitude)
                        )
                        if dist < distance_min:
                            distance_min = dist
                            meilleur_quartier = quartier
                    except:
                        continue

                if meilleur_quartier and distance_min <= 5.0:
                    return JsonResponse({
                        'success': True,
                        'localite': meilleur_quartier.nom,
                        'localite_id': meilleur_quartier.id,
                        'departement': pnoire.nom,
                        'departement_id': pnoire.id,
                        'distance_km': round(distance_min, 3),
                        'methode': 'proximite_quartier',
                        'precision': f'À {int(distance_min * 1000)} m de {meilleur_quartier.nom}',
                        'fiabilite': 'élevée' if distance_min < 1.0 else 'moyenne'
                    })
                else:
                    localite_par_defaut = Localite.objects.filter(
                        departement=pnoire,
                        type_localite='VILLE'
                    ).first()
                    return JsonResponse({
                        'success': True,
                        'localite': localite_par_defaut.nom if localite_par_defaut else 'Pointe-Noire',
                        'localite_id': localite_par_defaut.id if localite_par_defaut else None,
                        'departement': pnoire.nom,
                        'departement_id': pnoire.id,
                        'distance_km': round(dist_to_pnoire, 2),
                        'methode': 'proximite_ville',
                        'precision': f'Zone de Pointe-Noire ({int(dist_to_pnoire)} km du centre)',
                        'fiabilite': 'moyenne'
                    })

        # ==================== DÉTECTION CLASSIQUE POUR AUTRES ZONES ====================
        # 1. Détection par polygone
        departement = Departement.objects.filter(geom__contains=search_point).first()
        localite = None
        distance_min = None
        methode = 'polygone'

        # 2. Si pas de polygone, fallback par proximité
        if not departement:
            methode = 'proximite_departement'
            depts = Departement.objects.exclude(centre_latitude__isnull=True)
            dept_proche = None
            min_dist = float('inf')

            for dept in depts:
                try:
                    dist = haversine(
                        lat_float, lon_float,
                        float(dept.centre_latitude),
                        float(dept.centre_longitude)
                    )
                    if dist < min_dist:
                        min_dist = dist
                        dept_proche = dept
                except:
                    continue

            if dept_proche and min_dist < 50:
                departement = dept_proche
                distance_min = min_dist

        # 3. Chercher la localité dans ce département
        if departement:
            # D'abord par polygone
            localite = Localite.objects.filter(
                departement=departement,
                geom__contains=search_point
            ).first()

            # Sinon par proximité
            if not localite:
                methode = 'proximite_localite'
                localites = Localite.objects.filter(
                    departement=departement,
                    latitude__isnull=False,
                    longitude__isnull=False
                ).exclude(latitude=0, longitude=0)

                meilleure = None
                dist_min = float('inf')
                rayon_max = 10.0

                for loc in localites:
                    try:
                        dist = haversine(
                            lat_float, lon_float,
                            float(loc.latitude),
                            float(loc.longitude)
                        )
                        if dist < dist_min and dist <= rayon_max:
                            dist_min = dist
                            meilleure = loc
                    except:
                        continue

                localite = meilleure
                if localite:
                    distance_min = dist_min

            if localite:
                # ✅ Localité trouvée avec succès
                return JsonResponse({
                    'success': True,
                    'localite': localite.nom,
                    'localite_id': localite.id,  # IMPORTANT: renvoyer l'ID pour le formulaire
                    'departement': departement.nom,
                    'departement_id': departement.id,
                    'distance_km': round(distance_min, 2) if distance_min else None,
                    'methode': methode,
                    'precision': 'Dans les limites administratives' if methode == 'polygone' else f'À {int(distance_min * 1000)} m' if distance_min else 'Localité détectée',
                    'fiabilite': 'élevée' if methode == 'polygone' else ('moyenne' if distance_min and distance_min < 5 else 'faible')
                })
            else:
                # ✅ Département trouvé, mais pas de localité précise
                return JsonResponse({
                    'success': True,
                    'localite': departement.nom,  # Utiliser le nom du département
                    'localite_id': None,
                    'departement': departement.nom,
                    'departement_id': departement.id,
                    'distance_km': round(distance_min, 2) if distance_min else None,
                    'methode': 'departement',
                    'precision': f'Dans {departement.nom} (localité non précisée)',
                    'fiabilite': 'faible'
                })

        # ==================== AUCUN DÉPARTEMENT TROUVÉ ====================
        return JsonResponse({
            'success': False,
            'localite': 'Non détectée',
            'localite_id': None,
            'departement': 'Non détecté',
            'departement_id': None,
            'methode': 'aucune',
            'precision': 'Position hors zone couverte',
            'fiabilite': 'aucune'
        })

    except Exception as e:
        import traceback
        print(f"❌ ERREUR GÉOCODAGE: {e}")
        print(traceback.format_exc())

        return JsonResponse({
            'success': False,
            'error': str(e),
            'localite': 'Erreur',
            'localite_id': None,
            'departement': 'Erreur',
            'departement_id': None,
            'methode': 'erreur',
            'precision': f'Erreur: {str(e)}',
            'fiabilite': 'aucune'
        }, status=500)
# apps/menages/views.py - SOLUTION COMPLÈTE

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.http import JsonResponse
from .models import Menage
from .forms import MenageForm
from apps.users.models import CustomUser


# ==================== API POUR RÉCUPÉRER LES UTILISATEURS DISPONIBLES ====================

@login_required
def get_available_users_json(request):
    """
    ✅ API pour obtenir les utilisateurs CLIENT disponibles (sans ménage)

    Endpoint: /users/api/users/?role=CLIENT&available=true

    Paramètres:
        - role: Role de l'utilisateur (défaut: CLIENT)
        - available: Si true, filtre les utilisateurs sans ménage

    Retour:
        Liste d'utilisateurs avec: id, username, email, first_name, last_name, telephone
    """

    # ✅ Vérifier les permissions (ADMIN ou AGENT_TERRAIN)
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Non authentifié'}, status=401)

    if request.user.role not in ['ADMIN', 'AGENT_TERRAIN']:
        return JsonResponse({'error': 'Permission refusée'}, status=403)

    # Récupérer les paramètres
    role = request.GET.get('role', 'CLIENT')
    available = request.GET.get('available', 'false').lower() == 'true'

    # ✅ Construire la requête avec votre modèle CustomUser
    users_query = CustomUser.objects.filter(
        role=role,
        statut='ACTIF'  # ✅ Uniquement les utilisateurs actifs
    )

    # ✅ Filtrer uniquement les utilisateurs sans ménage
    if available:
        users_query = users_query.filter(menage__isnull=True)

    # Récupérer les données
    users = users_query.values(
        'id',
        'username',
        'email',
        'first_name',
        'last_name',
        'telephone'
    ).order_by('username')

    # ✅ Formater la réponse
    users_list = []
    for user in users:
        users_list.append({
            'id': user['id'],
            'username': user['username'],
            'email': user['email'] or '',
            'first_name': user['first_name'] or '',
            'last_name': user['last_name'] or '',
            'telephone': user['telephone'] or '',
            'full_name': f"{user['first_name'] or ''} {user['last_name'] or ''}".strip()
        })

    return JsonResponse(users_list, safe=False)


# ==================== VUE DE CRÉATION DE MÉNAGE ====================
class MenageCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    ✅ Vue de création de ménage avec support de sélection d'utilisateur existant
    ✅ Auto-assignation de l'agent connecté
    """
    model = Menage
    form_class = MenageForm
    template_name = 'gestion/menages/form.html'
    success_url = reverse_lazy('menages:list')

    def test_func(self):
        """Seuls les agents de terrain peuvent créer un ménage"""
        return self.request.user.is_agent

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ✅ Ajouter les utilisateurs CLIENT disponibles au contexte
        available_users = CustomUser.objects.filter(
            role='CLIENT',
            statut='ACTIF',
            menage__isnull=True  # Sans ménage assigné
        ).order_by('username')

        context['available_users'] = available_users
        context['title'] = 'Nouveau Ménage'
        context['is_agent'] = self.request.user.is_agent  # Pour le template
        context['agences'] = Agence.objects.filter(actif=True).order_by('nom')

        return context


    def form_valid(self, form):
        try:
            # 🔥 AUTO-ASSIGNATION : Si l'utilisateur est un agent, on l'assigne
            if self.request.user.is_agent:
                form.instance.agent = self.request.user
                messages.info(self.request, "Ce ménage vous a été automatiquement assigné.")

            self.object = form.save()
            messages.success(
                self.request,
                f"✅ Ménage {self.object.reference_menage} créé avec succès."
            )

            # ✅ Support AJAX
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Ménage créé',
                    'redirect_url': str(self.get_success_url()),
                })

            return redirect(self.get_success_url())

        except Exception as e:
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': str(e),
                    'errors': {'__all__': [str(e)]}
                }, status=400)

            messages.error(self.request, f'❌ Erreur: {str(e)}')
            return self.form_invalid(form)

    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {f: [str(e) for e in errs] for f, errs in form.errors.items()}
            return JsonResponse({
                'success': False,
                'message': 'Validation échouée',
                'errors': errors
            }, status=400)

        return super().form_invalid(form)


# apps/menages/views.py

# apps/menages/views.py
from django.http import JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from .models import Menage
from apps.compteurs.models import Compteur
from apps.users.models import CustomUser


@require_GET
@login_required
def menage_api_data(request):
    """
    API endpoint pour récupérer les ménages SANS COMPTEUR assigné
    avec rôle CLIENT
    """
    try:
        # Récupérer le paramètre de recherche
        search_term = request.GET.get('q', '').strip()
        limit = int(request.GET.get('limit', 20))
        localite_id = request.GET.get('localite_id')
        statut = request.GET.get('statut', 'ACTIF')

        # 1. Récupérer les IDs des ménages qui ont déjà un compteur
        menages_avec_compteur = Compteur.objects.values_list('menage_id', flat=True)

        # 2. Construire le queryset : ménages sans compteur
        queryset = Menage.objects.exclude(id__in=menages_avec_compteur)

        # 3. Filtrer uniquement les ménages avec utilisateur de rôle CLIENT
        queryset = queryset.filter(utilisateur__role='CLIENT')

        # Appliquer les filtres supplémentaires
        if statut:
            queryset = queryset.filter(statut=statut)

        if localite_id:
            queryset = queryset.filter(localite_id=localite_id)

        # Filtre de recherche
        if search_term:
            queryset = queryset.filter(
                Q(nom_menage__icontains=search_term) |
                Q(reference_menage__icontains=search_term) |
                Q(adresse_complete__icontains=search_term) |
                Q(personne_contact__icontains=search_term) |
                Q(telephone_secondaire__icontains=search_term) |
                Q(utilisateur__username__icontains=search_term) |
                Q(utilisateur__email__icontains=search_term)
            )

        # Trier et limiter
        queryset = queryset.order_by('nom_menage')[:limit]

        # Préparer les données pour JSON
        data = []
        for menage in queryset:
            # Vérifier si le ménage a déjà des compteurs
            has_compteur = Compteur.objects.filter(menage=menage).exists()

            # Récupérer le type d'habitation depuis la table parametrage
            type_habitation_nom = menage.type_habitation.nom if menage.type_habitation else None
            type_habitation_code = menage.type_habitation.code if menage.type_habitation else None
            type_habitation_id = menage.type_habitation.id if menage.type_habitation else None

            data.append({
                'id': menage.id,
                'nom_menage': menage.nom_menage,
                'reference_menage': menage.reference_menage,
                'adresse': menage.adresse_complete,
                'localite': menage.localite.nom if menage.localite else '',
                'localite_id': menage.localite.id if menage.localite else None,
                'personne_contact': menage.personne_contact,
                'telephone': menage.telephone_secondaire or (
                    menage.utilisateur.telephone if menage.utilisateur else ''),
                'latitude': str(menage.latitude) if menage.latitude else None,
                'longitude': str(menage.longitude) if menage.longitude else None,
                'nombre_personnes': menage.nombre_personnes,
                # CORRECTION ICI : Utiliser les champs de TypeHabitation
                'type_habitation_nom': type_habitation_nom,
                'type_habitation_code': type_habitation_code,
                'type_habitation_id': type_habitation_id,
                'statut': menage.statut,
                'utilisateur_id': menage.utilisateur.id if menage.utilisateur else None,
                'utilisateur_username': menage.utilisateur.username if menage.utilisateur else '',
                'utilisateur_role': menage.utilisateur.role if menage.utilisateur else '',
                'a_deja_compteur': has_compteur,
                'nombre_compteurs': Compteur.objects.filter(menage=menage).count(),
            })

        return JsonResponse({
            'success': True,
            'count': len(data),
            'total_sans_compteur': Menage.objects.exclude(id__in=menages_avec_compteur).filter(
                utilisateur__role='CLIENT').count(),
            'data': data,
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=400)


@require_GET
@login_required
def menage_api_detail(request, pk):
    """
    API endpoint pour récupérer les détails d'un ménage spécifique.
    """
    try:
        menage = get_object_or_404(
            Menage.objects.select_related('localite', 'utilisateur', 'type_habitation'),
            pk=pk
        )
        # Vérifier les permissions
        user = request.user
        if not (
            user.role == 'ADMIN' or
            user.role == 'AGENT_TERRAIN' or
            (user.role == 'CLIENT' and menage.utilisateur == user)
        ):
            return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
        # Préparer les données
        data = {
            'id': menage.id,
            'nom_menage': menage.nom_menage,
            'reference_menage': menage.reference_menage,
            'adresse_complete': menage.adresse_complete,
            'latitude': str(menage.latitude) if menage.latitude else None,
            'longitude': str(menage.longitude) if menage.longitude else None,
            'point_repere': menage.point_repere,
            'personne_contact': menage.personne_contact,
            'telephone_secondaire': menage.telephone_secondaire,
            # CORRECTION ICI : Utiliser les champs de TypeHabitation
            'type_habitation': {
                'id': menage.type_habitation.id if menage.type_habitation else None,
                'nom': menage.type_habitation.nom if menage.type_habitation else None,
                'code': menage.type_habitation.code if menage.type_habitation else None,
            } if menage.type_habitation else None,
            'statut': menage.statut,
            'localite': {
                'id': menage.localite.id,
                'nom': menage.localite.nom,
            } if menage.localite else None,
            'utilisateur': {
                'id': menage.utilisateur.id,
                'username': menage.utilisateur.username,
                'role': menage.utilisateur.role,
            } if menage.utilisateur else None,
        }

        return JsonResponse({
            'success': True,
            'menage': data,
        })

    except Menage.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Ménage non trouvé'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# OPTIONNEL : Nouvelle API pour récupérer les types d'habitation disponibles
@require_GET
@login_required
def type_habitation_list_api(request):
    """
    API endpoint pour récupérer la liste des types d'habitation depuis parametrage
    """
    try:
        from apps.parametrage.models import TypeHabitation

        # Récupérer les types d'habitation actifs
        types = TypeHabitation.objects.filter(actif=True).order_by('nom')

        data = []
        for type_hab in types:
            data.append({
                'id': type_hab.id,
                'nom': type_hab.nom,
                'code': type_hab.code,
                'description': type_hab.description,
            })

        return JsonResponse({
            'success': True,
            'count': len(data),
            'data': data,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)



