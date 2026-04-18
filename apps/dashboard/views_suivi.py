from django.views.generic import TemplateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
import json

from apps.menages.models import Menage
from apps.compteurs.models import Compteur
from apps.parametrage.models import Departement, Localite
from apps.dashboard.services.suivi_services import SuiviService
from apps.dashboard.utils import get_date_range_from_request
from apps.users.mixins import AdminRequiredMixin, AgentRequiredMixin, ClientRequiredMixin
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

class SuiviGlobalView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """
    Vue de suivi global pour l'administrateur
    """
    template_name = 'dashboard/suivi/global.html'

    @method_decorator(cache_page(60 * 5))  # Cache 5 minutes
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Récupération des dates
        date_debut, date_fin = get_date_range_from_request(self.request)

        # Récupération des données avec cache
        cache_key = f"suivi_global_{date_debut}_{date_fin}"
        data = cache.get(cache_key)

        if not data:
            data = SuiviService.get_global_stats(date_debut, date_fin)
            cache.set(cache_key, data, 300)  # 5 minutes

        # Sérialisation pour les graphiques
        evolution_labels = [d['mois'].strftime('%b %Y') for d in data['evolution']]
        evolution_values = [float(d['total'] or 0) for d in data['evolution']]

        context.update({
            **data,
            'evolution_labels': json.dumps(evolution_labels),
            'evolution_values': json.dumps(evolution_values),
            'page_title': 'Suivi Global des Consommations',
            'current_page': 'suivi_global'
        })

        return context


