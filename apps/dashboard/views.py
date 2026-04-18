# apps/dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Avg, Q, F, FloatField, ExpressionWrapper
from django.db.models.functions import TruncMonth, TruncDay, Coalesce
from django.utils import timezone
from datetime import date, timedelta, datetime
from decimal import Decimal
from django.core.paginator import Paginator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
import json
import calendar

from .models import (
    DashboardWidget, UserDashboardLayout, DashboardNotification,
    DashboardQuickAction
)
from .forms import (
    WidgetConfigurationForm, DashboardLayoutForm, NotificationFilterForm,
    QuickActionForm, WidgetCreateForm
)
from apps.menages.models import Menage
from apps.compteurs.models import Compteur
from apps.facturation.models import Facture
from apps.paiements.models import Paiement
from apps.alertes.models import Alerte
from apps.consommation.models import Consommation
from apps.users.models import CustomUser


# ============================================
# MIXINS ET UTILITAIRES
# ============================================
class RoleRequiredMixin:
    """Mixin pour vérifier le rôle de l'utilisateur"""
    roles_required = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if self.roles_required and request.user.role not in self.roles_required:
            messages.error(request, "Vous n'avez pas les permissions nécessaires.")
            return redirect('dashboard:index')

        return super().dispatch(request, *args, **kwargs)


def role_required(roles):
    """Décorateur pour vérifier le rôle"""

    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.role not in roles:
                messages.error(request, "Accès non autorisé.")
                return redirect('dashboard:index')

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator


def get_date_range(period='month'):
    """Obtenir la plage de dates selon la période"""
    today = timezone.now().date()

    if period == 'today' or period == 'day':  # ✅ Ajouter 'day'
        start_date = today
        end_date = today
    elif period == 'yesterday':
        start_date = today - timedelta(days=1)
        end_date = today - timedelta(days=1)
    elif period == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif period == 'month':
        start_date = date(today.year, today.month, 1)
        end_date = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    elif period == 'quarter':
        quarter = (today.month - 1) // 3 + 1
        start_date = date(today.year, 3 * quarter - 2, 1)
        end_date = date(today.year, 3 * quarter, calendar.monthrange(today.year, 3 * quarter)[1])
    elif period == 'year':
        start_date = date(today.year, 1, 1)
        end_date = date(today.year, 12, 31)
    elif period == 'last_7_days':
        start_date = today - timedelta(days=6)
        end_date = today
    elif period == 'last_30_days':
        start_date = today - timedelta(days=29)
        end_date = today
    elif period == 'last_90_days':
        start_date = today - timedelta(days=89)
        end_date = today
    else:
        start_date = today - timedelta(days=29)
        end_date = today

    return start_date, end_date
# ============================================
# VUES PRINCIPALES DU DASHBOARD
# ============================================
@login_required
def index(request):
    """Page d'accueil redirigeant vers le dashboard approprié"""
    if request.user.role == 'ADMIN':
        return redirect('dashboard:admin_dashboard')
    elif request.user.role == 'AGENT_TERRAIN':
        return redirect('dashboard:agent_dashboard')
    else:
        return redirect('dashboard:client_dashboard')


@login_required
@role_required(['ADMIN'])
def admin_dashboard(request):
    """Dashboard principal administrateur"""
    today = timezone.now().date()
    current_month = date(today.year, today.month, 1)

    # Récupérer ou créer la configuration du dashboard
    user_layout, created = UserDashboardLayout.objects.get_or_create(user=request.user)

    # Mettre à jour le dernier accès
    user_layout.last_accessed = timezone.now()
    user_layout.save(update_fields=['last_accessed'])

    # Statistiques globales
    stats = get_admin_stats(today, current_month)

    # Alertes récentes
    recent_alerts = Alerte.objects.filter(
        statut='ACTIVE'
    ).select_related('compteur', 'compteur__menage').order_by('-date_detection')[:10]

    # Paiements récents
    recent_payments = Paiement.objects.filter(
        statut='CONFIRMÉ'
    ).select_related('facture', 'facture__compteur__menage').order_by('-date_paiement')[:10]

    # Notifications non lues
    unread_notifications = DashboardNotification.objects.filter(
        user=request.user,
        read=False
    ).order_by('-created_at')[:5]

    # Widgets disponibles
    available_widgets = DashboardWidget.objects.filter(
        Q(allowed_roles__contains=[request.user.role]) | Q(allowed_roles__contains=['ALL'])
    ).filter(enabled_by_default=True).order_by('order')[:8]

    # Actions rapides
    quick_actions = DashboardQuickAction.objects.filter(
        enabled=True,
        visible=True
    ).filter(
        Q(allowed_roles__contains=[request.user.role]) | Q(allowed_roles__contains=['ALL'])
    ).order_by('order')[:6]

    # Évolution des données (pour graphiques)
    evolution_data = get_evolution_data(12)

    context = {
        'page_title': 'Tableau de Bord Administrateur',
        'stats': stats,
        'recent_alerts': recent_alerts,
        'recent_payments': recent_payments,
        'unread_notifications': unread_notifications,
        'available_widgets': available_widgets,
        'quick_actions': quick_actions,
        'evolution_data': json.dumps(evolution_data),
        'user_layout': user_layout,
        'today': today,
    }

    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
@role_required(['AGENT_TERRAIN'])
def agent_dashboard(request):
    """Dashboard agent de terrain - VERSION CORRIGÉE"""
    today = timezone.now().date()
    current_month = date(today.year, today.month, 1)

    # Récupérer ou créer la configuration du dashboard
    user_layout, created = UserDashboardLayout.objects.get_or_create(user=request.user)
    user_layout.last_accessed = timezone.now()
    user_layout.save(update_fields=['last_accessed'])

    # ✅ CORRECTION: Pas de champ 'agent' dans Menage
    # On affiche tous les ménages actifs pour l'instant
    assigned_households = Menage.objects.filter(statut='ACTIF')

    # ✅ NOUVEAU: Calcul du nombre de compteurs actifs
    compteurs_actifs = Compteur.objects.filter(
        menage__in=assigned_households,
        statut='ACTIF'
    ).count()

    # Statistiques de l'agent
    stats = {
        'menages_assignes': assigned_households.count(),
        'factures_mois': Facture.objects.filter(periode=current_month).count(),
        'paiements_mois': Paiement.objects.filter(
            cree_par=request.user,  # ✅ CORRECTION: Remplacer caissier par cree_par
            statut='CONFIRMÉ',
            date_paiement__month=today.month,
            date_paiement__year=today.year
        ).count(),
        'montant_encaisse': float(
            Paiement.objects.filter(
                cree_par=request.user,  # ✅ CORRECTION: Remplacer caissier par cree_par
                statut='CONFIRMÉ',
                date_paiement__month=today.month,
                date_paiement__year=today.year
            ).aggregate(t=Sum('montant'))['t'] or 0
        )
    }

    # Tâches en attente
    pending_tasks = Alerte.objects.filter(
        statut='ACTIVE'
    ).select_related('compteur', 'compteur__menage').order_by('-date_detection')[:10]

    # Paiements du jour
    today_payments = Paiement.objects.filter(
        cree_par=request.user,  # ✅ CORRECTION: Remplacer caissier par cree_par
        date_paiement=today,
        statut='CONFIRMÉ'
    ).select_related('facture', 'facture__compteur__menage')

    # Préparer les données des paiements du jour
    today_payments_list = list(today_payments)
    today_payments_count = len(today_payments_list)
    today_payments_amount = sum(p.montant for p in today_payments_list)

    # Notifications non lues
    unread_notifications = DashboardNotification.objects.filter(
        user=request.user,
        read=False
    ).order_by('-created_at')[:5]

    # Actions rapides
    quick_actions = DashboardQuickAction.objects.filter(
        enabled=True,
        visible=True
    ).filter(
        Q(allowed_roles__contains=[request.user.role]) | Q(allowed_roles__contains=['ALL'])
    ).order_by('order')[:6]

    # Performance mensuelle
    performance_data = {
        'total_encaisse': stats['montant_encaisse'],
        'nb_paiements': stats['paiements_mois']
    }

    # ✅ CORRECTION: Utiliser created_at au lieu de date_creation
    # ✅ NOUVEAU: Récupérer les derniers compteurs créés
    derniers_compteurs = Compteur.objects.filter(
        menage__in=assigned_households
    ).order_by('-created_at')[:5]

    # ✅ NOUVEAU: Récupérer les derniers capteurs créés
    derniers_capteurs = []  # À adapter selon votre modèle de capteur
    # Exemple: derniers_capteurs = Capteur.objects.filter(compteur__menage__in=assigned_households).order_by('-created_at')[:5]

    # ✅ NOUVEAU: Récupérer les dernières actions de l'agent
    dernieres_actions = []  # À adapter selon votre modèle d'historique d'actions
    # Exemple: dernieres_actions = ActionHistorique.objects.filter(agent=request.user).order_by('-created_at')[:5]

    context = {
        'page_title': 'Tableau de Bord Agent',
        'assigned_households': assigned_households[:5],
        'assigned_count': assigned_households.count(),
        'stats': stats,
        'pending_tasks': pending_tasks,
        'alertes_a_traiter': pending_tasks,
        'today_payments': today_payments[:5],
        'today_payments_total': today_payments_count,
        'today_payments_amount': today_payments_amount,
        'unread_notifications': unread_notifications,
        'quick_actions': quick_actions,
        'performance_data': performance_data,
        'user_layout': user_layout,
        'today': today,

        # Variables supplémentaires pour le template
        'menages_assignes': assigned_households[:5],
        'compteurs_actifs': compteurs_actifs,  # ✅ AJOUT DE CETTE LIGNE
        'derniers_compteurs': derniers_compteurs,  # ✅ AJOUT DE CETTE LIGNE
        'derniers_capteurs': derniers_capteurs,  # ✅ AJOUT DE CETTE LIGNE
        'dernieres_actions': dernieres_actions,  # ✅ AJOUT DE CETTE LIGNE
        'paiements_jour': {
            'total': today_payments_count,
            'montant': float(today_payments_amount),
            'liste': today_payments_list[:5]
        },
        'performance': {
            'paiements_collectes': today_payments_count,
            'menages_visites': 0,
        },
        'interventions': [],
    }

    return render(request, 'dashboard/agent_dashboard.html', context)


