# services/shelly_service.py
import requests
from django.utils import timezone
from decimal import Decimal


def sync_compteur_shelly(compteur):
    """
    Synchronise un compteur Shelly Pro 3EM (API Gen2 via /rpc).
    """
    capteur = compteur.capteurs.first()
    if not capteur:
        return None

    if not compteur.shelly_ip:
        return None

    url = f"http://{compteur.shelly_ip}/rpc"

    try:
        # ── Puissance instantanée (EM.GetStatus) ─────────────────────────
        payload_power = {
            "id": 1,
            "method": "EM.GetStatus",
            "params": {"id": 0}
        }
        response = requests.post(url, json=payload_power, timeout=5)
        response.raise_for_status()
        data = response.json().get('result', {})

        phase1 = float(data.get("a_act_power", 0) or 0)
        phase2 = float(data.get("b_act_power", 0) or 0)
        phase3 = float(data.get("c_act_power", 0) or 0)
        total_power = float(data.get("total_act_power", 0) or 0)

        # ── Énergie cumulée (EMData.GetStatus) ───────────────────────────
        energie_totale_kwh = float(compteur.index_actuel or 0)  # fallback
        try:
            payload_energy = {
                "id": 2,
                "method": "EMData.GetStatus",
                "params": {"id": 0}
            }
            response_energy = requests.post(url, json=payload_energy, timeout=5)
            data_energy = response_energy.json().get('result', {})

            # Shelly Pro 3EM retourne total_act_energy en Wh → kWh
            energie_wh = float(data_energy.get("total_act_energy", 0) or 0)
            if energie_wh > 0:
                energie_totale_kwh = energie_wh / 1000

        except Exception:
            pass  # On garde le fallback index_actuel

        # ── Mise à jour capteur ──────────────────────────────────────────
        capteur.puissance_instantanee = Decimal(str(total_power))
        capteur.energie_totale = Decimal(str(energie_totale_kwh))
        capteur.derniere_communication = timezone.now()
        capteur.status = 'ACTIF'
        capteur.save(update_fields=[
            'puissance_instantanee',
            'energie_totale',
            'derniere_communication',
            'status'
        ])

        # ── Mise à jour compteur ─────────────────────────────────────────
        # On ne met à jour index_actuel que si la valeur est supérieure
        # (évite d'écraser avec 0 si EMData ne répond pas)
        if energie_totale_kwh > float(compteur.index_actuel or 0):
            compteur.index_actuel = Decimal(str(energie_totale_kwh))

        compteur.shelly_status = 'CONNECTE'  # ✅ CONNECTE si EM.GetStatus répond
        compteur.derniere_sync_shelly = timezone.now()
        compteur.save(update_fields=[
            'index_actuel',
            'shelly_status',
            'derniere_sync_shelly'
        ])

        return capteur

    except requests.exceptions.Timeout:
        # Timeout = Shelly injoignable
        _marquer_deconnecte(compteur, capteur)
        return None

    except Exception:
        # Toute autre erreur réseau
        _marquer_deconnecte(compteur, capteur)
        return None


def _marquer_deconnecte(compteur, capteur):
    """Marque le compteur et le capteur comme déconnectés."""
    try:
        capteur.status = 'INACTIF'
        capteur.save(update_fields=['status'])
    except Exception:
        pass

    try:
        compteur.shelly_status = 'DECONNECTE'
        compteur.save(update_fields=['shelly_status'])
    except Exception:
        pass