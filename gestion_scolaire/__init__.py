"""
Point d'entrée du package de configuration Django.
"""

# Permet de s'assurer que l'application Celery est toujours importée
# lorsque Django démarre, afin que les tâches partagées (@shared_task) l'utilisent.
from .celery import app as celery_app

__all__ = ("celery_app",)

# --- Fallback PyMySQL pour MySQL sous Windows (décommenter si utilisation de MySQL) ---
# try:
#     import pymysql
#     pymysql.install_as_MySQLdb()
# except ImportError:
#     pass
