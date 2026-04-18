from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.views import View
from django.urls import reverse_lazy, reverse  # ✅ CORRIGÉ: ajout de reverse
from django.db.models import Q, Sum, Count, Avg, Max, Min, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncMonth
from django.http import JsonResponse, HttpResponse, FileResponse
from django.utils import timezone
from django.core.paginator import Paginator  # ✅ CORRIGÉ: ajout de Paginator
from datetime import date, datetime, timedelta
from decimal import Decimal
import csv, json, uuid, io

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# ✅ CORRIGÉ: ajout de Facture dans les imports
from .models import FactureConsommation, LigneFacture, BatchFacturation, Relance, Facture, DossierImpaye, PeriodeFacturation
from .forms import (
    FactureConsommationForm, LigneFactureForm,
    BatchFacturationForm, RelanceForm, FactureSearchForm, GenererFacturesForm, DossierImpayeForm, TraiterDossierImpayeForm, PeriodeFacturationForm
)
from apps.compteurs.models import Compteur
from apps.consommation.models import Consommation
from apps.menages.models import Menage
from apps.paiements.models import Paiement

# apps/facturation/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Avg, Q, F, FloatField, ExpressionWrapper
from django.utils import timezone
from datetime import date, timedelta, datetime
from decimal import Decimal
from django.core.paginator import Paginator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
import json
import calendar

from .models import Facture, FactureConsommation, LigneFacture
from apps.menages.models import Menage
from apps.users.models import CustomUser


# ============================================
# AJOUTEZ CES DÉCORATEURS ET CLASSES ICI
# ============================================
class RoleRequiredMixin:
    """Mixin pour vérifier le rôle de l'utilisateur"""
    roles_required = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if self.roles_required and request.user.role not in self.roles_required:
            messages.error(request, "Vous n'avez pas les permissions nécessaires.")
            return redirect('dashboard:index')

        return super().dispatch(request, *args, **kwargs)


def role_required(roles):
    """Décorateur pour vérifier le rôle"""

    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.role not in roles:
                messages.error(request, "Accès non autorisé.")
                return redirect('dashboard:index')

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
# ============================================


# ==================== DÉCORATEURS DE PERMISSION ====================

def admin_or_agent_required(view_func):
    """Décorateur pour vérifier si l'utilisateur est admin ou agent"""

    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Veuillez vous connecter.")
            return redirect('users:login')

        if not (request.user.role == 'ADMIN' or request.user.role == 'AGENT_TERRAIN'):
            messages.error(request, "Accès refusé. Administrateur ou agent requis.")
            return redirect('dashboard:home')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


def client_access(view_func):
    """Décorateur pour vérifier l'accès client à ses factures"""

    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Veuillez vous connecter.")
            return redirect('users:login')

        facture_id = kwargs.get('pk')
        if facture_id:
            facture = get_object_or_404(FactureConsommation, pk=facture_id)

            if not (request.user.role == 'ADMIN' or
                    request.user.role == 'AGENT_TERRAIN' or
                    (request.user.role == 'CLIENT' and facture.compteur.menage.utilisateur == request.user)):
                messages.error(request, "Accès refusé à cette facture.")
                return redirect('dashboard:home')

        return view_func(request, *args, **kwargs)

    return _wrapped_view


class AdminOrAgentRequiredMixin(UserPassesTestMixin):
    """Mixin pour vérifier si l'utilisateur est admin ou agent"""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.role == 'ADMIN' or user.role == 'AGENT_TERRAIN')



# ==================== LISTE DES FACTURES ====================

