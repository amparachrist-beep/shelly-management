from django.db import models

# Create your models here.
# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('ADMIN', 'Administrateur'),
        ('AGENT_TERRAIN', 'Agent de Terrain'),
        ('CLIENT', 'Client/Ménage'),
    )

    STATUT_CHOICES = (
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
        ('SUSPENDU', 'Suspendu'),
    )

    telephone = models.CharField(max_length=20, unique=True, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='CLIENT')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF')
    matricule_agent = models.CharField(max_length=30, unique=True, blank=True, null=True)
    poste_agent = models.CharField(max_length=50, blank=True, null=True)

    # ✅ NOUVEAU : rattachement à une agence pour les agents de terrain
    agence = models.ForeignKey(
        'menages.Agence',                        # ou 'agences.Agence' selon votre structure
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='agents',
        verbose_name="Agence"
    )

    profile_image = models.ImageField(
        upload_to='profile_photos/',
        null=True,
        blank=True,
        verbose_name='Photo de profil'
    )

    derniere_position_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    derniere_position_lng = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)

    cree_par = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='utilisateurs_crees')
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'utilisateur'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['statut']),
            models.Index(fields=['email']),
            models.Index(fields=['matricule_agent']),
            models.Index(fields=['agence']),      # ✅ index utile pour filtrer les agents par agence
        ]

    @property
    def is_admin(self):
        return self.role == 'ADMIN'

    @property
    def is_agent(self):
        return self.role == 'AGENT_TERRAIN'

    @property
    def is_client(self):
        return self.role == 'CLIENT'

    # ✅ NOUVEAU
    @property
    def agence_nom(self):
        """Raccourci pour afficher le nom de l'agence de l'agent"""
        return self.agence.nom if self.agence else None

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()  # ✅ à ajouter — AbstractUser a son propre clean()
        if self.role == 'AGENT_TERRAIN' and not self.agence_id:
            raise ValidationError({
                'agence': "Un agent de terrain doit être rattaché à une agence."
            })