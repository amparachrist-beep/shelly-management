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
        """
        Statistiques pour une localité spécifique
        """
        localite = Localite.objects.select_related('departement').get(pk=localite_id)

        # Récupérer les compteurs de la localité
        compteurs_loc = Compteur.objects.filter(
            menage__localite=localite,
            statut='ACTIF'
        ).values_list('id', flat=True)

        # Période précédente
        delta = date_fin - date_debut
        prev_debut = date_debut - delta
        prev_fin = date_debut - timedelta(days=1)

        # Consommations
        consos = Consommation.objects.filter(
            compteur_id__in=compteurs_loc,
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
            compteur_id__in=compteurs_loc,
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
                compteur_id__in=compteurs_loc,
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
            'localite': localite,
            'stats': stats,
            'variation': variation,
            'evolution': evolution,
            'total_menages': Menage.objects.filter(localite=localite).count(),
            'date_debut': date_debut,
            'date_fin': date_fin
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