from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.http import JsonResponse
from .models import CustomUser
from .forms import (
    CustomUserCreationForm, CustomUserUpdateForm,
    ProfileUpdateForm, PasswordChangeForm, CustomAuthenticationForm
)
from apps.menages.models import Agence

# ==================== VUES D'AUTHENTIFICATION ====================

def login_view(request):
    """Vue de connexion"""
    if request.user.is_authenticated:
        return redirect('dashboard:index')  # ✅ CORRIGÉ

    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f"Bienvenue {user.get_full_name()} !")

                # Redirection selon le rôle
                if user.role == 'ADMIN':
                    return redirect('dashboard:admin_dashboard')  # ✅ CORRIGÉ
                elif user.role == 'AGENT_TERRAIN':
                    return redirect('dashboard:agent_dashboard')  # ✅ CORRIGÉ
                elif user.role == 'CLIENT':
                    return redirect('dashboard:client_dashboard')  # ✅ CORRIGÉ
                else:
                    return redirect('dashboard:index')  # ✅ Fallback
            else:
                messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    else:
        form = CustomAuthenticationForm()

    return render(request, 'authentication/login.html', {'form': form})


from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings


def register_view(request):
    """
    Traite la demande d'inscription via Email (Gmail).
    Seul le rôle CLIENT/ménage est autorisé via ce formulaire public.
    Envoie un récapitulatif à l'administrateur.
    """
    # 1. Redirection si déjà connecté
    if request.user.is_authenticated:
        return redirect('dashboard:client_dashboard')

    # 2. Traitement du formulaire
    if request.method == 'POST':
        # Récupération des données du formulaire HTML
        first_name   = request.POST.get('first_name', '').strip()
        last_name    = request.POST.get('last_name', '').strip()
        email        = request.POST.get('email', '').strip()
        phone        = request.POST.get('phone', '').strip()
        user_message = request.POST.get('message', 'Aucun message particulier.').strip()

        # Rôle forcé côté serveur — jamais lu depuis le POST
        # Peu importe ce que le formulaire envoie, on ignore et on force CLIENT
        role = 'CLIENT'

        # Validation basique (role retiré de la validation car fixé côté serveur)
        if not (first_name and last_name and email and phone):
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
            return render(request, 'authentication/register.html')

        # Construction de l'email pour l'ADMIN
        admin_email = 'amparachrist@gmail.com'
        subject = f"[Shelly SGE] Nouvelle demande d'accès ménage : {first_name} {last_name}"

        email_content = f"""
Bonjour Admin,

Une nouvelle demande d'accès ménage a été soumise sur la plateforme Shelly SGE.

--- DÉTAILS DU DEMANDEUR ---
Nom complet  : {first_name} {last_name}
Email        : {email}
Téléphone    : {phone}
Rôle         : {role} (fixé automatiquement — formulaire public)

--- MESSAGE ---
{user_message}

---
Veuillez vous connecter au panneau d'administration pour créer ce compte
manuellement si la demande est valide.
        """

        try:
            # Envoi de l'email
            send_mail(
                subject=subject,
                message=email_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[admin_email],
                fail_silently=False,
            )

            # Succès : message à l'utilisateur et redirection vers le login
            messages.success(
                request,
                "Votre demande a été envoyée avec succès ! L'administrateur vous contactera sous peu."
            )
            return redirect('users:login')

        except Exception as e:
            # En cas d'erreur SMTP (connexion, config, etc.)
            print(f"Erreur d'envoi d'email: {e}")
            messages.error(
                request,
                "Une erreur est survenue lors de l'envoi de la demande. Veuillez réessayer plus tard."
            )

    # 3. Affichage du formulaire (GET)
    return render(request, 'authentication/register.html')

def logout_view(request):
    """Vue de déconnexion"""
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('users:login')


# ==================== VUES DE PROFIL ====================

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from PIL import Image
import io
import os


@login_required
def profile(request):
    """Affiche le profil de l'utilisateur"""
    context = {
        'user': request.user,
    }

    # Si c'est un client, récupérer son ménage
    if request.user.is_client:
        try:
            from apps.menages.models import Menage
            menage = Menage.objects.get(utilisateur=request.user)
            context['menage'] = menage
        except Menage.DoesNotExist:
            context['menage'] = None

    return render(request, 'client/profil.html', context)


