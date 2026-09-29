"""Attribue un numéro d'enregistrement aux documents administratifs existants."""

from collections import defaultdict

from django.db import migrations

PREFIXES = {
    "CERTIFICAT_SCOLARITE": "CER",
    "ATTESTATION_REUSSITE": "ATT",
    "RELEVE_NOTES": "REL",
    "LISTE_CLASSE": "LIS",
    "CONVOCATION": "COU",
    "AVIS_RELANCE": "AVR",
    "CARTE_SCOLAIRE": "CAR",
}


def backfill(apps, schema_editor):
    DocumentAdministratif = apps.get_model("documents", "DocumentAdministratif")
    compteurs = defaultdict(int)
    for doc in DocumentAdministratif.objects.order_by("date_generation", "pk"):
        if doc.numero:
            continue
        prefixe = PREFIXES.get(doc.type_document, "DOC")
        compteurs[prefixe] += 1
        doc.numero = f"{prefixe}-{doc.date_generation.year}-{compteurs[prefixe]:06d}"
        doc.save(update_fields=["numero"])


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0003_documentadministratif_numero"),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
