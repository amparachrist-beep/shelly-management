from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.utils import timezone
import json

from .models import AuditLog, SecurityEvent
from apps.menages.models import Menage
from apps.compteurs.models import Compteur
from apps.facturation.models import Facture
from apps.paiements.models import Paiement

User = get_user_model()


# ============================================
# SIGNALS POUR LES UTILISATEURS
# ============================================

@receiver(post_save, sender=User)
def log_user_change(sender, instance, created, **kwargs):
    """Journaliser les modifications d'utilisateurs"""
    if created:
        action = 'USER_CREATE'
        description = f"Utilisateur créé: {instance.username}"
        old_values = None
        new_values = {
            'username': instance.username,
            'email': instance.email,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'role': instance.get_role_display(),
        }
    else:
        action = 'USER_UPDATE'
        description = f"Utilisateur modifié: {instance.username}"
        # Note: pour obtenir les anciennes valeurs, il faut les stocker avant la sauvegarde
        old_values = None
        new_values = {
            'username': instance.username,
            'email': instance.email,
            'first_name': instance.first_name,
            'last_name': instance.last_name,
            'role': instance.get_role_display(),
            'is_active': instance.is_active,
        }

    # Récupérer l'utilisateur qui a fait la modification (si disponible via request)
    user = getattr(instance, '_current_user', None)

    AuditLog.objects.create(
        action=action,
        severity='MEDIUM',
        description=description,
        user=user,
        user_role=user.get_role_display() if user else None,
        entity_type='USER',
        entity_id=instance.id,
        entity_name=instance.username,
        old_values=old_values,
        new_values=new_values,
        success=True,
    )


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Journaliser les connexions réussies"""
    AuditLog.objects.create(
        action='USER_LOGIN',
        severity='LOW',
        description=f"Connexion réussie: {user.username}",
        user=user,
        user_role=user.get_role_display(),
        user_ip=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        entity_type='USER',
        entity_id=user.id,
        entity_name=user.username,
        success=True,
        request_path=request.path,
        request_method=request.method,
        session_id=request.session.session_key,
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Journaliser les déconnexions"""
    if user:
        AuditLog.objects.create(
            action='USER_LOGOUT',
            severity='LOW',
            description=f"Déconnexion: {user.username}",
            user=user,
            user_role=user.get_role_display(),
            user_ip=request.META.get('REMOTE_ADDR'),
            entity_type='USER',
            entity_id=user.id,
            entity_name=user.username,
            success=True,
            request_path=request.path,
            request_method=request.method,
        )


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    """Journaliser les tentatives de connexion échouées"""
    username = credentials.get('username', 'inconnu')

    # Vérifier s'il y a eu plusieurs échecs
    failures_recent = AuditLog.objects.filter(
        action='USER_LOGIN',
        success=False,
        entity_name=username,
        timestamp__gte=timezone.now() - timezone.timedelta(minutes=5)
    ).count()

    severity = 'HIGH' if failures_recent >= 3 else 'MEDIUM'

    # Log d'audit
    AuditLog.objects.create(
        action='USER_LOGIN',
        severity=severity,
        description=f"Échec connexion: {username}",
        user_ip=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        entity_type='USER',
        entity_name=username,
        success=False,
        error_message="Identifiants invalides",
        request_path=request.path,
        request_method=request.method,
    )

    # Créer un événement de sécurité si plusieurs échecs
    if failures_recent >= 5:
        SecurityEvent.objects.create(
            event_type='BRUTE_FORCE_ATTEMPT',
            severity='CRITICAL',
            description=f"Tentative de force brute sur le compte: {username}",
            source_ip=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            event_data={
                'username': username,
                'failures_last_5min': failures_recent + 1,
                'timestamp': timezone.now().isoformat(),
            },
            request_path=request.path,
            request_method=request.method,
            blocked=False,
            actions_taken=['LOGGED', 'ALERTED'],
        )


# ============================================
# SIGNALS POUR LES MÉNAGES
# ============================================

@receiver(post_save, sender=Menage)
def log_menage_change(sender, instance, created, **kwargs):
    """Journaliser les modifications de ménages"""
    if created:
        action = 'MENAGE_CREATE'
        description = f"Ménage créé: {instance.nom_famille}"
        new_values = {
            'nom_famille': instance.nom_famille,
            'code_menage': instance.code_menage,
            'statut': instance.get_statut_display(),
        }
    else:
        action = 'MENAGE_UPDATE'
        description = f"Ménage modifié: {instance.nom_famille}"
        new_values = {
            'nom_famille': instance.nom_famille,
            'code_menage': instance.code_menage,
            'statut': instance.get_statut_display(),
        }

    user = getattr(instance, '_current_user', None)

    AuditLog.objects.create(
        action=action,
        severity='MEDIUM',
        description=description,
        user=user,
        user_role=user.get_role_display() if user else None,
        entity_type='MENAGE',
        entity_id=instance.id,
        entity_name=instance.nom_famille,
        new_values=new_values,
        success=True,
    )


@receiver(post_delete, sender=Menage)
def log_menage_delete(sender, instance, **kwargs):
    """Journaliser la suppression de ménages"""
    user = getattr(instance, '_current_user', None)

    AuditLog.objects.create(
        action='MENAGE_DELETE',
        severity='HIGH',
        description=f"Ménage supprimé: {instance.nom_famille}",
        user=user,
        user_role=user.get_role_display() if user else None,
        entity_type='MENAGE',
        entity_id=instance.id,
        entity_name=instance.nom_famille,
        old_values={'nom_famille': instance.nom_famille},
        success=True,
    )