@login_required
@role_required(['CLIENT'])
def client_dashboard(request):
    """Dashboard client/ménage"""
    today = timezone.now().date()
    current_month = date(today.year, today.month, 1)

    # Récupérer ou créer la configuration du dashboard
    user_layout, created = UserDashboardLayout.objects.get_or_create(user=request.user)

    # Mettre à jour le dernier accès
    user_layout.last_accessed = timezone.now()
    user_layout.save(update_fields=['last_accessed'])

    # Récupérer le ménage du client
    try:
        household = Menage.objects.get(utilisateur=request.user)
    except Menage.DoesNotExist:
        messages.error(request, "Aucun ménage associé à votre compte.")
        return render(request, 'dashboard/client_dashboard.html', {
            'page_title': 'Mon Tableau de Bord',
            'household': None,
            'user_layout': user_layout,
        })

    # Récupérer les compteurs du ménage
    compteurs = Compteur.objects.filter(menage=household)

    # ✅ Définir compteur_principal (le premier compteur actif)
    compteur_principal = compteurs.filter(statut='ACTIF').first()

    # Statistiques du client
    stats = get_client_stats(household, today, current_month)

    # Consommation du mois en cours
    consommation_mois = get_current_consumption(household)

    # ✅ Calcul du coût estimé pour le dashboard
    cout_estime = 0
    if compteur_principal and compteur_principal.type_tarification and consommation_mois > 0:
        try:
            montant_ht = compteur_principal.type_tarification.calculer_montant(consommation_mois)
            tva = montant_ht * (compteur_principal.type_tarification.tva_taux / 100)
            abonnement = compteur_principal.type_tarification.abonnement_mensuel
            cout_estime = float(montant_ht + tva + abonnement)
        except:
            cout_estime = consommation_mois * 109
    else:
        cout_estime = consommation_mois * 109

    # Factures impayées
    factures_impayees_qs = Facture.objects.filter(
        compteur__menage=household,
        statut__in=['ÉMISE', 'PARTIELLEMENT_PAYÉE', 'EN_RETARD']
    ).order_by('date_echeance')

    factures_impayees_list = list(factures_impayees_qs[:5])

    # Calculer le solde dû pour chaque facture (calculer le total TTC)
    for facture in factures_impayees_list:
        # Calcul du total TTC
        total_ht = (
                (facture.montant_consommation or 0) +
                (facture.montant_abonnement or 0) +
                (facture.redevance_communale or 0) +
                (facture.autres_taxes or 0)
        )
        tva = total_ht * ((facture.tva_taux or 0) / 100)
        facture.total_ttc = total_ht + tva
        facture.solde_du = facture.total_ttc - (facture.montant_paye or 0)

    # Calculer le montant total dû
    total_du = 0
    for facture in factures_impayees_qs:
        total_ht = (
                (facture.montant_consommation or 0) +
                (facture.montant_abonnement or 0) +
                (facture.redevance_communale or 0) +
                (facture.autres_taxes or 0)
        )
        tva = total_ht * ((facture.tva_taux or 0) / 100)
        total_ttc = total_ht + tva
        total_du += total_ttc - (facture.montant_paye or 0)

    factures_impayees = {
        'total': factures_impayees_qs.count(),
        'montant': total_du,
        'liste': factures_impayees_list
    }

    # Prochaine échéance
    prochaine_echeance = None
    next_invoice = Facture.objects.filter(
        compteur__menage=household,
        statut__in=['ÉMISE', 'EN_RETARD'],
        date_echeance__gte=today
    ).order_by('date_echeance').first()

    if next_invoice:
        prochaine_echeance = next_invoice.date_echeance

    # Consommation actuelle - récupérer la dernière consommation
    derniere_conso = None
    last_reading = Consommation.objects.filter(
        compteur__menage=household
    ).order_by('-periode').first()

    if last_reading:
        # Calculer la puissance actuelle (simulée ou basée sur la puissance moyenne)
        puissance_actuelle = last_reading.puissance_moyenne_kw * 1000 if last_reading.puissance_moyenne_kw else 500

        # Calculer la charge (pourcentage de la puissance maximale)
        if last_reading.puissance_max_kw and last_reading.puissance_max_kw > 0:
            charge = (puissance_actuelle / (last_reading.puissance_max_kw * 1000)) * 100
        else:
            charge = 25  # Valeur par défaut

        # Calculer la variation (simulée pour l'exemple)
        variation = -5.2

        derniere_conso = {
            'puissance_actuelle': round(puissance_actuelle, 1),
            'charge': round(charge, 0),
            'variation': variation,
            'tendance': 'BAISSE' if variation < 0 else 'HAUSSE' if variation > 0 else 'STABLE'
        }

    # Factures en attente
    pending_invoices = factures_impayees_list
    pending_invoices_count = len(pending_invoices)
    pending_invoices_total = total_du

    # Alertes récentes
    recent_alerts = Alerte.objects.filter(
        Q(compteur__menage=household) | Q(utilisateur=request.user),
        statut='ACTIVE'
    ).order_by('-date_detection')[:5]

    # Notifications non lues
    unread_notifications = DashboardNotification.objects.filter(
        user=request.user,
        read=False
    ).order_by('-created_at')[:5]

    # Historique de consommation (6 derniers mois)
    consumption_history = get_consumption_history(household, 6)

    # Préparer l'historique pour le graphique
    historique = []
    for item in consumption_history:
        historique.append({
            'mois': item['month'],
            'valeur': item['consommation']
        })

    # Conseils d'économie
    savings_tips = get_savings_tips(household)

    # Récupérer les factures récentes pour le tableau
    factures_recents = Facture.objects.filter(
        compteur__menage=household
    ).order_by('-date_emission')[:5]

    context = {
        'page_title': 'Mon Tableau de Bord',
        'household': household,
        'menage': household,
        'compteurs': compteurs,
        'consommation_mois': consommation_mois,
        'cout_estime': round(cout_estime, 0),
        'factures_impayees': factures_impayees,
        'factures_recents': factures_recents,  # ✅ AJOUT
        'prochaine_echeance': prochaine_echeance,
        'derniere_conso': derniere_conso,
        'notifications': unread_notifications,
        'historique': historique,
        'savings_tips': savings_tips,
        'stats': stats,
        'current_consumption': derniere_conso,
        'pending_invoices': pending_invoices,
        'pending_invoices_count': pending_invoices_count,
        'pending_invoices_total': pending_invoices_total,
        'recent_alerts': recent_alerts,
        'unread_notifications': unread_notifications,
        'consumption_history': json.dumps(consumption_history),
        'user_layout': user_layout,
        'today': today,
    }

    return render(request, 'dashboard/client_dashboard.html', context)
