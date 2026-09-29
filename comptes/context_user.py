"""Utilisateur courant accessible depuis les signaux (contexte thread-local).

Les vues appellent ``set_current_user(request.user)`` autour des
enregistrements sensibles ; les signaux (ex. traçabilité des notes)
lisent ``get_current_user()`` pour connaître l'auteur.
"""

import threading

_local = threading.local()


def set_current_user(utilisateur):
    _local.utilisateur = utilisateur


def get_current_user():
    return getattr(_local, "utilisateur", None)
