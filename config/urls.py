from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView

urlpatterns = [
    # Admin Django
    path('admin/', admin.site.urls),

    # Authentication URLs - PAGE DE LOGIN COMME PAGE D'ACCUEIL
    path('', auth_views.LoginView.as_view(template_name='authentication/login.html'), name='login'),
    path('login/', auth_views.LoginView.as_view(template_name='authentication/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('register/', include('apps.users.urls')),  # Pour l'inscription si nécessaire

    # Dashboard URLs (après authentification)
    path('dashboard/', include('apps.dashboard.urls')),

    # URLs des différents modules
    path('menages/', include('apps.menages.urls')),
    path('compteurs/', include('apps.compteurs.urls')),
    path('consommation/', include('apps.consommation.urls')),
    path('facturation/', include('apps.facturation.urls')),
    path('paiements/', include('apps.paiements.urls')),
    path('parametrage/', include('apps.parametrage.urls')),
    path('alertes/', include('apps.alertes.urls')),
    path('audit/', include('apps.audit.urls')),
# config/urls.py
    path('dashboard/suivi/', include('apps.dashboard.urls_suivi')),

    # PWA — manifest et service worker (doivent être à la racine /)
    path('manifest.json', TemplateView.as_view(
        template_name='manifest.json',
        content_type='application/manifest+json'
    ), name='pwa-manifest'),

    path('sw.js', TemplateView.as_view(
        template_name='sw.js',
        content_type='application/javascript'
    ), name='pwa-sw'),
]

# URLs de debug et fichiers statiques
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)