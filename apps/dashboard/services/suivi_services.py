from django.db.models import Sum, Avg, F, Q, Count, FloatField, ExpressionWrapper
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta, date
from typing import Dict, Any, List

from apps.consommation.models import Consommation, ConsommationJournaliere, AnomalieConsommation
from apps.menages.models import Menage
from apps.compteurs.models import Compteur
from apps.parametrage.models import Departement, Localite
from apps.dashboard.utils import calculate_variation
from apps.facturation.models import FactureConsommation
from apps.paiements.models import Paiement
from apps.alertes.models import Alerte

class SuiviService:
    """Service principal pour les données de suivi des consommations"""

    @staticmethod
    def get_global_stats(date_debut: date, date_fin: date) -> Dict[str, Any]:
        """
        Statistiques globales pour l'admin - VERSION SIMPLIFIÉE ET CORRIGÉE
        """
        # Période précédente pour comparaison
        delta = date_fin - date_debut
        prev_debut = date_debut - delta
        prev_fin = date_debut - timedelta(days=1)

        # ✅ Étape 1: Récupérer les IDs des compteurs actifs
        compteurs_actifs = Compteur.objects.filter(statut='ACTIF').values_list('id', flat=True)

        # ✅ Étape 2: Requête de base avec filtre explicite
        consos = Consommation.objects.filter(
            compteur_id__in=compteurs_actifs,
            periode__gte=date_debut,
            periode__lte=date_fin
        )

        # Statistiques principales avec agrégations simples
        stats = consos.aggregate(
            total_consommation=Sum(F('index_fin_periode') - F('index_debut_periode')),
            consommation_phase1=Sum('phase_1_kwh'),
            consommation_phase2=Sum('phase_2_kwh'),
            consommation_phase3=Sum('phase_3_kwh'),
            puissance_max_moyenne=Avg('puissance_max_kw'),
            puissance_moyenne=Avg('puissance_moyenne_kw'),
            nombre_mois=Count('periode', distinct=True),
            nombre_compteurs=Count('compteur_id', distinct=True),
            nombre_anomalies=Count('id', filter=Q(anomalie=True))
        )

        # Période précédente
        prev_consos = Consommation.objects.filter(
            compteur_id__in=compteurs_actifs,
            periode__gte=prev_debut,
            periode__lte=prev_fin
        )
        prev_total = prev_consos.aggregate(
            total=Sum(F('index_fin_periode') - F('index_debut_periode'))
        )['total'] or 0

        current_total = stats['total_consommation'] or 0
        variation = calculate_variation(float(current_total), float(prev_total))

        # ✅ Étape 3: Top départements - APPROCHE SÉCURISÉE
        # Récupérer d'abord tous les départements
        tous_departements = Departement.objects.all()
        top_departements = []

        for dept in tous_departements:
            # Récupérer les compteurs de ce département
            compteurs_dept = Compteur.objects.filter(
                menage__localite__departement=dept,
                statut='ACTIF'
            ).values_list('id', flat=True)

            # Calculer la consommation
            conso = Consommation.objects.filter(
                compteur_id__in=compteurs_dept,
                periode__gte=date_debut,
                periode__lte=date_fin
            ).aggregate(
                total=Sum(F('index_fin_periode') - F('index_debut_periode'))
            )['total'] or 0

            if conso > 0:
                top_departements.append({
                    'id': dept.id,
                    'nom': dept.nom,
                    'consommation_totale': conso,
                    'nombre_menages': Menage.objects.filter(localite__departement=dept).count(),
                    'nombre_compteurs': compteurs_dept.count()
                })

        # Trier et limiter
        top_departements = sorted(top_departements, key=lambda x: x['consommation_totale'], reverse=True)[:5]

        # ✅ Étape 4: Évolution mensuelle - APPROCHE SIMPLE
        mois = []
        mois_data = []

        mois_courant = date_debut.replace(day=1)
        while mois_courant <= date_fin.replace(day=1):
            mois_suivant = mois_courant.replace(
                day=1,
                month=mois_courant.month + 1 if mois_courant.month < 12 else 1,
                year=mois_courant.year + 1 if mois_courant.month == 12 else mois_courant.year
            )

            conso_mois = Consommation.objects.filter(
                compteur_id__in=compteurs_actifs,
                periode=mois_courant
            ).aggregate(
                total=Sum(F('index_fin_periode') - F('index_debut_periode'))
            )['total'] or 0

            mois_data.append({
                'mois': mois_courant,
                'total': float(conso_mois),
                'moyenne': float(conso_mois) / max(compteurs_actifs.count(), 1)
            })

            mois.append(mois_courant.strftime('%Y-%m'))
            mois_courant = mois_suivant

        return {
            'stats': stats,
            'variation': variation,
            'current_total': float(current_total),
            'prev_total': float(prev_total),
            'top_departements': top_departements,
            'evolution': mois_data,
            'date_debut': date_debut,
            'date_fin': date_fin
        }

    @staticmethod
    def get_departement_stats(departement_id: int, date_debut: date, date_fin: date) -> Dict[str, Any]:
        """
        Statistiques pour un département spécifique - APPROCHE SIMPLE
        """
        departement = Departement.objects.get(pk=departement_id)

        # Récupérer les compteurs du département
        compteurs_dept = Compteur.objects.filter(
            menage__localite__departement=departement,
            statut='ACTIF'
        ).values_list('id', flat=True)

        # Période précédente
        delta = date_fin - date_debut
        prev_debut = date_debut - delta
        prev_fin = date_debut - timedelta(days=1)

        # Consommations
        consos = Consommation.objects.filter(
            compteur_id__in=compteurs_dept,
            periode__gte=date_debut,
            periode__lte=date_fin
        )

        stats = consos.aggregate(
            total_consommation=Sum(F('index_fin_periode') - F('index_debut_periode')),
            total_phase1=Sum('phase_1_kwh'),
            total_phase2=Sum('phase_2_kwh'),
            total_phase3=Sum('phase_3_kwh'),
            puissance_max_moyenne=Avg('puissance_max_kw'),
            nombre_compteurs=Count('compteur_id', distinct=True),
            nombre_menages=Count('compteur__menage_id', distinct=True),
            nombre_anomalies=Count('id', filter=Q(anomalie=True))
        )

        # Période précédente
        prev_total = Consommation.objects.filter(
            compteur_id__in=compteurs_dept,
            periode__gte=prev_debut,
            periode__lte=prev_fin
        ).aggregate(
            total=Sum(F('index_fin_periode') - F('index_debut_periode'))
        )['total'] or 0

        current_total = stats['total_consommation'] or 0
        variation = calculate_variation(float(current_total), float(prev_total))

        # Statistiques par localité
        localites = Localite.objects.filter(departement=departement)
        localites_stats = []

        for localite in localites:
            compteurs_loc = Compteur.objects.filter(
                menage__localite=localite,
                statut='ACTIF'
            ).values_list('id', flat=True)

            conso_loc = Consommation.objects.filter(
                compteur_id__in=compteurs_loc,
                periode__gte=date_debut,
                periode__lte=date_fin
            ).aggregate(
                total=Sum(F('index_fin_periode') - F('index_debut_periode'))
            )['total'] or 0

            localites_stats.append({
                'id': localite.id,
                'nom': localite.nom,
                'total_consommation': conso_loc,
                'nombre_menages': Menage.objects.filter(localite=localite).count(),
                'nombre_compteurs': compteurs_loc.count(),
                'consommation_moyenne': conso_loc / max(compteurs_loc.count(), 1)
            })

        # Top localités
        localites_stats = sorted(localites_stats, key=lambda x: x['total_consommation'], reverse=True)

        # Évolution mensuelle
        evolution = []
        mois_courant = date_debut.replace(day=1)
        while mois_courant <= date_fin.replace(day=1):
            conso_mois = Consommation.objects.filter(
                compteur_id__in=compteurs_dept,
                periode=mois_courant
            ).aggregate(
                total=Sum(F('index_fin_periode') - F('index_debut_periode'))
            )['total'] or 0

            evolution.append({
                'mois': mois_courant,
                'total': float(conso_mois)
            })

            mois_suivant = mois_courant.replace(
                day=1,
                month=mois_courant.month + 1 if mois_courant.month < 12 else 1,
                year=mois_courant.year + 1 if mois_courant.month == 12 else mois_courant.year
            )
            mois_courant = mois_suivant

        return {
            'departement': departement,
            'stats': stats,
            'variation': variation,
            'localites': localites_stats,
            'evolution': evolution,
            'total_menages': Menage.objects.filter(localite__departement=departement).count(),
            'date_debut': date_debut,
            'date_fin': date_fin
        }

    @staticmethod
    def get_localite_stats(localite_id: int, date_debut: date, date_fin: date) -> Dict[str, Any]:
        localite = Localite.objects.select_related('departement').get(pk=localite_id)

        # ── Ménages ──────────────────────────────────────────────
        menages_qs = Menage.objects.filter(localite=localite)
        total_menages = menages_qs.count()
        menages_actifs = menages_qs.filter(statut='ACTIF').count()
        menages_inactifs = menages_qs.filter(statut='INACTIF').count()
        menages_demenages = menages_qs.filter(statut='DEMENAGE').count()

        # ── Compteurs actifs de la localité ──────────────────────
        compteurs_loc = list(
            Compteur.objects.filter(
                menage__localite=localite,
                statut='ACTIF'
            ).values_list('id', flat=True)
        )

        # ── Période précédente ────────────────────────────────────
        delta = date_fin - date_debut
        prev_debut = date_debut - delta - timedelta(days=1)
        prev_fin = date_debut - timedelta(days=1)

        # ── Consommations période courante ────────────────────────
        consos = Consommation.objects.filter(
            compteur_id__in=compteurs_loc,
            periode__gte=date_debut,
            periode__lte=date_fin
        )

        conso_agg = consos.aggregate(
            total_phase1=Sum('phase_1_kwh'),
            total_phase2=Sum('phase_2_kwh'),
            total_phase3=Sum('phase_3_kwh'),
            puissance_max_moyenne=Avg('puissance_max_kw'),
            nombre_compteurs=Count('compteur_id', distinct=True),
        )

        total_consommation = float(
            (conso_agg['total_phase1'] or 0) +
            (conso_agg['total_phase2'] or 0) +
            (conso_agg['total_phase3'] or 0)
        )
        moyenne_consommation = (
            round(total_consommation / total_menages, 2) if total_menages > 0 else 0
        )

        # ── Consommation période précédente ───────────────────────
        prev_consos = Consommation.objects.filter(
            compteur_id__in=compteurs_loc,
            periode__gte=prev_debut,
            periode__lte=prev_fin
        ).aggregate(
            p1=Sum('phase_1_kwh'),
            p2=Sum('phase_2_kwh'),
            p3=Sum('phase_3_kwh'),
        )
        prev_total = float(
            (prev_consos['p1'] or 0) +
            (prev_consos['p2'] or 0) +
            (prev_consos['p3'] or 0)
        )
        variation_conso = calculate_variation(total_consommation, prev_total)

        # ── Facturation / Recouvrement ────────────────────────────
        # ✅ FactureConsommation au lieu de Facture
        factures_qs = FactureConsommation.objects.filter(
            compteur__menage__localite=localite
        )
        montant_facture = float(
            factures_qs.filter(
                date_emission__gte=date_debut,
                date_emission__lte=date_fin
            ).aggregate(t=Sum('montant_consommation'))['t'] or 0
        )
        montant_recouvre = float(
            Paiement.objects.filter(
                facture__compteur__menage__localite=localite,
                statut='CONFIRMÉ',
                date_paiement__gte=date_debut,
                date_paiement__lte=date_fin
            ).aggregate(t=Sum('montant'))['t'] or 0
        )
        taux_recouvrement = round(
            (montant_recouvre / montant_facture * 100) if montant_facture > 0 else 0, 1
        )

        # ✅ FactureConsommation au lieu de Facture
        factures_impayees = FactureConsommation.objects.filter(
            compteur__menage__localite=localite,
            statut__in=['ÉMISE', 'PARTIELLEMENT_PAYÉE', 'EN_RETARD']
        ).select_related('compteur__menage').order_by('date_echeance')

        total_impayes = float(
            factures_impayees.aggregate(t=Sum('montant_consommation'))['t'] or 0
        )

        # ── Alertes ───────────────────────────────────────────────
        alertes_qs = Alerte.objects.filter(compteur__menage__localite=localite)
        total_alertes = alertes_qs.filter(statut='ACTIVE').count()
        alertes_critiques = alertes_qs.filter(statut='ACTIVE', niveau='CRITIQUE').count()
        alertes_traitees = alertes_qs.filter(
            statut='TRAITEE',
            date_detection__gte=date_debut
        ).count()

        # ── Top consommateurs ─────────────────────────────────────
        top_consommateurs = Consommation.objects.filter(
            compteur_id__in=compteurs_loc,
            periode__gte=date_debut,
            periode__lte=date_fin
        ).values(
            'compteur__menage__nom_menage',
            'compteur__menage__reference_menage',
            'compteur__menage__statut',
        ).annotate(
            total=Sum('phase_1_kwh') + Sum('phase_2_kwh') + Sum('phase_3_kwh')
        ).order_by('-total')[:10]

        # ── Évolution mensuelle ───────────────────────────────────
        evolution = []
        mois_courant = date_debut.replace(day=1)
        while mois_courant <= date_fin.replace(day=1):
            c = Consommation.objects.filter(
                compteur_id__in=compteurs_loc,
                periode=mois_courant
            ).aggregate(
                p1=Sum('phase_1_kwh'),
                p2=Sum('phase_2_kwh'),
                p3=Sum('phase_3_kwh'),
            )
            total_mois = float((c['p1'] or 0) + (c['p2'] or 0) + (c['p3'] or 0))
            evolution.append({'mois': mois_courant, 'total': total_mois})

            m = mois_courant.month + 1
            y = mois_courant.year + (1 if m > 12 else 0)
            mois_courant = mois_courant.replace(year=y, month=(m - 1) % 12 + 1, day=1)

        # ── Tous les ménages (pour le tableau) ────────────────────
        menages = menages_qs.select_related(
            'type_habitation', 'utilisateur'
        ).prefetch_related('compteurs')

        # ── Stats dict ────────────────────────────────────────────
        stats = {
            'total_menages': total_menages,
            'menages_actifs': menages_actifs,
            'menages_inactifs': menages_inactifs,
            'menages_suspendus': menages_demenages,
            'total_consommation': round(total_consommation, 2),
            'moyenne_consommation': moyenne_consommation,
            'variation_conso': variation_conso,
            'taux_recouvrement': taux_recouvrement,
            'montant_recouvre': round(montant_recouvre, 0),
            'total_impayes': round(total_impayes, 0),
            'total_alertes': total_alertes,
            'alertes_critiques': alertes_critiques,
            'alertes_traitees': alertes_traitees,
            'repartition_statuts': total_menages > 0,
        }

        return {
            'localite': localite,
            'stats': stats,
            'menages': menages,
            'top_consommateurs': list(top_consommateurs),
            'factures_impayees': factures_impayees,
            'evolution': evolution,
            'date_debut': date_debut,
            'date_fin': date_fin,
        }

    @staticmethod
    def get_menage_stats(menage_id: int, date_debut: date, date_fin: date) -> Dict[str, Any]:
        """
        Statistiques pour un ménage spécifique
        """
        menage = Menage.objects.select_related('localite', 'localite__departement').get(pk=menage_id)

        # Récupérer les compteurs du ménage
        compteurs_menage = Compteur.objects.filter(menage=menage, statut='ACTIF').values_list('id', flat=True)

        # Période précédente
        delta = date_fin - date_debut
        prev_debut = date_debut - delta
        prev_fin = date_debut - timedelta(days=1)

        # Consommations
        consos = Consommation.objects.filter(
            compteur_id__in=compteurs_menage,
            periode__gte=date_debut,
            periode__lte=date_fin
        )

        stats = consos.aggregate(
            total_consommation=Sum(F('index_fin_periode') - F('index_debut_periode')),
            total_phase1=Sum('phase_1_kwh'),
            total_phase2=Sum('phase_2_kwh'),
            total_phase3=Sum('phase_3_kwh'),
            puissance_max_moyenne=Avg('puissance_max_kw'),
            puissance_moyenne=Avg('puissance_moyenne_kw'),
            nombre_anomalies=Count('id', filter=Q(anomalie=True))
        )

        # Période précédente
        prev_total = Consommation.objects.filter(
            compteur_id__in=compteurs_menage,
            periode__gte=prev_debut,
            periode__lte=prev_fin
        ).aggregate(
            total=Sum(F('index_fin_periode') - F('index_debut_periode'))
        )['total'] or 0

        current_total = stats['total_consommation'] or 0
        variation = calculate_variation(float(current_total), float(prev_total))

        # Évolution mensuelle
        evolution = []
        mois_courant = date_debut.replace(day=1)
        while mois_courant <= date_fin.replace(day=1):
            conso_mois = Consommation.objects.filter(
                compteur_id__in=compteurs_menage,
                periode=mois_courant
            ).aggregate(
                total=Sum(F('index_fin_periode') - F('index_debut_periode'))
            )['total'] or 0

            evolution.append({
                'mois': mois_courant,
                'total': float(conso_mois)
            })

            mois_suivant = mois_courant.replace(
                day=1,
                month=mois_courant.month + 1 if mois_courant.month < 12 else 1,
                year=mois_courant.year + 1 if mois_courant.month == 12 else mois_courant.year
            )
            mois_courant = mois_suivant

        return {
            'menage': menage,
            'stats': stats,
            'variation': variation,
            'evolution': evolution,
            'date_debut': date_debut,
            'date_fin': date_fin
        }

    @staticmethod
    def get_compteur_stats(compteur_id: int, date_debut: date, date_fin: date) -> Dict[str, Any]:
        """
        Statistiques pour un compteur spécifique
        """
        compteur = Compteur.objects.select_related('menage', 'menage__localite', 'menage__localite__departement').get(
            pk=compteur_id)

        # Période précédente
        delta = date_fin - date_debut
        prev_debut = date_debut - delta
        prev_fin = date_debut - timedelta(days=1)

        # Consommations mensuelles
        consos = Consommation.objects.filter(
            compteur=compteur,
            periode__gte=date_debut,
            periode__lte=date_fin
        ).order_by('periode')

        stats = consos.aggregate(
            total_consommation=Sum(F('index_fin_periode') - F('index_debut_periode')),
            total_phase1=Sum('phase_1_kwh'),
            total_phase2=Sum('phase_2_kwh'),
            total_phase3=Sum('phase_3_kwh'),
            puissance_max_moyenne=Avg('puissance_max_kw'),
            puissance_moyenne=Avg('puissance_moyenne_kw'),
            nombre_mois=Count('id'),
            nombre_anomalies=Count('id', filter=Q(anomalie=True))
        )

        # Période précédente
        prev_total = Consommation.objects.filter(
            compteur=compteur,
            periode__gte=prev_debut,
            periode__lte=prev_fin
        ).aggregate(
            total=Sum(F('index_fin_periode') - F('index_debut_periode'))
        )['total'] or 0

        current_total = stats['total_consommation'] or 0
        variation = calculate_variation(float(current_total), float(prev_total))

        return {
            'compteur': compteur,
            'stats': stats,
            'variation': variation,
            'consommations': consos,
            'date_debut': date_debut,
            'date_fin': date_fin
        }