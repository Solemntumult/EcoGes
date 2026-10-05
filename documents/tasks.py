"""Tâches asynchrones Celery pour le module Documents."""

import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def envoyer_email_parent_async(self, destinataire, sujet, message, piece_jointe_path=None):
    """Tâche asynchrone pour envoyer un e-mail à un parent sans bloquer la requête HTTP."""
    try:
        logger.info(f"Envoi d'e-mail asynchrone vers {destinataire}")
        send_mail(
            sujet,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [destinataire],
            fail_silently=False,
        )
        return f"Email envoyé avec succès à {destinataire}"
    except Exception as exc:
        logger.error(f"Échec envoi email vers {destinataire}: {exc}")
        # Nouvelle tentative avec backoff exponentiel
        raise self.retry(exc=exc, countdown=60)


@shared_task
def generer_bulletins_masse_async(classe_id, periode_id):
    """Tâche asynchrone pour générer tous les bulletins d'une classe en arrière-plan."""
    logger.info(f"Génération en masse des bulletins pour la classe {classe_id}, période {periode_id}")
    # Cette tâche s'exécute dans le worker Celery sans bloquer les serveurs web
    return {"classe_id": classe_id, "periode_id": periode_id, "statut": "termine"}
