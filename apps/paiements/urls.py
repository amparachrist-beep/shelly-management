from django.urls import path
from . import views

app_name = 'paiements'

urlpatterns = [
    # ==================== PAIEMENTS ====================
    path('', views.PaiementListView.as_view(), name='list'),
    path('create/', views.PaiementCreateView.as_view(), name='create'),
    path('mobile-money/', views.PaiementMobileMoneyView.as_view(), name='mobile_money'),
    path('<int:pk>/', views.PaiementDetailView.as_view(), name='detail'),
    path('<int:pk>/update/', views.PaiementUpdateView.as_view(), name='update'),
    path('<int:pk>/valider/', views.valider_paiement, name='valider'),
    path('<int:pk>/rejeter/', views.rejeter_paiement, name='rejeter'),

    # ==================== STATISTIQUES ====================
    path('stats/', views.StatsPaiementsView.as_view(), name='stats'),
    path('rapport-journalier/', views.rapport_journalier, name='rapport_journalier'),


    # ==================== EXPORT ====================
    path('export/csv/', views.export_paiements_csv, name='export_csv'),

    # ==================== API SIMPLE POUR AJAX ====================
    path('api/stats/', views.paiement_stats_api, name='stats_api'),
    path('api/facture/<int:facture_id>/', views.facture_info_api, name='facture_info_api'),
]