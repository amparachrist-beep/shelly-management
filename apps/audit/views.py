from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Count, Sum, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import date, timedelta, datetime
import json
import csv
import io

from .models import AuditLog, AuditPolicy, AuditReport, AuditArchive
from .forms import (
    AuditLogFilterForm, AuditPolicyForm,
    AuditReportForm, ArchiveFilterForm, DateRangeForm
)
from apps.users.models import CustomUser as User

# ============================================
# Vérificateurs de rôles
# ============================================
def is_admin(user):
    return user.is_authenticated and user.is_admin


def is_audit_admin(user):
    """Vérifie si l'utilisateur a les droits d'audit"""
    return user.is_authenticated and (user.is_admin or user.has_perm('audit.view_auditlog'))


# ============================================
# LOGS D'AUDIT
# ============================================
@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def audit_log_list(request):
    """Liste des logs d'audit"""
    logs = AuditLog.objects.select_related('user').order_by('-timestamp')

    # Filtres
    form = AuditLogFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data['action']:
            logs = logs.filter(action=form.cleaned_data['action'])
        if form.cleaned_data['severity']:
            logs = logs.filter(severity=form.cleaned_data['severity'])
        if form.cleaned_data['user']:
            logs = logs.filter(user=form.cleaned_data['user'])
        if form.cleaned_data['date_debut']:
            logs = logs.filter(timestamp__date__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            logs = logs.filter(timestamp__date__lte=form.cleaned_data['date_fin'])
        if form.cleaned_data['success'] is not None:
            logs = logs.filter(success=form.cleaned_data['success'])
        if form.cleaned_data['entity_type']:
            logs = logs.filter(entity_type=form.cleaned_data['entity_type'])
        if form.cleaned_data['search']:
            search_term = form.cleaned_data['search']
            logs = logs.filter(
                Q(description__icontains=search_term) |
                Q(entity_name__icontains=search_term) |
                Q(user__username__icontains=search_term) |
                Q(user_ip__icontains=search_term)
            )

    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistiques
    stats = {
        'total': logs.count(),
        'par_severite': logs.values('severity').annotate(count=Count('id')).order_by('-count'),
        'par_action': logs.values('action').annotate(count=Count('id')).order_by('-count')[:10],
        'par_utilisateur': logs.values('user__username').annotate(count=Count('id')).order_by('-count')[:10],
    }

    context = {
        'page_title': 'Journaux d\'audit',
        'page_obj': page_obj,
        'form': form,
        'stats': stats,
        'actions': AuditLog.ACTION_TYPES,
        'severities': AuditLog.SEVERITY_LEVELS,
    }

    return render(request, 'audit/log_list.html', context)


@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def audit_log_detail(request, pk):
    """Détail d'un log d'audit"""
    log = get_object_or_404(AuditLog.objects.select_related('user'), pk=pk)

    # Formater les données JSON pour l'affichage
    old_values = json.dumps(log.old_values, indent=2, ensure_ascii=False) if log.old_values else ''
    new_values = json.dumps(log.new_values, indent=2, ensure_ascii=False) if log.new_values else ''
    query_params = json.dumps(log.query_params, indent=2, ensure_ascii=False) if log.query_params else ''

    context = {
        'page_title': f'Log audit #{log.id}',
        'log': log,
        'old_values': old_values,
        'new_values': new_values,
        'query_params': query_params,
    }

    return render(request, 'audit/log_detail.html', context)


@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def audit_log_search_by_user(request, user_id):
    """Recherche des logs par utilisateur"""
    user = get_object_or_404(User, pk=user_id)
    logs = AuditLog.objects.filter(user=user).order_by('-timestamp')

    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': f'Logs d\'audit - {user.get_full_name() or user.username}',
        'page_obj': page_obj,
        'user': user,
        'logs_count': logs.count(),
    }

    return render(request, 'audit/logs_by_user.html', context)


