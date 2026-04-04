from django.urls import path
from . import views
from . import views_agence

app_name = 'menages'

urlpatterns = [
    # ==================== CRUD MÉNAGES ====================
    path('', views.MenageListView.as_view(), name='list'),
    path('create/', views.MenageCreateView.as_view(), name='create'),
    path('<int:pk>/', views.MenageDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.MenageUpdateView.as_view(), name='update'),

    # ==================== ACTIONS ====================
    path('<int:pk>/activer/', views.menage_activer, name='activer'),
    path('<int:pk>/desactiver/', views.menage_desactiver, name='desactiver'),
    path('<int:pk>/demenager/', views.menage_demenager, name='demenager'),
    path('<int:pk>/localisation/', views.update_localisation, name='update_localisation'),

    # ==================== VUES SPÉCIFIQUES ====================
    path('<int:pk>/compteurs/', views.MenageCompteursView.as_view(), name='compteurs'),
    path('<int:pk>/factures/', views.MenageFacturesView.as_view(), name='factures'),
    path('<int:pk>/consommation/', views.MenageConsommationView.as_view(), name='consommation'),
    path('<int:pk>/paiements/', views.MenagePaiementsView.as_view(), name='paiements'),

    # ==================== STATISTIQUES ====================
    path('stats/', views.StatsMenagesView.as_view(), name='stats'),

    # ==================== IMPORT/EXPORT ====================
    path('import/', views.import_menages, name='import'),
    path('export/csv/', views.export_menages_csv, name='export_csv'),

    # ==================== API SIMPLE POUR AJAX ====================
    path('api/search/', views.menage_search_api, name='search_api'),
    path('api/<int:pk>/stats/', views.menage_stats_api, name='stats_api'),
    path('api/<int:pk>/factures-impayees/', views.menage_factures_impayees_api, name='factures_impayees_api'),
    path('api/reverse-geocode-local/', views.reverse_geocode_local, name='reverse_geocode_local'),
    path('api/users/', views.get_available_users_json, name='available_users_json'),
    path('api/data/', views.menage_api_data, name='menage_api_data'),
    path('api/data/<int:pk>/', views.menage_api_detail, name='menage_api_detail'),
    path('api/types-habitation/', views.type_habitation_list_api, name='type_habitation_list_api'),

    path('agences/', views_agence.agence_list, name='agence_list'),
    path('agences/creer/', views_agence.agence_create, name='agence_create'),
    path('agences/<int:pk>/', views_agence.agence_detail, name='agence_detail'),
    path('agences/<int:pk>/modifier/', views_agence.agence_update, name='agence_update'),
    path('agences/<int:pk>/supprimer/', views_agence.agence_delete, name='agence_delete'),
]