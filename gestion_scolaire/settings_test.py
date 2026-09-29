"""Paramètres de test : base SQLite en mémoire.

Permet d'exécuter ``python manage.py test`` sans serveur MySQL actif :

    python manage.py test --settings=gestion_scolaire.settings_test
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Journalisation verbeuse désactivée pendant les tests
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