class FactureListView(LoginRequiredMixin, ListView):
    """Liste des factures"""
    model = FactureConsommation
    template_name = 'gestion/list_template.html'
    context_object_name = 'factures'
    paginate_by = 20

    def get_queryset(self):
        # Définition de l'expression pour le calcul du total TTC
        total_ttc_expression = ExpressionWrapper(
            (F('montant_consommation') + F('montant_abonnement')) * (1 + F('tva_taux') / 100) +
            F('redevance_communale') + F('autres_taxes'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )

        queryset = FactureConsommation.objects.select_related(
            'compteur', 'compteur__menage', 'consommation'
        ).annotate(
            montant_total_ttc=total_ttc_expression,
            solde_calcule=ExpressionWrapper(
                total_ttc_expression - F('montant_paye'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        user = self.request.user

        # ✅ CORRIGÉ: CLIENT ne voit que ses factures
        # ADMIN et AGENT_TERRAIN voient tout (pas de filtre)
        if user.role == 'CLIENT':
            queryset = queryset.filter(compteur__menage__utilisateur=user)

        # Recherche texte
        search = self.request.GET.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(numero_facture__icontains=search) |
                Q(compteur__numero_contrat__icontains=search) |
                Q(compteur__menage__nom_menage__icontains=search) |
                Q(compteur__menage__utilisateur__first_name__icontains=search) |
                Q(compteur__menage__utilisateur__last_name__icontains=search)
            )

        # Filtre statut
        statut = self.request.GET.get('statut', '')
        if statut:
            queryset = queryset.filter(statut=statut)

        # Filtre dates
        date_debut = self.request.GET.get('date_debut', '')
        date_fin = self.request.GET.get('date_fin', '')

        if date_debut:
            try:
                queryset = queryset.filter(
                    date_emission__gte=datetime.strptime(date_debut, '%Y-%m-%d').date()
                )
            except ValueError:
                pass

        if date_fin:
            try:
                queryset = queryset.filter(
                    date_emission__lte=datetime.strptime(date_fin, '%Y-%m-%d').date()
                )
            except ValueError:
                pass

        # Filtre période
        periode = self.request.GET.get('periode', '')
        if periode:
            try:
                annee, mois = map(int, periode.split('-'))
                queryset = queryset.filter(
                    periode__year=annee,
                    periode__month=mois
                )
            except ValueError:
                pass

        return queryset.order_by('-periode', '-date_emission')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()

        # Définition de l'expression pour le calcul du total TTC pour les agrégations
        total_ttc_expression = ExpressionWrapper(
            (F('montant_consommation') + F('montant_abonnement')) * (1 + F('tva_taux') / 100) +
            F('redevance_communale') + F('autres_taxes'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )

        stats = queryset.aggregate(
            total_factures=Count('id'),
            montant_total=Sum(total_ttc_expression), # ✅ CORRIGÉ: Utilisation de l'expression
            montant_paye=Sum('montant_paye'),
            montant_impaye=Sum('solde_calcule'),
        )

        # ✅ CORRIGÉ: Utilisation de l'expression pour la répartition
        repartition_statuts = queryset.values('statut').annotate(
            count=Count('id'),
            montant=Sum(total_ttc_expression)
        ).order_by('-count')

        context.update({
            'title': 'Factures',
            'icon': 'fas fa-file-invoice-dollar',
            'headers': [
                'Numéro', 'Client', 'Compteur', 'Période',
                'Total TTC', 'Payé', 'Solde', 'Statut', 'Échéance'
            ],
            'create_url': 'facturation:create',
            'detail_url': 'facturation:detail',
            'update_url': 'facturation:update',
            'show_filters': True,
            'form': FactureSearchForm(self.request.GET or None),
            'stats': [
                {
                    'title': 'Total Factures',
                    'value': stats['total_factures'] or 0,
                    'color': 'primary',
                    'icon': 'fas fa-file'
                },
                {
                    'title': 'Montant Total',
                    'value': f"{stats['montant_total'] or 0:.2f} FCFA",
                    'color': 'success',
                    'icon': 'fas fa-money-bill-wave'
                },
                {
                    'title': 'Montant Payé',
                    'value': f"{stats['montant_paye'] or 0:.2f} FCFA",
                    'color': 'info',
                    'icon': 'fas fa-check-circle'
                },
                {
                    'title': 'Montant Impayé',
                    'value': f"{stats['montant_impaye'] or 0:.2f} FCFA",
                    'color': 'danger',
                    'icon': 'fas fa-exclamation-circle'
                },
            ],
            'repartition_statuts': repartition_statuts,
        })
        return context


class FactureCreateView(LoginRequiredMixin, AdminOrAgentRequiredMixin, CreateView):
    """Création d'une facture"""
    model = FactureConsommation
    form_class = FactureConsommationForm
    template_name = 'gestion/form_template.html'
    success_url = reverse_lazy('facturation:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Nouvelle Facture',
            'icon': 'fas fa-file-invoice',
            'submit_text': 'Créer la facture',
            'extra_content': '''
                <div class="alert alert-info mt-3">
                    <h5><i class="fas fa-info-circle"></i> Information</h5>
                    <p class="mb-0">
                        <strong>Note:</strong> Le numéro de facture est généré automatiquement.<br>
                        <strong>Calcul:</strong> Total TTC = (Consommation + Abonnement) * (1 + TVA) + Taxes
                    </p>
                </div>
            '''
        })
        return context

    def form_valid(self, form):
        facture = form.save(commit=False)
        facture.emis_par = self.request.user

        total_ht = facture.montant_consommation + facture.montant_abonnement
        tva_montant = total_ht * facture.tva_taux / 100
        total_ttc = total_ht + tva_montant + facture.redevance_communale + facture.autres_taxes

        if facture.montant_paye > total_ttc:
            form.add_error('montant_paye',
                           f"Montant payé ({facture.montant_paye}) > Total TTC ({total_ttc:.2f})")
            return self.form_invalid(form)

        # ✅ CORRIGÉ: Suppression de la ligne qui tentait d'écrire dans un champ inexistant
        # Le total_ttc est calculé par la propriété du modèle, pas stocké en BDD
        facture.save()

        messages.success(self.request, f"Facture {facture.numero_facture} créée avec succès.")
        return redirect('facturation:detail', pk=facture.pk)


class FactureDetailView(LoginRequiredMixin, DetailView):
    """Détail d'une facture"""
    model = FactureConsommation
    template_name = 'facturation/detail.html'
    context_object_name = 'facture'

    def get_queryset(self):
        return FactureConsommation.objects.select_related(
            'compteur', 'compteur__menage', 'compteur__type_tarification',
            'consommation', 'emis_par'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        facture = self.object
        user = self.request.user

        if not (user.role == 'ADMIN' or
                user.role == 'AGENT_TERRAIN' or
                (user.role == 'CLIENT' and facture.compteur.menage.utilisateur == user)):
            messages.error(self.request, "Accès refusé.")
            return context

        context['lignes'] = LigneFacture.objects.filter(facture=facture).order_by('ordre')
        context['paiements'] = Paiement.objects.filter(facture=facture).select_related('cree_par')
        context['relances'] = Relance.objects.filter(facture=facture).order_by('-date_envoi_prevue')

        actions = []
        if user.role in ['ADMIN', 'AGENT_TERRAIN']:
            if facture.statut == 'BROUILLON':
                actions.append({
                    'text': 'Émettre',
                    'url': f'{facture.pk}/emettre/',
                    'icon': 'paper-plane',
                    'color': 'primary'
                })

            if facture.statut in ['BROUILLON', 'ÉMISE', 'PARTIELLEMENT_PAYÉE']:
                actions.append({
                    'text': 'Annuler',
                    'url': f'{facture.pk}/annuler/',
                    'icon': 'times',
                    'color': 'danger'
                })

            actions.append({
                'text': 'Générer PDF',
                'url': f'{facture.pk}/generer-pdf/',
                'icon': 'file-pdf',
                'color': 'warning'
            })

            if facture.statut in ['ÉMISE', 'EN_RETARD', 'PARTIELLEMENT_PAYÉE']:
                actions.append({
                    'text': 'Relancer',
                    'url': f'{facture.pk}/relancer/',
                    'icon': 'envelope',
                    'color': 'info'
                })

        context['actions'] = actions
        return context


class FactureUpdateView(LoginRequiredMixin, AdminOrAgentRequiredMixin, UpdateView):
    """Modification d'une facture"""
    model = FactureConsommation
    form_class = FactureConsommationForm
    template_name = 'gestion/form_template.html'
    success_url = reverse_lazy('facturation:list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Modifier {self.object.numero_facture}',
            'icon': 'fas fa-edit',
            'submit_text': 'Modifier',
        })
        return context

    def form_valid(self, form):
        # ✅ CORRIGÉ: Suppression de la ligne qui tentait d'écrire dans un champ inexistant
        # Le total_ttc est calculé par la propriété du modèle, pas stocké en BDD
        facture = form.save()
        messages.success(self.request, f"Facture {self.object.numero_facture} modifiée.")
        return redirect('facturation:detail', pk=facture.pk)
# ==================== VUES D'ACTIONS ====================

@login_required
@admin_or_agent_required
def facture_emettre(request, pk):
    """Émettre une facture (passer de BROUILLON à ÉMISE)"""
    facture = get_object_or_404(FactureConsommation, pk=pk)

    if facture.statut != 'BROUILLON':
        messages.warning(request, "Seules les factures en brouillon peuvent être émises.")
        return redirect('facturation:detail', pk=pk)

    facture.statut = 'ÉMISE'
    facture.save()

    messages.success(request, f"Facture {facture.numero_facture} émise.")
    return redirect('facturation:detail', pk=pk)


@login_required
@admin_or_agent_required
def facture_annuler(request, pk):
    """Annuler une facture"""
    facture = get_object_or_404(FactureConsommation, pk=pk)

    if facture.statut in ['PAYÉE', 'REMBOURSEE']:
        messages.error(request, "Impossible d'annuler une facture payée ou remboursée.")
        return redirect('facturation:detail', pk=pk)

    if request.method == 'POST':
        motif = request.POST.get('motif', '')
        facture.statut = 'ANNULEE'
        facture.motif_annulation = motif
        facture.save()

        messages.warning(request, f"Facture {facture.numero_facture} annulée.")
        return redirect('facturation:detail', pk=pk)

    return render(request, 'facturation/annuler_form.html', {'facture': facture})


@login_required
@admin_or_agent_required
def facture_relancer(request, pk):
    """Créer une relance pour une facture"""
    facture = get_object_or_404(FactureConsommation, pk=pk)

    if facture.statut not in ['ÉMISE', 'EN_RETARD', 'PARTIELLEMENT_PAYÉE']:
        messages.warning(request,
                         "Seules les factures émises, en retard ou partiellement payées peuvent être relancées.")
        return redirect('facturation:detail', pk=pk)

    numero_relance = Relance.objects.filter(facture=facture).count() + 1

    if request.method == 'POST':
        form = RelanceForm(request.POST)
        if form.is_valid():
            relance = form.save(commit=False)
            relance.facture = facture
            relance.numero_relance = numero_relance
            relance.agent = request.user
            relance.save()

            messages.info(request, f"Relance {numero_relance} créée pour la facture {facture.numero_facture}.")
            return redirect('facturation:detail', pk=pk)
    else:
        initial_data = {
            'type_relance': 'EMAIL',
            'sujet': f"Relance facture {facture.numero_facture}",
            'message': (
                f"Bonjour,\n\n"
                f"Votre facture {facture.numero_facture} d'un montant de "
                f"{facture.total_ttc:.2f} FCFA est en attente de paiement.\n"
                f"Échéance: {facture.date_echeance}\n\n"
                f"Veuillez régulariser votre situation.\n\n"
                f"Cordialement,\nService Facturation"
            ),
            'destinataire_email': facture.compteur.menage.utilisateur.email,
            'destinataire_telephone': facture.compteur.menage.utilisateur.telephone,
            'date_envoi_prevue': timezone.now() + timedelta(hours=1),
        }
        form = RelanceForm(initial=initial_data)

    return render(request, 'facturation/relancer_form.html', {
        'form': form,
        'facture': facture,
        'numero_relance': numero_relance,
    })


@login_required
@client_access
def facture_generer_pdf(request, pk):
    """Générer un PDF pour une facture"""
    facture = get_object_or_404(FactureConsommation, pk=pk)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    title = Paragraph(f"FACTURE N° {facture.numero_facture}", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    client_data = [
        ["CLIENT:", facture.compteur.menage.nom_menage],
        ["Adresse:", facture.compteur.menage.adresse_complete],
        ["Compteur:", facture.compteur.numero_contrat],
        ["Période:", facture.periode.strftime('%B %Y')],
        ["Date émission:", facture.date_emission.strftime('%d/%m/%Y')],
        ["Date échéance:", facture.date_echeance.strftime('%d/%m/%Y')],
    ]

    client_table = Table(client_data, colWidths=[100, 300])
    client_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 20))

    lignes = LigneFacture.objects.filter(facture=facture).order_by('ordre')
    if not lignes:
        prix_unitaire_conso = (
            facture.montant_consommation / facture.consommation_kwh
            if facture.consommation_kwh > 0 else Decimal('0.00')
        )
        ligne_data = [
            ["Description", "Quantité", "Unité", "Prix unitaire", "Montant HT"],
            [
                "Consommation",
                f"{facture.consommation_kwh:.2f}",
                "kWh",
                f"{prix_unitaire_conso:.2f}",
                f"{facture.montant_consommation:.2f}"
            ],
            [
                "Abonnement",
                "1",
                "Mois",
                f"{facture.montant_abonnement:.2f}",
                f"{facture.montant_abonnement:.2f}"
            ],
        ]
    else:
        ligne_data = [["Description", "Quantité", "Unité", "Prix unitaire", "Montant HT"]]
        for ligne in lignes:
            ligne_data.append([
                ligne.description,
                f"{ligne.quantite:.2f}",
                ligne.unite,
                f"{ligne.prix_unitaire:.2f}",
                f"{ligne.montant_ht:.2f}"
            ])

    ligne_table = Table(ligne_data, colWidths=[200, 60, 60, 80, 80])
    ligne_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(ligne_table)
    elements.append(Spacer(1, 20))

    # ✅ CORRIGÉ: utilisation des properties Python (pas d'annotation ORM ici, c'est du rendu)
    total_data = [
        ["Total HT:", f"{facture.total_ht:.2f} FCFA"],
        [f"TVA ({facture.tva_taux}%):", f"{facture.tva_montant:.2f} FCFA"],  # ✅ CORRIGÉ: f-string correcte
        ["Redevance communale:", f"{facture.redevance_communale:.2f} FCFA"],
        ["Autres taxes:", f"{facture.autres_taxes:.2f} FCFA"],
        ["", ""],
        ["TOTAL TTC:", f"{facture.total_ttc:.2f} FCFA"],
        ["Montant payé:", f"{facture.montant_paye:.2f} FCFA"],
        ["SOLDE DÛ:", f"{facture.solde_du:.2f} FCFA"],
    ]

    total_table = Table(total_data, colWidths=[200, 100])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 5), (1, 5), 'Helvetica-Bold'),  # TOTAL TTC en gras
        ('FONTNAME', (0, 7), (1, 7), 'Helvetica-Bold'),  # SOLDE DÛ en gras
        ('TEXTCOLOR', (0, 7), (1, 7), colors.red),
    ]))
    elements.append(total_table)

    doc.build(elements)

    from django.core.files.base import ContentFile
    filename = f"{facture.numero_facture}.pdf"
    facture.fichier_pdf.save(filename, ContentFile(buffer.getvalue()))
    facture.save()

    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=filename)


