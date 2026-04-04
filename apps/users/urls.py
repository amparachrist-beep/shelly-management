from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = 'users'

urlpatterns = [
    # ==================== AUTHENTIFICATION ====================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # ==================== PROFIL UTILISATEUR ====================
    path('profile/', views.profile, name='profile'),
    path('profile/update/', views.ProfileUpdateView.as_view(), name='profile_update'),
    path('profile/photo/update/', views.update_profile_photo, name='update_profile_photo'),
    path('profile/password/change/', views.change_password, name='change_password'),

    # ==================== ✅ GESTION DES UTILISATEURS (NOUVELLES VUES) ====================
    # CES URLS DOIVENT ÊTRE AVANT agents/ POUR ÉVITER LES CONFLITS !
    path('', views.UserListView.as_view(), name='user_list'),               # /
    path('ajouter/', views.UserCreateView.as_view(), name='user_create'),   # /ajouter/
    path('<int:pk>/', views.UserDetailView.as_view(), name='user_detail'),  # /123/
    path('<int:pk>/modifier/', views.UserUpdateView.as_view(), name='user_update'),  # /123/modifier/
    path('<int:pk>/supprimer/', views.UserDeleteView.as_view(), name='user_delete'),  # /123/supprimer/
    path('<int:pk>/toggle/', views.user_toggle_active, name='user_toggle'),  # /123/toggle/
    path('<int:pk>/suspendre/', views.user_suspend, name='user_suspend'),    # /123/suspendre/
    path('<int:pk>/reactiver/', views.user_reactivate, name='user_reactivate'),  # /123/reactiver/

    # ==================== GESTION DES AGENTS (ADMIN SEULEMENT) ====================
    # MAINTENANT PLACÉES APRÈS - avec préfixe 'agents/'
    path('agents/', views.AgentListView.as_view(), name='agents_list'),
    path('agents/create/', views.AgentCreateView.as_view(), name='agent_create'),
    path('agents/<int:pk>/', views.AgentDetailView.as_view(), name='agent_detail'),
    path('agents/<int:pk>/update/', views.AgentUpdateView.as_view(), name='agent_update'),
    path('agents/<int:pk>/toggle/', views.toggle_agent_status, name='agent_toggle'),

    # ==================== STATISTIQUES ====================
    path('stats/', views.user_stats_view, name='stats'),

    # ==================== VUES POUR AJAX/API ====================
    path('update-position/', views.update_position_view, name='update_position'),
    path('api/users/', views.get_users_json, name='users_json'),
    path('api/users/', views.get_available_users_json, name='available_users_json'),

    # ==================== MOT DE PASSE OUBLIÉ ====================
    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='authentication/password_reset.html',
             email_template_name='authentication/password_reset_email.html',
             subject_template_name='authentication/password_reset_subject.txt',
             success_url='/auth/password-reset/done/'
         ),
         name='password_reset'),
    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='authentication/password_reset_done.html'
         ),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='authentication/password_reset_confirm.html',
             success_url='/auth/password-reset-complete/'
         ),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='authentication/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]