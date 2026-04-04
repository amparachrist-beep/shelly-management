# apps/menages/migrations/0003_combined_type_habitation_migration.py

from django.db import migrations, models
import django.db.models.deletion


# Mapping pour convertir les anciennes valeurs en nouvelles
TYPE_MAP = {
    'MAISON': 'MAISON',
    'APPARTEMENT': 'APPARTEMENT',
    'VILLA': 'VILLA',
    'BANCO': 'BANCO',
    'AUTRE': 'AUTRE',
}


def migrate_data(apps, schema_editor):
    """
    Cette fonction de migration de données lit l'ancien champ 'type_habitation'
    (CharField) et le copie dans le nouveau champ 'type_habitation_new'
    (ForeignKey).
    """
    Menage = apps.get_model('menages', 'Menage')
    TypeHabitation = apps.get_model('parametrage', 'TypeHabitation')

    # On crée un cache pour ne pas requêter la BDD à chaque itération
    type_cache = {th.code: th for th in TypeHabitation.objects.all()}

    for menage in Menage.objects.iterator():
        old_type = menage.type_habitation  # Ancienne valeur texte
        if old_type:
            new_type_code = TYPE_MAP.get(old_type)
            if new_type_code and new_type_code in type_cache:
                # On assigne l'objet ForeignKey au NOUVEAU champ
                menage.type_habitation_new = type_cache[new_type_code]
                menage.save(update_fields=['type_habitation_new'])


class Migration(migrations.Migration):

    # Cette migration dépend de la création ET du peuplement de la table TypeHabitation
    dependencies = [
        ('menages', '0002_initial'), # La migration précédente pour menages
        ('parametrage', '0006_populate_typehabitation'), # Le peuplement des types
    ]

    operations = [
        # 1. On ajoute le nouveau champ ForeignKey avec un nom temporaire
        migrations.AddField(
            model_name='menage',
            name='type_habitation_new',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='menages_temp',
                to='parametrage.typehabitation',
                help_text="Type de compteur détaillé"
            ),
        ),

        # 2. On exécute la fonction pour déplacer les données de l'ancien champ vers le nouveau
        migrations.RunPython(migrate_data, migrations.RunPython.noop),

        # 3. On supprime l'ancien champ CharField qui contenait du texte
        migrations.RemoveField(
            model_name='menage',
            name='type_habitation',
        ),

        # 4. On renomme le nouveau champ pour qu'il remplace l'ancien
        migrations.RenameField(
            model_name='menage',
            old_name='type_habitation_new',
            new_name='type_habitation',
        ),

        # 5. On inclut l'autre modification que Django avait détectée (pour le champ utilisateur)
        migrations.AlterField(
            model_name='menage',
            name='utilisateur',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='menage',
                to='users.customuser'
            ),
        ),
    ]