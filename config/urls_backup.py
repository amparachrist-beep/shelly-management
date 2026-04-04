from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Admin Django (conservez-le pour l'administration)
    path('admin/', admin.site.urls),

    # Page d'accueil - redirige vers le dashboard approprié
    path('', RedirectView.as_view(pattern_name='dashboard:home'), name='home'),

    # Routes principales de l'application
    path('', include('apps.dashboard.urls'), name='dashboard'),

    # Authentification
    path('auth/', include('apps.users.urls')),

    # Routes par rôle avec namespace
   # path('admin-system/', include('apps.admin_system.urls', namespace='admin_system')),
    #path('agent/', include('apps.agent_terrain.urls', namespace='agent_terrain')),
    #path('client/', include('apps.client.urls', namespace='client')),

    # Routes fonctionnelles par module
    path('menages/', include('apps.menages.urls', namespace='menages')),
    path('compteurs/', include('apps.compteurs.urls', namespace='compteurs')),
    path('consommation/', include('apps.consommation.urls', namespace='consommation')),
    path('facturation/', include('apps.facturation.urls', namespace='facturation')),
    path('paiements/', include('apps.paiements.urls', namespace='paiements')),
    path('parametrage/', include('apps.parametrage.urls', namespace='parametrage')),
    path('alertes/', include('apps.alertes.urls', namespace='alertes')),
    path('supervision/', include('apps.supervision.urls', namespace='supervision')),

    # Support et autres
    path('support/', include('apps.support.urls', namespace='support')),

    # Webhooks externes (conservez si vous utilisez Shelly)
    path('webhooks/shelly/', include('apps.compteurs.webhooks_urls')),
]

# URLs de debug
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Ajouter debug toolbar si nécessaire
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]