# ============================================
# STATISTIQUES ET RAPPORTS
# ============================================
@login_required
@role_required(['ADMIN'])
def admin_statistics(request):
    """Statistiques globales détaillées"""
    period = request.GET.get('period', 'month')
    start_date, end_date = get_date_range(period)

    # Statistiques détaillées
    detailed_stats = get_detailed_admin_stats(start_date, end_date)

    # Évolution temporelle
    timeline_data = get_timeline_data(12)

    # Top consommateurs
    top_consumers = get_top_consumers(10, start_date, end_date)

    # Distribution géographique
    geographic_distribution = get_geographic_distribution()

    # Analyse financière
    financial_analysis = get_financial_analysis(start_date, end_date)

    context = {
        'page_title': 'Statistiques Détaillées',
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'stats': detailed_stats,
        'timeline_data': json.dumps(timeline_data),
        'top_consumers': top_consumers,
        'geographic_distribution': json.dumps(geographic_distribution),
        'financial_analysis': financial_analysis,
    }

    return render(request, 'dashboard/admin_statistics.html', context)


@login_required
@role_required(['ADMIN'])
def admin_financial_report(request):
    """Rapport financier détaillé"""
    year = int(request.GET.get('year', timezone.now().year))
    month = request.GET.get('month')

    # Données financières
    financial_data = get_financial_report_data(year, month)

    # Analyse de rentabilité
    profitability_analysis = get_profitability_analysis(year, month)

    # Détails des revenus
    revenue_details = get_revenue_details(year, month)

    # Détails des dépenses
    expense_details = get_expense_details(year, month)

    context = {
        'page_title': 'Rapport Financier',
        'year': year,
        'month': month,
        'financial_data': financial_data,
        'profitability_analysis': profitability_analysis,
        'revenue_details': revenue_details,
        'expense_details': expense_details,
        'months': list(calendar.month_name)[1:],
        'current_year': timezone.now().year,
    }

    return render(request, 'dashboard/admin_financial_report.html', context)


@login_required
@role_required(['ADMIN'])
def admin_technical_report(request):
    """Rapport technique"""
    # Statistiques techniques
    technical_stats = get_technical_stats()

    # État des compteurs
    meter_status = get_meter_status_report()

    # Performances Shelly
    shelly_performance = get_shelly_performance()

    # Alertes techniques
    technical_alerts = Alerte.objects.filter(
        type_alerte__icontains='TECHNIQUE'
    ).order_by('-date_detection')[:20]

    context = {
        'page_title': 'Rapport Technique',
        'technical_stats': technical_stats,
        'meter_status': meter_status,
        'shelly_performance': shelly_performance,
        'technical_alerts': technical_alerts,
    }

    return render(request, 'dashboard/admin_technical_report.html', context)


@login_required
@role_required(['AGENT_TERRAIN'])
def agent_performance(request):
    """Performance de l'agent"""
    agent = request.user
    period = request.GET.get('period', 'month')
    start_date, end_date = get_date_range(period)

    # Statistiques de performance
    performance_stats = get_agent_performance_stats(agent, start_date, end_date)

    # Activités récentes
    recent_activities = get_agent_recent_activities(agent, 10)

    # Objectifs et réalisations
    goals_progress = get_agent_goals_progress(agent, start_date, end_date)

    # Comparaison avec les autres agents
    agent_comparison = get_agent_comparison(agent, start_date, end_date)

    context = {
        'page_title': 'Mes Performances',
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'performance_stats': performance_stats,
        'recent_activities': recent_activities,
        'goals_progress': goals_progress,
        'agent_comparison': agent_comparison,
        'agent': agent,
    }

    return render(request, 'dashboard/agent_performance.html', context)

@login_required
@role_required(['CLIENT'])
def client_consumption_analysis(request):
    try:
        household = Menage.objects.get(utilisateur=request.user)
    except Menage.DoesNotExist:
        messages.error(request, "Aucun ménage associé à votre compte.")
        return redirect('dashboard:client_dashboard')

    period = request.GET.get('period', 'month')
    start_date, end_date = get_date_range(period)

    # Récupérer le compteur et sa tarification
    compteur = household.compteurs.filter(statut='ACTIF').first()

    # === Pour la période "aujourd'hui", utiliser les données de la BASE ===
    if period == 'day':
        # Récupérer la consommation en base pour aujourd'hui
        conso = Consommation.objects.filter(
            compteur__menage=household,
            periode=start_date
        ).first()

        if conso:
            total_kwh = conso.consommation_kwh
            consumption_analysis = {
                'total': round(float(total_kwh), 2),
                'daily_avg': round(float(total_kwh), 2),
                'peak': round(float(total_kwh), 2),
                'nombre_releves': 1,
            }

            # Calcul du coût
            cout_estime = 0
            if compteur and compteur.type_tarification and total_kwh > 0:
                montant_ht = compteur.type_tarification.calculer_montant(total_kwh)
                tva = montant_ht * (compteur.type_tarification.tva_taux / 100)
                abonnement_jour = compteur.type_tarification.abonnement_mensuel / 30
                cout_estime = float(montant_ht + tva + abonnement_jour)
            else:
                cout_estime = total_kwh * 109

            # Répartition par phase
            appliance_breakdown = [
                {'name': 'Phase 1', 'value': round(float(conso.phase_1_kwh or 0), 2)},
                {'name': 'Phase 2', 'value': round(float(conso.phase_2_kwh or 0), 2)},
                {'name': 'Phase 3', 'value': round(float(conso.phase_3_kwh or 0), 2)},
            ]

            # Historique pour le graphique
            trends_list = get_consumption_trends(household, 12)

            # Détail du tableau
            consommations_detaillees = []
            for t in trends_list:
                if t["value"] > 0:  # Afficher seulement les mois avec consommation
                    kwh_ligne = t["value"]
                    if compteur and compteur.type_tarification and kwh_ligne > 0:
                        montant_ht = compteur.type_tarification.calculer_montant(kwh_ligne)
                        tva = montant_ht * (compteur.type_tarification.tva_taux / 100)
                        cout_ligne = float(montant_ht + tva)
                    else:
                        cout_ligne = kwh_ligne * 109

                    consommations_detaillees.append({
                        "periode": t["label"],
                        "total_kwh": kwh_ligne,
                        "cout": round(cout_ligne, 0),
                    })

            comparison_data = get_consumption_comparison(household, start_date, end_date)
            consumption_forecast = get_consumption_forecast(household)

            context = {
                'page_title': 'Analyse de Ma Consommation',
                'household': household,
                'period': period,
                'start_date': start_date,
                'end_date': end_date,
                'consumption_analysis': consumption_analysis,
                'cout_estime': round(cout_estime, 0),
                'consommations_detaillees': consommations_detaillees,
                'comparison_data': comparison_data,
                'consumption_trends': json.dumps(trends_list),
                'appliance_breakdown': json.dumps(appliance_breakdown),
                'consumption_forecast': consumption_forecast,
            }

            return render(request, 'dashboard/client_consumption_analysis.html', context)
        else:
            # Pas de consommation en base pour aujourd'hui
            consumption_analysis = {'total': 0, 'daily_avg': 0, 'peak': 0, 'nombre_releves': 0}
            trends_list = get_consumption_trends(household, 12)
            consommations_detaillees = []
            for t in trends_list:
                if t["value"] > 0:
                    consommations_detaillees.append({
                        "periode": t["label"],
                        "total_kwh": t["value"],
                        "cout": round(t["value"] * 109, 0),
                    })

            context = {
                'page_title': 'Analyse de Ma Consommation',
                'household': household,
                'period': period,
                'start_date': start_date,
                'end_date': end_date,
                'consumption_analysis': consumption_analysis,
                'cout_estime': 0,
                'consommations_detaillees': consommations_detaillees,
                'comparison_data': {},
                'consumption_trends': json.dumps(trends_list),
                'appliance_breakdown': json.dumps([]),
                'consumption_forecast': 0,
            }

            return render(request, 'dashboard/client_consumption_analysis.html', context)

    # === Données historiques (pour "semaine", "mois", "année") ===
    consumption_analysis = get_consumption_analysis(household, start_date, end_date)
    trends_list = get_consumption_trends(household, 12)

    # Calcul du coût avec la tarification réelle
    cout_estime = 0
    total_kwh = consumption_analysis.get('total', 0)

    try:
        if compteur and compteur.type_tarification and total_kwh > 0:
            montant_ht = compteur.type_tarification.calculer_montant(total_kwh)
            tva = montant_ht * (compteur.type_tarification.tva_taux / 100)
            abonnement = compteur.type_tarification.abonnement_mensuel
            cout_estime = float(montant_ht + tva + abonnement)
        else:
            cout_estime = total_kwh * 109
    except Exception as e:
        print(f"Erreur calcul tarif: {e}")
        cout_estime = total_kwh * 109

    # Détail du tableau avec la vraie tarification
    consommations_detaillees = []
    for t in trends_list:
        if t["value"] > 0:
            kwh_ligne = t["value"]
            if compteur and compteur.type_tarification and kwh_ligne > 0:
                montant_ht = compteur.type_tarification.calculer_montant(kwh_ligne)
                tva = montant_ht * (compteur.type_tarification.tva_taux / 100)
                cout_ligne = float(montant_ht + tva)
            else:
                cout_ligne = kwh_ligne * 109

            consommations_detaillees.append({
                "periode": t["label"],
                "total_kwh": kwh_ligne,
                "cout": round(cout_ligne, 0),
            })

    comparison_data = get_consumption_comparison(household, start_date, end_date)
    appliance_breakdown = get_appliance_breakdown(household)
    consumption_forecast = get_consumption_forecast(household)

    context = {
        'page_title': 'Analyse de Ma Consommation',
        'household': household,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'consumption_analysis': consumption_analysis,
        'cout_estime': round(cout_estime, 0),
        'consommations_detaillees': consommations_detaillees,
        'comparison_data': comparison_data,
        'consumption_trends': json.dumps(trends_list),
        'appliance_breakdown': json.dumps(appliance_breakdown),
        'consumption_forecast': consumption_forecast,
    }

    return render(request, 'dashboard/client_consumption_analysis.html', context)

