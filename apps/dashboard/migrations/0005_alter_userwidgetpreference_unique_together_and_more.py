from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_delete_cacheddashboarddata'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='userwidgetpreference',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='userwidgetpreference',
            name='user_dashboard',
        ),
        migrations.RemoveField(
            model_name='userwidgetpreference',
            name='widget',
        ),
        migrations.RemoveField(
            model_name='userdashboardlayout',
            name='enabled_widgets',
        ),
        migrations.DeleteModel(
            name='DashboardAnalytics',
        ),
        migrations.DeleteModel(
            name='UserWidgetPreference',
        ),
    ]