@login_required
@client_access
def facture_telecharger_pdf(request, pk):
    """Télécharger le PDF d'une facture"""
    facture = get_object_or_404(FactureConsommation, pk=pk)

    if not facture.fichier_pdf:
        return facture_generer_pdf(request, pk)

    return FileResponse(
        facture.fichier_pdf.open('rb'),
        as_attachment=True,
        filename=f"{facture.numero_facture}.pdf"
    )


# ==================== GÉNÉRATION DES FACTURES ====================

class GenererFacturesView(LoginRequiredMixin, AdminOrAgentRequiredMixin, TemplateView):
    """Générer des factures pour une période"""
    template_name = 'facturation/generer.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Générer des Factures',
            'form': GenererFacturesForm(),
        })
        return context

    def post(self, request, *args, **kwargs):
        form = GenererFacturesForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'form': form})

        periode = form.cleaned_data['periode']
        date_echeance_jours = form.cleaned_data['date_echeance_jours']

        # Créer le batch de suivi
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        batch = BatchFacturation.objects.create(
            reference=f"BATCH-{timestamp}",
            periode=periode,
            description=f"Génération pour {periode.strftime('%B %Y')}",
            statut='EN_COURS',
            cree_par=request.user,
            started_at=timezone.now()
        )

        # ✅ CORRIGÉ: toutes les consommations validées de la période,
        # sans filtre par agent (100% Shelly EM, pas d'agent terrain)
        consommations = Consommation.objects.filter(
            periode=periode,
            statut='VALIDÉ',
            source = 'SHELLY_MENSUEL',
        ).select_related('compteur', 'compteur__type_tarification')

        batch.total_factures = consommations.count()
        batch.save()

        factures_creees = 0
        erreurs = []

        for conso in consommations:
            try:
                # Ignorer si facture déjà existante pour ce compteur/période
                if FactureConsommation.objects.filter(
                    compteur=conso.compteur,
                    periode=periode
                ).exists():
                    continue

                # Créer la facture en appliquant la tarification du compteur
                facture = FactureConsommation.creer_depuis_consommation(
                    consommation=conso,
                    user=request.user
                )

                # Ajuster l'échéance selon le paramètre du formulaire
                facture.date_echeance = timezone.now().date() + timedelta(days=date_echeance_jours)
                facture.montant_total_ttc = facture.total_ttc
                facture.save()

                factures_creees += 1
                batch.factures_generees += 1
                batch.total_ttc += facture.total_ttc
                batch.total_consommation_kwh += facture.consommation_kwh
                batch.progression = int(
                    (factures_creees + len(erreurs)) / batch.total_factures * 100
                )
                batch.save()

            except Exception as e:
                erreurs.append(f"Compteur {conso.compteur.numero_contrat}: {str(e)}")
                batch.factures_erreur += 1
                batch.save()

        # Finaliser le batch
        batch.statut = 'TERMINE' if not erreurs else 'ERREUR'
        batch.completed_at = timezone.now()
        batch.progression = 100
        if erreurs:
            batch.erreurs = '\n'.join(erreurs)
        batch.save()

        messages.success(
            request,
            f"{factures_creees} facture(s) générée(s) pour {periode.strftime('%B %Y')}."
        )
        if erreurs:
            messages.warning(request, f"{len(erreurs)} erreur(s) lors de la génération.")

        return redirect('facturation:batch_detail', pk=batch.pk)

