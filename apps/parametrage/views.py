from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
import csv, json
from datetime import datetime
from .models import Departement, Localite, TypeTarification, Zone
from .forms import (
    DepartementForm, LocaliteForm, ZoneForm,
    CalculConsommationForm, LocaliteSearchForm, ImportGeoDataForm
)


# ==================== DÉCORATEURS DE PERMISSION ====================

def admin_required(view_func):
    """Décorateur pour vérifier si l'utilisateur est admin"""

    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.role == 'ADMIN':
            messages.error(request, "Accès refusé. Administrateur requis.")
            return redirect('dashboard:home')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class AdminRequiredMixin(UserPassesTestMixin):
    """Mixin pour vérifier si l'utilisateur est admin"""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'ADMIN'


# ==================== VUES DE DASHBOARD ====================

class ParametrageDashboardView(LoginRequiredMixin, AdminRequiredMixin, TemplateView):
    """Tableau de bord du paramétrage"""
    template_name = 'parametrage/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            'title': 'Paramétrage du Système',
            'icon': 'fas fa-cogs',
            'stats': self.get_stats(),
            'recent_activities': self.get_recent_activities(),
        })
        return context

    def get_stats(self):
        """Récupérer les statistiques"""
        return [
            {
                'title': 'Départements',
                'value': Departement.objects.count(),
                'icon': 'fas fa-map',
                'color': 'primary',
                'url': 'parametrage:departements_list'
            },
            {
                'title': 'Localités',
                'value': Localite.objects.count(),
                'icon': 'fas fa-map-marker-alt',
                'color': 'success',
                'url': 'parametrage:localites_list'
            },
            {
                'title': 'Tarifications',
                'value': TypeTarification.objects.count(),
                'icon': 'fas fa-money-bill-wave',
                'color': 'info',
                'url': 'parametrage:tarifs_list'
            },
            {
                'title': 'Tarifs Actifs',
                'value': TypeTarification.objects.filter(actif=True).count(),
                'icon': 'fas fa-check-circle',
                'color': 'warning',
                'url': 'parametrage:tarifs_actifs'
            },
        ]

    def get_recent_activities(self):
        """Récupérer les activités récentes"""
        return [
            {'type': 'tarif', 'message': 'Nouvelle tarification créée', 'date': '2024-01-15'},
            {'type': 'localite', 'message': 'Localité mise à jour', 'date': '2024-01-14'},
            {'type': 'departement', 'message': 'Département ajouté', 'date': '2024-01-13'},
        ]


# ==================== VUES POUR DÉPARTEMENTS ====================

class DepartementListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Liste des départements"""
    model = Departement
    template_name = 'parametrage/departements_list.html'
    context_object_name = 'object_list'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Départements',
            'icon': 'fas fa-map',
            'headers': ['Nom', 'Code', 'Région', 'Coordonnées', 'Date création'],
            'create_url': 'parametrage:departement_create',
            'detail_url': 'parametrage:departement_detail',
            'update_url': 'parametrage:departement_update',
        })
        return context


class DepartementCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Création d'un département"""
    model = Departement
    form_class = DepartementForm
    template_name = 'parametrage/departement_form.html'
    success_url = reverse_lazy('parametrage:departements_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Nouveau Département',
            'icon': 'fas fa-map',
            'submit_text': 'Créer le département',
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, "Département créé avec succès.")
        return super().form_valid(form)


class DepartementDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """Détail d'un département"""
    model = Departement
    template_name = 'gestion/detail_template.html'
    context_object_name = 'object'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Département: {self.object.nom}',
            'icon': 'fas fa-map',
            'update_url': 'parametrage:departement_update',
            'list_url': 'parametrage:departements_list',
            'related_tables': [
                {
                    'title': 'Localités dans ce département',
                    'data': Localite.objects.filter(departement=self.object),
                    'headers': ['Nom', 'Type', 'Code Postal', 'Coordonnées'],
                    'create_url': 'parametrage:localite_create'
                }
            ]
        })
        return context


class DepartementUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    """Modification d'un département"""
    model = Departement
    form_class = DepartementForm
    template_name = 'parametrage/departement_form.html'
    success_url = reverse_lazy('parametrage:departements_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Modifier {self.object.nom}',
            'icon': 'fas fa-edit',
            'submit_text': 'Modifier',
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, "Département modifié avec succès.")
        return super().form_valid(form)


