from django.urls import path
from . import views

app_name = 'facturation'

urlpatterns = [
    # ==================== CRUD FACTURES ====================
    path('', views.FactureListView.as_view(), name='list'),
    path('create/', views.FactureCreateView.as_view(), name='create'),
    path('<int:pk>/', views.FactureDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.FactureUpdateView.as_view(), name='update'),

# ==================== VUE CLIENT ====================
    path('mes-factures/', views.client_factures_list, name='client_factures_list'),  # AJOUTEZ CECI

    # ==================== ACTIONS ====================
    path('<int:pk>/emettre/', views.facture_emettre, name='emettre'),
    path('<int:pk>/annuler/', views.facture_annuler, name='annuler'),
    path('<int:pk>/relancer/', views.facture_relancer, name='relancer'),
    path('<int:pk>/generer-pdf/', views.facture_generer_pdf, name='generer_pdf'),
    path('<int:pk>/telecharger-pdf/', views.facture_telecharger_pdf, name='telecharger_pdf'),

    # ==================== GÉNÉRATION ====================
    path('generer/', views.GenererFacturesView.as_view(), name='generer'),
    path('batch/<int:pk>/', views.BatchDetailView.as_view(), name='batch_detail'),

    # ==================== STATISTIQUES ====================
    path('stats/', views.StatsFacturesView.as_view(), name='stats'),
    path('stats/recouvrement/', views.StatsRecouvrementView.as_view(), name='stats_recouvrement'),

    # ==================== EXPORT ====================
    path('export/csv/', views.export_factures_csv, name='export_csv'),

    # ==================== API SIMPLE POUR AJAX ====================
    path('api/stats/', views.facture_stats_api, name='stats_api'),
    path('api/impayees/', views.facture_impayees_api, name='impayees_api'),
    path('api/<int:facture_id>/', views.facture_info_api, name='facture_info_api'),

# apps/facturation/urls.py - À ajouter
    path('impayes/', views.DossierImpayeListView.as_view(), name='impaye_list'),
    path('impayes/<int:pk>/', views.DossierImpayeDetailView.as_view(), name='impaye_detail'),
    path('impayes/<int:pk>/traiter/', views.traiter_impaye, name='traiter_impaye'),
# apps/facturation/urls.py - Ajoutez cette ligne
    path('impayes/creer/', views.DossierImpayeCreateView.as_view(), name='impaye_create'),

# apps/facturation/urls.py - À ajouter
    path('periodes/', views.PeriodeFacturationListView.as_view(), name='periode_list'),
    path('periodes/creer/', views.PeriodeFacturationCreateView.as_view(), name='periode_create'),
    path('periodes/<int:pk>/modifier/', views.PeriodeFacturationUpdateView.as_view(), name='periode_update'),
]