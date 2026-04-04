from apps.consommation.models import Consommation
from decimal import Decimal
from datetime import date

def create_consommation_from_shelly(compteur):
    from apps.consommation.models import Consommation
    from decimal import Decimal
    from datetime import date

    capteur = compteur.capteurs.first()
    if not capteur:
        return None

    periode = date.today().replace(day=1)

    # ✅ Utilise index_actuel du compteur (mis à jour par shelly_live_data_view)
    index_fin = Decimal(str(compteur.index_actuel or 0))
    puissance_kw = Decimal(str(capteur.puissance_instantanee or 0)) / 1000

    consommation_existante = Consommation.objects.filter(
        compteur=compteur,
        periode=periode
    ).first()

    if consommation_existante:
        # ✅ Met à jour index_fin seulement si la valeur a augmenté
        if index_fin > consommation_existante.index_fin_periode:
            consommation_existante.index_fin_periode = index_fin
            consommation_existante.phase_1_kwh = puissance_kw
            consommation_existante.source = 'SHELLY_AUTO'
            consommation_existante.save(update_fields=[
                'index_fin_periode', 'phase_1_kwh', 'source'
            ])
        return consommation_existante

    # Nouvelle période — index_debut = fin de la dernière consommation
    derniere = Consommation.objects.filter(
        compteur=compteur
    ).order_by('-periode').exclude(periode=periode).first()

    index_debut = derniere.index_fin_periode if derniere else (
        Decimal(str(compteur.index_initial)) if compteur.index_initial else Decimal('0')
    )

    consommation = Consommation.objects.create(
        compteur=compteur,
        periode=periode,
        index_debut_periode=index_debut,
        index_fin_periode=index_fin,
        phase_1_kwh=puissance_kw,
        source='SHELLY_AUTO',
        statut='BROUILLON',
        shelly_device_id=capteur.device_id or '',
    )

    compteur.index_actuel = index_fin
    compteur.save(update_fields=['index_actuel'])

    return consommation