@login_required
def update_profile_photo(request):
    """Met à jour la photo de profil de l'utilisateur"""
    if request.method == 'POST' and request.FILES.get('profile_image'):
        try:
            image_file = request.FILES['profile_image']

            # Vérifier la taille (2MB max)
            if image_file.size > 2 * 1024 * 1024:
                messages.error(request, 'La taille de l\'image ne doit pas dépasser 2MB.')
                return redirect('users:profile')

            # Vérifier le type de fichier
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if image_file.content_type not in allowed_types:
                messages.error(request, 'Format d\'image non supporté. Utilisez JPG, PNG, GIF ou WebP.')
                return redirect('users:profile')

            # Supprimer l'ancienne photo si elle existe
            if request.user.profile_image:
                try:
                    default_storage.delete(request.user.profile_image.name)
                except Exception as e:
                    print(f"Erreur suppression ancienne photo: {e}")

            # Générer un nom unique avec timestamp
            from django.utils import timezone
            import os
            timestamp = int(timezone.now().timestamp())
            ext = os.path.splitext(image_file.name)[1]  # Garder l'extension originale
            filename = f'profile_photos/user_{request.user.id}_{timestamp}{ext}'

            # Sauvegarde simple (sans optimisation PIL)
            path = default_storage.save(filename, ContentFile(image_file.read()))

            # Mettre à jour l'utilisateur
            request.user.profile_image = path
            request.user.save(update_fields=['profile_image'])

            messages.success(request, 'Votre photo de profil a été mise à jour avec succès !')

        except Exception as e:
            print(f"Erreur détaillée: {str(e)}")
            messages.error(request, f'Erreur lors du téléchargement : {str(e)}')

    return redirect('users:profile')


@login_required
def change_password(request):
    """Page de changement de mot de passe"""
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash

    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Votre mot de passe a été modifié avec succès !')
            return redirect('users:profile')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'users/change_password.html', {'form': form})
class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Mise à jour du profil"""
    model = CustomUser
    form_class = ProfileUpdateForm
    template_name = 'client/update_profil.html'
    success_url = reverse_lazy('users:profile')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profil mis à jour avec succès.")
        return super().form_valid(form)


@login_required
def change_password_view(request):
    """Changement de mot de passe"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Mot de passe changé avec succès.")
            return redirect('users:profile')
    else:
        form = PasswordChangeForm(request.user)

    return render(request, 'authentication/change_password.html', {'form': form})


# ==================== VUES ADMIN POUR GESTION DES UTILISATEURS ====================

def admin_required(view_func):
    """Décorateur pour vérifier si l'utilisateur est admin"""

    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.role == 'ADMIN':
            messages.error(request, "Accès refusé. Administrateur requis.")
            return redirect('dashboard:home')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class AgentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Liste des agents (admin seulement)"""
    model = CustomUser
    template_name = 'gestion/agents/list.html'
    context_object_name = 'agents'
    paginate_by = 20

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_queryset(self):
        queryset = CustomUser.objects.filter(role='AGENT_TERRAIN')

        # Recherche
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(matricule_agent__icontains=search) |
                Q(telephone__icontains=search)
            )

        # Filtre par statut
        statut = self.request.GET.get('statut', '')
        if statut:
            queryset = queryset.filter(statut=statut)

        return queryset.order_by('-date_joined')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Gestion des Agents',
            'icon': 'fas fa-users-cog',
            'headers': ['Nom', 'Email', 'Téléphone', 'Matricule', 'Statut', 'Date'],
            'create_url': 'users:agent_create',
            'stats': self.get_stats(),
        })
        return context

    def get_stats(self):
        """Récupérer les statistiques"""
        return [
            {
                'title': 'Total Agents',
                'value': CustomUser.objects.filter(role='AGENT_TERRAIN').count(),
                'color': 'primary'
            },
            {
                'title': 'Actifs',
                'value': CustomUser.objects.filter(role='AGENT_TERRAIN', statut='ACTIF').count(),
                'color': 'success'
            },
            {
                'title': 'Inactifs',
                'value': CustomUser.objects.filter(role='AGENT_TERRAIN', statut='INACTIF').count(),
                'color': 'warning'
            },
            {
                'title': 'Suspendus',
                'value': CustomUser.objects.filter(role='AGENT_TERRAIN', statut='SUSPENDU').count(),
                'color': 'danger'
            },
        ]


class AgentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Création d'un agent (admin seulement)"""
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'gestion/agents/form.html'
    success_url = reverse_lazy('users:agents_list')

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_initial(self):
        initial = super().get_initial()
        initial['role'] = 'AGENT_TERRAIN'
        initial['cree_par'] = self.request.user
        return initial

    def form_valid(self, form):
        form.instance.cree_par = self.request.user
        form.instance.role = 'AGENT_TERRAIN'
        messages.success(self.request, "Agent créé avec succès.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Nouvel Agent',
            'icon': 'fas fa-user-plus',
            'submit_text': 'Créer l\'agent',
            'cancel_url': 'users:agents_list',
        })
        return context


class AgentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Détail d'un agent"""
    model = CustomUser
    template_name = 'gestion/agents/detail.html'
    context_object_name = 'agent'

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Agent: {self.object.get_full_name()}',
            'icon': 'fas fa-user-tie',
            'update_url': 'users:agent_update',
            'list_url': 'users:agents_list',
        })
        return context


class AgentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Modification d'un agent"""
    model = CustomUser
    form_class = CustomUserUpdateForm
    template_name = 'gestion/agents/form.html'
    success_url = reverse_lazy('users:agents_list')

    def test_func(self):
        return self.request.user.role == 'ADMIN'

    def form_valid(self, form):
        messages.success(self.request, "Agent modifié avec succès.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Modifier {self.object.get_full_name()}',
            'icon': 'fas fa-edit',
            'submit_text': 'Modifier',
            'cancel_url': 'users:agents_list',
        })
        return context


@login_required
@admin_required
def toggle_agent_status(request, pk):
    """Activer/désactiver un agent"""
    agent = get_object_or_404(CustomUser, pk=pk, role='AGENT_TERRAIN')

    if agent.statut == 'ACTIF':
        agent.statut = 'INACTIF'
        agent.is_active = False
        message = "Agent désactivé"
    else:
        agent.statut = 'ACTIF'
        agent.is_active = True
        message = "Agent activé"

    agent.save()
    messages.success(request, message)
    return redirect('users:agents_list')


# ==================== STATISTIQUES ====================

@login_required
@admin_required
def user_stats_view(request):
    """Statistiques des utilisateurs"""
    stats = {
        'total': CustomUser.objects.count(),
        'admins': CustomUser.objects.filter(role='ADMIN').count(),
        'agents': CustomUser.objects.filter(role='AGENT_TERRAIN').count(),
        'clients': CustomUser.objects.filter(role='CLIENT').count(),
        'active': CustomUser.objects.filter(is_active=True).count(),
        'inactive': CustomUser.objects.filter(is_active=False).count(),
    }

    # Graphique d'inscription par mois
    from django.db.models.functions import TruncMonth
    inscriptions = CustomUser.objects.annotate(
        month=TruncMonth('date_joined')
    ).values('month').annotate(count=Count('id')).order_by('month')

    return render(request, 'admin_system/supervision/statistiques.html', {
        'stats': stats,
        'inscriptions': inscriptions,
        'title': 'Statistiques Utilisateurs'
    })


# ==================== VUES POUR AJAX/API SIMPLE ====================

@login_required
def update_position_view(request):
    """Mettre à jour la position GPS (pour agents)"""
    if request.method == 'POST' and request.user.role == 'AGENT_TERRAIN':
        lat = request.POST.get('lat')
        lng = request.POST.get('lng')

        if lat and lng:
            request.user.derniere_position_lat = lat
            request.user.derniere_position_lng = lng
            request.user.save()
            return JsonResponse({'success': True, 'message': 'Position mise à jour'})

    return JsonResponse({'success': False, 'message': 'Erreur'}, status=400)


@login_required
@admin_required
def get_users_json(request):
    """API simple pour obtenir les utilisateurs en JSON"""
    users = CustomUser.objects.all().values('id', 'username', 'email',
                                            'first_name', 'last_name', 'role')
    return JsonResponse(list(users), safe=False)


# ✅ AJOUTEZ CETTE VUE DANS apps/users/views.py

@login_required
def get_available_users_json(request):
    """
    API pour obtenir les utilisateurs CLIENT disponibles (sans ménage associé)
    """
    # Vérifier que l'utilisateur est admin ou agent
    if request.user.role not in ['ADMIN', 'AGENT_TERRAIN']:
        return JsonResponse({'error': 'Permission refusée'}, status=403)

    # Récupérer les paramètres de filtrage
    role = request.GET.get('role', 'CLIENT')
    available = request.GET.get('available', 'false').lower() == 'true'

    # Construire la requête
    users_query = CustomUser.objects.filter(role=role)

    # Filtrer uniquement les utilisateurs sans ménage associé
    if available:
        users_query = users_query.filter(menage__isnull=True)

    # Récupérer les données
    users = users_query.values(
        'id',
        'username',
        'email',
        'first_name',
        'last_name',
        'telephone'
    ).order_by('username')

    return JsonResponse(list(users), safe=False)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import Q
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserUpdateForm


# ============================================
# MIXIN POUR RESTREINDRE AUX ADMINISTRATEURS
# ============================================
class AdminRequiredMixin(UserPassesTestMixin):
    """Vérifie que l'utilisateur est administrateur"""

    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'ADMIN'


