# apps/parametrage/migrations/0006_populate_typehabitation.py
from django.db import migrations

TYPES_A_CREER = [
    {'code': 'MAISON', 'nom': 'Maison'},
    {'code': 'APPARTEMENT', 'nom': 'Appartement'},
    {'code': 'VILLA', 'nom': 'Villa'},
    {'code': 'BANCO', 'nom': 'Banco'},
    {'code': 'AUTRE', 'nom': 'Autre'},
]

def create_type_habitation(apps, schema_editor):
    TypeHabitation = apps.get_model('parametrage', 'TypeHabitation')
    for type_data in TYPES_A_CREER:
        TypeHabitation.objects.update_or_create(
            code=type_data['code'],
            defaults={'nom': type_data['nom']}
        )

def delete_type_habitation(apps, schema_editor):
    TypeHabitation = apps.get_model('parametrage', 'TypeHabitation')
    for type_data in TYPES_A_CREER:
        TypeHabitation.objects.filter(code=type_data['code']).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('parametrage', '0005_typehabitation'),
    ]
    operations = [
        migrations.RunPython(create_type_habitation, reverse_code=delete_type_habitation),
    ]