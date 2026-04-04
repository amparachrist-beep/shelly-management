# apps/alertes/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta

from .models import Alerte, RegleAlerte
from .forms import RegleAlerteForm, TraiterAlerteForm
from apps.users.models import CustomUser
from apps.menages.models import Menage
from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation
from apps.facturation.models import FactureConsommation


# =====================================
# Vues pour les Alertes
# =====================================

@login_required
def liste_alertes(request):
    """Liste toutes les alertes selon le rôle de l'utilisateur"""
    user = request.user

    if user.role == 'ADMIN':
        alertes = Alerte.objects.all().order_by('-date_detection')
    elif user.role == 'AGENT':
        # Agent voit les alertes de ses ménages assignés
        menages_assignes = Menage.objects.filter(agent=user)
        compteurs = Compteur.objects.filter(menage__in=menages_assignes)
        alertes = Alerte.objects.filter(compteur__in=compteurs).order_by('-date_detection')
    else:  # CLIENT
        # Client voit seulement ses propres alertes
        menage = get_object_or_404(Menage, utilisateur=user)
        compteur = get_object_or_404(Compteur, menage=menage)
        alertes = Alerte.objects.filter(
            compteur=compteur
        ).order_by('-date_detection')

    # Filtres
    type_alerte = request.GET.get('type_alerte')
    statut = request.GET.get('statut')
    niveau = request.GET.get('niveau')

    if type_alerte:
        alertes = alertes.filter(type_alerte=type_alerte)
    if statut:
        alertes = alertes.filter(statut=statut)
    if niveau:
        alertes = alertes.filter(niveau=niveau)

    # Pagination
    paginator = Paginator(alertes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'types_alerte': Alerte.TYPE_ALERTE,
        'statuts': Alerte.STATUT_CHOICES,
        'niveaux': Alerte.NIVEAU_CHOICES,
        'filtres': {
            'type_alerte': type_alerte,
            'statut': statut,
            'niveau': niveau,
        }
    }

    return render(request, 'gestion/alertes/list.html', context)


@login_required
def mes_alertes(request):
    """Affiche les alertes de l'utilisateur connecté"""
    user = request.user

    if user.role == 'CLIENT':
        menage = get_object_or_404(Menage, utilisateur=user)
        compteur = get_object_or_404(Compteur, menage=menage)
        alertes = Alerte.objects.filter(
            compteur=compteur
        ).order_by('-date_detection')
    elif user.role == 'AGENT':
        # Agent voit les alertes de ses ménages
        menages_assignes = Menage.objects.filter(agent=user)
        compteurs = Compteur.objects.filter(menage__in=menages_assignes)
        alertes = Alerte.objects.filter(compteur__in=compteurs).order_by('-date_detection')
    else:  # ADMIN
        alertes = Alerte.objects.all().order_by('-date_detection')

    # Pagination
    paginator = Paginator(alertes, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'title': 'Mes Alertes'
    }

    return render(request, 'client/alertes_list.html', context)


@login_required
def alertes_non_lues(request):
    """Affiche les alertes non lues de l'utilisateur"""
    user = request.user

    if user.role == 'CLIENT':
        menage = get_object_or_404(Menage, utilisateur=user)
        compteur = get_object_or_404(Compteur, menage=menage)
        alertes = Alerte.objects.filter(
            compteur=compteur,
            statut='ACTIVE'
        ).order_by('-date_detection')
    elif user.role == 'AGENT':
        menages_assignes = Menage.objects.filter(agent=user)
        compteurs = Compteur.objects.filter(menage__in=menages_assignes)
        alertes = Alerte.objects.filter(
            compteur__in=compteurs,
            statut='ACTIVE'
        ).order_by('-date_detection')
    else:  # ADMIN
        alertes = Alerte.objects.filter(
            statut='ACTIVE'
        ).order_by('-date_detection')

    context = {
        'alertes': alertes[:10],  # Limite à 10 alertes
        'title': 'Alertes Non Lues'
    }

    return render(request, 'gestion/alertes/non_lues.html', context)


