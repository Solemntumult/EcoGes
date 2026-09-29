"""Filtres de gabarit personnalisés du projet."""

from django import template

register = template.Library()


@register.filter
def get_item(dictionnaire, cle):
    """Retourne dictionnaire[cle] (None si absent)."""
    try:
        return dictionnaire.get(cle)
    except AttributeError:
        return None