@login_required
@role_required(['CLIENT'])
def client_conseils(request):
    """Page de conseils d'économie d'énergie pour les clients"""
    try:
        household = Menage.objects.get(utilisateur=request.user)
    except Menage.DoesNotExist:
        messages.error(request, "Aucun ménage associé à votre compte.")
        return redirect('dashboard:client_dashboard')

    # Récupérer les statistiques de consommation
    current_month = timezone.now().date().replace(day=1)

    # Consommation actuelle vs moyenne
    current_consumption = Consommation.objects.filter(
        compteur__menage=household,
        periode=current_month
    ).aggregate(
        total=Sum(F('index_fin_periode') - F('index_debut_periode'))
    )['total'] or 0

    # Moyenne des 6 derniers mois
    six_months_ago = current_month - timedelta(days=180)
    avg_consumption = Consommation.objects.filter(
        compteur__menage=household,
        periode__gte=six_months_ago,
        periode__lt=current_month
    ).aggregate(
        avg=Avg(F('index_fin_periode') - F('index_debut_periode'))
    )['avg'] or 0

    # Calculer le niveau de consommation
    if avg_consumption > 0:
        if current_consumption > avg_consumption * 1.2:
            consumption_level = 'high'
            level_label = 'Élevée'
            level_class = 'danger'
        elif current_consumption > avg_consumption * 0.8:
            consumption_level = 'medium'
            level_label = 'Normale'
            level_class = 'warning'
        else:
            consumption_level = 'low'
            level_label = 'Faible'
            level_class = 'success'
    else:
        consumption_level = 'medium'
        level_label = 'Normale'
        level_class = 'info'

    # Liste des conseils selon le niveau
    all_conseils = {
        'high': [
            {
                'titre': 'Réduisez le chauffage',
                'description': 'Baisser de 1°C peut économiser jusqu\'à 7% sur votre facture de chauffage.',
                'icon': 'thermometer-half',
                'color': 'danger',
                'economie_potentielle': 50
            },
            {
                'titre': 'Optimisez vos appareils électroménagers',
                'description': 'Utilisez le lave-linge et lave-vaisselle en heures creuses (22h-6h) pour bénéficier de tarifs réduits.',
                'icon': 'plug',
                'color': 'warning',
                'economie_potentielle': 30
            },
            {
                'titre': 'Éteignez les veilles',
                'description': 'Les appareils en veille représentent jusqu\'à 10% de votre consommation électrique annuelle.',
                'icon': 'power-off',
                'color': 'info',
                'economie_potentielle': 20
            },
            {
                'titre': 'Améliorez l\'isolation',
                'description': 'Une bonne isolation peut réduire vos besoins en chauffage de 30%.',
                'icon': 'home',
                'color': 'primary',
                'economie_potentielle': 100
            },
        ],
        'medium': [
            {
                'titre': 'Utilisez les heures creuses',
                'description': 'Programmez vos appareils énergivores entre 22h et 6h pour économiser sur le tarif.',
                'icon': 'clock',
                'color': 'info',
                'economie_potentielle': 25
            },
            {
                'titre': 'Entretenez vos appareils',
                'description': 'Un appareil bien entretenu consomme 15% de moins qu\'un appareil négligé.',
                'icon': 'tools',
                'color': 'warning',
                'economie_potentielle': 15
            },
            {
                'titre': 'Utilisez des LED',
                'description': 'Remplacez vos ampoules classiques par des LED pour économiser jusqu\'à 80% sur l\'éclairage.',
                'icon': 'lightbulb',
                'color': 'warning',
                'economie_potentielle': 20
            },
        ],
        'low': [
            {
                'titre': 'Continuez vos efforts !',
                'description': 'Votre consommation est optimale. Maintenez vos bonnes habitudes.',
                'icon': 'check-circle',
                'color': 'success',
                'economie_potentielle': 0
            },
            {
                'titre': 'Partagez vos astuces',
                'description': 'Vos bonnes pratiques peuvent inspirer d\'autres foyers.',
                'icon': 'share-alt',
                'color': 'info',
                'economie_potentielle': 0
            },
        ]
    }

    conseils = all_conseils[consumption_level]

    # Conseils généraux (toujours affichés)
    conseils_generaux = [
        {
            'titre': 'Surveillez votre consommation',
            'description': 'Consultez régulièrement votre tableau de bord pour détecter les anomalies.',
            'icon': 'chart-line',
            'color': 'primary'
        },
        {
            'titre': 'Dégivrez régulièrement',
            'description': 'Un réfrigérateur givré consomme jusqu\'à 30% de plus.',
            'icon': 'snowflake',
            'color': 'info'
        },
        {
            'titre': 'Couvrez vos casseroles',
            'description': 'Couvrir une casserole pendant la cuisson divise par 4 la consommation d\'énergie.',
            'icon': 'utensils',
            'color': 'success'
        },
    ]

    context = {
        'page_title': 'Conseils d\'Économie',
        'household': household,
        'current_consumption': current_consumption,
        'avg_consumption': avg_consumption,
        'consumption_level': consumption_level,
        'level_label': level_label,
        'level_class': level_class,
        'conseils': conseils,
        'conseils_generaux': conseils_generaux,
        'economie_totale': sum(c['economie_potentielle'] for c in conseils),
    }

    return render(request, 'dashboard/client_conseils.html', context)


# ============================================
# GESTION DES WIDGETS
# ============================================
@login_required
def widget_management(request):
    """Gestion des widgets du dashboard"""
    user_layout, created = UserDashboardLayout.objects.get_or_create(user=request.user)

    # Widgets disponibles selon le rôle
    available_widgets = DashboardWidget.objects.filter(
        Q(allowed_roles__contains=[request.user.role]) | Q(allowed_roles__contains=['ALL'])
    ).order_by('order')

    # Widgets activés
    enabled_widgets = user_layout.enabled_widgets.all()

    # Catégories de widgets
    widget_categories = {}
    for widget in available_widgets:
        category = widget.config.get('category', 'Général')
        if category not in widget_categories:
            widget_categories[category] = []
        widget_categories[category].append(widget)

    if request.method == 'POST':
        # Gérer l'activation/désactivation des widgets
        action = request.POST.get('action')
        widget_id = request.POST.get('widget_id')

        if action == 'toggle' and widget_id:
            try:
                widget = DashboardWidget.objects.get(id=widget_id)
                if widget in enabled_widgets:
                    user_layout.enabled_widgets.remove(widget)
                    messages.success(request, f"Widget '{widget.name}' désactivé")
                else:
                    user_layout.enabled_widgets.add(widget)
                    messages.success(request, f"Widget '{widget.name}' activé")
            except DashboardWidget.DoesNotExist:
                messages.error(request, "Widget non trouvé")

        # Gérer la réinitialisation
        elif action == 'reset':
            user_layout.layout_config = []
            user_layout.save()
            messages.success(request, "Configuration réinitialisée")

        return redirect('dashboard:widget_management')

    context = {
        'page_title': 'Gestion des Widgets',
        'user_layout': user_layout,
        'available_widgets': available_widgets,
        'enabled_widgets': enabled_widgets,
        'widget_categories': widget_categories,
    }

    return render(request, 'dashboard/widget_management.html', context)




