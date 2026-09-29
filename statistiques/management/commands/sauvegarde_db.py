"""Commande : sauvegarde automatique de la base MySQL (UC-42).

Usage :
    python manage.py sauvegarde_db

Copie la base via ``mysqldump`` dans ``backups/`` avec horodatage.
Pour automatiser en production : planifier la commande (cron, Planificateur
de tâches Windows, ou Celery Beat).

Restauration :
    mysql -u USER -p NOM_BASE < backups/XXXX_YYYY-MM-DD.sql.gz
"""

import gzip
import os
import shutil
import subprocess
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sauvegarde la base MySQL dans backups/ (UC-42)."

    def handle(self, *args, **options):
        dossier = settings.BASE_DIR / "backups"
        dossier.mkdir(exist_ok=True)

        base = settings.DATABASES["default"]
        nom_fichier = f"{base['NAME']}_{datetime.now():%Y-%m-%d_%H%M%S}.sql.gz"
        chemin = dossier / nom_fichier

        mysql_dump = shutil.which("mysqldump")
        if mysql_dump is None:
            mysql_dump = shutil.which("mysqldump.exe")
        if mysql_dump is None:
            self.stderr.write(self.style.ERROR(
                "mysqldump introuvable dans le PATH. Installez les outils MySQL "
                "ou lancez la sauvegarde manuellement via phpMyAdmin."
            ))
            return

        commande = [
            mysql_dump,
            f"--host={base['HOST']}",
            f"--port={base['PORT']}",
            f"--user={base['USER']}",
            f"--password={base['PASSWORD']}",
            "--routines",
            "--single-transaction",
            base["NAME"],
        ]

        try:
            resultat = subprocess.run(
                commande, capture_output=True, check=True, text=True, encoding="utf-8", errors="replace"
            )
            with gzip.open(chemin, "wt", encoding="utf-8") as f:
                f.write(resultat.stdout)
            self.stdout.write(self.style.SUCCESS(
                f"Sauvegarde créée : {chemin} ({chemin.stat().st_size / 1024:.0f} Ko)"
            ))
        except subprocess.CalledProcessError as erreur:
            self.stderr.write(self.style.ERROR(
                f"Échec de la sauvegarde : {erreur.stderr[-500:]}"
            ))
        except OSError as erreur:
            self.stderr.write(self.style.ERROR(f"Échec : {erreur}"))
