from django.urls import path
from . import views
app_name = 'audit'
urlpatterns = [
    # Dashboard
    path('', views.dashboard_audit, name='dashboard_audit'),

    # Logs d'audit
    path('logs/', views.audit_log_list, name='audit_log_list'),
    path('logs/<int:pk>/', views.audit_log_detail, name='audit_log_detail'),
    path('logs/utilisateur/<int:user_id>/', views.audit_log_search_by_user, name='audit_log_search_by_user'),

    # Événements de sécurité
    path('securite/', views.security_event_list, name='security_event_list'),
    path('securite/<int:pk>/', views.security_event_detail, name='security_event_detail'),
    path('securite/<int:pk>/bloquer-ip/', views.bloquer_ip, name='bloquer_ip'),

    # Politiques d'audit
    path('politiques/', views.audit_policy_list, name='audit_policy_list'),
    path('politiques/<int:pk>/', views.audit_policy_detail, name='audit_policy_detail'),
    path('politiques/creer/', views.audit_policy_create, name='audit_policy_create'),
    path('politiques/<int:pk>/modifier/', views.audit_policy_update, name='audit_policy_update'),
    path('politiques/<int:pk>/toggle/', views.audit_policy_toggle, name='audit_policy_toggle'),

    # Rapports
    path('rapports/', views.audit_report_list, name='audit_report_list'),
    path('rapports/<int:pk>/', views.audit_report_detail, name='audit_report_detail'),
    path('rapports/creer/', views.audit_report_create, name='audit_report_create'),
    path('rapports/<int:pk>/telecharger/', views.download_audit_report, name='download_audit_report'),

    # Archives
    path('archives/', views.audit_archive_list, name='audit_archive_list'),
    path('archives/<int:pk>/', views.audit_archive_detail, name='audit_archive_detail'),
    path('archives/creer/', views.create_audit_archive, name='create_audit_archive'),

    # Rapports statistiques
    path('rapport-activite/', views.rapport_activite, name='rapport_activite'),
    path('rapport-securite/', views.rapport_securite, name='rapport_securite'),

    # Export et maintenance
    path('export/csv/', views.export_logs_csv, name='export_logs_csv'),
    path('purge-logs/', views.purge_old_logs, name='purge_old_logs'),
]