# ============================================
# ÉVÉNEMENTS DE SÉCURITÉ
# ============================================
@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def security_event_list(request):
    """Liste des événements de sécurité"""
    events = SecurityEvent.objects.select_related('source_user').order_by('-detected_at')

    # Filtres
    form = SecurityEventFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data['event_type']:
            events = events.filter(event_type=form.cleaned_data['event_type'])
        if form.cleaned_data['severity']:
            events = events.filter(severity=form.cleaned_data['severity'])
        if form.cleaned_data['blocked'] is not None:
            events = events.filter(blocked=form.cleaned_data['blocked'])
        if form.cleaned_data['date_debut']:
            events = events.filter(detected_at__date__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            events = events.filter(detected_at__date__lte=form.cleaned_data['date_fin'])
        if form.cleaned_data['source_ip']:
            events = events.filter(source_ip__icontains=form.cleaned_data['source_ip'])

    # Pagination
    paginator = Paginator(events, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistiques
    stats = {
        'total': events.count(),
        'bloques': events.filter(blocked=True).count(),
        'critiques': events.filter(severity='CRITICAL').count(),
        'par_type': events.values('event_type').annotate(count=Count('id')).order_by('-count'),
        'top_ip': events.values('source_ip').annotate(count=Count('id')).order_by('-count')[:10],
    }

    context = {
        'page_title': 'Événements de sécurité',
        'page_obj': page_obj,
        'form': form,
        'stats': stats,
        'event_types': SecurityEvent.EVENT_TYPES,
        'severities': SecurityEvent.SEVERITY_LEVELS,
    }

    return render(request, 'audit/security_event_list.html', context)


@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def security_event_detail(request, pk):
    """Détail d'un événement de sécurité"""
    event = get_object_or_404(SecurityEvent.objects.select_related('source_user'), pk=pk)

    # Formater les données JSON
    event_data = json.dumps(event.event_data, indent=2, ensure_ascii=False) if event.event_data else ''
    request_body = event.request_body

    context = {
        'page_title': f'Événement de sécurité #{event.id}',
        'event': event,
        'event_data': event_data,
        'request_body': request_body,
    }

    return render(request, 'audit/security_event_detail.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def bloquer_ip(request, pk):
    """Bloquer une IP suite à un événement de sécurité"""
    event = get_object_or_404(SecurityEvent, pk=pk)

    if request.method == 'POST':
        # Ici, tu pourrais intégrer avec ton système de pare-feu
        # Pour l'exemple, on marque juste l'événement comme bloqué

        event.blocked = True
        event.block_reason = request.POST.get('raison', 'Bloqué manuellement par administrateur')
        event.actions_taken = event.actions_taken + ['IP_BLOCKED_MANUALLY']
        event.save()

        # Créer un log d'audit
        AuditLog.objects.create(
            action='SECURITY_EVENT',
            severity='HIGH',
            description=f'IP {event.source_ip} bloquée manuellement suite à {event.get_event_type_display()}',
            user=request.user,
            user_role=request.user.get_role_display(),
            user_ip=request.META.get('REMOTE_ADDR'),
            entity_type='SECURITY_EVENT',
            entity_id=event.id,
            entity_name=f'Événement #{event.id}',
            success=True,
            request_path=request.path,
            request_method=request.method,
        )

        messages.success(request, f'IP {event.source_ip} bloquée avec succès')
        return redirect('security_event_detail', pk=pk)

    context = {
        'page_title': f'Bloquer l\'IP {event.source_ip}',
        'event': event,
    }

    return render(request, 'audit/bloquer_ip.html', context)


# ============================================
# POLITIQUES D'AUDIT
# ============================================
@login_required
@user_passes_test(is_admin, login_url='/login/')
def audit_policy_list(request):
    """Liste des politiques d'audit"""
    policies = AuditPolicy.objects.select_related('created_by').order_by('name')

    context = {
        'page_title': 'Politiques d\'audit',
        'policies': policies,
        'policy_types': AuditPolicy.POLICY_TYPES,
        'retention_periods': AuditPolicy.RETENTION_PERIODS,
    }

    return render(request, 'audit/policy_list.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def audit_policy_detail(request, pk):
    """Détail d'une politique d'audit"""
    policy = get_object_or_404(AuditPolicy.objects.select_related('created_by'), pk=pk)

    context = {
        'page_title': f'Politique: {policy.name}',
        'policy': policy,
    }

    return render(request, 'audit/policy_detail.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def audit_policy_create(request):
    """Créer une politique d'audit"""
    if request.method == 'POST':
        form = AuditPolicyForm(request.POST)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.created_by = request.user
            policy.save()

            messages.success(request, f'Politique "{policy.name}" créée avec succès')
            return redirect('audit_policy_detail', pk=policy.pk)
    else:
        form = AuditPolicyForm()

    context = {
        'page_title': 'Créer une politique d\'audit',
        'form': form,
        'submit_label': 'Créer',
    }

    return render(request, 'audit/policy_form.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def audit_policy_update(request, pk):
    """Modifier une politique d'audit"""
    policy = get_object_or_404(AuditPolicy, pk=pk)

    if request.method == 'POST':
        form = AuditPolicyForm(request.POST, instance=policy)
        if form.is_valid():
            policy = form.save()

            messages.success(request, f'Politique "{policy.name}" modifiée avec succès')
            return redirect('audit_policy_detail', pk=policy.pk)
    else:
        form = AuditPolicyForm(instance=policy)

    context = {
        'page_title': f'Modifier: {policy.name}',
        'form': form,
        'submit_label': 'Modifier',
        'policy': policy,
    }

    return render(request, 'audit/policy_form.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def audit_policy_toggle(request, pk):
    """Activer/désactiver une politique d'audit"""
    policy = get_object_or_404(AuditPolicy, pk=pk)

    if request.method == 'POST':
        policy.enabled = not policy.enabled
        policy.save()

        action = "activée" if policy.enabled else "désactivée"
        messages.success(request, f'Politique "{policy.name}" {action}')

        # Log d'audit
        AuditLog.objects.create(
            action='SYSTEM_CONFIG_UPDATE',
            severity='MEDIUM',
            description=f'Politique d\'audit "{policy.name}" {action}',
            user=request.user,
            user_role=request.user.get_role_display(),
            entity_type='AUDIT_POLICY',
            entity_id=policy.id,
            entity_name=policy.name,
            success=True,
            old_values={'enabled': not policy.enabled},
            new_values={'enabled': policy.enabled},
        )

    return redirect('audit_policy_detail', pk=pk)


# ============================================
# RAPPORTS D'AUDIT
# ============================================
@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def audit_report_list(request):
    """Liste des rapports d'audit"""
    reports = AuditReport.objects.select_related('generated_by').order_by('-generated_at')

    # Filtres
    report_type = request.GET.get('type')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    if report_type:
        reports = reports.filter(report_type=report_type)
    if date_debut:
        reports = reports.filter(generated_at__date__gte=date_debut)
    if date_fin:
        reports = reports.filter(generated_at__date__lte=date_fin)

    # Pagination
    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': 'Rapports d\'audit',
        'page_obj': page_obj,
        'report_types': AuditReport.REPORT_TYPES,
        'formats': AuditReport.REPORT_FORMATS,
    }

    return render(request, 'audit/report_list.html', context)


@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def audit_report_detail(request, pk):
    """Détail d'un rapport d'audit"""
    report = get_object_or_404(AuditReport.objects.select_related('generated_by'), pk=pk)

    context = {
        'page_title': f'Rapport: {report.name}',
        'report': report,
        'can_download': report.status == 'COMPLETED' and report.file_path,
    }

    return render(request, 'audit/report_detail.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def audit_report_create(request):
    """Créer un rapport d'audit"""
    if request.method == 'POST':
        form = AuditReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.generated_by = request.user
            report.status = 'PENDING'
            report.save()

            # Ici, tu pourrais lancer une tâche asynchrone pour générer le rapport
            # Pour l'exemple, on marque comme complété directement

            report.status = 'COMPLETED'
            report.generation_duration = timedelta(seconds=30)  # Simulation
            report.file_path = f"/reports/audit_{report.id}.pdf"  # Simulation
            report.file_size = 1024000  # Simulation: 1MB
            report.save()

            messages.success(request, f'Rapport "{report.name}" généré avec succès')
            return redirect('audit_report_detail', pk=report.pk)
    else:
        # Par défaut: rapport du mois en cours
        today = date.today()
        start_date = today.replace(day=1)
        if today.month == 12:
            end_date = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        form = AuditReportForm(initial={
            'name': f'Rapport audit {today.strftime("%B %Y")}',
            'start_date': start_date,
            'end_date': end_date,
            'report_type': 'MONTHLY',
        })

    context = {
        'page_title': 'Générer un rapport d\'audit',
        'form': form,
        'submit_label': 'Générer le rapport',
    }

    return render(request, 'audit/report_form.html', context)


@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def download_audit_report(request, pk):
    """Télécharger un rapport d'audit"""
    report = get_object_or_404(AuditReport, pk=pk)

    if report.status != 'COMPLETED' or not report.file_path:
        messages.error(request, "Ce rapport n'est pas disponible au téléchargement")
        return redirect('audit_report_detail', pk=pk)

    # Incrémenter le compteur de téléchargements
    report.download_count += 1
    report.save()

    # Ici, tu retournerais le fichier réel
    # Pour l'exemple, on simule un téléchargement
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="audit_report_{report.id}.pdf"'
    response.write(b'Simulated PDF content')  # Contenu simulé

    return response


# ============================================
# ARCHIVES
# ============================================
@login_required
@user_passes_test(is_admin, login_url='/login/')
def audit_archive_list(request):
    """Liste des archives d'audit"""
    archives = AuditArchive.objects.select_related('created_by').order_by('-archived_at')

    # Filtres
    form = ArchiveFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data['date_debut']:
            archives = archives.filter(start_date__date__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            archives = archives.filter(end_date__date__lte=form.cleaned_data['date_fin'])
        if form.cleaned_data['storage_type']:
            archives = archives.filter(storage_type=form.cleaned_data['storage_type'])

    # Pagination
    paginator = Paginator(archives, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistiques
    stats = {
        'total': archives.count(),
        'total_logs': archives.aggregate(total=Sum('log_count'))['total'] or 0,
        'total_size_mb': archives.aggregate(total=Sum('total_size'))['total'] or 0 / (1024 * 1024),
        'par_annee': archives.extra(
            select={'year': "EXTRACT(year FROM start_date)"}
        ).values('year').annotate(count=Count('id'), logs=Sum('log_count')).order_by('-year'),
    }

    context = {
        'page_title': 'Archives d\'audit',
        'page_obj': page_obj,
        'form': form,
        'stats': stats,
    }

    return render(request, 'audit/archive_list.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def audit_archive_detail(request, pk):
    """Détail d'une archive d'audit"""
    archive = get_object_or_404(AuditArchive.objects.select_related('created_by'), pk=pk)

    context = {
        'page_title': f'Archive: {archive.archive_name}',
        'archive': archive,
        'periode_jours': (archive.end_date - archive.start_date).days,
        'taille_mb': archive.total_size / (1024 * 1024) if archive.total_size else 0,
    }

    return render(request, 'audit/archive_detail.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def create_audit_archive(request):
    """Créer une archive d'audit"""
    if request.method == 'POST':
        form = DateRangeForm(request.POST)
        if form.is_valid():
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            description = form.cleaned_data.get('description', '')

            # Récupérer les logs dans la période
            logs = AuditLog.objects.filter(
                timestamp__gte=start_date,
                timestamp__lte=end_date,
                archived=False
            )

            if logs.count() == 0:
                messages.warning(request, "Aucun log à archiver pour cette période")
                return redirect('audit_archive_list')

            # Créer l'archive (simulation)
            archive = AuditArchive.objects.create(
                archive_name=f'Archive_{start_date.strftime("%Y%m")}_{end_date.strftime("%Y%m")}',
                description=description,
                start_date=start_date,
                end_date=end_date,
                log_count=logs.count(),
                total_size=logs.count() * 1024,  # Simulation: 1KB par log
                compression_format='GZIP',
                storage_type='LOCAL',
                created_by=request.user,
                archived_at=timezone.now(),
                checksum='simulated_checksum',
                verified=True,
                verification_date=timezone.now(),
            )

            # Marquer les logs comme archivés
            logs.update(archived=True, archive_date=timezone.now())

            # Log d'audit
            AuditLog.objects.create(
                action='DATABASE_BACKUP',
                severity='MEDIUM',
                description=f'Archive d\'audit créée: {archive.archive_name} ({logs.count()} logs)',
                user=request.user,
                user_role=request.user.get_role_display(),
                entity_type='AUDIT_ARCHIVE',
                entity_id=archive.id,
                entity_name=archive.archive_name,
                success=True,
                old_values={'archived': False},
                new_values={'archived': True, 'archive_id': archive.id},
            )

            messages.success(request, f'Archive créée avec succès: {logs.count()} logs archivés')
            return redirect('audit_archive_detail', pk=archive.pk)
    else:
        # Par défaut: archiver les logs de plus de 90 jours
        end_date = timezone.now() - timedelta(days=90)
        start_date = end_date - timedelta(days=30)  # Archive mensuelle

        form = DateRangeForm(initial={
            'start_date': start_date,
            'end_date': end_date,
            'description': f'Archive automatique des logs de plus de 90 jours',
        })

    context = {
        'page_title': 'Créer une archive d\'audit',
        'form': form,
        'submit_label': 'Créer l\'archive',
    }

    return render(request, 'audit/create_archive.html', context)


# ============================================
# RAPPORTS ET STATISTIQUES
# ============================================
@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def rapport_activite(request):
    """Rapport d'activité du système"""
    # Formulaire de période
    form = DateRangeForm(request.GET or None)

    # Par défaut: 30 derniers jours
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    if form.is_valid():
        if form.cleaned_data['start_date']:
            start_date = form.cleaned_data['start_date']
        if form.cleaned_data['end_date']:
            end_date = form.cleaned_data['end_date']

    # Récupérer les logs
    logs = AuditLog.objects.filter(
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    )

    # Statistiques
    stats = {
        'periode': f'{start_date} à {end_date}',
        'total_logs': logs.count(),
        'logs_reussis': logs.filter(success=True).count(),
        'logs_echoues': logs.filter(success=False).count(),
        'par_severite': logs.values('severity').annotate(
            count=Count('id'),
            percentage=Count('id') * 100.0 / logs.count()
        ).order_by('-count'),
        'par_action': logs.values('action').annotate(count=Count('id')).order_by('-count')[:20],
        'par_utilisateur': logs.filter(user__isnull=False).values(
            'user__username', 'user__first_name', 'user__last_name'
        ).annotate(count=Count('id')).order_by('-count')[:10],
        'par_jour': logs.extra(
            select={'day': 'DATE(timestamp)'}
        ).values('day').annotate(count=Count('id')).order_by('day')[:30],
        'top_ips': logs.values('user_ip').annotate(count=Count('id')).order_by('-count')[:10],
        'top_entites': logs.exclude(entity_type='').values('entity_type').annotate(
            count=Count('id')
        ).order_by('-count'),
    }

    context = {
        'page_title': 'Rapport d\'activité',
        'form': form,
        'stats': stats,
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(request, 'audit/rapport_activite.html', context)


@login_required
@user_passes_test(is_admin, login_url='/login/')
def rapport_securite(request):
    """Rapport de sécurité"""
    # Formulaire de période
    form = DateRangeForm(request.GET or None)

    # Par défaut: 30 derniers jours
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    if form.is_valid():
        if form.cleaned_data['start_date']:
            start_date = form.cleaned_data['start_date']
        if form.cleaned_data['end_date']:
            end_date = form.cleaned_data['end_date']

    # Événements de sécurité
    events = SecurityEvent.objects.filter(
        detected_at__date__gte=start_date,
        detected_at__date__lte=end_date
    )

    # Logs d'audit pertinents
    security_logs = AuditLog.objects.filter(
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date,
        action__in=['USER_LOGIN', 'SECURITY_EVENT'],
        severity__in=['HIGH', 'CRITICAL']
    )

    # Statistiques
    stats = {
        'periode': f'{start_date} à {end_date}',
        'total_evenements': events.count(),
        'evenements_critiques': events.filter(severity='CRITICAL').count(),
        'evenements_bloques': events.filter(blocked=True).count(),
        'tentatives_connexion_echouees': AuditLog.objects.filter(
            timestamp__date__gte=start_date,
            action='USER_LOGIN',
            success=False
        ).count(),
        'par_type': events.values('event_type').annotate(
            count=Count('id'),
            bloques=Count('id', filter=Q(blocked=True))
        ).order_by('-count'),
        'top_ip_suspectes': events.values('source_ip').annotate(
            count=Count('id'),
            types=Count('event_type', distinct=True)
        ).order_by('-count')[:10],
        'connexions_suspectes': security_logs.filter(
            action='USER_LOGIN',
            user_ip__in=events.values_list('source_ip', flat=True).distinct()
        ).count(),
        'actions_securite': security_logs.filter(action='SECURITY_EVENT').values(
            'description'
        ).annotate(count=Count('id')).order_by('-count')[:10],
    }

    context = {
        'page_title': 'Rapport de sécurité',
        'form': form,
        'stats': stats,
        'start_date': start_date,
        'end_date': end_date,
        'event_types': SecurityEvent.EVENT_TYPES,
    }

    return render(request, 'audit/rapport_securite.html', context)


@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def dashboard_audit(request):
    """Dashboard d'audit"""
    # Périodes
    today = date.today()
    h24 = timezone.now() - timedelta(hours=24)
    j7 = today - timedelta(days=7)
    j30 = today - timedelta(days=30)

    # Statistiques globales
    stats = {
        'logs_24h': AuditLog.objects.filter(timestamp__gte=h24).count(),
        'logs_7j': AuditLog.objects.filter(timestamp__date__gte=j7).count(),
        'logs_30j': AuditLog.objects.filter(timestamp__date__gte=j30).count(),
        'evenements_securite_24h': SecurityEvent.objects.filter(detected_at__gte=h24).count(),
        'evenements_critiques_7j': SecurityEvent.objects.filter(
            detected_at__date__gte=j7,
            severity='CRITICAL'
        ).count(),
        'utilisateurs_actifs_7j': AuditLog.objects.filter(
            timestamp__date__gte=j7,
            user__isnull=False
        ).values('user').distinct().count(),
    }

    # Graphiques
    # Logs par jour (7 derniers jours)
    logs_par_jour = []
    for i in range(6, -1, -1):
        jour = today - timedelta(days=i)
        count = AuditLog.objects.filter(timestamp__date=jour).count()
        logs_par_jour.append({
            'jour': jour.strftime('%d/%m'),
            'count': count
        })

    # Logs par sévérité
    logs_par_severite = AuditLog.objects.filter(
        timestamp__date__gte=j7
    ).values('severity').annotate(count=Count('id')).order_by('severity')

    # Top actions
    top_actions = AuditLog.objects.filter(
        timestamp__date__gte=j7
    ).values('action').annotate(count=Count('id')).order_by('-count')[:10]

    # Derniers événements critiques
    derniers_evenements_critiques = SecurityEvent.objects.filter(
        severity='CRITICAL'
    ).order_by('-detected_at')[:5]

    # Derniers logs
    derniers_logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:10]

    context = {
        'page_title': 'Dashboard d\'audit',
        'stats': stats,
        'logs_par_jour': logs_par_jour,
        'logs_par_severite': logs_par_severite,
        'top_actions': top_actions,
        'derniers_evenements_critiques': derniers_evenements_critiques,
        'derniers_logs': derniers_logs,
    }

    return render(request, 'audit/dashboard.html', context)


# ============================================
# EXPORT ET IMPORT
# ============================================
@login_required
@user_passes_test(is_audit_admin, login_url='/login/')
def export_logs_csv(request):
    """Exporter les logs d'audit en CSV"""
    # Filtres
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    action = request.GET.get('action')

    logs = AuditLog.objects.all()

    if start_date:
        logs = logs.filter(timestamp__date__gte=start_date)
    if end_date:
        logs = logs.filter(timestamp__date__lte=end_date)
    if action:
        logs = logs.filter(action=action)

    # Limiter à 10000 logs maximum
    logs = logs[:10000]

    # Créer le CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'

    writer = csv.writer(response)

    # En-têtes
    headers = [
        'ID', 'Timestamp', 'Action', 'Sévérité', 'Description',
        'Utilisateur', 'Rôle utilisateur', 'IP utilisateur',
        'Type entité', 'ID entité', 'Nom entité',
        'Succès', 'Message erreur',
        'Méthode HTTP', 'Chemin requête',
        'Session ID', 'Corrélation ID'
    ]

    writer.writerow(headers)

    # Données
    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.get_action_display(),
            log.get_severity_display(),
            log.description[:100],  # Limiter la longueur
            log.user.username if log.user else '',
            log.user_role,
            log.user_ip or '',
            log.entity_type,
            log.entity_id or '',
            log.entity_name[:100],
            'Oui' if log.success else 'Non',
            log.error_message[:100] if log.error_message else '',
            log.request_method,
            log.request_path[:100],
            log.session_id,
            str(log.correlation_id) if log.correlation_id else '',
        ])

    # Log d'audit
    AuditLog.objects.create(
        action='DATA_EXPORT',
        severity='LOW',
        description=f'Export CSV des logs d\'audit ({logs.count()} enregistrements)',
        user=request.user,
        user_role=request.user.get_role_display(),
        success=True,
        request_path=request.path,
        request_method=request.method,
    )

    return response


@login_required
@user_passes_test(is_admin, login_url='/login/')
def purge_old_logs(request):
    """Purger les anciens logs"""
    if request.method == 'POST':
        # Récupérer la politique de rétention la plus courte
        policies = AuditPolicy.objects.filter(enabled=True)
        if policies.exists():
            # Trouver la période de rétention la plus courte
            retention_days = 365  # Par défaut: 1 an
            for policy in policies:
                if policy.retention_period == '30_DAYS':
                    retention_days = min(retention_days, 30)
                elif policy.retention_period == '90_DAYS':
                    retention_days = min(retention_days, 90)
                elif policy.retention_period == '180_DAYS':
                    retention_days = min(retention_days, 180)
                elif policy.retention_period == '1_YEAR':
                    retention_days = min(retention_days, 365)
                elif policy.retention_period == '3_YEARS':
                    retention_days = min(retention_days, 3 * 365)
        else:
            retention_days = 90  # Par défaut: 90 jours

        # Date limite
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        # Compter les logs à purger
        logs_to_purge = AuditLog.objects.filter(
            timestamp__lt=cutoff_date,
            archived=True  # Ne purger que les logs déjà archivés
        )

        count = logs_to_purge.count()

        if count == 0:
            messages.info(request, "Aucun log à purger")
            return redirect('dashboard_audit')

        if 'confirm' in request.POST:
            # Purger les logs
            logs_to_purge.delete()

            # Log d'audit
            AuditLog.objects.create(
                action='SYSTEM_CONFIG_UPDATE',
                severity='HIGH',
                description=f'Purgé {count} logs d\'audit antérieurs à {cutoff_date.strftime("%Y-%m-%d")}',
                user=request.user,
                user_role=request.user.get_role_display(),
                success=True,
            )

            messages.success(request, f'{count} logs purgés avec succès')
            return redirect('dashboard_audit')

        context = {
            'page_title': 'Confirmer la purge des logs',
            'count': count,
            'cutoff_date': cutoff_date.strftime('%d/%m/%Y'),
            'retention_days': retention_days,
        }

        return render(request, 'audit/confirm_purge.html', context)

    return redirect('dashboard_audit')