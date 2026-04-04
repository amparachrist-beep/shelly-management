# apps/alertes/urls.py
from django.urls import path
from . import views

app_name = 'alertes'

urlpatterns = [
    # ============================================
    # ALERTES (Consultation et traitement)
    # ============================================
    path('', views.liste_alertes, name='liste'),
    path('mes-alertes/', views.mes_alertes, name='mes_alertes'),
    path('non-lues/', views.alertes_non_lues, name='non_lues'),
    path('<int:pk>/', views.detail_alerte, name='detail'),
    path('<int:pk>/lire/', views.marquer_comme_lue, name='marquer_lue'),
    path('<int:pk>/ignorer/', views.ignorer_alerte, name='ignorer'),

    # ============================================
    # RÈGLES D'ALERTE (Configuration par l'admin)
    # ============================================
    path('regles/', views.RegleAlerteListView.as_view(), name='regles_list'),
    path('regles/nouvelle/', views.RegleAlerteCreateView.as_view(), name='regles_creer'),
    path('regles/<int:pk>/modifier/', views.RegleAlerteUpdateView.as_view(), name='regles_modifier'),
    path('regles/<int:pk>/supprimer/', views.RegleAlerteDeleteView.as_view(), name='regles_supprimer'),
    path('regles/<int:pk>/activer/', views.activer_regle, name='regles_activer'),
    path('regles/<int:pk>/desactiver/', views.desactiver_regle, name='regles_desactiver'),

    # ============================================
    # STATISTIQUES ET DÉTECTION
    # ============================================
    path('statistiques/', views.statistiques_alertes, name='statistiques'),
    path('detection/', views.detection_automatique, name='detection'),

    # ============================================
    # WIDGETS AJAX
    # ============================================
    path('widget/recentes/', views.widget_alertes_recentes, name='widget_recentes'),
]