from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.db.models import Q, Sum, Count, Avg, F
from django.db.models.functions import TruncMonth, TruncDay
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import date, timedelta, datetime
import csv
from decimal import Decimal
from .models import Paiement, CommissionAgent, FraisTransaction, HistoriqueStatutPaiement
from .forms import (
    PaiementForm, MobileMoneyPaymentForm, PaiementValidationForm,
    CommissionAgentForm, FraisTransactionForm, RapportJournalierForm,
    StatsPaiementForm
)
from apps.facturation.models import FactureConsommation
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


def admin_required(view_func):
    """Décorateur pour vérifier si l'utilisateur est admin"""

    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.role == 'ADMIN':
            messages.error(request, "Accès refusé. Administrateur requis.")
            return redirect('dashboard:home')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class AdminOrAgentRequiredMixin(UserPassesTestMixin):
    """Mixin pour vérifier si l'utilisateur est admin ou agent"""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.role == 'ADMIN' or user.role == 'AGENT_TERRAIN')


# ==================== VUES POUR LES PAIEMENTS ====================

class PaiementListView(LoginRequiredMixin, AdminOrAgentRequiredMixin, ListView):
    """Liste des paiements"""
    model = Paiement
    template_name = 'gestion/list_template.html'
    context_object_name = 'object_list'
    paginate_by = 20

    def get_queryset(self):
        queryset = Paiement.objects.select_related(
            'facture', 'facture__menage', 'cree_par'
        ).order_by('-date_paiement')

        user = self.request.user

        # Filtres selon le rôle
        if user.role == 'AGENT_TERRAIN':
            # Agents voient seulement leurs paiements et ceux de leurs ménages
            queryset = queryset.filter(
                Q(cree_par=user) |
                Q(facture__menage__agent=user)
            )

        # Recherche
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(reference_paiement__icontains=search) |
                Q(facture__numero_facture__icontains=search) |
                Q(reference_externe__icontains=search) |
                Q(facture__menage__nom__icontains=search) |
                Q(facture__menage__prenom__icontains=search)
            )

        # Filtres supplémentaires
        statut = self.request.GET.get('statut', '')
        if statut:
            queryset = queryset.filter(statut=statut)

        mode_paiement = self.request.GET.get('mode_paiement', '')
        if mode_paiement:
            queryset = queryset.filter(mode_paiement=mode_paiement)

        date_debut = self.request.GET.get('date_debut', '')
        date_fin = self.request.GET.get('date_fin', '')

        if date_debut:
            try:
                date_debut_dt = datetime.strptime(date_debut, '%Y-%m-%d')
                queryset = queryset.filter(date_paiement__date__gte=date_debut_dt.date())
            except ValueError:
                pass

        if date_fin:
            try:
                date_fin_dt = datetime.strptime(date_fin, '%Y-%m-%d')
                queryset = queryset.filter(date_paiement__date__lte=date_fin_dt.date())
            except ValueError:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques
        queryset = self.get_queryset()
        stats = queryset.aggregate(
            total_montant=Sum('montant'),
            total_paiements=Count('id'),
            montant_valide=Sum('montant', filter=Q(statut='VALIDÉ')),
            count_valide=Count('id', filter=Q(statut='VALIDÉ')),
        )

        context.update({
            'title': 'Paiements',
            'icon': 'fas fa-money-bill-wave',
            'headers': ['Référence', 'Facture', 'Client', 'Montant', 'Mode', 'Statut', 'Date', 'Créé par'],
            'create_url': 'paiements:create',
            'detail_url': 'paiements:detail',
            'update_url': 'paiements:update',
            'show_filters': True,
            'form': StatsPaiementForm(self.request.GET or None),
            'stats': [
                {
                    'title': 'Total Montant',
                    'value': f"{stats['total_montant'] or 0:.2f} FCFA",
                    'color': 'primary'
                },
                {
                    'title': 'Total Paiements',
                    'value': stats['total_paiements'] or 0,
                    'color': 'success'
                },
                {
                    'title': 'Montant Validé',
                    'value': f"{stats['montant_valide'] or 0:.2f} FCFA",
                    'color': 'info'
                },
                {
                    'title': 'Paiements Validés',
                    'value': stats['count_valide'] or 0,
                    'color': 'warning'
                },
            ]
        })
        return context


