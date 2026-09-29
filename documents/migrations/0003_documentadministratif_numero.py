# Étape 1 : ajout du champ (nullable, sans contrainte unique) — le backfill
# (0004) attribue les numéros, puis 0005 applique la contrainte unique.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentadministratif',
            name='numero',
            field=models.CharField(blank=True, editable=False, help_text="N° d'enregistrement (ex. CER-2026-000001)", max_length=30, null=True),
        ),
    ]