# ============================================
# LISTE DES UTILISATEURS
# ============================================
class UserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    """Liste de tous les utilisateurs (admin uniquement)"""
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    ordering = ['-date_joined']

    def get_queryset(self):
        queryset = super().get_queryset()

        # Filtre par recherche
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(first_name__icontains=search_query) |
                Q(last_name__icontains=search_query) |
                Q(telephone__icontains=search_query)
            )

        # Filtre par rôle
        role_filter = self.request.GET.get('role', '')
        if role_filter:
            queryset = queryset.filter(role=role_filter)

        # Filtre par statut
        statut_filter = self.request.GET.get('statut', '')
        if statut_filter:
            queryset = queryset.filter(statut=statut_filter)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Gestion des utilisateurs"
        context['role_choices'] = CustomUser.ROLE_CHOICES
        context['statut_choices'] = CustomUser.STATUT_CHOICES
        return context


# ============================================
# CRÉATION D'UN UTILISATEUR
# ============================================
class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, CreateView):
    """Création d'un nouvel utilisateur"""
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')
    success_message = "L'utilisateur « %(username)s » a été créé avec succès."

    def form_valid(self, form):
        # Enregistrer qui a créé cet utilisateur
        form.instance.cree_par = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agences'] = Agence.objects.filter(actif=True).order_by('nom')  # ✅
        return context


# ============================================
# MODIFICATION D'UN UTILISATEUR
# ============================================
# ============================================
# MODIFICATION D'UN UTILISATEUR
# ============================================
class UserUpdateView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, UpdateView):
    """Modification d'un utilisateur"""
    model = CustomUser
    form_class = CustomUserUpdateForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('users:user_list')
    success_message = "L'utilisateur « %(username)s » a été modifié avec succès."

    def get_success_message(self, cleaned_data):
        """Surcharge pour récupérer le username depuis l'objet utilisateur"""
        return self.success_message % {'username': self.object.username}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agences'] = Agence.objects.filter(actif=True).order_by('nom')
        return context


# ============================================
# DÉTAIL D'UN UTILISATEUR
# ============================================
class UserDetailView(LoginRequiredMixin, AdminRequiredMixin, DetailView):
    """Détail d'un utilisateur"""
    model = CustomUser
    template_name = 'users/user_detail.html'
    context_object_name = 'user_obj'  # Évite le conflit avec 'user' de la requête


# ============================================
# SUPPRESSION D'UN UTILISATEUR
# ============================================
class UserDeleteView(LoginRequiredMixin, AdminRequiredMixin, SuccessMessageMixin, DeleteView):
    """Suppression d'un utilisateur"""
    model = CustomUser
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('users:user_list')
    success_message = "L'utilisateur a été supprimé avec succès."
    context_object_name = 'user_obj'

    def delete(self, request, *args, **kwargs):
        user = self.get_object()
        messages.success(self.request, f"L'utilisateur « {user.username} » a été supprimé.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_obj'] = self.get_object()
        return context


# ============================================
# ACTIVATION / DÉSACTIVATION D'UN UTILISATEUR
# ============================================
@login_required
@user_passes_test(lambda u: u.is_authenticated and u.role == 'ADMIN')
def user_toggle_active(request, pk):
    """
    Active ou désactive un utilisateur (changement de statut).
    Cycle : ACTIF → INACTIF → ACTIF
    """
    user = get_object_or_404(CustomUser, pk=pk)

    # Empêcher l'auto-désactivation
    if user == request.user:
        messages.error(request, "Vous ne pouvez pas modifier votre propre statut.")
        return redirect('users:user_list')

    # Bascule du statut
    if user.statut == 'ACTIF':
        user.statut = 'INACTIF'
        messages.success(request, f"L'utilisateur « {user.username} » a été désactivé.")
    else:
        user.statut = 'ACTIF'
        messages.success(request, f"L'utilisateur « {user.username} » a été activé.")

    user.save()
    return redirect('users:user_list')


# ============================================
# SUSPENSION D'UN UTILISATEUR
# ============================================
@login_required
@user_passes_test(lambda u: u.is_authenticated and u.role == 'ADMIN')
def user_suspend(request, pk):
    """Met un utilisateur en statut 'SUSPENDU'"""
    user = get_object_or_404(CustomUser, pk=pk)

    if user == request.user:
        messages.error(request, "Vous ne pouvez pas suspendre votre propre compte.")
        return redirect('users:user_list')

    user.statut = 'SUSPENDU'
    user.save()
    messages.success(request, f"L'utilisateur « {user.username} » a été suspendu.")
    return redirect('users:user_list')


# ============================================
# RÉACTIVATION DEPUIS SUSPENSION
# ============================================
@login_required
@user_passes_test(lambda u: u.is_authenticated and u.role == 'ADMIN')
def user_reactivate(request, pk):
    """Réactive un utilisateur suspendu (remet à ACTIF)"""
    user = get_object_or_404(CustomUser, pk=pk)
    user.statut = 'ACTIF'
    user.save()
    messages.success(request, f"L'utilisateur « {user.username} » a été réactivé.")
    return redirect('users:user_list')

