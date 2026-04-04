from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json
from .models import Compteur, Capteur


from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from decimal import Decimal
import json

from .models import Compteur, Capteur
from apps.consommation.models import Consommation


from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from decimal import Decimal
import json

from .models import Compteur, Capteur
from apps.consommation.models import Consommation


@csrf_exempt
def shelly_energy_webhook(request):
    if request.method != 'POST':
        return HttpResponse('Méthode non autorisée', status=405)

    try:
        data = json.loads(request.body)

        device_id = data.get('device_id')

        # 🔥 Support Shelly 3EM réel
        emeters = data.get('emeters', [])

        if emeters:
            total_energy = sum([e.get("total", 0) for e in emeters])
            total_power = sum([e.get("power", 0) for e in emeters])
        else:
            total_energy = data.get('energy_total', 0)
            total_power = data.get('power', 0)

        capteur = Capteur.objects.select_related("compteur").filter(device_id=device_id).first()

        if not capteur:
            return HttpResponse('Capteur non trouvé', status=404)

        # 🔄 MAJ CAPTEUR
        capteur.energie_totale = Decimal(total_energy)
        capteur.puissance_instantanee = Decimal(total_power)
        capteur.derniere_communication = timezone.now()
        capteur.status = 'ACTIF'
        capteur.save()

        compteur = capteur.compteur

        if compteur:
            ancien_index = compteur.index_actuel or 0

            compteur.index_actuel = Decimal(total_energy)
            compteur.shelly_status = 'CONNECTE'
            compteur.derniere_sync_shelly = timezone.now()
            compteur.save()

            # 🔥 CREATION CONSOMMATION AUTOMATIQUE
            if compteur.index_actuel > ancien_index:
                Consommation.objects.create(
                    compteur=compteur,
                    index_debut_periode=ancien_index,
                    index_fin_periode=compteur.index_actuel,
                    date_releve=timezone.now(),
                    source='SHELLY',
                    statut='VALIDE'
                )

        return HttpResponse('OK', status=200)

    except json.JSONDecodeError:
        return HttpResponse('JSON invalide', status=400)

    except Exception as e:
        return HttpResponse(f'Erreur: {str(e)}', status=500)


@csrf_exempt
def shelly_status_webhook(request):
    if request.method != 'POST':
        return HttpResponse('Méthode non autorisée', status=405)

    try:
        data = json.loads(request.body)

        device_id = data.get('device_id')
        status = data.get('status', 'offline')

        capteur = Capteur.objects.select_related("compteur").filter(device_id=device_id).first()

        if not capteur:
            return HttpResponse('Capteur non trouvé', status=404)

        is_online = status == "online"

        capteur.status = 'ACTIF' if is_online else 'INACTIF'
        capteur.derniere_communication = timezone.now()
        capteur.save()

        if capteur.compteur:
            capteur.compteur.shelly_status = 'CONNECTE' if is_online else 'DECONNECTE'
            capteur.compteur.save()

        return HttpResponse('OK', status=200)

    except Exception as e:
        return HttpResponse(f'Erreur: {str(e)}', status=500)