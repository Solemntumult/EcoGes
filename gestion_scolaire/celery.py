import os
from celery import Celery

# Définir le module de paramètres Django par défaut pour le programme 'celery'.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gestion_scolaire.settings")

app = Celery("gestion_scolaire")

# Utiliser une chaîne ici pour que le worker n'ait pas besoin de sérialiser
# l'objet de configuration vers les processus enfants.
# Le namespace='CELERY' signifie que toutes les clés de configuration Celery
# doivent avoir le préfixe 'CELERY_'.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Charger automatiquement les modules de tâches (tasks.py) de toutes les applications Django enregistrées.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