class BatchDetailView(LoginRequiredMixin, AdminOrAgentRequiredMixin, DetailView):
    """Détail d'un batch de facturation"""
    model = BatchFacturation
    template_name = 'facturation/batch_detail.html'
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch = self.object

        factures = FactureConsommation.objects.filter(
            periode=batch.periode,
            date_emission=batch.date_generation
        ).select_related('compteur', 'compteur__menage')

        context['factures'] = factures
        return context


# ==================== VUES DE STATISTIQUES ====================

class StatsFacturesView(LoginRequiredMixin, AdminOrAgentRequiredMixin, TemplateView):
    """Statistiques des factures"""
    template_name = 'facturation/stats.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.now().date()
        debut_annee = date(today.year, 1, 1)

        date_debut = self.request.GET.get('date_debut', debut_annee.strftime('%Y-%m-%d'))
        date_fin = self.request.GET.get('date_fin', today.strftime('%Y-%m-%d'))

        try:
            date_debut_dt = datetime.strptime(date_debut, '%Y-%m-%d').date()
            date_fin_dt = datetime.strptime(date_fin, '%Y-%m-%d').date()
        except ValueError:
            date_debut_dt = debut_annee
            date_fin_dt = today

        factures = FactureConsommation.objects.filter(
            date_emission__range=[date_debut_dt, date_fin_dt]
        ).annotate(
            # ✅ CORRIGÉ: annotation ORM pour les agrégations
            solde_calcule=ExpressionWrapper(
                F('montant_total_ttc') - F('montant_paye'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        stats_globales = factures.aggregate(
            total_factures=Count('id'),
            montant_total=Sum('montant_total_ttc'),
            montant_paye=Sum('montant_paye'),
            montant_impaye=Sum('solde_calcule'),
            consommation_totale=Sum('consommation_kwh'),
            facture_moyenne=Avg('montant_total_ttc'),
            consommation_moyenne=Avg('consommation_kwh')
        )

        evolution = factures.annotate(
            mois=TruncMonth('date_emission')
        ).values('mois').annotate(
            nombre=Count('id'),
            montant=Sum('montant_total_ttc'),
            consommation=Sum('consommation_kwh')
        ).order_by('mois')

        repartition_statuts = factures.values('statut').annotate(
            nombre=Count('id'),
            montant=Sum('montant_total_ttc')
        ).order_by('-nombre')

        top_clients = factures.values(
            'compteur__menage__nom_menage',
            'compteur__menage__reference_menage'
        ).annotate(
            nombre_factures=Count('id'),
            montant_total=Sum('montant_total_ttc'),
            montant_moyen=Avg('montant_total_ttc')
        ).order_by('-montant_total')[:10]

        context.update({
            'title': 'Statistiques des Factures',
            'date_debut': date_debut_dt,
            'date_fin': date_fin_dt,
            'stats_globales': stats_globales,
            'evolution': list(evolution),
            'repartition_statuts': repartition_statuts,
            'top_clients': top_clients,
        })
        return context


class StatsRecouvrementView(LoginRequiredMixin, AdminOrAgentRequiredMixin, TemplateView):
    """Statistiques de recouvrement"""
    template_name = 'facturation/stats_recouvrement.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = date.today()

        # ✅ CORRIGÉ: annotation ORM pour solde_calcule
        factures_impayees = FactureConsommation.objects.filter(
            statut__in=['ÉMISE', 'EN_RETARD', 'PARTIELLEMENT_PAYÉE']
        ).annotate(
            solde_calcule=ExpressionWrapper(
                F('montant_total_ttc') - F('montant_paye'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )

        stats = factures_impayees.aggregate(
            total_factures=Count('id'),
            montant_total=Sum('montant_total_ttc'),
            montant_paye=Sum('montant_paye'),
            montant_impaye=Sum('solde_calcule'),
        )

        taux_recouvrement = 0
        if stats['montant_total'] and stats['montant_total'] > 0:
            taux_recouvrement = (stats['montant_paye'] or 0) / stats['montant_total'] * 100

        factures_retard = factures_impayees.filter(date_echeance__lt=today)

        # ✅ CORRIGÉ: annotation jours_retard en ORM au lieu d'une property Python
        factures_retard = factures_retard.annotate(
            jours_retard_calcule=ExpressionWrapper(
                today - F('date_echeance'),
                output_field=DecimalField(max_digits=6, decimal_places=0)
            )
        )

        stats_retard = factures_retard.aggregate(
            nombre=Count('id'),
            montant=Sum('solde_calcule'),
        )

        # Répartition par ancienneté du retard
        repartition_retard = []
        for jours in [30, 60, 90, 180]:
            qs = factures_retard.filter(
                date_echeance__lt=today - timedelta(days=jours)
            )
            montant = qs.aggregate(total=Sum('solde_calcule'))['total'] or 0
            repartition_retard.append({
                'jours': jours,
                'nombre': qs.count(),
                'montant': montant
            })

        context.update({
            'title': 'Statistiques de Recouvrement',
            'stats': stats,
            'taux_recouvrement': taux_recouvrement,
            'factures_retard': factures_retard,
            'stats_retard': stats_retard,
            'repartition_retard': repartition_retard,
        })
        return context


# ==================== VUES POUR AJAX/API SIMPLE ====================

@login_required
def facture_stats_api(request):
    """API pour les statistiques de facturation (AJAX)"""
    if request.method == 'GET':
        today = date.today()
        mois = []
        montants = []
        factures_counts = []

        for i in range(11, -1, -1):
            mois_date = today.replace(day=1) - timedelta(days=30 * i)
            mois_str = mois_date.strftime('%b %Y')

            # ✅ CORRIGÉ: utilisation de montant_total_ttc (champ DB)
            factures_mois = FactureConsommation.objects.filter(
                periode__year=mois_date.year,
                periode__month=mois_date.month
            )

            montant_mois = factures_mois.aggregate(total=Sum('montant_total_ttc'))['total'] or 0
            count_mois = factures_mois.count()

            mois.append(mois_str)
            montants.append(float(montant_mois))
            factures_counts.append(count_mois)

        return JsonResponse({
            'mois': mois,
            'montants': montants,
            'counts': factures_counts,
            'total_annee': sum(montants)
        })

    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@login_required
def facture_impayees_api(request):
    """API pour les factures impayées (AJAX)"""
    # ✅ CORRIGÉ: annotation ORM pour solde_calcule
    factures_impayees = FactureConsommation.objects.filter(
        statut__in=['ÉMISE', 'EN_RETARD', 'PARTIELLEMENT_PAYÉE']
    ).annotate(
        solde_calcule=ExpressionWrapper(
            F('montant_total_ttc') - F('montant_paye'),
            output_field=DecimalField(max_digits=12, decimal_places=2)
        )
    ).order_by('date_echeance')[:10]

    results = []
    today = date.today()

    for facture in factures_impayees:
        jours_retard = max(0, (today - facture.date_echeance).days) if facture.date_echeance else 0

        results.append({
            'numero': facture.numero_facture,
            'client': facture.compteur.menage.nom_menage,
            'montant': float(facture.solde_calcule),
            'jours_retard': jours_retard,
            'date_echeance': facture.date_echeance.strftime('%d/%m/%Y') if facture.date_echeance else '',
            'url': reverse('facturation:detail', args=[facture.pk])  # ✅ CORRIGÉ: reverse importé
        })

    return JsonResponse(results, safe=False)


@login_required
def facture_info_api(request, facture_id):
    """API pour obtenir les informations d'une facture (AJAX)"""
    facture = get_object_or_404(FactureConsommation, pk=facture_id)

    user = request.user
    if not (user.role == 'ADMIN' or
            user.role == 'AGENT_TERRAIN' or
            (user.role == 'CLIENT' and facture.compteur.menage.utilisateur == user)):
        return JsonResponse({'error': 'Accès refusé'}, status=403)

    data = {
        'numero_facture': facture.numero_facture,
        'client': facture.compteur.menage.nom_menage,
        'compteur': facture.compteur.numero_contrat,
        'periode': facture.periode.strftime('%B %Y'),
        'date_emission': facture.date_emission.strftime('%d/%m/%Y'),
        'date_echeance': facture.date_echeance.strftime('%d/%m/%Y'),
        'consommation_kwh': float(facture.consommation_kwh),
        'montant_consommation': float(facture.montant_consommation),
        'montant_abonnement': float(facture.montant_abonnement),
        'tva_taux': float(facture.tva_taux),
        'tva_montant': float(facture.tva_montant),
        'redevance_communale': float(facture.redevance_communale),
        'autres_taxes': float(facture.autres_taxes),
        'total_ht': float(facture.total_ht),
        'total_ttc': float(facture.total_ttc),
        'montant_paye': float(facture.montant_paye),
        'solde_du': float(facture.solde_du),
        'pourcentage_paye': float(facture.pourcentage_paye),
        'statut': facture.statut,
        'statut_display': facture.get_statut_display(),
        'jours_retard': facture.jours_retard,
        'has_pdf': bool(facture.fichier_pdf),
        'pdf_url': facture.fichier_pdf.url if facture.fichier_pdf else '',
    }

    return JsonResponse(data)


# ==================== VUES POUR L'EXPORT ====================

@login_required
@admin_or_agent_required
def export_factures_csv(request):
    """Exporter les factures en CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="factures.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Numéro', 'Client', 'Compteur', 'Période', 'Date émission',
        'Date échéance', 'Consommation (kWh)', 'Montant consommation',
        'Montant abonnement', 'TVA (%)', 'Redevance', 'Autres taxes',
        'Total HT', 'Total TTC', 'Montant payé', 'Solde dû', 'Statut'
    ])

    factures = FactureConsommation.objects.select_related(
        'compteur', 'compteur__menage'
    ).order_by('-periode', '-date_emission')

    if request.user.role == 'AGENT_TERRAIN':
        factures = factures.filter(
            Q(compteur__menage__utilisateur__cree_par=request.user) |
            Q(compteur__menage__agent=request.user)
        )
    elif request.user.role == 'CLIENT':
        factures = factures.filter(compteur__menage__utilisateur=request.user)

    for facture in factures:
        writer.writerow([
            facture.numero_facture,
            facture.compteur.menage.nom_menage,
            facture.compteur.numero_contrat,
            facture.periode.strftime('%Y-%m'),
            facture.date_emission.strftime('%Y-%m-%d'),
            facture.date_echeance.strftime('%Y-%m-%d') if facture.date_echeance else '',
            facture.consommation_kwh,
            facture.montant_consommation,
            facture.montant_abonnement,
            facture.tva_taux,
            facture.redevance_communale,
            facture.autres_taxes,
            facture.total_ht,
            facture.total_ttc,
            facture.montant_paye,
            facture.solde_du,
            facture.get_statut_display(),
        ])

    return response


@login_required
@role_required(['CLIENT'])
def client_factures_list(request):
    """Liste des factures du client"""
    try:
        household = Menage.objects.get(utilisateur=request.user)
    except Menage.DoesNotExist:
        messages.error(request, "Aucun ménage associé à votre compte.")
        return redirect('dashboard:client_dashboard')

    # Récupérer les factures du ménage avec calcul du montant total TTC
    from django.db.models import F, ExpressionWrapper, FloatField

    factures = Facture.objects.filter(
        compteur__menage=household
    ).annotate(
        # Calcul du total HT
        total_ht=ExpressionWrapper(
            F('montant_consommation') + F('montant_abonnement'),
            output_field=FloatField()
        ),
        # Calcul du montant TVA
        montant_tva=ExpressionWrapper(
            (F('montant_consommation') + F('montant_abonnement')) * (F('tva_taux') / 100),
            output_field=FloatField()
        ),
        # Calcul du montant total TTC
        montant_total_ttc=ExpressionWrapper(
            (F('montant_consommation') + F('montant_abonnement')) * (1 + F('tva_taux') / 100) +
            F('redevance_communale') + F('autres_taxes'),
            output_field=FloatField()
        ),
        # Calcul du solde dû
        solde_du=ExpressionWrapper(
            (F('montant_consommation') + F('montant_abonnement')) * (1 + F('tva_taux') / 100) +
            F('redevance_communale') + F('autres_taxes') - F('montant_paye'),
            output_field=FloatField()
        )
    ).select_related('compteur', 'compteur__menage').order_by('-date_emission')

    # Pagination
    from django.core.paginator import Paginator
    paginator = Paginator(factures, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_title': 'Mes Factures',
        'factures': page_obj,
        'household': household,
    }

    return render(request, 'facturation/client_factures_list.html', context)



# apps/facturation/views.py - Ajoutez ces vues à la fin du fichier

# ==================== VUES POUR DOSSIERS IMPAYÉS ====================

class DossierImpayeListView(LoginRequiredMixin, AdminOrAgentRequiredMixin, ListView):
    """Liste des dossiers d'impayés"""
    model = DossierImpaye
    template_name = 'facturation/impaye_list.html'
    context_object_name = 'dossiers'
    paginate_by = 20

    def get_queryset(self):
        queryset = DossierImpaye.objects.select_related('facture', 'client').order_by('-date_creation')

        # Filtre par statut
        statut = self.request.GET.get('statut', '')
        if statut:
            queryset = queryset.filter(statut=statut)

        # Filtre par client
        client_id = self.request.GET.get('client', '')
        if client_id:
            queryset = queryset.filter(client_id=client_id)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Dossiers d\'impayés',
            'icon': 'solar:wallet-danger-bold-duotone',
            'statuts': DossierImpaye.STATUT_CHOICES,
            'statut_filter': self.request.GET.get('statut', ''),
            'total_montant': self.get_queryset().aggregate(total=Sum('montant_du'))['total'] or 0,
        })
        return context


class DossierImpayeDetailView(LoginRequiredMixin, AdminOrAgentRequiredMixin, DetailView):
    """Détail d'un dossier d'impayé"""
    model = DossierImpaye
    template_name = 'facturation/impaye_detail.html'
    context_object_name = 'dossier'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Dossier impayé #{self.object.id}',
            'paiements': Paiement.objects.filter(facture=self.object.facture).order_by('-date_paiement'),
            'relances': Relance.objects.filter(facture=self.object.facture).order_by('-date_envoi_prevue'),
        })
        return context



# ==================== VUES POUR PÉRIODES DE FACTURATION ====================

class PeriodeFacturationListView(LoginRequiredMixin, AdminOrAgentRequiredMixin, ListView):
    """Liste des périodes de facturation"""
    model = PeriodeFacturation
    template_name = 'facturation/periode_list.html'
    context_object_name = 'periodes'
    paginate_by = 20

    def get_queryset(self):
        queryset = PeriodeFacturation.objects.all().order_by('-date_debut')

        # Filtre actif/inactif
        actif = self.request.GET.get('actif', '')
        if actif == '1':
            queryset = queryset.filter(actif=True)
        elif actif == '0':
            queryset = queryset.filter(actif=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Périodes de facturation',
            'icon': 'solar:calendar-mark-bold-duotone',
            'actif_filter': self.request.GET.get('actif', ''),
        })
        return context