# ==================== VUES POUR LOCALITÉS ====================

class LocaliteListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Liste des localités"""
    model = Localite
    template_name = 'parametrage/localite_list.html'
    context_object_name = 'object_list'
    paginate_by = 20

    def get_queryset(self):
        queryset = Localite.objects.select_related('departement')

        # Filtres
        search = self.request.GET.get('search', '')
        departement_id = self.request.GET.get('departement', '')
        type_localite = self.request.GET.get('type_localite', '')

        if search:
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(code_postal__icontains=search) |
                Q(google_place_id__icontains=search)
            )

        if departement_id:
            queryset = queryset.filter(departement_id=departement_id)

        if type_localite:
            queryset = queryset.filter(type_localite=type_localite)

        return queryset.order_by('nom')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Localités',
            'icon': 'fas fa-map-marker-alt',
            'headers': ['Nom', 'Type', 'Département', 'Code Postal', 'Coordonnées'],
            'create_url': 'parametrage:localite_create',
            'detail_url': 'parametrage:localite_detail',
            'update_url': 'parametrage:localite_update',
            'show_filters': True,
            'form': LocaliteSearchForm(self.request.GET),
        })
        return context


class LocaliteCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    """Création d'une localité"""
    model = Localite
    form_class = LocaliteForm
    template_name = 'parametrage/localite_form.html'
    success_url = reverse_lazy('parametrage:localites_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Nouvelle Localité',
            'icon': 'fas fa-map-marker-alt',
            'submit_text': 'Créer la localité',
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, "Localité créée avec succès.")
        return super().form_valid(form)


class LocaliteDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """Détail d'une localité"""
    model = Localite
    template_name = 'gestion/detail_template.html'
    context_object_name = 'object'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Localité: {self.object.nom}',
            'icon': 'fas fa-map-marker-alt',
            'update_url': 'parametrage:localite_update',
            'list_url': 'parametrage:localites_list',
        })
        return context


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import TypeTarification, ConfigurationTarifaire
from .forms import TypeTarificationFullForm, ConfigurationTarifaireForm


@login_required
def tarification_list(request):
    """Liste des types de tarification"""
    tarifications = TypeTarification.objects.all().order_by('-date_effet')
    return render(request, 'parametrage/tarification_list.html', {
        'tarifs': tarifications
    })


@login_required
def tarification_create(request):
    """Création d'un nouveau type de tarification"""
    if request.method == 'POST':
        form = TypeTarificationFullForm(request.POST)
        if form.is_valid():
            tarification = form.save()
            messages.success(request, f"Tarification {tarification.code} créée avec succès!")
            return redirect('parametrage:tarification_list')
    else:
        form = TypeTarificationFullForm()

    return render(request, 'parametrage/tarification_form.html', {
        'form': form,
        'title': 'Nouveau type de tarification',
        'submit_text': 'Créer'
    })


@login_required
def tarification_edit(request, pk):
    """Modification d'un type de tarification"""
    tarification = get_object_or_404(TypeTarification, pk=pk)

    if request.method == 'POST':
        form = TypeTarificationFullForm(request.POST, instance=tarification)
        if form.is_valid():
            tarification = form.save()
            messages.success(request, f"Tarification {tarification.code} modifiée avec succès!")
            return redirect('parametrage:tarification_list')
    else:
        form = TypeTarificationFullForm(instance=tarification)

    return render(request, 'parametrage/tarification_form.html', {
        'form': form,
        'title': f'Modifier {tarification.code}',
        'submit_text': 'Enregistrer'
    })


@login_required
def tarification_delete(request, pk):
    """Suppression d'un type de tarification"""
    tarification = get_object_or_404(TypeTarification, pk=pk)

    if request.method == 'POST':
        code = tarification.code
        tarification.delete()
        messages.success(request, f"Tarification {code} supprimée avec succès!")
        return redirect('parametrage:tarification_list')

    return render(request, 'parametrage/tarification_confirm_delete.html', {
        'tarification': tarification
    })