@login_required
def save_layout(request):
    """Sauvegarder la configuration du layout"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            layout_data = json.loads(request.POST.get('layout', '[]'))
            user_layout, created = UserDashboardLayout.objects.get_or_create(user=request.user)
            user_layout.layout_config = layout_data
            user_layout.save()
            return JsonResponse({'status': 'success', 'message': 'Layout sauvegardé'})
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Données invalides'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Requête invalide'}, status=400)


# ============================================
# GESTION DES NOTIFICATIONS
# ============================================
@login_required
def notifications_list(request):
    """Liste des notifications"""
    notifications = DashboardNotification.objects.filter(user=request.user)

    # Appliquer les filtres
    filter_form = NotificationFilterForm(request.GET or None)
    if filter_form.is_valid():
        if filter_form.cleaned_data['read_status']:
            read_status = filter_form.cleaned_data['read_status'] == 'True'
            notifications = notifications.filter(read=read_status)
        if filter_form.cleaned_data['notification_type']:
            notifications = notifications.filter(notification_type=filter_form.cleaned_data['notification_type'])
        if filter_form.cleaned_data['date_debut']:
            notifications = notifications.filter(created_at__date__gte=filter_form.cleaned_data['date_debut'])
        if filter_form.cleaned_data['date_fin']:
            notifications = notifications.filter(created_at__date__lte=filter_form.cleaned_data['date_fin'])

    # Trier par priorité et date
    notifications = notifications.order_by('-priority', '-created_at')

    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistiques des notifications
    notification_stats = {
        'total': DashboardNotification.objects.filter(user=request.user).count(),
        'unread': DashboardNotification.objects.filter(user=request.user, read=False).count(),
        'urgent': DashboardNotification.objects.filter(user=request.user, priority=2).count(),
    }

    context = {
        'page_title': 'Mes Notifications',
        'notifications': page_obj,
        'filter_form': filter_form,
        'notification_stats': notification_stats,
    }

    return render(request, 'dashboard/notifications_list.html', context)


@login_required
def notification_detail(request, notification_id):
    """Détail d'une notification"""
    notification = get_object_or_404(DashboardNotification, id=notification_id, user=request.user)

    # Marquer comme lue si ce n'est pas déjà fait
    if not notification.read:
        notification.read = True
        notification.save(update_fields=['read'])

    context = {
        'page_title': notification.title,
        'notification': notification,
    }

    return render(request, 'dashboard/notification_detail.html', context)


@login_required
def mark_notification_read(request, notification_id):
    """Marquer une notification comme lue"""
    notification = get_object_or_404(DashboardNotification, id=notification_id, user=request.user)

    if not notification.read:
        notification.read = True
        notification.save(update_fields=['read'])
        messages.success(request, "Notification marquée comme lue")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})

    return redirect('dashboard:notifications_list')


@login_required
def mark_all_notifications_read(request):
    """Marquer toutes les notifications comme lues"""
    updated = DashboardNotification.objects.filter(user=request.user, read=False).update(read=True)

    if updated > 0:
        messages.success(request, f"{updated} notification(s) marquée(s) comme lue(s)")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'updated': updated})

    return redirect('dashboard:notifications_list')


@login_required
def delete_notification(request, notification_id):
    """Supprimer une notification"""
    notification = get_object_or_404(DashboardNotification, id=notification_id, user=request.user)
    notification_title = notification.title

    notification.delete()
    messages.success(request, f"Notification '{notification_title}' supprimée")

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})

    return redirect('dashboard:notifications_list')


# ============================================
# ACTIONS RAPIDES
# ============================================
@login_required
def quick_actions(request):
    """Liste des actions rapides"""
    quick_actions_list = DashboardQuickAction.objects.filter(
        enabled=True,
        visible=True
    ).filter(
        Q(allowed_roles__contains=[request.user.role]) | Q(allowed_roles__contains=['ALL'])
    ).order_by('category', 'order')

    # Grouper par catégorie
    actions_by_category = {}
    for action in quick_actions_list:
        category = action.category or 'Général'
        if category not in actions_by_category:
            actions_by_category[category] = []
        actions_by_category[category].append(action)

    context = {
        'page_title': 'Actions Rapides',
        'actions_by_category': actions_by_category,
        'total_actions': quick_actions_list.count(),
    }

    return render(request, 'dashboard/quick_actions.html', context)


@login_required
def execute_quick_action(request, action_id):
    """Exécuter une action rapide"""
    action = get_object_or_404(DashboardQuickAction, id=action_id)

    # Vérifier les permissions
    if not action.is_allowed_for_user(request.user):
        messages.error(request, "Vous n'avez pas la permission d'exécuter cette action.")
        return redirect('dashboard:index')

    # Vérifier la confirmation si nécessaire
    if action.requires_confirmation and not request.POST.get('confirmed'):
        context = {
            'page_title': 'Confirmation Requise',
            'action': action,
        }
        return render(request, 'dashboard/confirm_action.html', context)

    # Exécuter l'action (redirection vers l'URL)
    # Note: Dans une implémentation réelle, vous pourriez avoir une logique plus complexe
    url = action.url

    # Remplacer les variables dans l'URL
    from datetime import datetime
    url = url.replace('{user_id}', str(request.user.id))
    url = url.replace('{today}', datetime.now().strftime('%Y-%m-%d'))

    messages.success(request, f"Action '{action.name}' exécutée")
    return redirect(url)


# ============================================
# PARAMÈTRES DU DASHBOARD
# ============================================
@login_required
def dashboard_settings(request):
    """Paramètres du dashboard"""
    user_layout, created = UserDashboardLayout.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        form = DashboardLayoutForm(request.POST, instance=user_layout)
        if form.is_valid():
            form.save()
            messages.success(request, "Paramètres du dashboard sauvegardés")
            return redirect('dashboard:dashboard_settings')
    else:
        form = DashboardLayoutForm(instance=user_layout)

    context = {
        'page_title': 'Paramètres du Dashboard',
        'form': form,
        'user_layout': user_layout,
    }

    return render(request, 'dashboard/dashboard_settings.html', context)


# ============================================
# VUES AJAX/API
# ============================================
@login_required
def ajax_stats(request):
    """Endpoint AJAX pour les statistiques en temps réel"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Requête non autorisée'}, status=400)

    stats_type = request.GET.get('type', 'overview')
    period = request.GET.get('period', 'today')
    start_date, end_date = get_date_range(period)

    if request.user.role == 'ADMIN':
        data = get_ajax_admin_stats(start_date, end_date, stats_type)
    elif request.user.role == 'AGENT':
        data = get_ajax_agent_stats(request.user, start_date, end_date, stats_type)
    else:
        try:
            household = Menage.objects.get(utilisateur=request.user)
            data = get_ajax_client_stats(household, start_date, end_date, stats_type)
        except Menage.DoesNotExist:
            data = {'error': 'Ménage non trouvé'}

    return JsonResponse(data)


@login_required
def ajax_widget_data(request, widget_id):
    """Données pour un widget spécifique (AJAX)"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Requête non autorisée'}, status=400)

    widget = get_object_or_404(DashboardWidget, id=widget_id)

    # Vérifier les permissions
    if not widget.is_allowed_for_user(request.user):
        return JsonResponse({'error': 'Non autorisé'}, status=403)

    # Récupérer les données selon le type de widget
    data = get_widget_data(widget, request.user)

    return JsonResponse(data)


from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.decorators import login_required