@login_required
@permission_required('alertes.view_alerte', raise_exception=True)
def detail_alerte(request, pk):
    """Détail d'une alerte"""
    alerte = get_object_or_404(Alerte, pk=pk)

    # Vérification des permissions
    user = request.user
    if user.role == 'AGENT':
        # Agent ne peut voir que les alertes de ses ménages
        if alerte.compteur and alerte.compteur.menage.agent != user:
            messages.error(request, "Vous n'avez pas accès à cette alerte.")
            return redirect('alertes:liste')

    elif user.role == 'CLIENT':
        # Client ne peut voir que ses propres alertes
        if alerte.compteur and alerte.compteur.menage.utilisateur != user:
            messages.error(request, "Vous n'avez pas accès à cette alerte.")
            return redirect('alertes:mes_alertes')

    form = TraiterAlerteForm(instance=alerte)

    if request.method == 'POST':
        form = TraiterAlerteForm(request.POST, instance=alerte)
        if form.is_valid():
            alerte = form.save(commit=False)
            alerte.traite_par = request.user
            alerte.date_traitement = timezone.now()
            alerte.save()
            messages.success(request, f"Alerte {alerte.get_statut_display().lower()} avec succès.")
            return redirect('alertes:detail', pk=alerte.pk)

    context = {
        'alerte': alerte,
        'form': form,
    }

    return render(request, 'gestion/alertes/detail.html', context)


@login_required
def marquer_comme_lue(request, pk):
    """Marquer une alerte comme lue"""
    alerte = get_object_or_404(Alerte, pk=pk)

    # Vérifier les permissions
    if not (request.user == alerte.utilisateur or
            request.user.has_perm('alertes.change_alerte')):
        messages.error(request, "Vous n'avez pas la permission de modifier cette alerte.")
        return redirect('alertes:mes_alertes')

    alerte.statut = 'LU'
    alerte.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'statut': 'LU'})

    messages.success(request, "Alerte marquée comme lue.")
    return redirect('alertes:mes_alertes')


@login_required
def ignorer_alerte(request, pk):
    """Ignorer une alerte"""
    alerte = get_object_or_404(Alerte, pk=pk)

    # Vérifier les permissions
    if not (request.user == alerte.utilisateur or
            request.user.has_perm('alertes.change_alerte')):
        messages.error(request, "Vous n'avez pas la permission de modifier cette alerte.")
        return redirect('alertes:mes_alertes')

    alerte.statut = 'IGNOREE'
    alerte.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'statut': 'IGNOREE'})

    messages.success(request, "Alerte ignorée.")
    return redirect('alertes:mes_alertes')


# =====================================
# Vues pour les Règles d'Alerte
# =====================================

class RegleAlerteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """Liste des règles d'alerte"""
    model = RegleAlerte
    template_name = 'gestion/regles_alerte/list.html'
    context_object_name = 'regles'
    permission_required = 'alertes.view_reglealerte'
    paginate_by = 20

    def get_queryset(self):
        return RegleAlerte.objects.all().order_by('type_alerte', 'nom')


class RegleAlerteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """Créer une nouvelle règle d'alerte"""
    model = RegleAlerte
    form_class = RegleAlerteForm
    template_name = 'gestion/form_template.html'
    permission_required = 'alertes.add_reglealerte'
    success_url = reverse_lazy('alertes:regles_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Créer une Règle d\'Alerte'
        return context

    def form_valid(self, form):
        messages.success(self.request, "Règle d'alerte créée avec succès.")
        return super().form_valid(form)


class RegleAlerteUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Modifier une règle d'alerte"""
    model = RegleAlerte
    form_class = RegleAlerteForm
    template_name = 'gestion/form_template.html'
    permission_required = 'alertes.change_reglealerte'
    success_url = reverse_lazy('alertes:regles_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Modifier la règle {self.object.nom}'
        return context

    def form_valid(self, form):
        messages.success(self.request, "Règle d'alerte modifiée avec succès.")
        return super().form_valid(form)


class RegleAlerteDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """Supprimer une règle d'alerte"""
    model = RegleAlerte
    template_name = 'gestion/confirm_delete.html'
    permission_required = 'alertes.delete_reglealerte'
    success_url = reverse_lazy('alertes:regles_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Supprimer la règle {self.object.nom}'
        context['message'] = f'Êtes-vous sûr de vouloir supprimer la règle "{self.object.nom}" ?'
        return context

    def delete(self, request, *args, **kwargs):
        messages.success(request, "Règle d'alerte supprimée avec succès.")
        return super().delete(request, *args, **kwargs)


@login_required
@permission_required('alertes.change_reglealerte', raise_exception=True)
def activer_regle(request, pk):
    """Activer une règle d'alerte"""
    regle = get_object_or_404(RegleAlerte, pk=pk)
    regle.actif = True
    regle.save()

    messages.success(request, f"Règle '{regle.nom}' activée.")
    return redirect('alertes:regles_list')


@login_required
@permission_required('alertes.change_reglealerte', raise_exception=True)
def desactiver_regle(request, pk):
    """Désactiver une règle d'alerte"""
    regle = get_object_or_404(RegleAlerte, pk=pk)
    regle.actif = False
    regle.save()

    messages.success(request, f"Règle '{regle.nom}' désactivée.")
    return redirect('alertes:regles_list')


# =====================================
# Statistiques et Tableaux de Bord
# =====================================

@login_required
@permission_required('alertes.view_alerte', raise_exception=True)
def statistiques_alertes(request):
    """Affiche les statistiques des alertes"""
    user = request.user

    # Filtrer selon le rôle
    if user.role == 'ADMIN':
        alertes = Alerte.objects.all()
    elif user.role == 'AGENT':
        menages_assignes = Menage.objects.filter(agent=user)
        compteurs = Compteur.objects.filter(menage__in=menages_assignes)
        alertes = Alerte.objects.filter(compteur__in=compteurs)
    else:
        menage = get_object_or_404(Menage, utilisateur=user)
        compteur = get_object_or_404(Compteur, menage=menage)
        alertes = Alerte.objects.filter(compteur=compteur)

    # Statistiques par type
    stats_type = alertes.values('type_alerte').annotate(
        count=Count('id'),
        actives=Count('id', filter=Q(statut='ACTIVE')),
        traitees=Count('id', filter=Q(statut='TRAITEE'))
    )

    # Statistiques par niveau
    stats_niveau = alertes.values('niveau').annotate(
        count=Count('id')
    )

    # Statistiques par statut
    stats_statut = alertes.values('statut').annotate(
        count=Count('id')
    )

    # Alertes récentes (7 derniers jours)
    date_limite = timezone.now() - timezone.timedelta(days=7)
    alertes_recentes = alertes.filter(date_detection__gte=date_limite).count()

    context = {
        'stats_type': stats_type,
        'stats_niveau': stats_niveau,
        'stats_statut': stats_statut,
        'total_alertes': alertes.count(),
        'alertes_actives': alertes.filter(statut='ACTIVE').count(),
        'alertes_recentes': alertes_recentes,
        'types_alerte': dict(Alerte.TYPE_ALERTE),
        'niveaux': dict(Alerte.NIVEAU_CHOICES),
        'statuts': dict(Alerte.STATUT_CHOICES),
    }

    return render(request, 'supervision/stats_alertes.html', context)


# =====================================
# Détection automatique (appelable manuellement)
# =====================================

@login_required
@permission_required('alertes.view_alerte', raise_exception=True)
def detection_automatique(request):
    """
    Exécute la détection automatique des anomalies
    Cette fonction peut être appelée par :
    - Une commande cron (recommandé)
    - Un bouton manuel (pour les tests)
    - Une tâche Celery (pour l'asynchrone)
    """
    if request.method == 'POST':
        alertes_creees = 0

        # ============================================
        # 1. DÉTECTION DES CAPTEURS DÉCONNECTÉS
        # ============================================
        date_limite_connexion = timezone.now() - timedelta(hours=1)
        compteurs_deconnectes = Compteur.objects.filter(
            shelly_status='CONNECTE',
            shelly_last_seen__lt=date_limite_connexion
        ).exclude(
            alertes__type_alerte='CAPTEUR_DECONNECTE',
            alertes__statut__in=['ACTIVE', 'LU']
        )

        for compteur in compteurs_deconnectes:
            Alerte.objects.create(
                compteur=compteur,
                type_alerte='CAPTEUR_DECONNECTE',
                message=f"Capteur déconnecté depuis plus d'une heure. Dernière connexion: {compteur.shelly_last_seen}",
                niveau='WARNING',
                destinataire_role='AGENT',
                statut='ACTIVE'
            )
            alertes_creees += 1

        # ============================================
        # 2. DÉTECTION DES PAIEMENTS EN RETARD
        # ============================================
        today = timezone.now().date()
        factures_retard = FactureConsommation.objects.filter(
            statut__in=['ÉMISE', 'PARTIELLEMENT_PAYÉE'],
            date_echeance__lt=today
        ).exclude(
            alertes__type_alerte='PAIEMENT_EN_RETARD'
        )

        for facture in factures_retard:
            jours_retard = (today - facture.date_echeance).days
            niveau = 'CRITIQUE' if jours_retard > 30 else 'WARNING'

            Alerte.objects.create(
                compteur=facture.compteur,
                type_alerte='PAIEMENT_EN_RETARD',
                message=f"Paiement en retard de {jours_retard} jours pour la facture {facture.numero_facture}",
                niveau=niveau,
                valeur_mesuree=facture.solde_du,
                unite='FCFA',
                destinataire_role='CLIENT',
                utilisateur=facture.compteur.menage.utilisateur,
                statut='ACTIVE'
            )
            alertes_creees += 1

        # ============================================
        # 3. DÉTECTION DES ANOMALIES TECHNIQUES
        # ============================================
        # Compteurs avec index négatif
        compteurs_anormaux = Compteur.objects.filter(
            index_actuel__lt=0
        ).exclude(
            alertes__type_alerte='ANOMALIE_TECHNIQUE'
        )

        for compteur in compteurs_anormaux:
            Alerte.objects.create(
                compteur=compteur,
                type_alerte='ANOMALIE_TECHNIQUE',
                message=f"Anomalie technique: index actuel négatif ({compteur.index_actuel})",
                niveau='CRITIQUE',
                valeur_mesuree=compteur.index_actuel,
                destinataire_role='ADMIN',
                statut='ACTIVE'
            )
            alertes_creees += 1

        # ============================================
        # MESSAGE DE CONFIRMATION
        # ============================================
        if alertes_creees > 0:
            messages.success(
                request,
                f"Détection automatique terminée. {alertes_creees} alerte(s) créée(s)."
            )
        else:
            messages.info(request, "Détection automatique terminée. Aucune nouvelle anomalie détectée.")

        return redirect('alertes:statistiques')

    # ============================================
    # AFFICHAGE DE LA PAGE (GET)
    # ============================================
    regles_actives = RegleAlerte.objects.filter(actif=True)

    # Statistiques pour l'affichage
    stats = {
        'alertes_aujourdhui': Alerte.objects.filter(
            date_detection__date=timezone.now().date()
        ).count(),
        'alertes_non_traitees': Alerte.objects.filter(
            statut='ACTIVE'
        ).count(),
        'regles_actives': regles_actives.count(),
        'derniere_detection': timezone.now().strftime('%d/%m/%Y %H:%M:%S')
    }

    context = {
        'regles_actives': regles_actives,
        'types_alerte': Alerte.TYPE_ALERTE,
        'stats': stats,
    }

    return render(request, 'gestion/alertes/detection.html', context)


# =====================================
# Vues AJAX/API pour les widgets
# =====================================

@login_required
def widget_alertes_recentes(request):
    """Widget pour afficher les alertes récentes (AJAX)"""
    if request.user.role == 'CLIENT':
        menage = get_object_or_404(Menage, utilisateur=request.user)
        compteur = get_object_or_404(Compteur, menage=menage)
        alertes = Alerte.objects.filter(
            compteur=compteur,
            statut='ACTIVE'
        ).order_by('-date_detection')[:5]
    elif request.user.role == 'AGENT':
        menages_assignes = Menage.objects.filter(agent=request.user)
        compteurs = Compteur.objects.filter(menage__in=menages_assignes)
        alertes = Alerte.objects.filter(
            compteur__in=compteurs,
            statut='ACTIVE'
        ).order_by('-date_detection')[:5]
    else:  # ADMIN
        alertes = Alerte.objects.filter(
            statut='ACTIVE'
        ).order_by('-date_detection')[:5]

    data = {
        'alertes': [
            {
                'id': a.id,
                'type': a.get_type_alerte_display(),
                'message': a.message[:50] + '...' if len(a.message) > 50 else a.message,
                'date': a.date_detection.strftime('%d/%m/%Y %H:%M'),
                'niveau': a.get_niveau_display(),
                'niveau_class': 'danger' if a.niveau == 'CRITIQUE' else 'warning' if a.niveau == 'WARNING' else 'info'
            }
            for a in alertes
        ]
    }

    return JsonResponse(data)