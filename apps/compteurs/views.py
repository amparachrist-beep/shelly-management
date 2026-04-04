from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Sum, Avg, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import date, timedelta
import json

from .models import Compteur, Capteur
from .forms import (
    CompteurForm, CapteurForm, CompteurSearchForm,
    CompteurFilterForm, AssocierCapteurForm, UpdateIndexForm,
    DiagnosticForm, ShellyConfigForm
)
from apps.menages.models import Menage
from apps.consommation.models import Consommation
from apps.alertes.models import Alerte


# ============================================
# Verificateurs de roles
# ============================================
def is_admin(user):
    return user.is_authenticated and user.is_admin


def is_agent(user):
    return user.is_authenticated and user.is_agent


def is_client(user):
    return user.is_authenticated and user.is_client


# ============================================
# LISTES ET RECHERCHE
# ============================================
@login_required
def compteur_list(request):
    """Liste des compteurs"""
    if request.user.is_admin or request.user.is_agent:
        compteurs = Compteur.objects.select_related(
            'menage', 'type_tarification', 'localite'
        ).order_by('-created_at')
    else:
        try:
            menage = Menage.objects.get(utilisateur=request.user)
            compteurs = Compteur.objects.filter(
                menage=menage
            ).select_related('type_tarification', 'localite').order_by('-created_at')
        except Menage.DoesNotExist:
            compteurs = Compteur.objects.none()

    form = CompteurFilterForm(request.GET or None, user=request.user)
    if form.is_valid():
        if form.cleaned_data['statut']:
            compteurs = compteurs.filter(statut=form.cleaned_data['statut'])
        if form.cleaned_data['type_compteur']:
            compteurs = compteurs.filter(type_compteur=form.cleaned_data['type_compteur'])
        if form.cleaned_data['localite']:
            compteurs = compteurs.filter(localite=form.cleaned_data['localite'])
        if form.cleaned_data['date_debut']:
            compteurs = compteurs.filter(date_installation__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            compteurs = compteurs.filter(date_installation__lte=form.cleaned_data['date_fin'])
        if form.cleaned_data['shelly_status']:
            compteurs = compteurs.filter(shelly_status=form.cleaned_data['shelly_status'])

    search_form = CompteurSearchForm(request.GET or None)
    if search_form.is_valid():
        query = search_form.cleaned_data['q']
        if query:
            compteurs = compteurs.filter(
                Q(numero_contrat__icontains=query) |
                Q(matricule_compteur__icontains=query) |
                Q(menage__nom_menage__icontains=query) |
                Q(adresse_installation__icontains=query)
            )

    paginator = Paginator(compteurs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    stats_agg = compteurs.aggregate(
        total=Count('id'),
        actifs=Count('id', filter=Q(statut='ACTIF')),
        shelly_connectes=Count('id', filter=Q(shelly_status='CONNECTE')),
        en_panne=Count('id', filter=Q(statut='EN_PANNE')),
    )
    stats = {
        'total': stats_agg['total'],
        'actifs': stats_agg['actifs'],
        'shelly_connectes': stats_agg['shelly_connectes'],
        'en_panne': stats_agg['en_panne'],
    }

    context = {
        'page_title': 'Compteurs',
        'page_obj': page_obj,
        'form': form,
        'search_form': search_form,
        'stats': stats,
        'is_admin': request.user.is_admin,
        'is_agent': request.user.is_agent,
        'is_client': request.user.is_client,
    }

    return render(request, 'gestion/compteurs/list.html', context)


@login_required
def compteur_search(request):
    """Recherche avancee de compteurs"""
    if request.method == 'GET':
        form = CompteurSearchForm(request.GET or None)
        results = Compteur.objects.none()
        query = ''

        if form.is_valid():
            query = form.cleaned_data.get('q', '')
            search_type = form.cleaned_data.get('search_type', 'all')

            if query:
                if search_type == 'matricule' or search_type == 'all':
                    results = Compteur.objects.filter(matricule_compteur__icontains=query)
                elif search_type == 'contrat':
                    results = Compteur.objects.filter(numero_contrat__icontains=query)
                elif search_type == 'client':
                    results = Compteur.objects.filter(numero_client__icontains=query)
                elif search_type == 'menage':
                    results = Compteur.objects.filter(menage__nom_menage__icontains=query)

        context = {
            'page_title': 'Recherche de compteurs',
            'form': form,
            'results': results,
            'query': query,
        }

        return render(request, 'gestion/compteurs/search.html', context)


@login_required
def compteur_detail(request, pk):
    """Detail d'un compteur"""
    compteur = get_object_or_404(
        Compteur.objects.select_related('menage', 'type_tarification', 'localite'),
        pk=pk
    )

    if request.user.is_client and compteur.menage.utilisateur != request.user:
        messages.error(request, "Acces non autorise")
        return redirect('compteur_list')

    capteurs = compteur.capteurs.all()

    consommations = Consommation.objects.filter(
        compteur=compteur
    ).order_by('-periode')[:6]

    # champ correct du modele Alerte : date_detection
    alertes = Alerte.objects.filter(
        compteur=compteur,
        statut='ACTIVE'
    ).order_by('-date_detection')[:5]

    stats = {
        'consommation_mois': get_consommation_mois(compteur),
        'consommation_annee': get_consommation_annee(compteur),
        'moyenne_mensuelle': get_moyenne_mensuelle(compteur),
        'dernier_index': float(compteur.index_actuel),
    }

    context = {
        'page_title': f'Compteur {compteur.numero_contrat}',
        'compteur': compteur,
        'capteurs': capteurs,
        'consommations': consommations,
        'alertes': alertes,
        'stats': stats,
        'can_edit': request.user.is_admin or request.user.is_agent,
        'can_manage': request.user.is_admin or request.user.is_agent,
    }

    return render(request, 'gestion/compteurs/compteur_detail.html', context)


# ============================================
# CREATION ET MODIFICATION
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def compteur_create(request):
    """Creer un compteur"""
    if request.method == 'POST':
        form = CompteurForm(request.POST, user=request.user)
        if form.is_valid():
            compteur = form.save(commit=False)
            compteur.index_initial = compteur.index_initial or 0
            compteur.index_actuel = compteur.index_actuel or compteur.index_initial
            compteur.save()
            messages.success(request, f"Compteur {compteur.numero_contrat} cree avec succes")
            return redirect('compteurs:compteur_detail', pk=compteur.pk)
        else:
            messages.error(request, "Le formulaire contient des erreurs. Veuillez corriger les champs.")
    else:
        form = CompteurForm(user=request.user)

    context = {
        'page_title': 'Creer un compteur',
        'form': form,
        'submit_label': 'Creer',
    }

    return render(request, 'gestion/compteurs/form.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def compteur_update(request, pk):
    """Modifier un compteur"""
    compteur = get_object_or_404(Compteur, pk=pk)

    if request.method == 'POST':
        form = CompteurForm(request.POST, instance=compteur, user=request.user)
        if form.is_valid():
            compteur = form.save()
            messages.success(request, f"Compteur {compteur.numero_contrat} modifie avec succes")
            return redirect('compteurs:compteur_detail', pk=compteur.pk)
    else:
        form = CompteurForm(instance=compteur, user=request.user)

    context = {
        'page_title': f'Modifier le compteur {compteur.numero_contrat}',
        'form': form,
        'submit_label': 'Modifier',
        'compteur': compteur,
    }

    return render(request, 'gestion/compteurs/form.html', context)


# ============================================
# GESTION DU STATUT
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def compteur_activer(request, pk):
    compteur = get_object_or_404(Compteur, pk=pk)
    if compteur.statut == 'ACTIF':
        messages.warning(request, "Ce compteur est deja actif")
    else:
        compteur.statut = 'ACTIF'
        compteur.save()
        messages.success(request, "Compteur active avec succes")
    return redirect('compteurs:compteur_detail', pk=pk)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def compteur_desactiver(request, pk):
    compteur = get_object_or_404(Compteur, pk=pk)
    if compteur.statut == 'INACTIF':
        messages.warning(request, "Ce compteur est deja inactif")
    else:
        compteur.statut = 'INACTIF'
        compteur.save()
        messages.warning(request, "Compteur desactive")
    return redirect('compteurs:compteur_detail', pk=pk)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def compteur_suspendre(request, pk):
    compteur = get_object_or_404(Compteur, pk=pk)
    if compteur.statut == 'SUSPENDU':
        messages.warning(request, "Ce compteur est deja suspendu")
    else:
        compteur.statut = 'SUSPENDU'
        compteur.save()
        messages.warning(request, "Compteur suspendu")
    return redirect('compteurs:compteur_detail', pk=pk)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def compteur_resilier(request, pk):
    compteur = get_object_or_404(Compteur, pk=pk)
    if compteur.statut == 'RESILIE':
        messages.warning(request, "Ce compteur est deja resilie")
    else:
        compteur.statut = 'RESILIE'
        compteur.save()
        messages.warning(request, "Compteur resilie")
    return redirect('compteurs:compteur_detail', pk=pk)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def compteur_marquer_panne(request, pk):
    """Marquer un compteur comme en panne"""
    compteur = get_object_or_404(Compteur, pk=pk)

    if compteur.statut == 'EN_PANNE':
        messages.warning(request, "Ce compteur est deja marque comme en panne")
    else:
        compteur.statut = 'EN_PANNE'
        compteur.save()

        # champs conformes au modele Alerte reel (sans titre ni created_by)
        Alerte.objects.create(
            message=f"Le compteur {compteur.numero_contrat} a ete marque comme en panne",
            compteur=compteur,
            type_alerte='TECHNIQUE',
            niveau='HAUTE',
            statut='ACTIVE',
            utilisateur=request.user,
        )

        messages.error(request, "Compteur marque comme en panne")

    return redirect('compteurs:compteur_detail', pk=pk)


# ============================================
# GESTION DES INDEX
# ============================================
@login_required
def index_view(request, pk):
    """Afficher les index d'un compteur"""
    compteur = get_object_or_404(Compteur, pk=pk)

    if request.user.is_client and compteur.menage.utilisateur != request.user:
        messages.error(request, "Acces non autorise")
        return redirect('compteur_list')

    context = {
        'page_title': f'Index - {compteur.numero_contrat}',
        'compteur': compteur,
        'can_update': request.user.is_admin or request.user.is_agent,
    }

    return render(request, 'gestion/compteurs/index.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def update_index(request, pk):
    """Mettre a jour l'index d'un compteur"""
    compteur = get_object_or_404(Compteur, pk=pk)

    if request.method == 'POST':
        form = UpdateIndexForm(request.POST, instance=compteur)
        if form.is_valid():
            ancien_index = compteur.index_actuel
            compteur = form.save()
            nouveau_index = compteur.index_actuel
            consommation = nouveau_index - ancien_index
            if consommation > 0:
                messages.info(request, f"Consommation enregistree: {consommation} kWh")
            messages.success(request, "Index mis a jour avec succes")
            return redirect('compteurs:compteur_detail', pk=compteur.pk)
    else:
        form = UpdateIndexForm(instance=compteur)

    context = {
        'page_title': f"Mettre a jour l'index - {compteur.numero_contrat}",
        'form': form,
        'submit_label': 'Mettre a jour',
        'compteur': compteur,
    }

    return render(request, 'gestion/compteurs/update_index.html', context)


# ============================================
# GESTION DES CAPTEURS SHELLY
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def associer_capteur(request, pk):
    """Associer un capteur Shelly a un compteur"""
    compteur = get_object_or_404(Compteur, pk=pk)

    if request.method == 'POST':
        form = AssocierCapteurForm(request.POST, user=request.user)
        if form.is_valid():
            device_id = form.cleaned_data['device_id']
            device_name = form.cleaned_data.get('device_name', '')
            compteur_selected = form.cleaned_data.get('compteur', compteur)
            capteur_existant = Capteur.objects.filter(device_id=device_id).first()

            if capteur_existant:
                if capteur_existant.compteur:
                    messages.error(request,
                        f"Ce capteur est deja associe au compteur {capteur_existant.compteur.numero_contrat}")
                else:
                    capteur_existant.compteur = compteur_selected
                    capteur_existant.device_name = device_name
                    capteur_existant.status = 'ACTIF'
                    capteur_existant.derniere_communication = timezone.now()
                    capteur_existant.save()
                    compteur_selected.shelly_device_id = device_id
                    compteur_selected.shelly_status = 'CONNECTE'
                    compteur_selected.derniere_sync_shelly = timezone.now()
                    compteur_selected.save()
                    messages.success(request,
                        f"Capteur existant associe au compteur {compteur_selected.numero_contrat}")
            else:
                Capteur.objects.create(
                    compteur=compteur_selected,
                    device_id=device_id,
                    device_name=device_name,
                    status='ACTIF',
                    derniere_communication=timezone.now()
                )
                compteur_selected.shelly_device_id = device_id
                compteur_selected.shelly_status = 'CONNECTE'
                compteur_selected.derniere_sync_shelly = timezone.now()
                compteur_selected.save()
                messages.success(request,
                    f"Nouveau capteur cree et associe au compteur {compteur_selected.numero_contrat}")

            return redirect('compteurs:compteur_detail', pk=compteur_selected.pk)
    else:
        form = AssocierCapteurForm(initial={'compteur': compteur}, user=request.user)

    context = {
        'page_title': f'Associer un capteur au compteur {compteur.numero_contrat}',
        'form': form,
        'submit_label': 'Associer',
        'compteur': compteur,
    }

    return render(request, 'gestion/compteurs/associer_capteur.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def dissocier_capteur(request, pk, capteur_id):
    """Dissocier un capteur d'un compteur"""
    compteur = get_object_or_404(Compteur, pk=pk)
    capteur = get_object_or_404(Capteur, pk=capteur_id, compteur=compteur)

    if request.method == 'POST':
        capteur.compteur = None
        capteur.status = 'INACTIF'
        capteur.save()
        if compteur.shelly_device_id == capteur.device_id:
            compteur.shelly_device_id = None
            compteur.shelly_status = 'DECONNECTE'
            compteur.save()
        messages.success(request, "Capteur dissocie avec succes")
        return redirect('compteurs:compteur_detail', pk=compteur.pk)

    context = {
        'page_title': 'Dissocier le capteur',
        'compteur': compteur,
        'capteur': capteur,
    }

    return render(request, 'gestion/compteurs/dissocier_capteur.html', context)


@login_required
def capteur_detail(request, pk):
    """Detail d'un capteur"""
    capteur = get_object_or_404(Capteur.objects.select_related('compteur'), pk=pk)

    if request.user.is_client and capteur.compteur.menage.utilisateur != request.user:
        messages.error(request, "Acces non autorise")
        return redirect('compteur_list')

    # Historique reel depuis les consommations (7 derniers jours)
    dernieres_communications = []
    for i in range(7):
        date_jour = (timezone.now() - timedelta(days=i)).date()
        conso_jour = Consommation.objects.filter(
            compteur=capteur.compteur,
            periode=date_jour.replace(day=1),
        ).first()
        puissance = float(
            (conso_jour.phase_1_kwh or 0) +
            (conso_jour.phase_2_kwh or 0) +
            (conso_jour.phase_3_kwh or 0)
        ) if conso_jour else None
        dernieres_communications.append({
            'date': date_jour,
            'status': capteur.status if i == 0 else ('CONNECTE' if conso_jour else 'INCONNU'),
            'puissance': puissance,
        })

    context = {
        'page_title': f'Capteur {capteur.device_name or capteur.device_id}',
        'capteur': capteur,
        'dernieres_communications': dernieres_communications,
        'can_manage': request.user.is_admin or request.user.is_agent,
    }

    return render(request, 'gestion/compteurs/capteur_detail.html', context)


# ============================================
# DIAGNOSTIC ET SUPERVISION
# ============================================
@login_required
def diagnostic_compteur(request, pk):
    """Diagnostic d'un compteur"""
    compteur = get_object_or_404(Compteur, pk=pk)

    if request.user.is_client and compteur.menage.utilisateur != request.user:
        messages.error(request, "Acces non autorise")
        return redirect('compteur_list')

    diagnostic_data = {
        'connectivite': get_diagnostic_connectivite(compteur),
        'donnees': get_diagnostic_donnees(compteur),
        'performance': get_diagnostic_performance(compteur),
        'anomalies': get_diagnostic_anomalies(compteur),
        'etat_general': get_etat_general(compteur),
    }

    context = {
        'page_title': f'Diagnostic - {compteur.numero_contrat}',
        'compteur': compteur,
        'diagnostic_data': diagnostic_data,
        'can_generer_rapport': request.user.is_admin or request.user.is_agent,
    }

    return render(request, 'supervision/diagnostic_compteur.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def generer_rapport_diagnostic(request, pk):
    """Generer un rapport de diagnostic"""
    compteur = get_object_or_404(Compteur, pk=pk)

    rapport = {
        'compteur': {
            'numero_contrat': compteur.numero_contrat,
            'matricule': compteur.matricule_compteur,
            'menage': compteur.menage.nom_menage,
            'statut': compteur.get_statut_display(),
            'type': compteur.type_compteur_detail.nom if compteur.type_compteur_detail else '',
        },
        'connectivite': get_diagnostic_connectivite(compteur),
        'donnees': get_diagnostic_donnees(compteur),
        'performance': get_diagnostic_performance(compteur),
        'anomalies': get_diagnostic_anomalies(compteur),
        'consommations': get_historique_consommation(compteur),
        'alertes': get_alertes_recentes(compteur),
        'recommandations': get_recommandations(compteur),
        'date_generation': timezone.now().strftime('%d/%m/%Y %H:%M'),
        'generer_par': request.user.get_full_name() or request.user.username,
    }

    context = {
        'page_title': f'Rapport de diagnostic - {compteur.numero_contrat}',
        'compteur': compteur,
        'rapport': rapport,
    }

    return render(request, 'supervision/rapport_diagnostic.html', context)


# ============================================
# CONFIGURATION SHELLY
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin, login_url='/login/')
def configurer_shelly(request, pk):
    """Configurer un appareil Shelly"""
    compteur = get_object_or_404(Compteur, pk=pk)

    if not compteur.shelly_device_id:
        messages.error(request, "Aucun capteur Shelly associe a ce compteur")
        return redirect('compteurs:compteur_detail', pk=pk)

    if request.method == 'POST':
        form = ShellyConfigForm(request.POST)
        if form.is_valid():
            config_data = form.cleaned_data
            messages.info(request,
                f"Configuration envoyee au Shelly {compteur.shelly_device_id}. "
                f"IP: {config_data['ip_address']}, Port: {config_data['port']}"
            )
            messages.success(request, "Configuration Shelly appliquee avec succes")
            return redirect('compteurs:compteur_detail', pk=compteur.pk)
    else:
        form = ShellyConfigForm(initial={
            'ip_address': compteur.shelly_ip,
            'device_id': compteur.shelly_device_id,
        })

    context = {
        'page_title': f'Configurer Shelly - {compteur.numero_contrat}',
        'form': form,
        'compteur': compteur,
        'submit_label': 'Appliquer la configuration',
    }

    return render(request, 'supervision/configurer_shelly.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def tester_connexion_shelly(request, pk):
    """Tester la connexion avec un Shelly"""
    import requests as http_requests

    compteur = get_object_or_404(Compteur, pk=pk)

    if not compteur.shelly_device_id:
        messages.error(request, "Aucun capteur Shelly associe a ce compteur")
        return redirect('compteurs:compteur_detail', pk=pk)

    if not compteur.shelly_ip:
        messages.error(request, "Adresse IP Shelly non configuree pour ce compteur")
        return redirect('compteurs:compteur_detail', pk=pk)

    try:
        response = http_requests.get(f"http://{compteur.shelly_ip}/status", timeout=3)
        test_reussi = response.status_code == 200
    except Exception:
        test_reussi = False

    if test_reussi:
        messages.success(request,
            f"Connexion reussie avec le Shelly {compteur.shelly_device_id}. "
            f"Derniere synchro: {compteur.derniere_sync_shelly or 'Jamais'}"
        )
        compteur.shelly_status = 'CONNECTE'
        compteur.derniere_sync_shelly = timezone.now()
        compteur.save()
    else:
        messages.error(request,
            f"Echec de connexion avec le Shelly {compteur.shelly_device_id}. "
            "Verifiez l'alimentation et la connexion reseau."
        )
        compteur.shelly_status = 'DECONNECTE'
        compteur.save()

    return redirect('compteurs:compteur_detail', pk=pk)


# ============================================
# STATISTIQUES
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def stats_compteurs(request):
    """Statistiques des compteurs"""
    stats_par_statut = Compteur.objects.values('statut').annotate(
        count=Count('id'),
        pourcentage=Count('id') * 100.0 / Compteur.objects.count()
    ).order_by('-count')

    stats_par_type = Compteur.objects.values('type_compteur_detail').annotate(
        count=Count('id')
    ).order_by('-count')

    stats_shelly = Compteur.objects.values('shelly_status').annotate(
        count=Count('id')
    ).order_by('-count')

    compteurs_recents = Compteur.objects.order_by('-created_at')[:10]
    evolution = get_evolution_compteurs()

    context = {
        'page_title': 'Statistiques des compteurs',
        'stats_par_statut': stats_par_statut,
        'stats_par_type': stats_par_type,
        'stats_shelly': stats_shelly,
        'compteurs_recents': compteurs_recents,
        'evolution': evolution,
        'total_compteurs': Compteur.objects.count(),
    }

    return render(request, 'supervision/stats_compteurs.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def carte_compteurs(request):
    """Carte geographique des compteurs"""
    compteurs = Compteur.objects.filter(
        gps_latitude__isnull=False,
        gps_longitude__isnull=False
    ).select_related('menage', 'localite')

    points_carte = []
    for compteur in compteurs:
        points_carte.append({
            'id': compteur.id,
            'numero': compteur.numero_contrat,
            'latitude': float(compteur.gps_latitude),
            'longitude': float(compteur.gps_longitude),
            'menage': compteur.menage.nom_menage,
            'statut': compteur.statut,
            'popup': (
                f"<strong>{compteur.numero_contrat}</strong><br/>"
                f"{compteur.menage.nom_menage}<br/>"
                f"Statut: {compteur.get_statut_display()}<br/>"
                f'<a href="/compteurs/{compteur.id}/">Voir details</a>'
            ),
        })

    context = {
        'page_title': 'Carte des compteurs',
        'points_carte': json.dumps(points_carte),
        'total_compteurs': compteurs.count(),
        'compteurs_avec_gps': compteurs.count(),
        'compteurs_sans_gps': Compteur.objects.filter(gps_latitude__isnull=True).count(),
    }

    return render(request, 'supervision/carte_compteurs.html', context)


# ============================================
# VUES CLIENT
# ============================================
@login_required
def client_mes_compteurs(request):
    try:
        household = Menage.objects.get(utilisateur=request.user)
    except Menage.DoesNotExist:
        messages.error(request, "Aucun ménage associé à votre compte.")
        return redirect('dashboard:client_dashboard')

    compteurs = Compteur.objects.filter(menage=household).select_related(
        'type_tarification', 'localite'
    ).order_by('-date_installation')

    compteur_principal = compteurs.first() if compteurs.exists() else None
    autres_compteurs = list(compteurs[1:]) if compteurs.count() > 1 else []

    # ✅ Données temps réel depuis le capteur Shelly
    consommation_actuelle = None
    if compteur_principal and compteur_principal.shelly_status == 'CONNECTE':
        capteur = compteur_principal.capteurs.first()
        if capteur:
            puissance = float(capteur.puissance_instantanee or 0)
            puissance_max = float(compteur_principal.puissance_souscrite) * 1000
            charge = round((puissance / puissance_max * 100), 1) if puissance_max > 0 else 0

            consommation_actuelle = {
                'phase_1': round(puissance / 3, 1),  # approximation si mono
                'phase_2': 0,
                'phase_3': 0,
                'charge': min(charge, 100),
            }

    interventions = []

    stats = {
        'total': compteurs.count(),
        'actifs': compteurs.filter(statut='ACTIF').count(),
        'shelly_connectes': compteurs.filter(shelly_status='CONNECTE').count(),
    }

    context = {
        'page_title': 'Mes Compteurs',
        'household': household,
        'compteur_principal': compteur_principal,
        'autres_compteurs': autres_compteurs,
        'consommation_actuelle': consommation_actuelle,
        'interventions': interventions,
        'stats': stats,
    }

    return render(request, 'client/compteurs.html', context)


@login_required
def client_compteur_detail(request, pk):
    """Detail d'un compteur specifique pour le client"""
    try:
        household = Menage.objects.get(utilisateur=request.user)
        compteur = get_object_or_404(Compteur, id=pk, menage=household)
    except Menage.DoesNotExist:
        messages.error(request, "Aucun menage associe a votre compte.")
        return redirect('dashboard:client_dashboard')

    # Récupérer les consommations des 12 derniers mois
    consommations = Consommation.objects.filter(
        compteur=compteur
    ).order_by('-periode')[:12]

    # Récupérer les alertes actives
    alertes = Alerte.objects.filter(
        compteur=compteur,
        statut='ACTIVE'
    ).order_by('-date_detection')[:10]

    # Mois en cours
    current_month = timezone.now().date().replace(day=1)

    # Consommation du mois en cours
    consommation_mois = Consommation.objects.filter(
        compteur=compteur,
        periode=current_month
    ).first()

    # Calcul du total de consommation depuis l'installation
    total_consommation = Consommation.objects.filter(compteur=compteur).aggregate(
        total_phase1=Sum('phase_1_kwh'),
        total_phase2=Sum('phase_2_kwh'),
        total_phase3=Sum('phase_3_kwh')
    )
    total_consommation_kwh = (
            (total_consommation['total_phase1'] or 0) +
            (total_consommation['total_phase2'] or 0) +
            (total_consommation['total_phase3'] or 0)
    )

    # Calcul du pourcentage de consommation par rapport à la puissance souscrite
    pourcentage = 0
    max_consommation = 0

    if consommation_mois and compteur.puissance_souscrite and compteur.puissance_souscrite > 0:
        # Calcul du total du mois
        total_mois = (
                (consommation_mois.phase_1_kwh or 0) +
                (consommation_mois.phase_2_kwh or 0) +
                (consommation_mois.phase_3_kwh or 0)
        )
        # Puissance maximale possible pour le mois (720 heures = 30 jours * 24h)
        max_possible = float(compteur.puissance_souscrite) * 720
        pourcentage = (total_mois / max_possible) * 100 if max_possible > 0 else 0

    # Calcul de la consommation maximale parmi l'historique
    if consommations:
        for conso in consommations:
            total_conso = (
                    (conso.phase_1_kwh or 0) +
                    (conso.phase_2_kwh or 0) +
                    (conso.phase_3_kwh or 0)
            )
            if total_conso > max_consommation:
                max_consommation = total_conso

    # Récupérer les données du capteur
    capteur = compteur.capteurs.first()
    donnees_instantanee = None
    if compteur.shelly_status == 'CONNECTE' and capteur:
        donnees_instantanee = {
            'puissance': capteur.puissance_instantanee,
            'energie_totale': capteur.energie_totale,
            'status': capteur.status,
            'derniere_maj': capteur.derniere_communication,
        }

    # Calcul de la moyenne mensuelle
    moyenne_mensuelle = 0
    if consommations:
        moyenne_mensuelle = total_consommation_kwh / consommations.count()

    context = {
        'page_title': f'Compteur {compteur.matricule_compteur}',  # ✅ Changé de numero_serie à matricule_compteur
        'household': household,
        'compteur': compteur,
        'consommations': consommations,
        'alertes': alertes,
        'consommation_mois': consommation_mois,
        'total_consommation_kwh': total_consommation_kwh,
        'capteur': capteur,
        'donnees_instantanee': donnees_instantanee,
        'current_month': current_month,
        'pourcentage': pourcentage,
        'max_consommation': max_consommation,
        'moyenne_mensuelle': moyenne_mensuelle,
    }

    return render(request, 'client/compteur_detail.html', context)
# ============================================
# FONCTIONS UTILITAIRES
# ============================================
def _total_phases(conso_obj):
    """Somme des 3 phases d'un objet Consommation"""
    return (
        float(conso_obj.phase_1_kwh or 0) +
        float(conso_obj.phase_2_kwh or 0) +
        float(conso_obj.phase_3_kwh or 0)
    )


# apps/compteurs/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Compteur, Capteur
from apps.menages.models import Menage
# apps/compteurs/views.py
from apps.dashboard.views import role_required


# ... vos autres vues ...

@login_required
@role_required(['CLIENT'])
def client_mes_capteurs(request):
    """
    Liste des capteurs pour le client (ménage)
    Affiche tous les capteurs associés aux compteurs du ménage
    """
    try:
        # Récupérer le ménage du client
        household = Menage.objects.get(utilisateur=request.user)
    except Menage.DoesNotExist:
        messages.error(request, "Aucun ménage associé à votre compte.")
        return redirect('dashboard:client_dashboard')

    # Récupérer les compteurs du ménage
    compteurs = Compteur.objects.filter(menage=household)

    # Récupérer les capteurs associés à ces compteurs
    capteurs = Capteur.objects.filter(compteur__in=compteurs).select_related('compteur').order_by('-date_installation')

    # Statistiques pour l'affichage
    total_capteurs = capteurs.count()
    capteurs_actifs = capteurs.filter(status='ACTIF').count()
    capteurs_connectes = capteurs.filter(derniere_communication__isnull=False).count()

    # Calculer le taux de connectivité
    taux_connectivite = round((capteurs_connectes / total_capteurs * 100) if total_capteurs > 0 else 0)

    # Dernière mise à jour globale
    derniere_mise_a_jour = capteurs.order_by('-derniere_communication').first()
    derniere_mise_a_jour_date = derniere_mise_a_jour.derniere_communication if derniere_mise_a_jour else None

    # Pagination
    paginator = Paginator(capteurs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Données pour le graphique de performance (7 derniers jours)
    performance_data = {
        'labels': ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'],
        'connectivity': [98, 97, 99, 96, 95, 97, 96],
        'reliability': [99, 98, 97, 98, 99, 96, 97]
    }

    context = {
        'page_title': 'Mes Capteurs',
        'capteurs': page_obj,
        'total_capteurs': total_capteurs,
        'capteurs_actifs': capteurs_actifs,
        'capteurs_connectes': capteurs_connectes,
        'taux_connectivite': taux_connectivite,
        'derniere_mise_a_jour': derniere_mise_a_jour_date,
        'performance_json': json.dumps(performance_data),
        'household': household,
    }

    return render(request, 'client/capteurs.html', context)

def get_consommation_mois(compteur):
    """Calculer la consommation du mois courant"""
    mois_actuel = date.today().replace(day=1)
    try:
        conso = Consommation.objects.get(compteur=compteur, periode=mois_actuel)
        return _total_phases(conso)
    except Consommation.DoesNotExist:
        return 0.0


def get_consommation_annee(compteur):
    """Calculer la consommation de l'annee en cours"""
    debut_annee = date(date.today().year, 1, 1)
    result = Consommation.objects.filter(
        compteur=compteur,
        periode__gte=debut_annee
    ).aggregate(
        t1=Sum('phase_1_kwh'),
        t2=Sum('phase_2_kwh'),
        t3=Sum('phase_3_kwh'),
    )
    return float((result['t1'] or 0) + (result['t2'] or 0) + (result['t3'] or 0))


def get_moyenne_mensuelle(compteur):
    """Calculer la moyenne mensuelle de consommation"""
    consommations = Consommation.objects.filter(compteur=compteur)
    count = consommations.count()
    if count > 0:
        result = consommations.aggregate(
            t1=Sum('phase_1_kwh'),
            t2=Sum('phase_2_kwh'),
            t3=Sum('phase_3_kwh'),
        )
        total = float((result['t1'] or 0) + (result['t2'] or 0) + (result['t3'] or 0))
        return total / count
    return 0.0


def get_diagnostic_connectivite(compteur):
    """Diagnostic de connectivite"""
    return {
        'shelly_connecte': compteur.shelly_status == 'CONNECTE',
        'derniere_sync': compteur.derniere_sync_shelly,
        'statut': compteur.shelly_status,
        'recommandation': 'Verifier la connexion reseau' if compteur.shelly_status != 'CONNECTE' else 'OK',
    }


def get_diagnostic_donnees(compteur):
    """Diagnostic des donnees"""
    derniere_conso = Consommation.objects.filter(compteur=compteur).order_by('-periode').first()
    return {
        'derniere_conso': derniere_conso.periode if derniere_conso else None,
        'index_actuel': float(compteur.index_actuel),
        'regularite': 'Regulier' if Consommation.objects.filter(compteur=compteur).count() > 3 else 'Irregulier',
        'recommandation': 'Releves reguliers OK' if derniere_conso else 'Aucun releve recent',
    }


def get_diagnostic_performance(compteur):
    """Diagnostic de performance"""
    return {
        'puissance_souscrite': float(compteur.puissance_souscrite),
        'tension': compteur.get_tension_display(),
        'phase': compteur.get_phase_display(),
        'adequation': 'Adequate',
        'recommandation': f'Puissance souscrite: {compteur.puissance_souscrite} kVA',
    }


def get_diagnostic_anomalies(compteur):
    """Detection d'anomalies via les alertes actives"""
    alertes = Alerte.objects.filter(compteur=compteur, statut='ACTIVE')
    return {
        'nombre_alertes': alertes.count(),
        'alertes_critiques': alertes.filter(niveau='CRITIQUE').count(),
        'derniere_alerte': alertes.order_by('-date_detection').first(),
        'recommandation': (
            'Resoudre les alertes critiques'
            if alertes.filter(niveau='CRITIQUE').exists()
            else 'Aucune anomalie critique'
        ),
    }


def get_etat_general(compteur):
    """Etat general du compteur"""
    anomalies = get_diagnostic_anomalies(compteur)
    connectivite = get_diagnostic_connectivite(compteur)

    if anomalies['alertes_critiques'] > 0:
        return 'CRITIQUE'
    elif not connectivite['shelly_connecte']:
        return 'ATTENTION'
    elif compteur.statut != 'ACTIF':
        return 'INACTIF'
    else:
        return 'BON'


def get_historique_consommation(compteur):
    """Historique des consommations (12 derniers mois)"""
    consommations = Consommation.objects.filter(
        compteur=compteur
    ).order_by('periode')[:12]

    return [{
        'periode': c.periode.strftime('%m/%Y'),
        'consommation': _total_phases(c),
        'statut': c.statut,
    } for c in consommations]


def get_alertes_recentes(compteur):
    """Alertes recentes du compteur"""
    alertes = Alerte.objects.filter(
        compteur=compteur
    ).order_by('-date_detection')[:5]

    return [{
        'message': a.message,
        'niveau': a.niveau,
        'date': a.date_detection.strftime('%d/%m/%Y'),
        'statut': a.statut,
    } for a in alertes]


def get_recommandations(compteur):
    """Recommandations basees sur le diagnostic"""
    recommandations = []

    if compteur.shelly_status != 'CONNECTE':
        recommandations.append("Verifier la connexion du capteur Shelly")

    if compteur.statut != 'ACTIF':
        recommandations.append(f"Compteur {compteur.get_statut_display()} - action requise")

    derniere_conso = Consommation.objects.filter(compteur=compteur).order_by('-periode').first()
    if not derniere_conso:
        recommandations.append("Aucun releve de consommation - verifier le compteur")

    if not recommandations:
        recommandations.append("Aucune action requise - compteur en bon etat")

    return recommandations


def get_evolution_compteurs():
    """Evolution des compteurs sur 12 mois"""
    import calendar
    evolution = []
    today = date.today()

    for i in range(12):
        mois_date = date(today.year, today.month, 1)
        for _ in range(i):
            if mois_date.month == 1:
                mois_date = date(mois_date.year - 1, 12, 1)
            else:
                mois_date = date(mois_date.year, mois_date.month - 1, 1)

        _, dernier_jour = calendar.monthrange(mois_date.year, mois_date.month)
        fin_mois = date(mois_date.year, mois_date.month, dernier_jour)

        count = Compteur.objects.filter(
            created_at__gte=mois_date,
            created_at__lte=fin_mois
        ).count()

        evolution.append({
            'mois': mois_date.strftime('%b %Y'),
            'count': count,
        })

    return evolution


# ============================================
# VUES AJAX POUR DASHBOARD
# ============================================
@login_required
def compteur_stats_ajax(request):
    """Statistiques pour dashboard"""
    if request.user.is_admin or request.user.is_agent:
        stats = {
            'total': Compteur.objects.count(),
            'actifs': Compteur.objects.filter(statut='ACTIF').count(),
            'shelly_connectes': Compteur.objects.filter(shelly_status='CONNECTE').count(),
            'en_panne': Compteur.objects.filter(statut='EN_PANNE').count(),
        }
    else:
        stats = {'total': 0, 'actifs': 0, 'shelly_connectes': 0, 'en_panne': 0}

    return JsonResponse(stats)


@login_required
def compteur_recent_ajax(request):
    """Compteurs recents pour dashboard"""
    limit = int(request.GET.get('limit', 5))

    if request.user.is_admin or request.user.is_agent:
        compteurs = Compteur.objects.select_related('menage').order_by('-created_at')[:limit]
    else:
        try:
            menage = Menage.objects.get(utilisateur=request.user)
            compteurs = Compteur.objects.filter(menage=menage).order_by('-created_at')[:limit]
        except Menage.DoesNotExist:
            compteurs = []

    data = [{
        'id': c.id,
        'numero_contrat': c.numero_contrat,
        'menage': c.menage.nom_menage,
        'statut': c.statut,
        'shelly_status': c.shelly_status,
        'date_installation': c.date_installation.strftime('%d/%m/%Y'),
    } for c in compteurs]

    return JsonResponse({'compteurs': data})


# ============================================
# CREATION DE CAPTEUR
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def capteur_create(request):
    """Creer un capteur independamment ou pour un compteur specifique"""
    compteur_id = request.GET.get('compteur_id') or request.POST.get('compteur')
    compteur = None

    if compteur_id:
        compteur = get_object_or_404(Compteur, pk=compteur_id)

    if request.method == 'POST':
        form = CapteurForm(request.POST)
        if form.is_valid():
            capteur_obj = form.save(commit=False)

            if compteur:
                capteur_obj.compteur = compteur
            elif not capteur_obj.compteur_id:
                messages.error(request, "Veuillez selectionner un compteur pour ce capteur.")
                return render(request, 'capteurs/form.html', {
                    'page_title': 'Creer un capteur',
                    'form': form,
                    'submit_label': 'Creer le capteur',
                    'compteur': compteur,
                })

            capteur_obj.derniere_communication = timezone.now()
            capteur_obj.derniere_mise_a_jour = timezone.now()
            capteur_obj.save()

            if capteur_obj.compteur and capteur_obj.status == 'ACTIF':
                compteur_assoc = capteur_obj.compteur
                compteur_assoc.shelly_device_id = capteur_obj.device_id
                compteur_assoc.shelly_status = 'CONNECTE'
                compteur_assoc.shelly_ip = capteur_obj.ip_address
                compteur_assoc.derniere_sync_shelly = timezone.now()
                compteur_assoc.save()
                messages.success(request,
                    f"Capteur {capteur_obj.device_id} cree et associe au compteur {compteur_assoc.numero_contrat}")
                return redirect('compteurs:compteur_detail', pk=compteur_assoc.pk)
            else:
                messages.success(request, f"Capteur {capteur_obj.device_id} cree avec succes")
                return redirect('compteurs:capteur_list')
    else:
        initial_data = {'compteur': compteur} if compteur else {}
        form = CapteurForm(initial=initial_data)

    context = {
        'page_title': 'Creer un capteur',
        'form': form,
        'submit_label': 'Creer le capteur',
        'compteur': compteur,
    }

    return render(request, 'capteurs/form.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def capteur_list(request):
    """Liste de tous les capteurs"""
    capteurs = Capteur.objects.select_related('compteur').order_by('-date_installation')

    status_filter = request.GET.get('status', '')
    if status_filter:
        capteurs = capteurs.filter(status=status_filter)

    search_query = request.GET.get('q', '')
    if search_query:
        capteurs = capteurs.filter(
            Q(device_id__icontains=search_query) |
            Q(device_name__icontains=search_query) |
            Q(compteur__numero_contrat__icontains=search_query) |
            Q(mac_address__icontains=search_query)
        )

    paginator = Paginator(capteurs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    stats = {
        'total': capteurs.count(),
        'actifs': capteurs.filter(status='ACTIF').count(),
        'avec_compteur': capteurs.filter(compteur__isnull=False).count(),
        'sans_compteur': capteurs.filter(compteur__isnull=True).count(),
    }

    context = {
        'page_title': 'Capteurs',
        'page_obj': page_obj,
        'stats': stats,
        'search_query': search_query,
        'status_filter': status_filter,
    }

    return render(request, 'capteurs/list.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def capteur_update(request, pk):
    """Modifier un capteur existant"""
    capteur = get_object_or_404(Capteur.objects.select_related('compteur'), pk=pk)

    if request.method == 'POST':
        form = CapteurForm(request.POST, instance=capteur)
        if form.is_valid():
            ancien_compteur = capteur.compteur
            capteur = form.save(commit=False)
            capteur.derniere_mise_a_jour = timezone.now()
            capteur.save()

            if capteur.compteur:
                compteur_assoc = capteur.compteur
                compteur_assoc.shelly_device_id = capteur.device_id
                compteur_assoc.shelly_status = 'CONNECTE' if capteur.status == 'ACTIF' else 'DECONNECTE'
                compteur_assoc.shelly_ip = capteur.ip_address
                compteur_assoc.save()

            if ancien_compteur and ancien_compteur != capteur.compteur:
                ancien_compteur.shelly_device_id = None
                ancien_compteur.shelly_status = 'DECONNECTE'
                ancien_compteur.save()

            messages.success(request, f"Capteur {capteur.device_id} modifie avec succes")

            if capteur.compteur:
                return redirect('compteurs:compteur_detail', pk=capteur.compteur.pk)
            else:
                return redirect('compteurs:capteur_list')
    else:
        form = CapteurForm(instance=capteur)

    context = {
        'page_title': f'Modifier le capteur {capteur.device_id}',
        'form': form,
        'submit_label': 'Modifier',
        'capteur': capteur,
    }

    return render(request, 'capteurs/form.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def capteur_delete(request, pk):
    """Supprimer un capteur"""
    capteur = get_object_or_404(Capteur.objects.select_related('compteur'), pk=pk)
    compteur_asso = capteur.compteur

    if request.method == 'POST':
        if compteur_asso and compteur_asso.shelly_device_id == capteur.device_id:
            compteur_asso.shelly_device_id = None
            compteur_asso.shelly_status = 'DECONNECTE'
            compteur_asso.save()
        capteur.delete()
        messages.success(request, "Capteur supprime avec succes")
        if compteur_asso:
            return redirect('compteurs:compteur_detail', pk=compteur_asso.pk)
        else:
            return redirect('compteurs:capteur_list')

    context = {
        'page_title': 'Supprimer le capteur',
        'capteur': capteur,
        'compteur': compteur_asso,
    }

    return render(request, 'capteurs/delete.html', context)


# ============================================
# SURVEILLANCE EN DIRECT
# ============================================
from apps.dashboard.views import role_required


@login_required
@role_required(['CLIENT'])
def live_surveillance(request, pk):
    """Surveillance en direct d'un compteur"""
    try:
        household = Menage.objects.get(utilisateur=request.user)
        compteur = get_object_or_404(Compteur, id=pk, menage=household)
    except Menage.DoesNotExist:
        return JsonResponse({'error': 'Menage non trouve'}, status=404)

    if compteur.shelly_status != 'CONNECTE':
        messages.warning(request, "Ce compteur n'est pas connecte. La surveillance en direct n'est pas disponible.")
        return redirect('compteurs:client_compteur_detail', pk=pk)

    capteur = compteur.capteurs.first()

    donnees_live = None
    if capteur:
        donnees_live = {
            'puissance': capteur.puissance_instantanee,
            'energie_totale': capteur.energie_totale,
            'status': capteur.status,
            'derniere_maj': capteur.derniere_communication,
        }

    from django.urls import reverse
    ajax_url = reverse('compteurs:shelly_live_data', kwargs={'compteur_id': compteur.id})

    context = {
        'page_title': f'Surveillance en direct - {compteur.numero_contrat}',
        'household': household,
        'compteur': compteur,
        'capteur': capteur,
        'donnees_live': donnees_live,
        'ajax_live_url': ajax_url,
    }

    return render(request, 'client/compteur_live.html', context)


# ============================================
# TYPES DE COMPTEUR (CBV)
# ============================================
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from .models import TypeCompteur
from .forms import TypeCompteurForm


class TypeCompteurListView(ListView):
    model = TypeCompteur
    context_object_name = 'types_compteur'
    template_name = 'compteurs/typecompteur_list.html'
    paginate_by = 20
    ordering = ['ordre_affichage', 'nom']


class TypeCompteurCreateView(SuccessMessageMixin, CreateView):
    model = TypeCompteur
    form_class = TypeCompteurForm
    template_name = 'compteurs/typecompteur_form.html'
    success_url = reverse_lazy('compteurs:typecompteur_list')
    success_message = "Le type de compteur %(nom)s a ete cree avec succes."


class TypeCompteurUpdateView(SuccessMessageMixin, UpdateView):
    model = TypeCompteur
    form_class = TypeCompteurForm
    template_name = 'compteurs/typecompteur_form.html'
    success_url = reverse_lazy('compteurs:typecompteur_list')
    success_message = "Le type de compteur %(nom)s a ete modifie avec succes."


class TypeCompteurDeleteView(DeleteView):
    model = TypeCompteur
    context_object_name = 'type_compteur'
    template_name = 'compteurs/typecompteur_confirm_delete.html'
    success_url = reverse_lazy('compteurs:typecompteur_list')
    success_message = "Le type de compteur a ete supprime."

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)


# ============================================
# SYNCHRONISATION SHELLY
# ============================================
from .services.shelly_service import sync_compteur_shelly
from apps.consommation.services import create_consommation_from_shelly


from django.utils import timezone

@login_required
def sync_shelly_compteur_view(request, compteur_id):
    compteur = get_object_or_404(Compteur, pk=compteur_id)

    capteur = sync_compteur_shelly(compteur)

    if not capteur:
        messages.error(request, "❌ Erreur de synchronisation Shelly")
        return redirect("compteurs:compteur_list")

    # ✅ AJOUT IMPORTANT
    compteur.shelly_last_seen = timezone.now()
    compteur.save()

    create_consommation_from_shelly(compteur)

    messages.success(request, "✅ Synchronisation réussie")
    return redirect("compteurs:compteur_list")

from django.views.decorators.csrf import csrf_exempt
import json as _json


@csrf_exempt
def shelly_energy_webhook(request, compteur_id):
    """Webhook Shelly -- recoit les donnees energie en temps reel."""
    if request.method != 'POST':
        return HttpResponse('Method Not Allowed', status=405)

    from django.conf import settings
    try:
        data = _json.loads(request.body)
    except (ValueError, KeyError):
        return HttpResponse('Bad Request', status=400)

    if data.get('api_key') != getattr(settings, 'SHELLY_SECRET_KEY', None):
        return HttpResponse('Unauthorized', status=403)

    compteur = get_object_or_404(Compteur, pk=compteur_id)
    capteur = compteur.capteurs.first()
    if not capteur:
        return JsonResponse({'error': 'Aucun capteur'}, status=404)

    params = data.get('params', data)
    capteur.puissance_instantanee = params.get('total_act_power', capteur.puissance_instantanee)
    energie_data = params.get('total_act_energy', {})
    if isinstance(energie_data, dict):
        capteur.energie_totale = energie_data.get('total', capteur.energie_totale)
    capteur.derniere_communication = timezone.now()
    capteur.save(update_fields=['puissance_instantanee', 'energie_totale', 'derniere_communication'])

    create_consommation_from_shelly(compteur)

    return JsonResponse({'status': 'ok'})


# apps/compteurs/views.py
# apps/compteurs/views.py
# apps/compteurs/views.py
import requests
import traceback
from decimal import Decimal
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt

from .models import Compteur


@login_required
@csrf_exempt
def shelly_live_data_view(request, compteur_id):
    """
    Endpoint AJAX - Récupère les données live du Shelly Pro 3EM
    Version avec logs détaillés
    """
    print("=" * 60)
    print(f"[LIVE] Début - Compteur ID: {compteur_id}")
    print(f"[LIVE] Utilisateur: {request.user}")

    try:
        # 1. Récupération du compteur
        compteur = get_object_or_404(Compteur, id=compteur_id)
        print(f"[LIVE] Compteur trouvé: ID={compteur.id}")
        print(f"[LIVE] IP Shelly: {compteur.shelly_ip}")
        print(f"[LIVE] Statut actuel: {compteur.shelly_status}")

        # 2. Vérification IP
        if not compteur.shelly_ip:
            print("[LIVE] ERREUR: IP non configurée")
            return JsonResponse({"error": "IP Shelly non configurée"}, status=400)

        # 3. Construction URL
        url = f"http://{compteur.shelly_ip}/rpc"
        print(f"[LIVE] URL: {url}")

        # 4. Requête puissance
        print("[LIVE] Envoi requête EM.GetStatus...")
        try:
            power_resp = requests.post(
                url,
                json={"id": 1, "method": "EM.GetStatus", "params": {"id": 0}},
                timeout=5
            )
            print(f"[LIVE] Status code: {power_resp.status_code}")

            if power_resp.status_code != 200:
                print(f"[LIVE] ERREUR: Shelly retourne {power_resp.status_code}")
                compteur.shelly_status = 'DECONNECTE'
                compteur.save(update_fields=['shelly_status'])
                return JsonResponse({"error": f"Shelly error: {power_resp.status_code}"}, status=503)

            power_data = power_resp.json()
            print(f"[LIVE] Réponse reçue, clés: {list(power_data.keys())}")

            # Extraction du result
            result = power_data.get('result', {})
            print(f"[LIVE] Result keys: {list(result.keys())}")

        except requests.exceptions.Timeout:
            print("[LIVE] TIMEOUT: Shelly ne répond pas")
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])
            return JsonResponse({"error": "Timeout"}, status=503)

        except requests.exceptions.ConnectionError as e:
            print(f"[LIVE] CONNECTION ERROR: {e}")
            compteur.shelly_status = 'DECONNECTE'
            compteur.save(update_fields=['shelly_status'])
            return JsonResponse({"error": "Connection error"}, status=503)

        except Exception as e:
            print(f"[LIVE] Erreur inattendue: {e}")
            traceback.print_exc()
            return JsonResponse({"error": str(e)}, status=500)

        # 5. Extraction des données puissance
        try:
            phase1 = float(result.get('a_act_power', 0))
            phase2 = float(result.get('b_act_power', 0))
            phase3 = float(result.get('c_act_power', 0))
            total_power = float(result.get('total_act_power', 0))
            print(f"[LIVE] Puissance - P1={phase1}, P2={phase2}, P3={phase3}, Total={total_power}")
        except Exception as e:
            print(f"[LIVE] Erreur extraction puissance: {e}")
            traceback.print_exc()
            phase1 = phase2 = phase3 = total_power = 0

        # 6. Requête énergie
        print("[LIVE] Envoi requête EMData.GetStatus...")
        total_energy_kwh = float(compteur.index_actuel or 0)

        try:
            energy_resp = requests.post(
                url,
                json={"id": 2, "method": "EMData.GetStatus", "params": {"id": 0}},
                timeout=5
            )
            print(f"[LIVE] Energy status: {energy_resp.status_code}")

            if energy_resp.status_code == 200:
                energy_data = energy_resp.json()
                energy_result = energy_data.get('result', {})
                total_energy_wh = float(energy_result.get('total_act', 0))
                total_energy_kwh = total_energy_wh / 1000
                print(f"[LIVE] Énergie: {total_energy_wh} Wh = {total_energy_kwh} kWh")
            else:
                print(f"[LIVE] Énergie non disponible, garde index existant: {total_energy_kwh}")

        except Exception as e:
            print(f"[LIVE] Erreur récupération énergie: {e}")
            traceback.print_exc()

        # 7. Mise à jour base de données
        print("[LIVE] Mise à jour base de données...")
        try:
            compteur.index_actuel = Decimal(str(total_energy_kwh))
            compteur.shelly_status = 'CONNECTE'
            compteur.derniere_sync_shelly = timezone.now()
            compteur.save(update_fields=['index_actuel', 'shelly_status', 'derniere_sync_shelly'])
            print("[LIVE] Compteur mis à jour")
        except Exception as e:
            print(f"[LIVE] Erreur mise à jour compteur: {e}")
            traceback.print_exc()

        # 8. Mise à jour capteur
        try:
            capteur = compteur.capteurs.first()
            if capteur:
                capteur.puissance_instantanee = Decimal(str(total_power))
                capteur.energie_totale = Decimal(str(total_energy_kwh))
                capteur.derniere_communication = timezone.now()
                capteur.status = 'ACTIF'
                capteur.save(
                    update_fields=['puissance_instantanee', 'energie_totale', 'derniere_communication', 'status'])
                print(f"[LIVE] Capteur mis à jour: {capteur.id}")
        except Exception as e:
            print(f"[LIVE] Erreur mise à jour capteur: {e}")
            traceback.print_exc()

        # 9. Réponse
        response_data = {
            "phase1": round(phase1, 1),
            "phase2": round(phase2, 1),
            "phase3": round(phase3, 1),
            "avg_power": round(total_power, 1),
            "energie_totale_kwh": round(total_energy_kwh, 3),
            "timestamp": timezone.now().isoformat(),
        }

        print(f"[LIVE] SUCCÈS! Réponse: {response_data}")
        print("=" * 60)
        return JsonResponse(response_data)

    except Exception as e:
        print(f"[LIVE] ERREUR GLOBALE: {e}")
        traceback.print_exc()
        print("=" * 60)
        return JsonResponse({
            "error": str(e),
            "type": type(e).__name__
        }, status=500)



@login_required
def sync_all_compteurs_view(request):
    compteurs = Compteur.objects.filter(shelly_status='CONNECTE')
    success = 0
    errors = 0

    for compteur in compteurs:
        capteur = sync_compteur_shelly(compteur)
        if capteur:
            create_consommation_from_shelly(compteur)
            success += 1
        else:
            errors += 1

    messages.success(request, f"✅ {success} synchronisés, ❌ {errors} erreurs")
    return redirect("compteurs:compteur_list")  # ← nom correct


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def capteur_associate(request, pk):
    """Associer un capteur existant a un compteur"""
    capteur = get_object_or_404(Capteur.objects.select_related('compteur'), pk=pk)

    if request.method == 'POST':
        form = CapteurForm(request.POST, instance=capteur)
        if form.is_valid():
            ancien_compteur = capteur.compteur
            capteur = form.save(commit=False)
            capteur.derniere_mise_a_jour = timezone.now()
            capteur.save()

            if capteur.compteur:
                compteur_assoc = capteur.compteur
                compteur_assoc.shelly_device_id = capteur.device_id
                compteur_assoc.shelly_status = 'CONNECTE' if capteur.status == 'ACTIF' else 'DECONNECTE'
                compteur_assoc.shelly_ip = capteur.ip_address
                compteur_assoc.derniere_sync_shelly = timezone.now()
                compteur_assoc.save()

            if ancien_compteur and ancien_compteur != capteur.compteur:
                ancien_compteur.shelly_device_id = None
                ancien_compteur.shelly_status = 'DECONNECTE'
                ancien_compteur.save()

            messages.success(request, f"Capteur {capteur.device_id} associe avec succes")

            if capteur.compteur:
                return redirect('compteurs:compteur_detail', pk=capteur.compteur.pk)
            else:
                return redirect('compteurs:capteur_list')
    else:
        form = CapteurForm(instance=capteur)

    context = {
        'page_title': f'Associer le capteur {capteur.device_id} a un compteur',
        'form': form,
        'capteur': capteur,
        'submit_label': 'Associer',
    }

    return render(request, 'capteurs/associate_form.html', context)