class PeriodeFacturationCreateView(LoginRequiredMixin, AdminOrAgentRequiredMixin, CreateView):
    model = PeriodeFacturation
    form_class = PeriodeFacturationForm  # Utiliser le formulaire personnalisé
    template_name = 'facturation/periode_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Nouvelle période de facturation',
            'submit_text': 'Créer la période',
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, "Période de facturation créée avec succès.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('facturation:periode_list')


class PeriodeFacturationUpdateView(LoginRequiredMixin, AdminOrAgentRequiredMixin, UpdateView):
    model = PeriodeFacturation
    form_class = PeriodeFacturationForm  # Utiliser le formulaire personnalisé
    template_name = 'facturation/periode_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': f'Modifier {self.object.libelle}',
            'submit_text': 'Enregistrer',
        })
        return context

    def form_valid(self, form):
        messages.success(self.request, "Période de facturation modifiée avec succès.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('facturation:periode_list')


class DossierImpayeCreateView(LoginRequiredMixin, AdminOrAgentRequiredMixin, CreateView):
    """Créer un dossier d'impayé"""
    model = DossierImpaye
    form_class = DossierImpayeForm
    template_name = 'facturation/impaye_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Nouveau dossier d\'impayé',
            'submit_text': 'Créer le dossier',
        })
        return context

    def form_valid(self, form):
        dossier = form.save(commit=False)
        dossier.date_creation = timezone.now()
        dossier.save()
        messages.success(self.request, f"Dossier d'impayé #{dossier.id} créé avec succès.")
        return redirect('facturation:impaye_detail', pk=dossier.pk)