@login_required
def tarification_duplicate(request, pk):
    """Dupliquer une tarification existante"""
    original = get_object_or_404(TypeTarification, pk=pk)

    if request.method == 'POST':
        # Créer une copie
        nouvelle = TypeTarification.objects.get(pk=original.pk)
        nouvelle.pk = None
        nouvelle.code = f"{original.code}_COPY"
        nouvelle.nom = f"{original.nom} (Copie)"
        nouvelle.date_effet = timezone.now().date()
        nouvelle.actif = True
        nouvelle.save()

        # Copier les tranches
        for tranche in original.tranches.all():
            tranche.pk = None
            tranche.tarification = nouvelle
            tranche.save()

        # Copier les taxes
        for taxe in original.taxes.filter(active=True):
            taxe.pk = None
            taxe.tarification = nouvelle
            taxe.save()

        messages.success(request, f"Tarification dupliquée avec succès! Nouveau code: {nouvelle.code}")
        return redirect('tarification_edit', pk=nouvelle.pk)

    return render(request, 'parametrage/tarification_confirm_duplicate.html', {
        'original': original
    })


@login_required
def configuration_list(request):
    """Liste des configurations tarifaires"""
    configs = ConfigurationTarifaire.objects.all().select_related('tarification')
    return render(request, 'parametrage/configuration_list.html', {
        'configs': configs
    })


@login_required
def configuration_create(request):
    """Création d'une configuration"""
    if request.method == 'POST':
        form = ConfigurationTarifaireForm(request.POST)
        if form.is_valid():
            config = form.save()
            messages.success(request, f"Configuration pour {config.pays} créée avec succès!")
            return redirect('configuration_list')
    else:
        form = ConfigurationTarifaireForm()

    return render(request, 'parametrage/configuration_form.html', {
        'form': form,
        'title': 'Nouvelle configuration',
        'submit_text': 'Créer'
    })


@login_required
@admin_required
def calculer_montant(request, pk):
    """Calculer le montant pour une consommation"""
    tarif = get_object_or_404(TypeTarification, pk=pk)

    if request.method == 'POST':
        form = CalculConsommationForm(request.POST)
        if form.is_valid():
            consommation = form.cleaned_data['consommation_kwh']
            montant = tarif.calculer_montant(float(consommation))
            total = montant + float(tarif.abonnement_mensuel)

            return render(request, 'parametrage/calcul_result.html', {
                'tarif': tarif,
                'consommation': consommation,
                'montant': montant,
                'abonnement': tarif.abonnement_mensuel,
                'total': total,
            })

    return redirect('parametrage:tarif_detail', pk=pk)


# ==================== VUES POUR ZONES ====================

class ZoneListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Liste des zones"""
    model = Zone
    template_name = 'gestion/list_template.html'
    context_object_name = 'object_list'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Zones',
            'icon': 'fas fa-layer-group',
            'headers': ['Nom', 'Département', 'Statut'],
            'create_url': 'parametrage:zone_create',
            'update_url': 'parametrage:zone_update',
        })
        return context


# ==================== VUES POUR GÉOLOCALISATION ====================

@login_required
@admin_required
def geocoding_reverse(request):
    """Géocodage inversé"""
    if request.method == 'POST':
        lat = request.POST.get('latitude')
        lng = request.POST.get('longitude')

        if lat and lng:
            # Simuler l'appel API (en production, utiliser Google Maps API)
            # Vous pouvez utiliser requests ou googlemaps library
            context = {
                'formatted_address': f"Lat: {lat}, Lng: {lng}",
                'place_id': 'simulated_place_id',
                'latitude': lat,
                'longitude': lng,
            }
            return render(request, 'parametrage/geocoding_result.html', context)

    return render(request, 'parametrage/geocoding_reverse.html')


@login_required
@admin_required
def carte_departements(request):
    """Carte des départements"""
    departements = Departement.objects.all()
    return render(request, 'parametrage/map_departements.html', {
        'departements': departements,
        'title': 'Carte des Départements'
    })


# ==================== VUES POUR IMPORT/EXPORT ====================

@login_required
@admin_required
def import_geodata(request):
    """Importation de données géographiques"""
    if request.method == 'POST':
        form = ImportGeoDataForm(request.POST, request.FILES)
        if form.is_valid():
            fichier = form.cleaned_data['fichier_csv']
            type_donnees = form.cleaned_data['type_donnees']
            delimiter = form.cleaned_data['delimiter']

            # Lire le fichier CSV
            decoded_file = fichier.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file, delimiter=delimiter)

            imported_count = 0
            errors = []

            if type_donnees == 'DEPARTEMENTS':
                for row in reader:
                    try:
                        Departement.objects.create(
                            nom=row.get('nom'),
                            code_departement=row.get('code'),
                            region=row.get('region', ''),
                            centre_latitude=row.get('latitude'),
                            centre_longitude=row.get('longitude')
                        )
                        imported_count += 1
                    except Exception as e:
                        errors.append(f"Ligne {reader.line_num}: {str(e)}")

            elif type_donnees == 'LOCALITES':
                for row in reader:
                    try:
                        departement = Departement.objects.get(code_departement=row.get('departement_code'))
                        Localite.objects.create(
                            nom=row.get('nom'),
                            code_postal=row.get('code_postal', ''),
                            departement=departement,
                            type_localite=row.get('type', 'QUARTIER'),
                            latitude=row.get('latitude'),
                            longitude=row.get('longitude'),
                            zone_rayon_km=row.get('rayon_km', 5)
                        )
                        imported_count += 1
                    except Exception as e:
                        errors.append(f"Ligne {reader.line_num}: {str(e)}")

            messages.success(request, f"{imported_count} enregistrements importés avec succès.")
            if errors:
                messages.warning(request, f"{len(errors)} erreurs lors de l'import.")
                # Vous pouvez logger les erreurs

            return redirect('parametrage:dashboard')
    else:
        form = ImportGeoDataForm()

    return render(request, 'parametrage/import_geodata.html', {'form': form})


@login_required
@admin_required
def export_geojson(request):
    """Exportation en GeoJSON"""
    import json
    from django.http import HttpResponse

    # Créer un GeoJSON des localités
    features = []
    for localite in Localite.objects.select_related('departement').all():
        feature = {
            "type": "Feature",
            "properties": {
                "nom": localite.nom,
                "type": localite.type_localite,
                "code_postal": localite.code_postal,
                "departement": localite.departement.nom,
                "rayon_km": str(localite.zone_rayon_km)
            },
            "geometry": {
                "type": "Point",
                "coordinates": [float(localite.longitude), float(localite.latitude)]
            }
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    response = HttpResponse(
        json.dumps(geojson, indent=2, ensure_ascii=False),
        content_type='application/json'
    )
    response['Content-Disposition'] = 'attachment; filename="localites.geojson"'
    return response


# ==================== VUES POUR AJAX/API SIMPLE ====================

@login_required
def localites_by_departement(request, departement_id):
    """API simple pour obtenir les localités d'un département (AJAX)"""
    localites = Localite.objects.filter(departement_id=departement_id).values(
        'id', 'nom', 'type_localite', 'latitude', 'longitude'
    )
    return JsonResponse(list(localites), safe=False)


@login_required
def search_localites_api(request):
    """Recherche de localités (AJAX)"""
    q = request.GET.get('q', '')
    if q:
        localites = Localite.objects.filter(
            Q(nom__icontains=q) |
            Q(code_postal__icontains=q)
        ).values('id', 'nom', 'type_localite', 'code_postal', 'departement__nom')[:10]
        return JsonResponse(list(localites), safe=False)
    return JsonResponse([], safe=False)


@login_required
def active_tarifications_api(request):
    """Tarifications actives (AJAX) - Format détaillé pour le formulaire"""
    try:
        tarifs = TypeTarification.objects.filter(actif=True)

        data = []
        for tarif in tarifs:
            # Calculer le prix moyen du kWh à partir des tranches
            prix_kwh = 0
            if tarif.tranches and isinstance(tarif.tranches, list) and len(tarif.tranches) > 0:
                # Prendre le prix de la première tranche comme référence
                prix_kwh = tarif.tranches[0].get('prix_kwh', 0)

            data.append({
                'id': tarif.id,
                'code': tarif.code,
                'nom': tarif.nom,
                'categorie': tarif.categorie,
                'abonnement_mensuel': str(tarif.abonnement_mensuel),
                'devise': tarif.devise,
                'prix_kwh': str(prix_kwh),
                'description': tarif.description or '',
                'tranches': tarif.tranches if tarif.tranches else []
            })

        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)

# apps/parametrage/views.py - AJOUTEZ CETTE FONCTION :

@login_required
def localites_api(request):
    """API pour obtenir toutes les localités (format JSON)"""
    try:
        localites = Localite.objects.select_related('departement').all()

        data = []
        for loc in localites:
            data.append({
                'id': loc.id,
                'nom': loc.nom,
                'type_localite': loc.type_localite,
                'departement': loc.departement.nom if loc.departement else '',
                'departement_id': loc.departement.id if loc.departement else None,
                'latitude': float(loc.latitude) if loc.latitude else None,
                'longitude': float(loc.longitude) if loc.longitude else None,
            })

        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import TypeTarification


