from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect
from django.contrib import messages


class AdminRequiredMixin(UserPassesTestMixin):
    """
    Vérifie que l'utilisateur est administrateur
    """
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'ADMIN'

    def handle_no_permission(self):
        messages.error(self.request, "Accès refusé. Vous devez être administrateur.")
        return redirect('dashboard:index')


class AgentRequiredMixin(UserPassesTestMixin):
    """
    Vérifie que l'utilisateur est agent de terrain
    """
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'AGENT_TERRAIN'

    def handle_no_permission(self):
        messages.error(self.request, "Accès refusé. Vous devez être agent de terrain.")
        return redirect('dashboard:index')


class ClientRequiredMixin(UserPassesTestMixin):
    """
    Vérifie que l'utilisateur est client
    """
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role == 'CLIENT'

    def handle_no_permission(self):
        messages.error(self.request, "Accès refusé. Vous devez être connecté en tant que client.")
        return redirect('dashboard:index')


class LoginAndRoleRequiredMixin(UserPassesTestMixin):
    """
    Mixin combiné pour vérifier le rôle ET l'authentification
    """
    roles_required = []

    def test_func(self):
        if not self.request.user.is_authenticated:
            return False
        if self.roles_required and self.request.user.role not in self.roles_required:
            return False
        return True

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('users:login')
        messages.error(self.request, "Vous n'avez pas les permissions nécessaires.")
        return redirect('dashboard:index')