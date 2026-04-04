# apps/menages/views_agence.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .models import Agence
from apps.parametrage.models import Departement, Localite


# ─────────────────────────────────────────────
# MIXINS / HELPERS
# ─────────────────────────────────────────────

def _require_admin(user):
    """Lève une 403 si l'utilisateur n'est pas admin."""
    if not user.is_admin:
        raise PermissionDenied


# ─────────────────────────────────────────────
# LIST
# ─────────────────────────────────────────────

@login_required
def agence_list(request):
    """
    - ADMIN       → toutes les agences
    - AGENT       → uniquement son agence
    - CLIENT      → uniquement l'agence de son ménage
    """
    user = request.user

    if user.is_admin:
        agences = Agence.objects.select_related('localite', 'departement').all()

    elif user.is_agent:
        if user.agence:
            agences = Agence.objects.filter(pk=user.agence_id).select_related('localite', 'departement')
        else:
            agences = Agence.objects.none()

    else:  # CLIENT
        try:
            agence = user.menage.agence
            agences = Agence.objects.filter(pk=agence.pk).select_related('localite', 'departement') if agence else Agence.objects.none()
        except AttributeError:
            agences = Agence.objects.none()

    context = {
        'agences': agences,
        'can_manage': user.is_admin,
        'agences_actives_count': agences.filter(actif=True).count(),
    }
    return render(request, 'gestion/agences/list.html', context)


# ─────────────────────────────────────────────
# DETAIL
# ─────────────────────────────────────────────

@login_required
def agence_detail(request, pk):
    """
    - ADMIN  → n'importe quelle agence
    - AGENT  → seulement la sienne
    - CLIENT → seulement celle de son ménage
    """
    agence = get_object_or_404(
        Agence.objects.select_related('localite', 'departement').prefetch_related('agents', 'menages'),
        pk=pk
    )
    user = request.user

    if user.is_agent and user.agence_id != agence.pk:
        raise PermissionDenied
    if user.is_client:
        try:
            if not user.menage.agence or user.menage.agence_id != agence.pk:
                raise PermissionDenied
        except AttributeError:
            raise PermissionDenied

    context = {
        'agence': agence,
        'agents_actifs': agence.agents_actifs,
        'can_manage': user.is_admin,
    }
    return render(request, 'gestion/agences/detail.html', context)


# ─────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────

@login_required
def agence_create(request):
    """Réservé aux admins."""
    _require_admin(request.user)

    departements = Departement.objects.filter().order_by('nom')
    localites = Localite.objects.filter(actif=True).select_related('departement').order_by('nom')

    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        code_agence = request.POST.get('code_agence', '').strip()
        departement_id = request.POST.get('departement')
        localite_id = request.POST.get('localite')
        pays = request.POST.get('pays', 'Congo-Brazzaville').strip()
        actif = request.POST.get('actif') == 'on'

        errors = {}
        if not nom:
            errors['nom'] = "Le nom de l'agence est obligatoire."
        if not code_agence:
            errors['code_agence'] = "Le code agence est obligatoire."
        elif Agence.objects.filter(code_agence=code_agence).exists():
            errors['code_agence'] = "Ce code agence existe déjà."
        if not departement_id:
            errors['departement'] = "Le département est obligatoire."
        if not localite_id:
            errors['localite'] = "La localité est obligatoire."

        if not errors:
            agence = Agence.objects.create(
                nom=nom,
                code_agence=code_agence,
                departement_id=departement_id,
                localite_id=localite_id,
                pays=pays,
                actif=actif,
            )
            messages.success(request, f"Agence « {agence.nom} » créée avec succès.")
            return redirect('menages:agence_detail', pk=agence.pk)

        context = {
            'departements': departements,
            'localites': localites,
            'errors': errors,
            'form_data': request.POST,
            'action': 'Créer',
            'agence': None,
        }
        return render(request, 'gestion/agences/form.html', context)

    context = {
        'departements': departements,
        'localites': localites,
        'action': 'Créer',
        'agence': None,
    }
    return render(request, 'gestion/agences/form.html', context)


# ─────────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────────

@login_required
def agence_update(request, pk):
    """Réservé aux admins."""
    _require_admin(request.user)

    agence = get_object_or_404(Agence, pk=pk)
    departements = Departement.objects.order_by('nom')
    localites = Localite.objects.filter(actif=True).select_related('departement').order_by('nom')

    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        code_agence = request.POST.get('code_agence', '').strip()
        departement_id = request.POST.get('departement')
        localite_id = request.POST.get('localite')
        pays = request.POST.get('pays', 'Congo-Brazzaville').strip()
        actif = request.POST.get('actif') == 'on'

        errors = {}
        if not nom:
            errors['nom'] = "Le nom de l'agence est obligatoire."
        if not code_agence:
            errors['code_agence'] = "Le code agence est obligatoire."
        elif Agence.objects.filter(code_agence=code_agence).exclude(pk=pk).exists():
            errors['code_agence'] = "Ce code agence existe déjà."
        if not departement_id:
            errors['departement'] = "Le département est obligatoire."
        if not localite_id:
            errors['localite'] = "La localité est obligatoire."

        if not errors:
            agence.nom = nom
            agence.code_agence = code_agence
            agence.departement_id = departement_id
            agence.localite_id = localite_id
            agence.pays = pays
            agence.actif = actif
            agence.save()
            messages.success(request, f"Agence « {agence.nom} » mise à jour avec succès.")
            return redirect('menages:agence_detail', pk=agence.pk)

        context = {
            'agence': agence,
            'departements': departements,
            'localites': localites,
            'errors': errors,
            'form_data': request.POST,
            'action': 'Modifier',
        }
        return render(request, 'gestion/agences/form.html', context)

    context = {
        'agence': agence,
        'departements': departements,
        'localites': localites,
        'action': 'Modifier',
    }
    return render(request, 'gestion/agences/form.html', context)


# ─────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────

@login_required
def agence_delete(request, pk):
    """Réservé aux admins."""
    _require_admin(request.user)

    agence = get_object_or_404(Agence, pk=pk)

    if request.method == 'POST':
        nom = agence.nom
        # Sécurité : on ne supprime pas si des ménages ou agents sont rattachés
        if agence.menages.exists() or agence.agents.exists():
            messages.error(
                request,
                f"Impossible de supprimer « {nom} » : elle contient des ménages ou des agents. "
                "Réaffectez-les d'abord."
            )
            return redirect('menages:agence_detail', pk=pk)

        agence.delete()
        messages.success(request, f"Agence « {nom} » supprimée avec succès.")
        return redirect('menages:agence_list')

    context = {
        'agence': agence,
        'nb_menages': agence.nombre_menages,
        'nb_agents': agence.nombre_agents,
    }
    return render(request, 'gestion/agences/confirm_delete.html', context)