# ============================================
# SIGNALS POUR LES COMPTEURS
# ============================================

@receiver(post_save, sender=Compteur)
def log_compteur_change(sender, instance, created, **kwargs):
    """Journaliser les modifications de compteurs"""
    if created:
        action = 'COMPTEUR_CREATE'
        description = f"Compteur créé: {instance.numero_contrat}"
        new_values = {
            'numero_contrat': instance.numero_contrat,
            'matricule': instance.matricule_compteur,
            'menage': instance.menage.nom_famille if instance.menage else None,
            'statut': instance.get_statut_display(),
        }
    else:
        action = 'COMPTEUR_UPDATE'
        description = f"Compteur modifié: {instance.numero_contrat}"
        new_values = {
            'numero_contrat': instance.numero_contrat,
            'matricule': instance.matricule_compteur,
            'statut': instance.get_statut_display(),
        }

    user = getattr(instance, '_current_user', None)

    AuditLog.objects.create(
        action=action,
        severity='MEDIUM',
        description=description,
        user=user,
        user_role=user.get_role_display() if user else None,
        entity_type='COMPTEUR',
        entity_id=instance.id,
        entity_name=instance.numero_contrat,
        new_values=new_values,
        success=True,
    )


# ============================================
# SIGNALS POUR LES FACTURES
# ============================================

@receiver(post_save, sender=Facture)
def log_facture_change(sender, instance, created, **kwargs):
    """Journaliser les modifications de factures"""
    if created:
        action = 'FACTURE_CREATE'
        description = f"Facture créée: {instance.numero}"
    else:
        action = 'FACTURE_UPDATE'
        description = f"Facture modifiée: {instance.numero}"

    user = getattr(instance, '_current_user', None)

    AuditLog.objects.create(
        action=action,
        severity='MEDIUM',
        description=description,
        user=user,
        user_role=user.get_role_display() if user else None,
        entity_type='FACTURE',
        entity_id=instance.id,
        entity_name=instance.numero,
        new_values={
            'numero': instance.numero,
            'periode': instance.periode.strftime('%Y-%m') if instance.periode else None,
            'montant': float(instance.total_ttc) if instance.total_ttc else 0,
            'statut': instance.get_statut_display(),
        },
        success=True,
    )


# ============================================
# SIGNALS POUR LES PAIEMENTS
# ============================================

@receiver(post_save, sender=Paiement)
def log_paiement_change(sender, instance, created, **kwargs):
    """Journaliser les modifications de paiements"""
    if created:
        action = 'PAIEMENT_CREATE'
        description = f"Paiement créé: {instance.montant} €"
    else:
        action = 'PAIEMENT_UPDATE'
        description = f"Paiement modifié: {instance.montant} €"

    user = getattr(instance, '_current_user', None)

    AuditLog.objects.create(
        action=action,
        severity='MEDIUM',
        description=description,
        user=user,
        user_role=user.get_role_display() if user else None,
        entity_type='PAIEMENT',
        entity_id=instance.id,
        entity_name=f"Paiement #{instance.id}",
        new_values={
            'montant': float(instance.montant),
            'methode': instance.get_methode_display(),
            'statut': instance.get_statut_display(),
            'facture': instance.facture.numero if instance.facture else None,
        },
        success=True,
    )


# ============================================
# MIDDLEWARE POUR AUDIT
# ============================================

class AuditMiddleware:
    """Middleware pour capturer les informations de requête"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Stocker l'utilisateur pour les signals
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Ceci sera utilisé par les signals pour savoir qui a fait l'action
            request._current_user = request.user

        response = self.get_response(request)

        # Journaliser les requêtes importantes (optionnel)
        self._log_important_requests(request, response)

        return response

    def _log_important_requests(self, request, response):
        """Journaliser certaines requêtes importantes"""
        if not request.user.is_authenticated:
            return

        # Liste des chemins à journaliser
        important_paths = [
            '/admin/', '/api/', '/parametrage/', '/supervision/',
            '/menages/', '/compteurs/', '/facturation/', '/paiements/',
        ]

        # Vérifier si le chemin est important
        path_important = any(path in request.path for path in important_paths)

        # Vérifier les méthodes importantes
        method_important = request.method in ['POST', 'PUT', 'DELETE', 'PATCH']

        # Journaliser les requêtes importantes qui modifient des données
        if path_important and method_important and response.status_code >= 200 and response.status_code < 300:
            # Éviter de journaliser certaines actions trop fréquentes
            excluded_paths = ['/api/auth/', '/api/token/']
            if not any(path in request.path for path in excluded_paths):
                AuditLog.objects.create(
                    action='SYSTEM_CONFIG_UPDATE',
                    severity='LOW',
                    description=f"Requête {request.method} sur {request.path}",
                    user=request.user,
                    user_role=request.user.get_role_display(),
                    user_ip=request.META.get('REMOTE_ADDR'),
                    request_path=request.path,
                    request_method=request.method,
                    query_params=dict(request.GET),
                    success=response.status_code < 400,
                )