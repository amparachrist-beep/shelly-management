from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Dashboard principal
    path('', views.index, name='index'),

    # Dashboard par rôle
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('agent/', views.agent_dashboard, name='agent_dashboard'),
    path('client/', views.client_dashboard, name='client_dashboard'),

    # Statistiques et rapports
    path('admin/statistics/', views.admin_statistics, name='admin_statistics'),
    path('admin/financial-report/', views.admin_financial_report, name='admin_financial_report'),
    path('admin/technical-report/', views.admin_technical_report, name='admin_technical_report'),
    path('agent/performance/', views.agent_performance, name='agent_performance'),
    path('client/consumption-analysis/', views.client_consumption_analysis, name='client_consumption_analysis'),
    path('client/conseils/', views.client_conseils, name='client_conseils'),
    # Gestion des widgets
    path('widgets/', views.widget_management, name='widget_management'),
    path('widgets/<int:widget_id>/configure/', views.widget_configuration, name='widget_configuration'),
    path('save-layout/', views.save_layout, name='save_layout'),

    # Notifications
    path('notifications/', views.notifications_list, name='notifications_list'),
    path('notifications/<int:notification_id>/', views.notification_detail, name='notification_detail'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    path('notifications/mark-all-read/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/<int:notification_id>/delete/', views.delete_notification, name='delete_notification'),

    # Actions rapides
    path('quick-actions/', views.quick_actions, name='quick_actions'),
    path('quick-actions/<int:action_id>/execute/', views.execute_quick_action, name='execute_quick_action'),

    # Paramètres
    path('settings/', views.dashboard_settings, name='dashboard_settings'),

    # Vues AJAX/API
    path('ajax/stats/', views.ajax_stats, name='stats_ajax'),
    path('ajax/widget/<int:widget_id>/data/', views.ajax_widget_data, name='ajax_widget_data'),
    path('ajax/notifications/', views.ajax_notifications, name='ajax_notifications'),
    path('ajax/notifications/<int:notification_id>/mark-read/', views.ajax_mark_notification_read, name='ajax_mark_notification_read'),
    path('ajax/notifications/mark-all-read/', views.ajax_mark_all_read, name='ajax_mark_all_read'),

    # Gestion admin (seulement pour les administrateurs)
    path('admin/widgets/', views.admin_widget_list, name='admin_widget_list'),
    path('admin/widgets/create/', views.admin_widget_create, name='admin_widget_create'),
    path('admin/widgets/<int:widget_id>/edit/', views.admin_widget_edit, name='admin_widget_edit'),
    path('admin/widgets/<int:widget_id>/delete/', views.admin_widget_delete, name='admin_widget_delete'),

    path('api/stats/', views.dashboard_stats_ajax, name='dashboard_stats_ajax'),
    path('cron/sync/', views.cron_sync, name='cron_sync'),
]