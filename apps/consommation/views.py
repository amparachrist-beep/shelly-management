from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Sum, Avg, Count, Q
from django.db import transaction
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import date, datetime, timedelta
from decimal import Decimal
import csv
import io
import json

from .models import Consommation
from .forms import (
    ConsommationForm, ReleverManuelForm, CorrigerReleveForm,
    ImportCSVForm, PeriodeFilterForm, StatsFilterForm
)
from apps.compteurs.models import Compteur
from apps.menages.models import Menage


# ============================================
# Vérificateurs de rôles
# ============================================
def is_admin(user):
    return user.is_authenticated and user.is_admin


def is_agent(user):
    return user.is_authenticated and user.is_agent


def is_client(user):
    return user.is_authenticated and user.is_client


# ============================================
# LISTES ET CONSULTATION
# ============================================
@login_required
def consommation_list(request):
    """Liste des consommations"""
    # Déterminer le type d'utilisateur et filtrer
    if request.user.is_admin or request.user.is_agent:
        consommations = Consommation.objects.select_related(
            'compteur', 'compteur__menage'
        ).order_by('-periode', 'compteur__menage__nom_menage')
    else:
        try:
            menage = Menage.objects.get(utilisateur=request.user)
            consommations = Consommation.objects.filter(
                compteur__menage=menage
            ).select_related('compteur').order_by('-periode')
        except Menage.DoesNotExist:
            consommations = Consommation.objects.none()

    # Filtres
    form = PeriodeFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data['periode_debut']:
            consommations = consommations.filter(
                periode__gte=form.cleaned_data['periode_debut']
            )
        if form.cleaned_data['periode_fin']:
            consommations = consommations.filter(
                periode__lte=form.cleaned_data['periode_fin']
            )
        if form.cleaned_data['compteur']:
            consommations = consommations.filter(
                compteur=form.cleaned_data['compteur']
            )
        if form.cleaned_data['statut']:
            consommations = consommations.filter(
                statut=form.cleaned_data['statut']
            )

    # Pagination
    paginator = Paginator(consommations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistiques
    stats = {
        'total': consommations.count(),
        'total_kwh': consommations.aggregate(
            total=Sum('index_fin_periode') - Sum('index_debut_periode')
        )['total'] or Decimal('0'),
        'moyenne': consommations.aggregate(
            avg=Avg('index_fin_periode') - Avg('index_debut_periode')
        )['avg'] or Decimal('0'),
    }

    context = {
        'page_title': 'Consommations',
        'page_obj': page_obj,
        'form': form,
        'stats': stats,
        'is_admin': request.user.is_admin,
        'is_agent': request.user.is_agent,
        'is_client': request.user.is_client,
    }

    return render(request, 'gestion/consommation/list.html', context)


@login_required
def consommation_detail(request, pk):
    """Détail d'une consommation"""
    consommation = get_object_or_404(
        Consommation.objects.select_related('compteur', 'compteur__menage'),
        pk=pk
    )

    # Vérifier les permissions
    if request.user.is_client and consommation.compteur.menage.utilisateur != request.user:
        messages.error(request, "Accès non autorisé")
        return redirect('consommation_list')

    # Données journalières
    details_journaliers = []
    if consommation.details_journaliers:
        try:
            details_journaliers = json.loads(consommation.details_journaliers)
        except:
            details_journaliers = []

    # Statistiques sur les détails journaliers
    stats_journalieres = {
        'jours': len(details_journaliers),
        'max': max([d.get('consommation', 0) for d in details_journaliers]) if details_journaliers else 0,
        'min': min([d.get('consommation', 0) for d in details_journaliers]) if details_journaliers else 0,
        'moyenne': sum([d.get('consommation', 0) for d in details_journaliers]) / len(
            details_journaliers) if details_journaliers else 0,
    }

    context = {
        'page_title': f'Consommation {consommation.periode.strftime("%m/%Y")}',
        'consommation': consommation,
        'details_journaliers': details_journaliers,
        'stats_journalieres': stats_journalieres,
        'can_validate': request.user.is_admin or request.user.is_agent,
        'can_correct': request.user.is_admin or request.user.is_agent,
    }

    return render(request, 'gestion/consommation/detail.html', context)


@login_required
def consommation_compteur_periode(request, compteur_id, periode_str):
    """Consommation d'un compteur pour une période spécifique"""
    compteur = get_object_or_404(Compteur, pk=compteur_id)

    # Vérifier les permissions
    if request.user.is_client and compteur.menage.utilisateur != request.user:
        messages.error(request, "Accès non autorisé")
        return redirect('consommation_list')

    # Parser la période
    try:
        periode = datetime.strptime(periode_str, '%Y-%m').date()
    except ValueError:
        messages.error(request, "Format de période invalide. Utilisez AAAA-MM")
        return redirect('consommation_list')

    consommation = get_object_or_404(
        Consommation.objects.select_related('compteur', 'compteur__menage'),
        compteur=compteur,
        periode=periode
    )

    context = {
        'page_title': f'Consommation {compteur.numero_contrat} - {periode.strftime("%m/%Y")}',
        'consommation': consommation,
        'compteur': compteur,
        'can_validate': request.user.is_admin or request.user.is_agent,
        'can_correct': request.user.is_admin or request.user.is_agent,
    }

    return render(request, 'gestion/consommation/detail.html', context)


# ============================================
# CRÉATION ET MODIFICATION
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def consommation_create(request):
    """Créer une consommation"""
    if request.method == 'POST':
        form = ConsommationForm(request.POST, user=request.user)
        if form.is_valid():
            consommation = form.save(commit=False)
            consommation.source = 'RELEVE_MANUEL'
            consommation.releve_par = request.user
            consommation.date_releve = timezone.now()
            consommation.statut = 'BROUILLON'
            consommation.save()

            messages.success(request, "Consommation créée avec succès")
            return redirect('consommation_detail', pk=consommation.pk)
    else:
        form = ConsommationForm(user=request.user)

    context = {
        'page_title': 'Créer une consommation',
        'form': form,
        'submit_label': 'Créer',
    }

    return render(request, 'gestion/consommation/form.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def consommation_update(request, pk):
    """Modifier une consommation"""
    consommation = get_object_or_404(Consommation, pk=pk)

    if request.method == 'POST':
        form = ConsommationForm(request.POST, instance=consommation, user=request.user)
        if form.is_valid():
            consommation = form.save(commit=False)
            consommation.statut = 'BROUILLON'  # Retour en brouillon après modification
            consommation.save()

            messages.success(request, "Consommation modifiée avec succès")
            return redirect('consommation_detail', pk=consommation.pk)
    else:
        form = ConsommationForm(instance=consommation, user=request.user)

    context = {
        'page_title': f'Modifier la consommation {consommation.periode.strftime("%m/%Y")}',
        'form': form,
        'submit_label': 'Modifier',
        'consommation': consommation,
    }

    return render(request, 'gestion/consommation/form.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def relever_manuel(request):
    """Relevé manuel rapide"""
    if request.method == 'POST':
        form = ReleverManuelForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Vérifier si une consommation existe déjà
                    periode = form.cleaned_data['periode']
                    compteur = form.cleaned_data['compteur']

                    if Consommation.objects.filter(compteur=compteur, periode=periode).exists():
                        messages.error(request, "Une consommation existe déjà pour cette période")
                        return redirect('relever_manuel')

                    # Calculer la consommation
                    consommation_kwh = form.cleaned_data['index_fin'] - form.cleaned_data['index_debut']

                    if consommation_kwh < 0:
                        messages.error(request, "L'index de fin doit être supérieur à l'index de début")
                        return redirect('relever_manuel')

                    # Créer la consommation
                    consommation = Consommation.objects.create(
                        compteur=compteur,
                        periode=periode,
                        index_debut_periode=form.cleaned_data['index_debut'],
                        index_fin_periode=form.cleaned_data['index_fin'],
                        source='RELEVE_MANUEL',
                        releve_par=request.user,
                        date_releve=timezone.now(),
                        statut='EN_ATTENTE',
                        notes=form.cleaned_data.get('notes', '')
                    )

                    messages.success(request, f"Relevé créé avec succès : {consommation_kwh} kWh")
                    return redirect('consommation_detail', pk=consommation.pk)

            except Exception as e:
                messages.error(request, f"Erreur lors de la création : {str(e)}")
    else:
        form = ReleverManuelForm(user=request.user)

    context = {
        'page_title': 'Relevé manuel',
        'form': form,
        'submit_label': 'Enregistrer le relevé',
    }

    return render(request, 'gestion/consommation/relever_manuel.html', context)


# ============================================
# VALIDATION ET CORRECTION
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def valider_consommation(request, pk):
    """Valider une consommation"""
    consommation = get_object_or_404(Consommation, pk=pk)

    if consommation.statut == 'VALIDÉ':
        messages.warning(request, "Cette consommation est déjà validée")
    else:
        consommation.statut = 'VALIDÉ'
        consommation.date_validation = date.today()
        consommation.valide_par = request.user
        consommation.save()
        messages.success(request, "Consommation validée avec succès")

    return redirect('consommation_detail', pk=pk)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def marquer_anomalie(request, pk):
    """Marquer une consommation comme anomalie"""
    consommation = get_object_or_404(Consommation, pk=pk)

    if consommation.statut == 'ANOMALIE':
        messages.warning(request, "Cette consommation est déjà marquée comme anomalie")
    else:
        consommation.statut = 'ANOMALIE'
        consommation.notes_anomalie = request.POST.get('motif', 'Anomalie détectée')
        consommation.save()
        messages.warning(request, "Consommation marquée comme anomalie")

    return redirect('consommation_detail', pk=pk)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def corriger_releve(request, pk):
    """Corriger un relevé"""
    consommation = get_object_or_404(Consommation, pk=pk)

    if request.method == 'POST':
        form = CorrigerReleveForm(request.POST, instance=consommation)
        if form.is_valid():
            consommation = form.save(commit=False)
            consommation.statut = 'CORRIGE'
            consommation.corrige_par = request.user
            consommation.date_correction = date.today()
            consommation.save()

            messages.success(request, "Relevé corrigé avec succès")
            return redirect('consommation_detail', pk=consommation.pk)
    else:
        form = CorrigerReleveForm(instance=consommation)

    context = {
        'page_title': f'Corriger la consommation {consommation.periode.strftime("%m/%Y")}',
        'form': form,
        'submit_label': 'Corriger',
        'consommation': consommation,
    }

    return render(request, 'gestion/consommation/corriger_releve.html', context)


# ============================================
# IMPORT/EXPORT
# ============================================
@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def import_csv(request):
    """Importer des consommations depuis CSV"""
    if request.method == 'POST':
        form = ImportCSVForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']

            # Vérifier l'extension
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Veuillez uploader un fichier CSV")
                return redirect('import_csv')

            try:
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                reader = csv.DictReader(decoded_file)

                resultats = {
                    'importes': 0,
                    'erreurs': 0,
                    'doublons': 0,
                    'details': []
                }

                for row_num, row in enumerate(reader, start=1):
                    try:
                        # Validation des champs requis
                        required_fields = ['numero_contrat', 'periode', 'index_debut', 'index_fin']
                        for field in required_fields:
                            if field not in row or not row[field]:
                                raise ValueError(f"Champ {field} manquant")

                        # Trouver le compteur
                        compteur = Compteur.objects.get(numero_contrat=row['numero_contrat'])

                        # Parser la période
                        periode = datetime.strptime(row['periode'] + "-01", "%Y-%m-%d").date()

                        # Vérifier si existe déjà
                        if Consommation.objects.filter(compteur=compteur, periode=periode).exists():
                            resultats['doublons'] += 1
                            resultats['details'].append({
                                'ligne': row_num,
                                'statut': 'DOUBLON',
                                'message': f"Consommation déjà existante pour {row['periode']}"
                            })
                            continue

                        # Calculer la consommation
                        index_debut = Decimal(row['index_debut'])
                        index_fin = Decimal(row['index_fin'])
                        consommation_kwh = index_fin - index_debut

                        if consommation_kwh < 0:
                            raise ValueError("Index de fin inférieur à index de début")

                        # Créer la consommation
                        Consommation.objects.create(
                            compteur=compteur,
                            periode=periode,
                            index_debut_periode=index_debut,
                            index_fin_periode=index_fin,
                            source='IMPORT_CSV',
                            releve_par=request.user,
                            date_releve=timezone.now(),
                            statut='EN_ATTENTE'
                        )

                        resultats['importes'] += 1
                        resultats['details'].append({
                            'ligne': row_num,
                            'statut': 'SUCCÈS',
                            'message': f"Importé : {consommation_kwh} kWh"
                        })

                    except Compteur.DoesNotExist:
                        resultats['erreurs'] += 1
                        resultats['details'].append({
                            'ligne': row_num,
                            'statut': 'ERREUR',
                            'message': f"Compteur {row.get('numero_contrat', 'N/A')} introuvable"
                        })
                    except ValueError as e:
                        resultats['erreurs'] += 1
                        resultats['details'].append({
                            'ligne': row_num,
                            'statut': 'ERREUR',
                            'message': str(e)
                        })
                    except Exception as e:
                        resultats['erreurs'] += 1
                        resultats['details'].append({
                            'ligne': row_num,
                            'statut': 'ERREUR',
                            'message': f"Erreur inattendue : {str(e)}"
                        })

                messages.success(request,
                                 f"Import terminé : {resultats['importes']} importés, "
                                 f"{resultats['erreurs']} erreurs, {resultats['doublons']} doublons"
                                 )

                # Stocker les résultats dans la session pour les afficher
                request.session['import_resultats'] = resultats
                return redirect('import_csv_resultats')

            except Exception as e:
                messages.error(request, f"Erreur lors de la lecture du fichier : {str(e)}")
    else:
        form = ImportCSVForm()

    context = {
        'page_title': 'Importer des consommations',
        'form': form,
    }

    return render(request, 'gestion/consommation/import_csv.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def import_csv_resultats(request):
    """Afficher les résultats de l'import"""
    resultats = request.session.get('import_resultats', None)
    if not resultats:
        messages.info(request, "Aucun résultat d'import à afficher")
        return redirect('import_csv')

    context = {
        'page_title': 'Résultats de l\'import',
        'resultats': resultats,
    }

    # Nettoyer la session
    if 'import_resultats' in request.session:
        del request.session['import_resultats']

    return render(request, 'gestion/consommation/import_resultats.html', context)


@login_required
def export_csv(request):
    """Exporter les consommations en CSV"""
    # Déterminer les consommations à exporter
    if request.user.is_admin or request.user.is_agent:
        consommations = Consommation.objects.select_related(
            'compteur', 'compteur__menage'
        ).order_by('periode', 'compteur__numero_contrat')
    else:
        try:
            menage = Menage.objects.get(utilisateur=request.user)
            consommations = Consommation.objects.filter(
                compteur__menage=menage
            ).select_related('compteur').order_by('periode')
        except Menage.DoesNotExist:
            consommations = Consommation.objects.none()

    # Filtrer par période si spécifié
    periode_str = request.GET.get('periode')
    if periode_str:
        try:
            periode = datetime.strptime(periode_str, '%Y-%m').date()
            consommations = consommations.filter(periode=periode)
        except ValueError:
            pass

    # Créer le CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="consommations.csv"'

    writer = csv.writer(response)

    # En-têtes
    headers = [
        'Numéro contrat', 'Ménage', 'Période',
        'Index début', 'Index fin', 'Consommation (kWh)',
        'Statut', 'Source', 'Date relevé'
    ]

    if request.user.is_admin or request.user.is_agent:
        headers.extend(['Validé par', 'Date validation'])

    writer.writerow(headers)

    # Données
    for conso in consommations:
        row = [
            conso.compteur.numero_contrat,
            conso.compteur.menage.nom_famille,
            conso.periode.strftime('%Y-%m'),
            float(conso.index_debut_periode),
            float(conso.index_fin_periode),
            float(conso.consommation_kwh),
            conso.get_statut_display(),
            conso.get_source_display(),
            conso.date_releve.strftime('%Y-%m-%d') if conso.date_releve else '',
        ]

        if request.user.is_admin or request.user.is_agent:
            row.extend([
                conso.valide_par.username if conso.valide_par else '',
                conso.date_validation.strftime('%Y-%m-%d') if conso.date_validation else ''
            ])

        writer.writerow(row)

    return response


# ============================================
# STATISTIQUES
# ============================================
@login_required
def stats_mensuelles(request):
    """Statistiques mensuelles de consommation"""
    # Déterminer les données à analyser
    if request.user.is_admin or request.user.is_agent:
        consommations = Consommation.objects.all()
    else:
        try:
            menage = Menage.objects.get(utilisateur=request.user)
            consommations = Consommation.objects.filter(compteur__menage=menage)
        except Menage.DoesNotExist:
            consommations = Consommation.objects.none()

    form = StatsFilterForm(request.GET or None)

    if form.is_valid():
        annee = form.cleaned_data.get('annee')
        compteur = form.cleaned_data.get('compteur')

        if annee:
            consommations = consommations.filter(periode__year=annee)

        if compteur:
            consommations = consommations.filter(compteur=compteur)
    else:
        # Par défaut : année en cours
        consommations = consommations.filter(periode__year=date.today().year)

    # Statistiques globales
    stats_globales = {
        'total_kwh': consommations.aggregate(
            total=Sum('index_fin_periode') - Sum('index_debut_periode')
        )['total'] or Decimal('0'),
        'moyenne_kwh': consommations.aggregate(
            avg=Avg('index_fin_periode') - Avg('index_debut_periode')
        )['avg'] or Decimal('0'),
        'nombre': consommations.count(),
    }

    # Données par mois
    donnees_par_mois = []
    mois_labels = []
    mois_data = []

    for mois in range(1, 13):
        conso_mois = consommations.filter(periode__month=mois)
        total_mois = conso_mois.aggregate(
            total=Sum('index_fin_periode') - Sum('index_debut_periode')
        )['total'] or Decimal('0')

        mois_nom = date(2000, mois, 1).strftime('%b')

        donnees_par_mois.append({
            'mois': mois_nom,
            'annee': form.cleaned_data.get('annee', date.today().year),
            'total': float(total_mois),
            'nombre': conso_mois.count(),
        })

        mois_labels.append(mois_nom)
        mois_data.append(float(total_mois))

    # Top 5 compteurs
    if request.user.is_admin or request.user.is_agent:
        top_compteurs = consommations.values(
            'compteur__numero_contrat',
            'compteur__menage__nom_famille'
        ).annotate(
            total=Sum('index_fin_periode') - Sum('index_debut_periode'),
            nombre=Count('id')
        ).order_by('-total')[:5]
    else:
        top_compteurs = []

    context = {
        'page_title': 'Statistiques mensuelles',
        'form': form,
        'stats_globales': stats_globales,
        'donnees_par_mois': donnees_par_mois,
        'mois_labels': json.dumps(mois_labels),
        'mois_data': json.dumps(mois_data),
        'top_compteurs': top_compteurs,
    }

    return render(request, 'supervision/stats_mensuelles.html', context)


@login_required
@user_passes_test(lambda u: u.is_admin or u.is_agent, login_url='/login/')
def stats_comparatives(request):
    """Statistiques comparatives"""
    form = StatsFilterForm(request.GET or None)

    consommations = Consommation.objects.all()

    if form.is_valid():
        annee = form.cleaned_data.get('annee')
        compteur = form.cleaned_data.get('compteur')

        if annee:
            consommations = consommations.filter(periode__year=annee)

        if compteur:
            consommations = consommations.filter(compteur=compteur)

    # Comparaison année en cours vs année précédente
    annee_actuelle = form.cleaned_data.get('annee', date.today().year)
    annee_precedente = annee_actuelle - 1

    conso_annee_actuelle = consommations.filter(periode__year=annee_actuelle)
    conso_annee_precedente = consommations.filter(periode__year=annee_precedente)

    total_actuel = conso_annee_actuelle.aggregate(
        total=Sum('index_fin_periode') - Sum('index_debut_periode')
    )['total'] or Decimal('0')

    total_precedent = conso_annee_precedente.aggregate(
        total=Sum('index_fin_periode') - Sum('index_debut_periode')
    )['total'] or Decimal('0')

    # Calcul de l'évolution
    evolution = Decimal('0')
    if total_precedent > 0:
        evolution = ((total_actuel - total_precedent) / total_precedent) * 100

    # Données comparatives par mois
    donnees_comparatives = []

    for mois in range(1, 13):
        conso_mois_actuel = conso_annee_actuelle.filter(periode__month=mois)
        conso_mois_precedent = conso_annee_precedente.filter(periode__month=mois)

        total_mois_actuel = conso_mois_actuel.aggregate(
            total=Sum('index_fin_periode') - Sum('index_debut_periode')
        )['total'] or Decimal('0')

        total_mois_precedent = conso_mois_precedent.aggregate(
            total=Sum('index_fin_periode') - Sum('index_debut_periode')
        )['total'] or Decimal('0')

        evolution_mois = Decimal('0')
        if total_mois_precedent > 0:
            evolution_mois = ((total_mois_actuel - total_mois_precedent) / total_mois_precedent) * 100

        donnees_comparatives.append({
            'mois': date(2000, mois, 1).strftime('%B'),
            'annee_actuelle': float(total_mois_actuel),
            'annee_precedente': float(total_mois_precedent),
            'evolution': float(evolution_mois),
        })

    context = {
        'page_title': 'Statistiques comparatives',
        'form': form,
        'annee_actuelle': annee_actuelle,
        'annee_precedente': annee_precedente,
        'total_actuel': float(total_actuel),
        'total_precedent': float(total_precedent),
        'evolution': float(evolution),
        'donnees_comparatives': donnees_comparatives,
    }

    return render(request, 'supervision/stats_comparatives.html', context)


@login_required
def graphique_mensuel(request, compteur_id):
    """Graphique mensuel d'un compteur"""
    compteur = get_object_or_404(Compteur, pk=compteur_id)

    # Vérifier les permissions
    if request.user.is_client and compteur.menage.utilisateur != request.user:
        messages.error(request, "Accès non autorisé")
        return redirect('consommation_list')

    # Récupérer les 12 derniers mois
    donnees = []
    today = date.today()

    for i in range(12):
        mois_date = date(today.year, today.month, 1)
        for _ in range(i):
            # Mois précédent
            if mois_date.month == 1:
                mois_date = date(mois_date.year - 1, 12, 1)
            else:
                mois_date = date(mois_date.year, mois_date.month - 1, 1)

        try:
            conso = Consommation.objects.get(
                compteur=compteur,
                periode=mois_date
            )
            donnees.append({
                'periode': mois_date.strftime('%Y-%m'),
                'label': mois_date.strftime('%b %Y'),
                'consommation': float(conso.consommation_kwh),
                'statut': conso.statut,
            })
        except Consommation.DoesNotExist:
            donnees.append({
                'periode': mois_date.strftime('%Y-%m'),
                'label': mois_date.strftime('%b %Y'),
                'consommation': 0,
                'statut': 'NON_RELEVEE',
            })

    # Trier par période
    donnees.sort(key=lambda x: x['periode'])

    context = {
        'page_title': f'Graphique de consommation - {compteur.numero_contrat}',
        'compteur': compteur,
        'donnees': donnees,
        'donnees_json': json.dumps(donnees),
    }

    return render(request, 'supervision/graphique_mensuel.html', context)


# ============================================
# VUES AJAX POUR DASHBOARD
# ============================================
@login_required
def consommation_en_attente_count(request):
    """Nombre de consommations en attente (pour dashboard)"""
    if request.user.is_admin or request.user.is_agent:
        count = Consommation.objects.filter(statut='EN_ATTENTE').count()
    else:
        count = 0

    return JsonResponse({'count': count})


@login_required
def consommation_recente(request):
    """Dernières consommations (pour dashboard)"""
    limit = int(request.GET.get('limit', 5))

    if request.user.is_admin or request.user.is_agent:
        consommations = Consommation.objects.select_related(
            'compteur', 'compteur__menage'
        ).order_by('-date_releve')[:limit]
    else:
        try:
            menage = Menage.objects.get(utilisateur=request.user)
            consommations = Consommation.objects.filter(
                compteur__menage=menage
            ).select_related('compteur').order_by('-date_releve')[:limit]
        except Menage.DoesNotExist:
            consommations = []

    data = []
    for conso in consommations:
        data.append({
            'id': conso.id,
            'compteur': conso.compteur.numero_contrat,
            'menage': conso.compteur.menage.nom_famille,
            'periode': conso.periode.strftime('%m/%Y'),
            'consommation': float(conso.consommation_kwh),
            'statut': conso.statut,
            'date_releve': conso.date_releve.strftime('%d/%m/%Y %H:%M'),
        })

    return JsonResponse({'consommations': data})


# ============================================
# VUES CLIENT
# ============================================
@login_required
@user_passes_test(is_client, login_url='/login/')
def client_consommation(request):
    """Page consommation pour client"""
    try:
        menage = Menage.objects.get(utilisateur=request.user)
        consommations = Consommation.objects.filter(
            compteur__menage=menage
        ).select_related('compteur').order_by('-periode')

        # Filtre par période
        periode_str = request.GET.get('periode')
        if periode_str:
            try:
                periode = datetime.strptime(periode_str, '%Y-%m').date()
                consommations = consommations.filter(periode=periode)
            except ValueError:
                pass

        # Statistiques
        stats = {
            'total': consommations.count(),
            'total_kwh': consommations.aggregate(
                total=Sum('index_fin_periode') - Sum('index_debut_periode')
            )['total'] or Decimal('0'),
            'derniere_periode': consommations.first().periode if consommations.exists() else None,
        }

        # Graphique des 6 derniers mois
        graphique_data = []
        today = date.today()

        for i in range(5, -1, -1):
            mois_date = date(today.year, today.month, 1)
            for _ in range(i):
                if mois_date.month == 1:
                    mois_date = date(mois_date.year - 1, 12, 1)
                else:
                    mois_date = date(mois_date.year, mois_date.month - 1, 1)

            conso_mois = consommations.filter(periode=mois_date)
            total_mois = conso_mois.aggregate(
                total=Sum('index_fin_periode') - Sum('index_debut_periode')
            )['total'] or Decimal('0')

            graphique_data.append({
                'periode': mois_date.strftime('%b %Y'),
                'consommation': float(total_mois),
            })

        context = {
            'page_title': 'Ma consommation',
            'menage': menage,
            'consommations': consommations[:10],  # Limiter à 10
            'stats': stats,
            'graphique_data': json.dumps(graphique_data),
        }

        return render(request, 'client/consommation.html', context)

    except Menage.DoesNotExist:
        messages.error(request, "Ménage non trouvé")
        return redirect('client_dashboard')


@login_required
@user_passes_test(is_client, login_url='/login/')
def client_graphique_consommation(request, compteur_id):
    """Graphique de consommation détaillé pour client"""
    try:
        menage = Menage.objects.get(utilisateur=request.user)
        compteur = get_object_or_404(Compteur, pk=compteur_id, menage=menage)

        # Récupérer les consommations
        consommations = Consommation.objects.filter(
            compteur=compteur
        ).order_by('periode')[:12]  # 12 derniers mois

        donnees = []
        for conso in consommations:
            donnees.append({
                'periode': conso.periode.strftime('%b %Y'),
                'consommation': float(conso.consommation_kwh),
                'statut': conso.statut,
            })

        context = {
            'page_title': f'Graphique de consommation - {compteur.numero_contrat}',
            'compteur': compteur,
            'donnees': donnees,
            'donnees_json': json.dumps(donnees),
        }

        return render(request, 'client/graphique_consommation.html', context)

    except Menage.DoesNotExist:
        messages.error(request, "Ménage non trouvé")
        return redirect('client_dashboard')


import json
import calendar
from django.db.models import Sum, Q
from django.utils import timezone

@login_required
def client_consommation(request):
    household = get_object_or_404(Menage, utilisateur=request.user)
    compteur  = Compteur.objects.filter(menage=household, statut='ACTIF').first()

    today      = timezone.now().date()
    mois_actuel = today.replace(day=1)
    mois_prec   = (mois_actuel.replace(day=1) - timedelta(days=1)).replace(day=1)

    # consommation_mois / variation
    conso_mois = Consommation.objects.filter(compteur=compteur, periode=mois_actuel).first()
    conso_prec = Consommation.objects.filter(compteur=compteur, periode=mois_prec).first()
    consommation_mois = float(conso_mois.consommation_kwh) if conso_mois else 0
    variation = None
    if conso_prec and conso_prec.consommation_kwh:
        variation = ((consommation_mois - float(conso_prec.consommation_kwh))
                     / float(conso_prec.consommation_kwh)) * 100

    # cout_estime (à adapter selon ton modèle tarif)
    tarif = getattr(compteur.type_tarification, 'prix_kwh', 0) if compteur else 0
    cout_estime = consommation_mois * float(tarif)

    # consommation_moyenne (6 mois)
    six_mois = mois_actuel.replace(day=1)
    for _ in range(5):
        six_mois = (six_mois - timedelta(days=1)).replace(day=1)
    consos_6m = Consommation.objects.filter(
        compteur=compteur, periode__gte=six_mois
    ).values_list('consommation_kwh', flat=True)
    consommation_moyenne = (sum(float(c) for c in consos_6m) / len(consos_6m)) if consos_6m else 0

    # historique_json (12 mois)
    historique = Consommation.objects.filter(
        compteur=compteur
    ).order_by('periode')[:12]
    historique_json = json.dumps({
        'labels': [c.periode.strftime('%b %Y') for c in historique],
        'data':   [float(c.consommation_kwh) for c in historique],
    })

    # consommations_detaillees (avec evolution et facture_id)
    consos_detail = list(Consommation.objects.filter(
        compteur=compteur
    ).order_by('-periode').select_related('facture')[:24])
    for i, c in enumerate(consos_detail):
        prev = consos_detail[i + 1] if i + 1 < len(consos_detail) else None
        c.total_kwh   = float(c.consommation_kwh)
        c.cout        = float(c.consommation_kwh) * float(tarif)
        c.evolution   = None
        if prev and prev.consommation_kwh:
            c.evolution = ((float(c.consommation_kwh) - float(prev.consommation_kwh))
                           / float(prev.consommation_kwh)) * 100
        c.facture_id  = getattr(c, 'facture_id', None)

    # moyenne_quartier / position / difference (à brancher sur vraies données)
    moyenne_quartier   = 320  # placeholder — remplacer par une vraie agrégation
    difference_quartier = abs(((consommation_mois - moyenne_quartier) / moyenne_quartier) * 100) if moyenne_quartier else 0
    position_quartier  = 'inférieure' if consommation_mois < moyenne_quartier else 'supérieure'

    # repartition_plages (simulé — à remplacer par données Shelly si disponibles)
    repartition_plages = [
        {'nom': 'Nuit (00h-06h)',   'pourcentage': 15},
        {'nom': 'Matin (06h-12h)',  'pourcentage': 30},
        {'nom': 'Après-midi (12h-18h)', 'pourcentage': 35},
        {'nom': 'Soir (18h-00h)',   'pourcentage': 20},
    ]

    # conseils_economie
    conseils_economie = [
        {'titre': 'Climatisation',  'description': 'Régler à 26°C minimum.', 'icone': 'solar:snowflake-linear',  'couleur': 'sky',     'economie': 3500},
        {'titre': 'Éclairage LED',  'description': 'Remplacer les ampoules.', 'icone': 'solar:lightbulb-linear', 'couleur': 'amber',   'economie': 1200},
        {'titre': 'Heures creuses', 'description': 'Lancer les appareils la nuit.', 'icone': 'solar:clock-linear', 'couleur': 'emerald', 'economie': 2000},
    ]

    context = {
        'consommation_mois':    consommation_mois,
        'variation':            variation,
        'cout_estime':          cout_estime,
        'consommation_moyenne': consommation_moyenne,
        'historique_json':      historique_json,
        'consommations_detaillees': consos_detail,
        'moyenne_quartier':     moyenne_quartier,
        'position_quartier':    position_quartier,
        'difference_quartier':  difference_quartier,
        'repartition_plages':   repartition_plages,
        'conseils_economie':    conseils_economie,
    }
    return render(request, 'client/consommation.html', context)