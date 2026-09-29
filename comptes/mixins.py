"""Mixins et décorateurs de contrôle d'accès par rôle (sécurité transverse)."""

from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from functools import wraps


def roles_requis(roles):
    """Décorateur : restreint une vue à certains rôles métier.

    Les utilisateurs anonymes sont redirigés vers la page de connexion,
    les autres voient une page 403.
    """

    def decorateur(vue):
        @wraps(vue)
        def _wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            # Un superutilisateur Django a toujours accès, quel que soit son rôle métier
            if not (request.user.is_superuser or request.user.role in roles):
                raise PermissionDenied
            return vue(request, *args, **kwargs)

        return _wrapper

    return decorateur


class RoleRequisMixin(UserPassesTestMixin):
    """Mixin pour vues basées sur les classes : restreint par rôle."""

    roles = []

    def test_func(self):
        return (
            self.request.user.is_authenticated
            and (self.request.user.is_superuser or self.request.user.role in self.roles)
        )
