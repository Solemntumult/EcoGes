"""Context processors : menu de navigation et libellés par rôle."""

from .services import get_menu


def menu_app(request):
    return {"menu_app": get_menu(getattr(request, "user", None))}