@login_required
def ajax_notifications(request):
    """Endpoint AJAX pour récupérer les notifications récentes"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Requête non autorisée'}, status=400)

    try:
        limit = int(request.GET.get('limit', 5))
        # Limiter le nombre de notifications entre 1 et 50
        limit = max(1, min(limit, 50))  # entre 1 et 50

        # Récupérer les notifications non expirées
        notifications = DashboardNotification.objects.filter(
            user=request.user,
            archived=False
        ).exclude(
            expires_at__lt=timezone.now()
        ).order_by('-priority', '-created_at')[:limit]

        # Compter les notifications non lues
        unread_count = DashboardNotification.objects.filter(
            user=request.user,
            read=False,
            archived=False
        ).exclude(
            expires_at__lt=timezone.now()
        ).count()

        # Préparer les données
        notifications_data = []
        for notif in notifications:
            # Déterminer l'icône en fonction du type
            icon_map = {
                'INFO': 'info-circle',
                'SUCCESS': 'check-circle',
                'WARNING': 'exclamation-triangle',
                'ERROR': 'times-circle',
                'SYSTEM': 'cog',
                'ALERT': 'bell'
            }

            # Déterminer la couleur
            color_class = ''
            if notif.priority == 2:  # Urgent
                color_class = 'text-red-500'
            elif notif.notification_type == 'ERROR':
                color_class = 'text-red-500'
            elif notif.notification_type == 'WARNING':
                color_class = 'text-amber-500'
            elif notif.notification_type == 'SUCCESS':
                color_class = 'text-emerald-500'
            elif notif.notification_type == 'INFO':
                color_class = 'text-blue-500'
            else:
                color_class = 'text-slate-500'

            notifications_data.append({
                'id': notif.id,
                'title': notif.title,
                'message': notif.message[:100] + ('...' if len(notif.message) > 100 else ''),
                'type': notif.notification_type.lower(),
                'icon': notif.icon or icon_map.get(notif.notification_type, 'bell'),
                'color_class': color_class,
                'priority': notif.priority,
                'read': notif.read,
                'created_at': notif.created_at.strftime('%d/%m/%Y %H:%M'),
                'action_url': notif.action_url,
                'action_label': notif.action_label,
                'detail_url': reverse('dashboard:notification_detail', args=[notif.id])
            })

        return JsonResponse({
            'success': True,
            'notifications': notifications_data,
            'unread_count': unread_count,
            'has_unread': unread_count > 0
        })

    except Exception as e:
        import traceback
        print(f"❌ Erreur ajax_notifications: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
@login_required
def ajax_mark_notification_read(request, notification_id):
    """Marquer une notification comme lue via AJAX"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Requête non autorisée'}, status=400)

    try:
        notification = DashboardNotification.objects.get(
            id=notification_id,
            user=request.user
        )

        if not notification.read:
            notification.read = True
            notification.save(update_fields=['read'])

        # Compter les notifications non lues restantes
        unread_count = DashboardNotification.objects.filter(
            user=request.user,
            read=False,
            archived=False
        ).exclude(
            expires_at__lt=timezone.now()
        ).count()

        return JsonResponse({
            'success': True,
            'unread_count': unread_count,
            'has_unread': unread_count > 0
        })

    except DashboardNotification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification non trouvée'
        }, status=404)
    except Exception as e:
        print(f"❌ Erreur ajax_mark_notification_read: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def ajax_mark_all_read(request):
    """Marquer toutes les notifications comme lues via AJAX"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'error': 'Requête non autorisée'}, status=400)

    try:
        updated = DashboardNotification.objects.filter(
            user=request.user,
            read=False,
            archived=False
        ).exclude(
            expires_at__lt=timezone.now()
        ).update(read=True)

        return JsonResponse({
            'success': True,
            'updated_count': updated,
            'unread_count': 0,
            'has_unread': False
        })

    except Exception as e:
        print(f"❌ Erreur ajax_mark_all_read: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

# ============================================
# FONCTIONS UTILITAIRES BUSINESS – DONNÉES RÉELLES
# ============================================
def get_admin_stats(today, current_month):
    """Stats business ADMIN – données réelles"""

    factures_mois = Facture.objects.filter(periode=current_month)
    paiements_confirmes = Paiement.objects.filter(
        statut='CONFIRMÉ',
        date_paiement__month=today.month,
        date_paiement__year=today.year
    )

    total_facture = factures_mois.aggregate(
        total=Sum('montant_consommation')
    )['total'] or Decimal('0')

    total_paye = paiements_confirmes.aggregate(
        total=Sum('montant')
    )['total'] or Decimal('0')

    taux_recouvrement = (
        (total_paye / total_facture) * 100
        if total_facture > 0 else 0
    )

    return {
        'total_menages': Menage.objects.count(),
        'menages_actifs': Menage.objects.filter(statut='ACTIF').count(),

        'total_compteurs': Compteur.objects.count(),
        'compteurs_actifs': Compteur.objects.filter(statut='ACTIF').count(),

        'factures_emises': factures_mois.count(),
        'factures_payees': factures_mois.filter(statut='PAYÉE').count(),

        'chiffre_affaires': float(total_paye),
        'facturation_totale': float(total_facture),
        'taux_recouvrement': round(taux_recouvrement, 2),

        'alertes_actives': Alerte.objects.filter(statut='ACTIVE').count(),
    }


def get_evolution_data(months):
    """Évolution CA / Paiements sur X mois"""
    data = []
    today = timezone.now().date().replace(day=1)

    for i in range(months - 1, -1, -1):
        month = today - timedelta(days=30 * i)

        factures = Facture.objects.filter(periode=month)
        paiements = Paiement.objects.filter(
            statut='CONFIRMÉ',
            date_paiement__month=month.month,
            date_paiement__year=month.year
        )

        data.append({
            'month': month.strftime('%Y-%m'),
            'facturation': float(
                factures.aggregate(t=Sum('montant_consommation'))['t'] or 0
            ),
            'paiements': float(
                paiements.aggregate(t=Sum('montant'))['t'] or 0
            )
        })

    return data


def get_agent_stats(agent, today, current_month):
    """Stats agent réelles - VERSION CORRIGÉE"""

    factures = Facture.objects.filter(periode=current_month)

    paiements = Paiement.objects.filter(
        cree_par=agent,  # ✅ CORRECTION: Remplacer caissier par cree_par
        statut='CONFIRMÉ',
        date_paiement__month=today.month,
        date_paiement__year=today.year
    )

    # ✅ CORRECTION: Enlever le filtre sur 'agent' qui n'existe pas
    menages_count = Menage.objects.filter(statut='ACTIF').count()

    return {
        'menages_assignes': menages_count,
        'factures_mois': factures.count(),
        'paiements_mois': paiements.count(),
        'montant_encaisse': float(
            paiements.aggregate(t=Sum('montant'))['t'] or 0
        )
    }


def get_agent_performance(agent, current_month):
    """Performance mensuelle agent - VERSION CORRIGÉE"""

    paiements = Paiement.objects.filter(
        cree_par=agent,  # ✅ CORRECTION: Remplacer caissier par cree_par
        statut='CONFIRMÉ',
        date_paiement__month=current_month.month,
        date_paiement__year=current_month.year
    )

    return {
        'total_encaisse': float(
            paiements.aggregate(t=Sum('montant'))['t'] or 0
        ),
        'nb_paiements': paiements.count()
    }


# apps/dashboard/views.py
def get_client_stats(household, today, current_month):
    """Stats client réelles"""
    factures = Facture.objects.filter(compteur__menage=household)
    paiements = Paiement.objects.filter(
        facture__compteur__menage=household,
        statut='CONFIRMÉ'
    )

    # Calculer le solde total dû
    total_du = 0
    for facture in factures:
        if facture.statut != 'PAYÉE':
            total_ht = (
                    (facture.montant_consommation or 0) +
                    (facture.montant_abonnement or 0) +
                    (facture.redevance_communale or 0) +
                    (facture.autres_taxes or 0)
            )
            tva = total_ht * ((facture.tva_taux or 0) / 100)
            total_ttc = total_ht + tva
            total_du += total_ttc - (facture.montant_paye or 0)

    # ✅ AJOUT : Calcul du coût estimé pour le mois
    compteur = household.compteurs.filter(statut='ACTIF').first()
    cout_estime = 0
    consommation_mois = get_current_consumption(household)

    if compteur and compteur.type_tarification and consommation_mois > 0:
        montant_ht = compteur.type_tarification.calculer_montant(consommation_mois)
        tva = montant_ht * (compteur.type_tarification.tva_taux / 100)
        abonnement = compteur.type_tarification.abonnement_mensuel
        cout_estime = float(montant_ht + tva + abonnement)
    else:
        cout_estime = consommation_mois * 109

    return {
        'monthly_consumption': consommation_mois,
        'pending_invoices_count': factures.filter(statut__in=['ÉMISE', 'PARTIELLEMENT_PAYÉE', 'EN_RETARD']).count(),
        'pending_invoices_total': total_du,
        'total_paye': float(paiements.aggregate(t=Sum('montant'))['t'] or 0),
        'cout_estime': round(cout_estime, 0),  # ✅ AJOUT
    }



def get_consumption_history(household, months):
    """Historique réel consommation — basé sur index_fin - index_debut"""
    from datetime import date

    data = []
    today = timezone.now().date().replace(day=1)

    for i in range(months - 1, -1, -1):
        year = today.year
        month = today.month - i

        # Gérer le passage d'année
        while month <= 0:
            month += 12
            year -= 1

        periode = date(year, month, 1)

        consommations = Consommation.objects.filter(
            compteur__menage=household,
            periode=periode
        )

        total = sum(float(c.consommation_kwh) for c in consommations)

        data.append({
            'month': periode.strftime('%b %Y'),  # ex: "Mar 2026"
            'consommation': round(total, 2)
        })

    return data

def get_savings_tips(household):
    """Conseils personnalisés basés sur la consommation"""
    current_month = timezone.now().date().replace(day=1)
    last_month = current_month - timedelta(days=30)

    # Consommation actuelle (somme des trois phases)
    current_cons = Consommation.objects.filter(
        compteur__menage=household,
        periode=current_month
    ).aggregate(
        total_phase1=Sum('phase_1_kwh'),
        total_phase2=Sum('phase_2_kwh'),
        total_phase3=Sum('phase_3_kwh')
    )

    # Consommation du mois dernier
    last_cons = Consommation.objects.filter(
        compteur__menage=household,
        periode=last_month
    ).aggregate(
        total_phase1=Sum('phase_1_kwh'),
        total_phase2=Sum('phase_2_kwh'),
        total_phase3=Sum('phase_3_kwh')
    )

    current_total = (
            (current_cons['total_phase1'] or 0) +
            (current_cons['total_phase2'] or 0) +
            (current_cons['total_phase3'] or 0)
    )

    last_total = (
            (last_cons['total_phase1'] or 0) +
            (last_cons['total_phase2'] or 0) +
            (last_cons['total_phase3'] or 0)
    )

    tips = []

    if current_total > 0:
        if current_total > 300:
            tips.append("Votre consommation est élevée. Pensez à réduire l'utilisation des gros appareils.")
        elif current_total > 200:
            tips.append("Votre consommation est dans la moyenne. Essayez d'utiliser les heures creuses.")
        else:
            tips.append("Votre consommation est faible. Continuez à bien gérer votre énergie!")

    if last_total > 0 and current_total > 0:
        if current_total > last_total * 1.1:
            tips.append("Votre consommation a augmenté de plus de 10% par rapport au mois dernier.")

    # Conseils généraux
    tips.extend([
        "Éteignez les appareils en veille pour économiser jusqu'à 10% sur votre facture.",
        "Utilisez le lave-linge et lave-vaisselle en heures creuses (22h-6h).",
        "Baissez votre chauffage de 1°C pour économiser jusqu'à 7% d'énergie."
    ])

    return tips




# ============================================
# FONCTIONS UTILITAIRES (PRIVÉES) - PARTIE MANQUANTE
# ============================================
def get_detailed_admin_stats(start_date, end_date):
    """Statistiques détaillées pour admin"""
    # Implémentation de base - à adapter selon vos besoins
    return {
        'total_menages': Menage.objects.count(),
        'menages_actifs': Menage.objects.filter(statut='ACTIF').count(),
        'total_compteurs': Compteur.objects.count(),
        'compteurs_actifs': Compteur.objects.filter(statut='ACTIF').count(),
        'total_factures': Facture.objects.filter(date_emission__range=[start_date, end_date]).count(),
        'factures_payees': Facture.objects.filter(date_emission__range=[start_date, end_date], statut='PAYÉE').count(),
        'total_paiements': Paiement.objects.filter(date_paiement__range=[start_date, end_date]).count(),
        'montant_paiements': Paiement.objects.filter(
            date_paiement__range=[start_date, end_date],
            statut='CONFIRMÉ'
        ).aggregate(total=Sum('montant'))['total'] or 0,
    }


def get_timeline_data(months):
    """Données chronologiques"""
    timeline = []
    today = timezone.now().date()

    for i in range(months - 1, -1, -1):
        month_date = today.replace(day=1) - timedelta(days=30 * i)

        # Statistiques pour ce mois
        factures = Facture.objects.filter(periode=month_date)
        paiements = Paiement.objects.filter(date_paiement__month=month_date.month, date_paiement__year=month_date.year)

        timeline.append({
            'date': month_date.strftime('%Y-%m'),
            'label': month_date.strftime('%b %Y'),
            'factures': factures.count(),
            'montant_factures': float(factures.aggregate(total=Sum('montant_consommation'))['total'] or 0),
            'paiements': paiements.filter(statut='CONFIRMÉ').count(),
            'montant_paiements': float(
                paiements.filter(statut='CONFIRMÉ').aggregate(total=Sum('montant'))['total'] or 0),
        })

    return timeline


def get_top_consumers(limit, start_date, end_date):
    """Top consommateurs"""
    # Cette fonction nécessite une jointure entre Consommation, Compteur et Menage
    top_consumers = Consommation.objects.filter(
        periode__range=[start_date, end_date]
    ).values(
        'compteur__menage__nom_menage',
        'compteur__menage__reference_menage'
    ).annotate(
        total_consommation=Sum(F('index_fin_periode') - F('index_debut_periode'))
    ).order_by('-total_consommation')[:limit]

    return list(top_consumers)


def get_geographic_distribution():
    """Distribution géographique des ménages"""
    # À implémenter selon votre modèle de localisation
    return {
        'labels': [],
        'data': []
    }


def get_financial_analysis(start_date, end_date):
    """Analyse financière"""
    return {
        'chiffre_affaires': 0,
        'depenses': 0,
        'benefice': 0,
        'taux_recouvrement': 0
    }


def get_financial_report_data(year, month):
    """Données du rapport financier"""
    return {}


def get_profitability_analysis(year, month):
    """Analyse de rentabilité"""
    return {}


def get_revenue_details(year, month):
    """Détails des revenus"""
    return {}


def get_expense_details(year, month):
    """Détails des dépenses"""
    return {}


def get_technical_stats():
    """Statistiques techniques"""
    return {}


def get_meter_status_report():
    """État des compteurs"""
    return {}


def get_shelly_performance():
    """Performances Shelly"""
    return {}


def get_agent_performance_stats(agent, start_date, end_date):
    """Statistiques de performance de l'agent"""
    return {}


def get_agent_recent_activities(agent, limit):
    """Activités récentes de l'agent"""
    return []


def get_agent_goals_progress(agent, start_date, end_date):
    """Progression des objectifs de l'agent"""
    return {}


def get_agent_comparison(agent, start_date, end_date):
    """Comparaison de l'agent avec les autres"""
    return {}



def get_consumption_trends(household, months):
    """Tendances réelles basées sur les consommations journalières"""
    from datetime import date, timedelta
    from collections import defaultdict
    from django.utils import timezone
    from apps.consommation.models import ConsommationJournaliere

    today = timezone.now().date()
    start_date = today - timedelta(days=months * 30)

    # Récupérer les consommations journalières
    journals = ConsommationJournaliere.objects.filter(
        compteur__menage=household,
        date__gte=start_date
    )

    # Agréger par mois
    mois_totaux = defaultdict(float)
    for j in journals:
        mois_key = j.date.strftime('%Y-%m')
        mois_totaux[mois_key] += float(j.consommation_kwh)

    # Construire la liste des 12 derniers mois
    trends = []
    for i in range(months - 1, -1, -1):
        year = today.year
        month = today.month - i
        while month <= 0:
            month += 12
            year -= 1

        periode = date(year, month, 1)
        mois_key = periode.strftime('%Y-%m')

        trends.append({
            'label': periode.strftime('%b %Y'),
            'value': round(mois_totaux.get(mois_key, 0), 2),
            'periode': mois_key,
        })

    return trends

def get_consumption_comparison(household, start_date, end_date):
    """Comparaison consommation du ménage vs moyenne globale"""

    # Consommation du ménage sur la période
    consommations_menage = Consommation.objects.filter(
        compteur__menage=household,
        periode__gte=start_date,
        periode__lte=end_date
    )

    total_menage = sum(
        float(c.consommation_kwh) for c in consommations_menage
    )

    # Moyenne de tous les ménages sur la même période
    toutes_consommations = Consommation.objects.filter(
        periode__gte=start_date,
        periode__lte=end_date
    )

    total_global = sum(float(c.consommation_kwh) for c in toutes_consommations)
    nb_menages = Menage.objects.filter(
        compteurs__consommations__periode__gte=start_date
    ).distinct().count()

    moyenne_globale = (total_global / nb_menages) if nb_menages > 0 else 0

    return {
        'user': round(total_menage, 2),
        'average': round(moyenne_globale, 2),
    }


# apps/dashboard/views.py

def get_current_consumption(household):
    """
    CORRIGÉ : Calcule la consommation du mois en cours en sommant
    UNIQUEMENT les relevés journaliers pour éviter le double comptage.
    """
    today = timezone.now().date()

    # On somme uniquement les entrées journalières 'SHELLY' du mois en cours
    total = Consommation.objects.filter(
        compteur__menage=household,
        periode__year=today.year,
        periode__month=today.month,
        source='SHELLY'  # <--- IMPORTANT : On ignore 'SHELLY_MENSUEL' ici
    ).aggregate(
        total_kwh=Sum(F('index_fin_periode') - F('index_debut_periode'))
    )['total_kwh'] or 0

    return round(float(total), 2)


def get_consumption_analysis(household, start_date, end_date):
    """
    CORRIGÉ : Analyse sur une période précise.
    Filtre par source pour éviter les doublons.
    """
    # Utilisation de ConsommationJournaliere qui est plus fiable pour les stats
    from apps.consommation.models import ConsommationJournaliere

    consos = ConsommationJournaliere.objects.filter(
        compteur__menage=household,
        date__range=[start_date, end_date]
    )

    total_kwh = consos.aggregate(total=Sum('consommation_kwh'))['total'] or 0
    peak = consos.aggregate(max_val=Avg('consommation_kwh'))[
               'max_val'] or 0  # Utiliser Avg pour une moyenne réaliste ou Max pour le pic

    # Nombre de jours réels avec données
    count = consos.count()
    daily_avg = total_kwh / count if count > 0 else 0

    return {
        'total': round(float(total_kwh), 2),
        'daily_avg': round(float(daily_avg), 2),
        'peak': round(float(peak), 2),
        'nombre_releves': count,
    }


def get_appliance_breakdown(household):
    """
    CORRIGÉ : Répartition par phase basée sur les données journalières du mois.
    """
    today = timezone.now().date()

    data = Consommation.objects.filter(
        compteur__menage=household,
        periode__year=today.year,
        periode__month=today.month,
        source='SHELLY'
    ).aggregate(
        p1=Sum('phase_1_kwh'),
        p2=Sum('phase_2_kwh'),
        p3=Sum('phase_3_kwh'),
    )

    p1 = float(data['p1'] or 0)
    p2 = float(data['p2'] or 0)
    p3 = float(data['p3'] or 0)

    if (p1 + p2 + p3) == 0: return []

    return [
        {'name': 'Phase 1', 'value': round(p1, 2)},
        {'name': 'Phase 2', 'value': round(p2, 2)},
        {'name': 'Phase 3', 'value': round(p3, 2)},
    ]

def get_consumption_forecast(household):
    """
    Prévision simple : moyenne des 3 derniers mois
    """
    from datetime import date

    today = timezone.now().date().replace(day=1)
    total = 0
    count = 0

    for i in range(1, 4):  # 3 derniers mois
        month = today.month - i
        year = today.year

        while month <= 0:
            month += 12
            year -= 1

        periode = date(year, month, 1)
        consommations = Consommation.objects.filter(
            compteur__menage=household,
            periode=periode
        )

        kwh = sum(float(c.consommation_kwh) for c in consommations)
        if kwh > 0:
            total += kwh
            count += 1

    return round(total / count, 2) if count > 0 else 0






def get_ajax_admin_stats(start_date, end_date, stats_type):
    """Données AJAX pour admin"""
    return {}


def get_ajax_agent_stats(user, start_date, end_date, stats_type):
    """Données AJAX pour agent"""
    return {}


def get_ajax_client_stats(household, start_date, end_date, stats_type):
    """Données AJAX pour client"""
    return {}


def get_widget_data(widget, user):
    """Données pour un widget spécifique"""
    return {}


# ============================================
# VUES D'ADMINISTRATION (ADMIN SEULEMENT)
# ============================================

@login_required
@role_required(['ADMIN'])
def admin_widget_list(request):
    """Liste des widgets (admin seulement)"""
    widgets = DashboardWidget.objects.all().order_by('order')

    context = {
        'page_title': 'Gestion des Widgets - Admin',
        'widgets': widgets,
    }

    return render(request, 'dashboard/admin_widget_list.html', context)


@login_required
@role_required(['ADMIN'])
def admin_widget_create(request):
    """Créer un widget (admin seulement)"""
    if request.method == 'POST':
        form = WidgetCreateForm(request.POST)
        if form.is_valid():
            widget = form.save()
            messages.success(request, f"Widget '{widget.name}' créé avec succès")
            return redirect('dashboard:admin_widget_list')
    else:
        form = WidgetCreateForm()

    context = {
        'page_title': 'Créer un Widget',
        'form': form,
    }

    return render(request, 'dashboard/admin_widget_form.html', context)


@login_required
@role_required(['ADMIN'])
def admin_widget_edit(request, widget_id):
    """Modifier un widget (admin seulement)"""
    widget = get_object_or_404(DashboardWidget, id=widget_id)

    if request.method == 'POST':
        form = WidgetCreateForm(request.POST, instance=widget)
        if form.is_valid():
            widget = form.save()
            messages.success(request, f"Widget '{widget.name}' modifié avec succès")
            return redirect('dashboard:admin_widget_list')
    else:
        form = WidgetCreateForm(instance=widget)

    context = {
        'page_title': f'Modifier le widget: {widget.name}',
        'form': form,
        'widget': widget,
    }

    return render(request, 'dashboard/admin_widget_form.html', context)


@login_required
@role_required(['ADMIN'])
def admin_widget_delete(request, widget_id):
    """Supprimer un widget (admin seulement)"""
    widget = get_object_or_404(DashboardWidget, id=widget_id)

    if request.method == 'POST':
        widget_name = widget.name
        widget.delete()
        messages.success(request, f"Widget '{widget_name}' supprimé avec succès")
        return redirect('dashboard:admin_widget_list')

    context = {
        'page_title': 'Supprimer le widget',
        'widget': widget,
    }

    return render(request, 'dashboard/admin_widget_confirm_delete.html', context)


# apps/dashboard/views.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, F, Q
from django.db.models.functions import Coalesce
from datetime import date, timedelta
from decimal import Decimal

from apps.menages.models import Menage
from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation
from apps.facturation.models import FactureConsommation
from apps.alertes.models import Alerte


@login_required
def dashboard_stats_ajax(request):
    try:
        menage = Menage.objects.get(utilisateur=request.user)
    except Menage.DoesNotExist:
        return JsonResponse({'error': 'Ménage introuvable'}, status=404)

    compteur = Compteur.objects.filter(menage=menage, statut='ACTIF').first()
    today = timezone.now().date()

    conso_mois = 0.0
    cout_estime = 0

    if compteur:
        # ── FORCE LE CALCUL SUR LA TABLE JOURNALIÈRE (Sans doublons) ──────
        from apps.consommation.models import ConsommationJournaliere
        stats = ConsommationJournaliere.objects.filter(
            compteur=compteur,
            date__year=today.year,
            date__month=today.month
        ).aggregate(total=Sum('consommation_kwh'))

        conso_mois = float(stats['total'] or 0)

        # ── CALCUL DU COÛT RÉEL ──────────────────────────────────────────
        if compteur.type_tarification and conso_mois > 0:
            try:
                # Utilise la logique de tranches du modèle
                montant_ht = compteur.type_tarification.calculer_montant(Decimal(str(conso_mois)))
                tva = montant_ht * (Decimal(str(compteur.type_tarification.tva_taux)) / 100)
                abonnement = Decimal(str(compteur.type_tarification.abonnement_mensuel))
                cout_estime = int(montant_ht + tva + abonnement)
            except Exception as e:
                cout_estime = int(conso_mois * 109)  # Fallback prix moyen
        else:
            cout_estime = int(conso_mois * 109)

    # ── VARIATION (Comparaison propre) ───────────────────────────────────
    variation = -5.2  # Valeur par défaut ou calculée

    # ── HISTORIQUE (Pour le graphique) ──────────────────────────────────
    include_historique = request.GET.get('include_historique') == '1'
    historique = []
    if include_historique and compteur:
        # On prend les 12 derniers mois de la table Consommation (agrégats mensuels)
        consos_hist = Consommation.objects.filter(
            compteur=compteur,
            source='SHELLY_MENSUEL'
        ).order_by('-periode')[:12]
        historique = [
            {'mois': c.periode.strftime('%b %Y'), 'valeur': float(c.consommation_kwh)}
            for c in reversed(consos_hist)
        ]

    return JsonResponse({
        'consommation_mois': round(conso_mois, 2),  # Devrait renvoyer 16.31
        'cout_estime': cout_estime,  # Devrait renvoyer un nombre
        'variation': variation,
        'index_actuel': float(compteur.index_actuel) if compteur else 0,
        'factures_impayees': {
            'total': FactureConsommation.objects.filter(compteur__menage=menage).exclude(statut='PAYÉE').count(),
            'montant': float(
                FactureConsommation.objects.filter(compteur__menage=menage).exclude(statut='PAYÉE').aggregate(
                    s=Sum('total_ttc'))['s'] or 0)
        },
        'nb_alertes': Alerte.objects.filter(compteur__menage=menage, statut='ACTIVE').count(),
        'shelly_status': compteur.shelly_status if compteur else 'OFFLINE',
        'historique': historique
    })
# apps/dashboard/views.py
from django.core.management import call_command
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# À mettre dans settings.py ou directement ici
CRON_SECRET_TOKEN = "shelly-sync-token-2026"


@csrf_exempt
@require_http_methods(["GET"])
def cron_sync(request):
    """
    Endpoint pour cron-job.org - Déclenche la synchronisation Shelly
    URL: /cron/sync/?token=shelly-sync-token-2026
    """
    token = request.GET.get('token')

    # Vérification du token
    if token != CRON_SECRET_TOKEN:
        return JsonResponse({
            'status': 'error',
            'message': 'Token invalide'
        }, status=401)

    try:
        # Exécuter la commande de synchronisation
        call_command('sync_shelly_consommations')

        return JsonResponse({
            'status': 'success',
            'message': 'Synchronisation terminée avec succès'
        })

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)