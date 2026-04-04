from django.urls import path
from . import views
app_name = 'consommation'
urlpatterns = [
    # Listes et consultation
    path('', views.consommation_list, name='consommation_list'),
    path('<int:pk>/', views.consommation_detail, name='consommation_detail'),
    path('compteur/<int:compteur_id>/periode/<str:periode_str>/',
         views.consommation_compteur_periode, name='consommation_compteur_periode'),

    # Création et modification
    path('creer/', views.consommation_create, name='consommation_create'),
    path('<int:pk>/modifier/', views.consommation_update, name='consommation_update'),
    path('relever-manuel/', views.relever_manuel, name='relever_manuel'),

    # Validation et correction
    path('<int:pk>/valider/', views.valider_consommation, name='valider_consommation'),
    path('<int:pk>/anomalie/', views.marquer_anomalie, name='marquer_anomalie'),
    path('<int:pk>/corriger/', views.corriger_releve, name='corriger_releve'),

    # Import/Export
    path('import/csv/', views.import_csv, name='import_csv'),
    path('import/csv/resultats/', views.import_csv_resultats, name='import_csv_resultats'),
    path('export/csv/', views.export_csv, name='export_csv'),

    # Statistiques
    path('stats/mensuelles/', views.stats_mensuelles, name='stats_mensuelles'),
    path('stats/comparatives/', views.stats_comparatives, name='stats_comparatives'),
    path('graphique/mensuel/<int:compteur_id>/', views.graphique_mensuel, name='graphique_mensuel'),

    # Vues AJAX
    path('ajax/en-attente/', views.consommation_en_attente_count, name='consommation_en_attente_count'),
    path('ajax/recentes/', views.consommation_recente, name='consommation_recente'),

    # Vues client
    path('client/mes-consommations/', views.client_consommation, name='client_consommation'),
    path('client/graphique/<int:compteur_id>/',
         views.client_graphique_consommation, name='client_graphique_consommation'),
    path('<int:pk>/', views.consommation_detail, name='detail'),
]