class PaiementCreateView(LoginRequiredMixin, AdminOrAgentRequiredMixin, CreateView):
    """Création d'un paiement"""
    model = Paiement
    form_class = PaiementForm
    template_name = 'gestion/form_template.html'
    success_url = reverse_lazy('paiements:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Nouveau Paiement',
            'icon': 'fas fa-money-bill-alt',
            'submit_text': 'Enregistrer le paiement',
            'extra_content': '''
                <div class="alert alert-info mt-3">
                    <h5><i class="fas fa-info-circle"></i> Information</h5>
                    <p class="mb-0">
                        <strong>Pour Mobile Money:</strong> Utilisez le formulaire dédié<br>
                        <strong>Statut:</strong> Les paiements sont créés avec statut "En attente" par défaut
                    </p>
                </div>
            '''
        })
        return context

    def form_valid(self, form):
        paiement = form.save(commit=False)
        paiement.cree_par = self.request.user
        paiement.save()

        messages.success(self.request, f"Paiement {paiement.reference_paiement} créé avec succès.")
        return redirect('paiements:detail', pk=paiement.pk)


class PaiementMobileMoneyView(LoginRequiredMixin, AdminOrAgentRequiredMixin, View):
    """Paiement Mobile Money spécifique"""
    template_name = 'paiements/mobile_money_form.html'

    def get(self, request):
        form = MobileMoneyPaymentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = MobileMoneyPaymentForm(request.POST)

        if form.is_valid():
            # Créer le paiement
            paiement = Paiement(
                facture=form.cleaned_data['facture'],
                montant=form.cleaned_data['montant'],
                mode_paiement=form.cleaned_data['operateur'],
                statut='EN_ATTENTE',
                date_paiement=form.cleaned_data['date_paiement'],
                reference_externe=form.cleaned_data['numero_transaction'],
                notes=f"Mobile Money - Opérateur: {form.cleaned_data['operateur']}, "
                      f"Tél: {form.cleaned_data['telephone_payeur']}",
                cree_par=request.user
            )
            paiement.save()

            messages.success(request, f"Paiement Mobile Money {paiement.reference_paiement} enregistré.")
            return redirect('paiements:detail', pk=paiement.pk)

        return render(request, self.template_name, {'form': form})


