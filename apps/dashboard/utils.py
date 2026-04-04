from datetime import datetime, timedelta
from django.utils import timezone
from calendar import monthrange
from typing import Tuple, Dict, Any
import calendar


def get_date_range_from_request(request) -> Tuple[datetime.date, datetime.date]:
    """
    Extrait et valide les dates de début et fin de la requête.
    Par défaut : 12 derniers mois
    """
    today = timezone.now().date()
    default_start = today.replace(day=1) - timedelta(days=365)
    default_end = today

    try:
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')

        if date_debut and date_fin:
            start = datetime.strptime(date_debut, '%Y-%m-%d').date()
            end = datetime.strptime(date_fin, '%Y-%m-%d').date()
            return min(start, end), max(start, end)
        elif date_debut:
            start = datetime.strptime(date_debut, '%Y-%m-%d').date()
            return start, default_end
        elif date_fin:
            end = datetime.strptime(date_fin, '%Y-%m-%d').date()
            return default_start, end
    except (ValueError, TypeError):
        pass

    return default_start, default_end


def calculate_variation(current: float, previous: float) -> Dict[str, Any]:
    """
    Calcule la variation entre deux valeurs et retourne
    le pourcentage, la tendance et la classe CSS
    """
    if previous == 0:
        return {
            'percentage': 0,
            'trend': 'stable',
            'class': 'text-slate-400',
            'icon': 'solar:minus-circle-linear'
        }

    variation = ((current - previous) / previous) * 100

    if variation > 5:
        trend = 'up'
        css_class = 'text-red-400'
        icon = 'solar:arrow-up-linear'
    elif variation < -5:
        trend = 'down'
        css_class = 'text-emerald-400'
        icon = 'solar:arrow-down-linear'
    else:
        trend = 'stable'
        css_class = 'text-slate-400'
        icon = 'solar:minus-circle-linear'

    return {
        'percentage': round(variation, 1),
        'trend': trend,
        'class': css_class,
        'icon': icon
    }


def get_month_name(month_num: int) -> str:
    """Retourne le nom du mois en français"""
    months = [
        'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'
    ]
    return months[month_num - 1]


def format_chart_labels(dates: list) -> list:
    """Formate les dates pour les graphiques"""
    return [d.strftime('%b %Y') for d in dates]


# apps/dashboard/utils.py
from .models import DashboardNotification
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def create_notification(user, title, message, notification_type='INFO',
                        icon=None, priority=0, action_url=None, action_label=None,
                        source_module=None, source_id=None, data=None, expires_at=None):
    """
    Crée une notification pour un utilisateur

    Args:
        user: L'utilisateur destinataire
        title: Titre de la notification
        message: Message détaillé
        notification_type: INFO, SUCCESS, WARNING, ERROR, SYSTEM, ALERT
        icon: Nom de l'icône (sans le préfixe solar:)
        priority: 0=Normal, 1=Important, 2=Urgent
        action_url: URL d'action (si applicable)
        action_label: Libellé du bouton d'action
        source_module: Module source (ex: 'alertes', 'facturation')
        source_id: ID source dans le module
        data: Données JSON supplémentaires
        expires_at: Date d'expiration (None = jamais)

    Returns:
        DashboardNotification or None
    """
    try:
        # Déterminer l'icône par défaut
        if not icon:
            icon = get_default_icon(notification_type)

        # Déterminer la date d'expiration par défaut (30 jours)
        if not expires_at and priority == 2:
            expires_at = timezone.now() + timezone.timedelta(days=30)

        notification = DashboardNotification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            icon=icon,
            priority=priority,
            action_url=action_url,
            action_label=action_label,
            source_module=source_module,
            source_id=source_id,
            data=data or {},
            expires_at=expires_at,
            created_at=timezone.now()
        )

        logger.info(f"Notification créée: {title} pour {user.email}")
        return notification

    except Exception as e:
        logger.error(f"Erreur création notification: {e}")
        return None


def get_default_icon(notification_type):
    """Retourne l'icône par défaut selon le type de notification"""
    icons = {
        'INFO': 'info-circle',
        'SUCCESS': 'check-circle',
        'WARNING': 'exclamation-triangle',
        'ERROR': 'times-circle',
        'SYSTEM': 'cog',
        'ALERT': 'bell'
    }
    return icons.get(notification_type, 'bell')


def mark_notification_as_read(notification_id, user):
    """Marque une notification comme lue"""
    try:
        notification = DashboardNotification.objects.get(id=notification_id, user=user)
        if not notification.read:
            notification.read = True
            notification.save(update_fields=['read'])
            return True
    except DashboardNotification.DoesNotExist:
        pass
    return False


def mark_all_notifications_as_read(user):
    """Marque toutes les notifications de l'utilisateur comme lues"""
    updated = DashboardNotification.objects.filter(
        user=user,
        read=False,
        archived=False
    ).update(read=True)
    return updated


def get_unread_count(user):
    """Récupère le nombre de notifications non lues"""
    return DashboardNotification.objects.filter(
        user=user,
        read=False,
        archived=False
    ).exclude(
        expires_at__lt=timezone.now()
    ).count()