from django.urls import path
from . import views_suivi

app_name = 'dashboard_suivi'

urlpatterns = [
    # Vue globale
    path('',
         views_suivi.SuiviGlobalView.as_view(),
         name='suivi_global'),

    # Vues par département
    path('departement/<int:pk>/',
         views_suivi.SuiviDepartementView.as_view(),
         name='suivi_departement'),

    # Vues par localité
    path('localite/<int:pk>/',
         views_suivi.SuiviLocaliteView.as_view(),
         name='suivi_localite'),

    # Vues par ménage
    path('menage/<int:pk>/',
         views_suivi.SuiviMenageView.as_view(),
         name='suivi_menage'),

    # Vues par compteur
    path('compteur/<int:pk>/',
         views_suivi.SuiviCompteurView.as_view(),
         name='suivi_compteur'),

    # Vue journalière
    path('journalier/<int:pk>/',
         views_suivi.SuiviJournalierView.as_view(),
         name='suivi_journalier'),

    path('departements/', views_suivi.SuiviDepartementListView.as_view(), name='suivi_departement_list'),
    path('localites/', views_suivi.SuiviLocaliteListView.as_view(), name='suivi_localite_list'),
    path('mes-menages/', views_suivi.SuiviAgentMenagesView.as_view(), name='suivi_agent_menages'),
]