@login_required
def tarifications_actives_api(request):
    """API pour récupérer les tarifications actives"""
    try:
        tarifications = TypeTarification.objects.filter(
            actif=True  # ✅ Utiliser actif=True
        ).order_by('categorie', 'nom')

        data = []
        for tarif in tarifications:
            data.append({
                'id': tarif.id,
                'nom': tarif.nom,
                'description': tarif.description or '',
                'code': tarif.code,
                'categorie': tarif.categorie,
                'abonnement_mensuel': float(tarif.abonnement_mensuel),
                'prix_kwh': 120,  # ⚠️ À adapter selon votre logique
                'devise': tarif.devise or 'FCFA',
            })

        return JsonResponse({
            'success': True,
            'count': len(data),
            'results': data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.messages.views import SuccessMessageMixin
from .models import TypeHabitation
from .forms import TypeHabitationForm

class TypeHabitationListView(ListView):
    model = TypeHabitation
    context_object_name = 'types_habitation'
    template_name = 'parametrage/typehabitation_list.html'
    paginate_by = 20
    ordering = ['ordre_affichage', 'nom']

class TypeHabitationCreateView(SuccessMessageMixin, CreateView):
    model = TypeHabitation
    form_class = TypeHabitationForm
    template_name = 'parametrage/typehabitation_form.html'
    success_url = reverse_lazy('parametrage:typehabitation_list')
    success_message = "Le type d'habitation « %(nom)s » a été créé avec succès."

class TypeHabitationUpdateView(SuccessMessageMixin, UpdateView):
    model = TypeHabitation
    form_class = TypeHabitationForm
    template_name = 'parametrage/typehabitation_form.html'
    success_url = reverse_lazy('parametrage:typehabitation_list')
    success_message = "Le type d'habitation « %(nom)s » a été modifié avec succès."

class TypeHabitationDeleteView(DeleteView):
    model = TypeHabitation
    context_object_name = 'type_habitation'
    template_name = 'parametrage/typehabitation_confirm_delete.html'
    success_url = reverse_lazy('parametrage:typehabitation_list')
    success_message = "Le type d'habitation a été supprimé."

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message)
        return super().delete(request, *args, **kwargs)



# ==================== SUPPRESSION D'UN DÉPARTEMENT ====================
class DepartementDeleteView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, DeleteView):
    """Suppression d'un département"""
    model = Departement
    template_name = 'parametrage/departement_confirm_delete.html'
    success_url = reverse_lazy('parametrage:departements_list')
    success_message = "Le département « %(nom)s » a été supprimé avec succès."

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message % self.get_object().__dict__)
        return super().delete(request, *args, **kwargs)


# ==================== MISE À JOUR D'UNE LOCALITÉ ====================
class LocaliteUpdateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, UpdateView):
    """Modification d'une localité"""
    model = Localite
    form_class = LocaliteForm
    template_name = 'parametrage/localite_form.html'
    success_url = reverse_lazy('parametrage:localites_list')
    success_message = "La localité « %(nom)s » a été modifiée avec succès."


# ==================== SUPPRESSION D'UNE LOCALITÉ ====================
class LocaliteDeleteView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, DeleteView):
    """Suppression d'une localité"""
    model = Localite
    template_name = 'parametrage/localite_confirm_delete.html'
    success_url = reverse_lazy('parametrage:localites_list')
    success_message = "La localité « %(nom)s » a été supprimée avec succès."

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message % self.get_object().__dict__)
        return super().delete(request, *args, **kwargs)


# ==================== SUPPRESSION D'UNE TARIFICATION ====================
class TarifDeleteView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, DeleteView):
    """Suppression d'une tarification"""
    model = TypeTarification
    template_name = 'parametrage/tarif_confirm_delete.html'
    success_url = reverse_lazy('parametrage:tarifs_list')
    success_message = "La tarification « %(nom)s » a été supprimée avec succès."

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, self.success_message % self.get_object().__dict__)
        return super().delete(request, *args, **kwargs)


@login_required
def tarification_detail(request, pk):
    tarification = get_object_or_404(TypeTarification, pk=pk)

    return render(request, 'parametrage/tarification_detail.html', {
        'tarification': tarification
    })