@login_required
@admin_or_agent_required
def traiter_impaye(request, pk):
    """Traiter un dossier d'impayé"""
    dossier = get_object_or_404(DossierImpaye, pk=pk)

    if request.method == 'POST':
        form = TraiterDossierImpayeForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data.get('action')
            motif = form.cleaned_data.get('motif')

            if action == 'resoudre':
                dossier.statut = 'RESOLU'
                dossier.date_resolution = timezone.now()
                dossier.notes = motif
                dossier.save()
                messages.success(request, f"Dossier #{dossier.id} marqué comme résolu.")

            elif action == 'cloturer':
                dossier.statut = 'CLOTURE'
                dossier.date_resolution = timezone.now()
                dossier.notes = motif
                dossier.save()
                messages.success(request, f"Dossier #{dossier.id} clôturé.")

            elif action == 'relancer':
                # Créer une relance
                relance = Relance.objects.create(
                    facture=dossier.facture,
                    type_relance='EMAIL',
                    numero_relance=Relance.objects.filter(facture=dossier.facture).count() + 1,
                    sujet=f"Relance impayé - Dossier #{dossier.id}",
                    message=f"Votre dossier d'impayé #{dossier.id} est toujours en attente de règlement.\n\nMotif: {motif}",
                    destinataire_email=dossier.client.email,
                    date_envoi_prevue=timezone.now(),
                    agent=request.user,
                    statut='EN_ATTENTE'
                )
                messages.info(request, f"Relance créée pour le dossier #{dossier.id}.")

            return redirect('facturation:impaye_detail', pk=dossier.pk)
    else:
        form = TraiterDossierImpayeForm()

    return render(request, 'facturation/impaye_traiter.html', {
        'form': form,
        'dossier': dossier
    })