class SuiviDepartementView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Vue de suivi par département
    Admin : tous les départements
    Agent : uniquement son département (à adapter selon votre modèle)
    Client : pas d'accès
    """
    model = Departement
    template_name = 'dashboard/suivi/departement.html'
    context_object_name = 'departement'
    pk_url_kwarg = 'pk'

    def test_func(self):
        user = self.request.user

        # Admin a toujours accès
        if user.is_admin:
            return True

        # Agent : à adapter selon votre modèle de données
        # Si l'agent est rattaché à un département spécifique
        if user.is_agent:
            departement = self.get_object()
            # Décommentez et adaptez selon votre modèle
            # return user.agent_profile.departement == departement
            return False  # Pour l'instant, les agents n'ont pas accès

        # Client n'a pas accès
        return False

    def handle_no_permission(self):
        messages.error(self.request, "Vous n'avez pas accès à ce département.")
        return redirect('dashboard:index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date_debut, date_fin = get_date_range_from_request(self.request)

        # Cache par département
        cache_key = f"suivi_dept_{self.object.pk}_{date_debut}_{date_fin}"
        data = cache.get(cache_key)

        if not data:
            data = SuiviService.get_departement_stats(
                self.object.pk,
                date_debut,
                date_fin
            )
            cache.set(cache_key, data, 300)

        # Préparation des données pour les graphiques
        evolution_labels = [d['mois'].strftime('%b %Y') for d in data['evolution']]
        evolution_values = [float(d['total'] or 0) for d in data['evolution']]

        # ✅ CORRECTION : data['localites'] contient des dictionnaires
        localite_labels = [l['nom'] for l in data['localites'][:10]]
        localite_values = [float(l['total_consommation'] or 0) for l in data['localites'][:10]]

        context.update({
            **data,
            'evolution_labels': json.dumps(evolution_labels),
            'evolution_values': json.dumps(evolution_values),
            'localite_labels': json.dumps(localite_labels),
            'localite_values': json.dumps(localite_values),
            'page_title': f'Suivi - {self.object.nom}',
            'current_page': 'suivi_departement'
        })

        return context


class SuiviLocaliteView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """
    Vue de suivi par localité
    Admin : toutes les localités
    Agent : uniquement sa localité
    Client : pas d'accès
    """
    model = Localite
    template_name = 'dashboard/suivi/localite.html'
    context_object_name = 'localite'
    pk_url_kwarg = 'pk'

    def test_func(self):
        user = self.request.user

        # Admin a toujours accès
        if user.is_admin:
            return True

        # Agent : vérifier que c'est sa localité
        if user.is_agent:
            localite = self.get_object()
            return user.agence.localite_id == localite.pk if user.agence else False

        return False

    def handle_no_permission(self):
        messages.error(self.request, "Vous n'avez pas accès à cette localité.")
        return redirect('dashboard:index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date_debut, date_fin = get_date_range_from_request(self.request)

        data = SuiviService.get_localite_stats(
            self.object.pk,
            date_debut,
            date_fin
        )

        # Préparation des graphiques
        evolution_labels = [d['mois'].strftime('%b %Y') for d in data['evolution']]
        evolution_values = [float(d['total'] or 0) for d in data['evolution']]

        context.update({
            **data,
            'evolution_labels': json.dumps(evolution_labels),
            'evolution_values': json.dumps(evolution_values),
            'page_title': f'Suivi - {self.object.nom}',
            'current_page': 'suivi_localite'
        })

        return context

class SuiviMenageView(LoginRequiredMixin, DetailView):
    """
    Vue de suivi par ménage
    Client : uniquement son ménage
    Agent : ménages de sa localité
    Admin : tous les ménages
    """
    model = Menage
    template_name = 'dashboard/suivi/menage.html'
    context_object_name = 'menage'
    pk_url_kwarg = 'pk'

    def dispatch(self, request, *args, **kwargs):
        menage = get_object_or_404(Menage, pk=kwargs['pk'])

        if request.user.is_client:
            # Client : vérifier que c'est son ménage
            if menage.utilisateur != request.user:
                return self.handle_no_permission()
        elif request.user.is_agent:
            # Agent : accès à tous les ménages (pas de profil agent séparé)
            # Si vous voulez restreindre par localité plus tard, ajoutez un champ
            # 'localite' sur CustomUser et filtrez ici
            pass
        elif not request.user.is_admin:
            return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date_debut, date_fin = get_date_range_from_request(self.request)

        data = SuiviService.get_menage_stats(
            self.object.pk,
            date_debut,
            date_fin
        )

        # Graphiques
        evolution_labels = [d['mois'].strftime('%b %Y') for d in data['evolution']]
        evolution_values = [float(d['total'] or 0) for d in data['evolution']]

        context.update({
            **data,
            'evolution_labels': json.dumps(evolution_labels),
            'evolution_values': json.dumps(evolution_values),
            'page_title': f'Suivi - {self.object.nom_menage}',
            'current_page': 'suivi_menage'
        })

        return context


class SuiviCompteurView(LoginRequiredMixin, DetailView):
    """
    Vue de suivi par compteur
    """
    model = Compteur
    template_name = 'dashboard/suivi/compteur.html'
    context_object_name = 'compteur'
    pk_url_kwarg = 'pk'

    def dispatch(self, request, *args, **kwargs):
        compteur = get_object_or_404(Compteur, pk=kwargs['pk'])

        if request.user.is_client:
            if compteur.menage.utilisateur != request.user:
                return self.handle_no_permission()
        # Puisque agent est rattaché à une agence, et l'agence à une localité :
        elif request.user.is_agent:
            if compteur.menage.localite != request.user.agence.localite:
                return self.handle_no_permission()

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date_debut, date_fin = get_date_range_from_request(self.request)

        data = SuiviService.get_compteur_stats(
            self.object.pk,
            date_debut,
            date_fin
        )

        # Graphiques
        evolution_labels = [d['periode'].strftime('%b %Y') for d in data['evolution']]
        evolution_values = [float(d['consommation'] or 0) for d in data['evolution']]

        context.update({
            **data,
            'evolution_labels': json.dumps(evolution_labels),
            'evolution_values': json.dumps(evolution_values),
            'page_title': f'Suivi - Compteur {self.object.matricule_compteur}',
            'current_page': 'suivi_compteur'
        })

        return context


class SuiviJournalierView(LoginRequiredMixin, DetailView):
    """
    Vue de suivi journalier détaillé
    """
    model = Compteur
    template_name = 'dashboard/suivi/journalier.html'
    context_object_name = 'compteur'
    pk_url_kwarg = 'pk'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Date du jour ou date spécifiée
        try:
            date = self.request.GET.get('date')
            if date:
                from datetime import datetime
                date = datetime.strptime(date, '%Y-%m-%d').date()
            else:
                from django.utils import timezone
                date = timezone.now().date()
        except (ValueError, TypeError):
            from django.utils import timezone
            date = timezone.now().date()

        data = SuiviService.get_journalier_stats(
            self.object.pk,
            date
        )

        # Graphique horaire (simulé pour l'exemple)
        heures = list(range(24))
        conso_horaire = []
        if data['journalier']:
            # Simulation d'une courbe de charge
            base = data['journalier'].consommation_kwh / 24
            for h in heures:
                if 6 <= h <= 9 or 18 <= h <= 21:
                    conso_horaire.append(base * 1.5)  # Heures de pointe
                elif 22 <= h or h <= 5:
                    conso_horaire.append(base * 0.6)  # Heures creuses
                else:
                    conso_horaire.append(base)  # Heures normales

        context.update({
            **data,
            'heures': json.dumps(heures),
            'conso_horaire': json.dumps(conso_horaire),
            'page_title': f'Suivi Journalier - {date.strftime("%d/%m/%Y")}',
            'current_page': 'suivi_journalier'
        })

        return context



from django.views.generic import ListView
from apps.parametrage.models import Departement, Localite


class SuiviDepartementListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """
    Liste des départements pour le suivi
    """
    model = Departement
    template_name = 'dashboard/suivi/departement_list.html'
    context_object_name = 'departements'
    paginate_by = 20

    def get_queryset(self):
        return Departement.objects.all().order_by('nom')


class SuiviLocaliteListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """
    Liste des localités pour le suivi
    """
    model = Localite
    template_name = 'dashboard/suivi/localite_list.html'
    context_object_name = 'localites'
    paginate_by = 20

    def get_queryset(self):
        return Localite.objects.select_related('departement').all().order_by('departement__nom', 'nom')


class SuiviAgentMenagesView(LoginRequiredMixin, AgentRequiredMixin, ListView):
    """
    Liste des ménages assignés à l'agent
    """
    model = Menage
    template_name = 'dashboard/suivi/agent_menages.html'
    context_object_name = 'menages'
    paginate_by = 20

    def get_queryset(self):
        return Menage.objects.filter(
            agent=self.request.user,
            statut='ACTIF'
        ).select_related(
            'localite',  # Pour avoir localite.nom
            'localite__departement',  # Pour avoir departement.nom
            'type_habitation'  # Optionnel
        ).prefetch_related(
            'compteurs'  # Pour compter les compteurs
        ).order_by('nom_menage')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Mes ménages assignés'

        # Ajouter le nombre de compteurs pour chaque ménage
        for menage in context['menages']:
            menage.nb_compteurs = menage.compteurs.count()

        return context