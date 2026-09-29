# Étape 2 : après le backfill (0004), la colonne numero est unique.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0004_backfill_numeros'),
    ]

    operations = [
        migrations.AlterField(
            model_name='documentadministratif',
            name='numero',
            field=models.CharField(blank=True, editable=False, help_text="N° d'enregistrement (ex. CER-2026-000001)", max_length=30, null=True, unique=True),
        ),
    ]