class PaiementDetailView(LoginRequiredMixin, AdminOrAgentRequiredMixin, DetailView):
    """Détail d'un paiement"""
    model = Paiement
    template_name = 'paiements/detail.html'
    context_object_name = 'paiement'

    def get_queryset(self):
        queryset = Paiement.objects.select_related(
            'facture', 'facture__menage', 'cree_par', 'valide_par'
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Formulaire de validation
        context['validation_form'] = PaiementValidationForm()

        # Historique des statuts
        context['historique'] = HistoriqueStatutPaiement.objects.filter(
            paiement=self.object
        ).select_related('utilisateur').order_by('-created_at')

        # Frais associés
        context['frais'] = FraisTransaction.objects.filter(paiement=self.object)

        # Commission associée
        context['commission'] = CommissionAgent.objects.filter(paiement=self.object).first()

        # Actions disponibles selon le statut
        actions = []
        if self.object.statut == 'EN_ATTENTE':
            actions.append({
                'text': 'Valider',
                'url': f"{self.object.pk}/valider/",
                'icon': 'check',
                'color': 'success'
            })
            actions.append({
                'text': 'Rejeter',
                'url': f"{self.object.pk}/rejeter/",
                'icon': 'times',
                'color': 'danger'
            })

        context['actions'] = actions

        return context


class PaiementUpdateView(LoginRequiredMixin, AdminOrAgentRequiredMixin, UpdateView):
    """Modification d'un paiement"""
    model = Paiement
    form_class = PaiementForm
    template_name = 'gestion/form_template.html'
    success_url = reverse_lazy('paiements:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Modifier {self.object.reference_paiement}',
            'icon': 'fas fa-edit',
            'submit_text': 'Modifier',
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Paiement {self.object.reference_paiement} modifié.")
        return super().form_valid(form)


@login_required
@admin_or_agent_required
def valider_paiement(request, pk):
    """Valider un paiement"""
    paiement = get_object_or_404(Paiement, pk=pk)

    if paiement.statut != 'EN_ATTENTE':
        messages.error(request, "Seuls les paiements en attente peuvent être validés.")
        return redirect('paiements:detail', pk=pk)

    # Créer historique
    HistoriqueStatutPaiement.objects.create(
        paiement=paiement,
        ancien_statut=paiement.statut,
        nouveau_statut='VALIDÉ',
        utilisateur=request.user,
        raison='Validation manuelle'
    )

    # Mettre à jour le paiement
    paiement.statut = 'VALIDÉ'
    paiement.valide_par = request.user
    paiement.date_validation = timezone.now()
    paiement.save()

    # Mettre à jour la facture
    facture = paiement.facture
    facture.montant_paye += paiement.montant

    if facture.montant_paye >= facture.montant_total:
        facture.statut = 'PAYEE'
    elif facture.montant_paye > 0:
        facture.statut = 'PARTIELLEMENT_PAYEE'

    facture.save()

    messages.success(request, f"Paiement {paiement.reference_paiement} validé.")
    return redirect('paiements:detail', pk=pk)


@login_required
@admin_or_agent_required
def rejeter_paiement(request, pk):
    """Rejeter un paiement"""
    paiement = get_object_or_404(Paiement, pk=pk)

    if paiement.statut != 'EN_ATTENTE':
        messages.error(request, "Seuls les paiements en attente peuvent être rejetés.")
        return redirect('paiements:detail', pk=pk)

    if request.method == 'POST':
        raison = request.POST.get('raison', '')

        if not raison:
            messages.error(request, "Veuillez indiquer une raison pour le rejet.")
            return redirect('paiements:detail', pk=pk)

        # Créer historique
        HistoriqueStatutPaiement.objects.create(
            paiement=paiement,
            ancien_statut=paiement.statut,
            nouveau_statut='REJETÉ',
            utilisateur=request.user,
            raison=raison
        )

        # Mettre à jour le paiement
        paiement.statut = 'REJETÉ'
        paiement.valide_par = request.user
        paiement.save()

        messages.warning(request, f"Paiement {paiement.reference_paiement} rejeté.")
        return redirect('paiements:detail', pk=pk)

    # GET - afficher le formulaire de rejet
    return render(request, 'paiements/rejeter_form.html', {'paiement': paiement})


# ==================== VUES POUR LES STATISTIQUES ====================

class StatsPaiementsView(LoginRequiredMixin, AdminOrAgentRequiredMixin, TemplateView):
    """Statistiques des paiements"""
    template_name = 'paiements/stats.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Période par défaut (derniers 30 jours)
        date_fin = timezone.now().date()
        date_debut = date_fin - timedelta(days=30)

        form = StatsPaiementForm(self.request.GET or {
            'date_debut': date_debut,
            'date_fin': date_fin
        })

        if form.is_valid():
            date_debut = form.cleaned_data['date_debut']
            date_fin = form.cleaned_data['date_fin']
            mode_paiement = form.cleaned_data['mode_paiement']
            statut = form.cleaned_data['statut']
        else:
            mode_paiement = ''
            statut = ''

        # Filtre de base
        paiements = Paiement.objects.filter(
            date_paiement__date__range=[date_debut, date_fin]
        )

        # Filtres supplémentaires
        if mode_paiement:
            paiements = paiements.filter(mode_paiement=mode_paiement)

        if statut:
            paiements = paiements.filter(statut=statut)

        # Statistiques globales
        stats_globales = paiements.aggregate(
            total_montant=Sum('montant'),
            total_paiements=Count('id'),
            montant_moyen=Avg('montant'),
            montant_max=Max('montant'),
            montant_min=Min('montant')
        )

        # Par mode de paiement
        par_mode = paiements.values('mode_paiement').annotate(
            nombre=Count('id'),
            montant_total=Sum('montant'),
            pourcentage=Count('id') * 100.0 / paiements.count()
        ).order_by('-montant_total')

        # Par statut
        par_statut = paiements.values('statut').annotate(
            nombre=Count('id'),
            montant_total=Sum('montant')
        ).order_by('-montant_total')

        # Évolution journalière
        evolution = paiements.annotate(
            jour=TruncDay('date_paiement')
        ).values('jour').annotate(
            montant=Sum('montant'),
            nombre=Count('id')
        ).order_by('jour')

        context.update({
            'title': 'Statistiques des Paiements',
            'form': form,
            'stats_globales': stats_globales,
            'par_mode': par_mode,
            'par_statut': par_statut,
            'evolution': list(evolution),
            'date_debut': date_debut,
            'date_fin': date_fin,
        })
        return context


@login_required
@admin_or_agent_required
def rapport_journalier(request):
    """Rapport journalier des paiements"""
    today = timezone.now().date()

    form = RapportJournalierForm(request.GET or {'date_rapport': today})

    if form.is_valid():
        date_rapport = form.cleaned_data['date_rapport']
    else:
        date_rapport = today

    # Paiements du jour
    paiements = Paiement.objects.filter(date_paiement__date=date_rapport)

    # Filtre par utilisateur si agent
    if request.user.role == 'AGENT_TERRAIN':
        paiements = paiements.filter(cree_par=request.user)

    # Statistiques
    stats = paiements.aggregate(
        total_montant=Sum('montant'),
        total_paiements=Count('id'),
        montant_valide=Sum('montant', filter=Q(statut='VALIDÉ')),
        montant_attente=Sum('montant', filter=Q(statut='EN_ATTENTE')),
        montant_rejete=Sum('montant', filter=Q(statut='REJETÉ')),
    )

    # Par mode de paiement
    par_mode = paiements.values('mode_paiement').annotate(
        nombre=Count('id'),
        montant=Sum('montant')
    ).order_by('-montant')

    # Par statut
    par_statut = paiements.values('statut').annotate(
        nombre=Count('id'),
        montant=Sum('montant')
    ).order_by('-montant')

    return render(request, 'paiements/rapport_journalier.html', {
        'title': f'Rapport Journalier - {date_rapport}',
        'form': form,
        'paiements': paiements,
        'stats': stats,
        'par_mode': par_mode,
        'par_statut': par_statut,
        'date_rapport': date_rapport,
    })


# ==================== VUES POUR LES COMMISSIONS ====================

class CommissionListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Liste des commissions (admin seulement)"""
    model = CommissionAgent
    template_name = 'gestion/list_template.html'
    context_object_name = 'object_list'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_queryset(self):
        queryset = CommissionAgent.objects.select_related('agent', 'paiement')

        # Recherche
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(agent__username__icontains=search) |
                Q(agent__first_name__icontains=search) |
                Q(agent__last_name__icontains=search) |
                Q(paiement__reference_paiement__icontains=search)
            )

        # Filtre par statut
        statut = self.request.GET.get('statut', '')
        if statut:
            queryset = queryset.filter(statut=statut)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Statistiques
        queryset = self.get_queryset()
        stats = queryset.aggregate(
            total_commission=Sum('montant_commission'),
            total_due=Sum('montant_commission', filter=Q(statut='DUE')),
            total_payee=Sum('montant_commission', filter=Q(statut='PAYEE')),
        )

        context.update({
            'title': 'Commissions des Agents',
            'icon': 'fas fa-hand-holding-usd',
            'headers': ['Agent', 'Paiement', 'Taux', 'Montant', 'Statut', 'Date paiement'],
            'stats': [
                {
                    'title': 'Total Commissions',
                    'value': f"{stats['total_commission'] or 0:.2f} FCFA",
                    'color': 'primary'
                },
                {
                    'title': 'Commissions dues',
                    'value': f"{stats['total_due'] or 0:.2f} FCFA",
                    'color': 'warning'
                },
                {
                    'title': 'Commissions payées',
                    'value': f"{stats['total_payee'] or 0:.2f} FCFA",
                    'color': 'success'
                },
            ]
        })
        return context


# ==================== VUES POUR AJAX/API SIMPLE ====================

@login_required
def paiement_stats_api(request):
    """API pour les statistiques de paiement (AJAX)"""
    if request.method == 'GET':
        # Derniers 7 jours
        date_fin = timezone.now().date()
        date_debut = date_fin - timedelta(days=6)

        paiements = Paiement.objects.filter(
            date_paiement__date__range=[date_debut, date_fin],
            statut='VALIDÉ'
        )

        # Données par jour
        jours = []
        montants = []
        for i in range(7):
            jour = date_debut + timedelta(days=i)
            montant_jour = paiements.filter(
                date_paiement__date=jour
            ).aggregate(total=Sum('montant'))['total'] or 0

            jours.append(jour.strftime('%a'))
            montants.append(float(montant_jour))

        return JsonResponse({
            'jours': jours,
            'montants': montants,
            'total_semaine': float(paiements.aggregate(total=Sum('montant'))['total'] or 0)
        })

    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@login_required
def facture_info_api(request, facture_id):
    """API pour obtenir les informations d'une facture (AJAX)"""
    facture = get_object_or_404(FactureConsommation, pk=facture_id)

    data = {
        'numero_facture': facture.numero_facture,
        'menage_nom': facture.menage.nom_complet,
        'montant_total': float(facture.montant_total),
        'montant_paye': float(facture.montant_paye),
        'reste_a_payer': float(facture.montant_total - facture.montant_paye),
        'statut': facture.statut,
        'periode': f"{facture.periode_facturation.date_debut} - {facture.periode_facturation.date_fin}",
    }

    return JsonResponse(data)


# ==================== VUES POUR L'EXPORT ====================

@login_required
@admin_or_agent_required
def export_paiements_csv(request):
    """Exporter les paiements en CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="paiements.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Référence', 'Facture', 'Client', 'Montant', 'Mode paiement',
        'Statut', 'Date paiement', 'Date validation', 'Créé par'
    ])

    # Récupérer les paiements selon les filtres
    paiements = Paiement.objects.select_related(
        'facture', 'facture__menage', 'cree_par'
    ).order_by('-date_paiement')

    # Appliquer les mêmes filtres que la liste
    if request.user.role == 'AGENT_TERRAIN':
        paiements = paiements.filter(cree_par=request.user)

    for paiement in paiements:
        writer.writerow([
            paiement.reference_paiement,
            paiement.facture.numero_facture,
            paiement.facture.menage.nom_complet,
            paiement.montant,
            paiement.get_mode_paiement_display(),
            paiement.get_statut_display(),
            paiement.date_paiement.strftime('%Y-%m-%d %H:%M'),
            paiement.date_validation.strftime('%Y-%m-%d %H:%M') if paiement.date_validation else '',
            paiement.cree_par.get_full_name() if paiement.cree_par else ''
        ])

    return response