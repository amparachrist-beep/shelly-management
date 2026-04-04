# apps/parametrage/management/commands/clean_brazzaville_doublon.py
"""
Commande pour nettoyer la localité "Brazzaville" qui chevauche les quartiers
"""
from django.core.management.base import BaseCommand
from apps.parametrage.models import Departement, Localite


class Command(BaseCommand):
    help = 'Supprime ou corrige la localité Brazzaville en doublon'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('NETTOYAGE DES DOUBLONS BRAZZAVILLE'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        dept_brazza = Departement.objects.filter(nom__icontains='brazza').first()

        if not dept_brazza:
            self.stdout.write(self.style.ERROR('❌ Département Brazzaville non trouvé'))
            return

        # Chercher la localité "Brazzaville" (qui ne devrait pas exister)
        localite_brazza = Localite.objects.filter(
            nom__iexact='Brazzaville',
            departement=dept_brazza
        ).first()

        if localite_brazza:
            self.stdout.write(f'\n⚠️  Localité "Brazzaville" trouvée:')
            self.stdout.write(f'   - ID: {localite_brazza.id}')
            self.stdout.write(f'   - Type: {localite_brazza.type_localite}')
            self.stdout.write(f'   - A un polygone: {"Oui" if localite_brazza.geom else "Non"}')

            # Supprimer cette localité car elle chevauche les quartiers
            localite_brazza.delete()
            self.stdout.write(self.style.SUCCESS('   ✅ Localité "Brazzaville" supprimée'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Aucune localité "Brazzaville" en doublon'))

        # Vérifier qu'il ne reste que des quartiers
        localites = Localite.objects.filter(departement=dept_brazza)

        self.stdout.write(f'\n📊 Localités restantes dans Brazzaville:')
        for loc in localites:
            self.stdout.write(f'   - {loc.nom} ({loc.type_localite})')

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('✅ NETTOYAGE TERMINÉ'))
        self.stdout.write('=' * 80)

        self.stdout.write('\n💡 Relancez maintenant: python manage.py corriger_quartiers_brazza\n')