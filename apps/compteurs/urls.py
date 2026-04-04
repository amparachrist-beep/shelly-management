from django.urls import path
from . import views

app_name = 'compteurs'
from .webhooks import shelly_energy_webhook, shelly_status_webhook
urlpatterns = [
    # Listes et consultation
    path('', views.compteur_list, name='compteur_list'),
    path('recherche/', views.compteur_search, name='compteur_search'),
    path('<int:pk>/', views.compteur_detail, name='compteur_detail'),

    # Création et modification
    path('creer/', views.compteur_create, name='compteur_create'),
    path('<int:pk>/modifier/', views.compteur_update, name='compteur_update'),

    # Gestion du statut
    path('<int:pk>/activer/', views.compteur_activer, name='compteur_activer'),
    path('<int:pk>/desactiver/', views.compteur_desactiver, name='compteur_desactiver'),
    path('<int:pk>/suspendre/', views.compteur_suspendre, name='compteur_suspendre'),
    path('<int:pk>/resilier/', views.compteur_resilier, name='compteur_resilier'),
    path('<int:pk>/marquer-panne/', views.compteur_marquer_panne, name='compteur_marquer_panne'),

    # Gestion des index
    path('<int:pk>/index/', views.index_view, name='index_view'),
    path('<int:pk>/index/mettre-a-jour/', views.update_index, name='update_index'),

    # Gestion des capteurs Shelly
    path('<int:pk>/associer-capteur/', views.associer_capteur, name='associer_capteur'),
    path('<int:pk>/dissocier-capteur/<int:capteur_id>/', views.dissocier_capteur, name='dissocier_capteur'),

    # Diagnostic et supervision
    path('<int:pk>/diagnostic/', views.diagnostic_compteur, name='diagnostic_compteur'),
    path('<int:pk>/diagnostic/rapport/', views.generer_rapport_diagnostic, name='generer_rapport_diagnostic'),

    # Configuration Shelly
    path('<int:pk>/configurer-shelly/', views.configurer_shelly, name='configurer_shelly'),
    path('<int:pk>/tester-connexion-shelly/', views.tester_connexion_shelly, name='tester_connexion_shelly'),

    # Statistiques
    path('statistiques/', views.stats_compteurs, name='stats_compteurs'),
    path('carte/', views.carte_compteurs, name='carte_compteurs'),

    # Vues client
    path('client/mes-compteurs/', views.client_mes_compteurs, name='client_mes_compteurs'),
    path('client/<int:pk>/', views.client_compteur_detail, name='client_compteur_detail'),
    path('client/mes-capteurs/', views.client_mes_capteurs, name='client_mes_capteurs'),

    # Vues AJAX
    path('ajax/stats/', views.compteur_stats_ajax, name='compteur_stats_ajax'),
    path('ajax/recent/', views.compteur_recent_ajax, name='compteur_recent_ajax'),

    # ============================================
    # URLs POUR LES CAPTEURS - à ajouter manuellement
    # ============================================
    path('capteurs/liste/', views.capteur_list, name='capteur_list'),
    path('capteurs/creer/', views.capteur_create, name='capteur_create'),
    path('capteurs/<int:pk>/', views.capteur_detail, name='capteur_detail'),
    path('capteurs/<int:pk>/associer/', views.capteur_associate, name='capteur_associate'),
    path('capteurs/<int:pk>/modifier/', views.capteur_update, name='capteur_update'),
    path('capteurs/<int:pk>/supprimer/', views.capteur_delete, name='capteur_delete'),

    path('types-compteur/', views.TypeCompteurListView.as_view(), name='typecompteur_list'),
    path('types-compteur/ajouter/', views.TypeCompteurCreateView.as_view(), name='typecompteur_create'),
    path('types-compteur/<int:pk>/modifier/', views.TypeCompteurUpdateView.as_view(), name='typecompteur_update'),
    path('types-compteur/<int:pk>/supprimer/', views.TypeCompteurDeleteView.as_view(), name='typecompteur_delete'),

    path("sync/<int:compteur_id>/", views.sync_shelly_compteur_view, name="sync_shelly"),
    path("live/<int:compteur_id>/", views.shelly_live_data_view, name="live_data"),
    path("sync-all/", views.sync_all_compteurs_view, name="sync_all"),

    path("webhook/shelly/energy/", shelly_energy_webhook),
    path("webhook/shelly/status/", shelly_status_webhook),


]