from django.urls import path
from . import views

app_name = 'parametrage'

urlpatterns = [
    # ==================== DASHBOARD ====================
    path('', views.ParametrageDashboardView.as_view(), name='dashboard'),

    # ==================== DÉPARTEMENTS ====================
    path('departements/', views.DepartementListView.as_view(), name='departements_list'),
    path('departements/create/', views.DepartementCreateView.as_view(), name='departement_create'),
    path('departements/<int:pk>/', views.DepartementDetailView.as_view(), name='departement_detail'),
    path('departements/<int:pk>/update/', views.DepartementUpdateView.as_view(), name='departement_update'),
    # ➕ AJOUT : suppression
    path('departements/<int:pk>/delete/', views.DepartementDeleteView.as_view(), name='departement_delete'),
    # ==================== LOCALITÉS ====================
    path('localites/', views.LocaliteListView.as_view(), name='localites_list'),
    path('localites/create/', views.LocaliteCreateView.as_view(), name='localite_create'),
    path('localites/<int:pk>/', views.LocaliteDetailView.as_view(), name='localite_detail'),
    path('localites/<int:pk>/update/', views.LocaliteUpdateView.as_view(), name='localite_update'),
    path('localites/<int:pk>/delete/', views.LocaliteDeleteView.as_view(), name='localite_delete'),
    # ==================== TARIFICATIONS ====================

    path('tarifications/', views.tarification_list, name='tarification_list'),
    path('tarifications/create/', views.tarification_create, name='tarification_create'),
    path('tarifications/<int:pk>/edit/', views.tarification_edit, name='tarification_edit'),
    path('tarifications/<int:pk>/delete/', views.tarification_delete, name='tarification_delete'),
    path('tarifications/<int:pk>/duplicate/', views.tarification_duplicate, name='tarification_duplicate'),
    path('tarifications/<int:pk>/', views.tarification_detail, name='tarification_detail'),

    # Configuration
    path('configurations/', views.configuration_list, name='configuration_list'),
    path('configurations/create/', views.configuration_create, name='configuration_create'),
    # ==================== ZONES ====================
    path('zones/', views.ZoneListView.as_view(), name='zones_list'),
    #path('zones/create/', views.ZoneCreateView.as_view(), name='zone_create'),
    #path('zones/<int:pk>/update/', views.ZoneUpdateView.as_view(), name='zone_update'),

    # ==================== GÉOLOCALISATION ====================
    path('geocoding/reverse/', views.geocoding_reverse, name='geocoding_reverse'),
    path('map/departements/', views.carte_departements, name='map_departements'),

    # ==================== IMPORT/EXPORT ====================
    path('import/geodata/', views.import_geodata, name='import_geodata'),
    path('export/geojson/', views.export_geojson, name='export_geojson'),

    # ==================== API SIMPLE POUR AJAX ====================
    path('api/localites/by-departement/<int:departement_id>/',
         views.localites_by_departement, name='localites_by_departement'),
    path('api/localites/search/', views.search_localites_api, name='search_localites_api'),
    path('api/localites/', views.localites_api, name='localites_api'),  # AJOUTÉE
    path('api/tarifications/actives/', views.active_tarifications_api, name='active_tarifications_api'),
    path('api/tarifications/actives/', views.tarifications_actives_api, name='tarifications_actives_api'),


    path('types-habitation/', views.TypeHabitationListView.as_view(), name='typehabitation_list'),
    path('types-habitation/ajouter/', views.TypeHabitationCreateView.as_view(), name='typehabitation_create'),
    path('types-habitation/<int:pk>/modifier/', views.TypeHabitationUpdateView.as_view(), name='typehabitation_update'),
    path('types-habitation/<int:pk>/supprimer/', views.TypeHabitationDeleteView.as_view(),
         name='typehabitation_delete'),


]