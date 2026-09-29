"""Services du module Paramétrage : établissement et contexte commun aux documents."""

import base64
from decimal import Decimal

from django.conf import settings

from .models import ClasseMatiereCoefficient, Etablissement, LogoEtablissement


def obtenir_etablissement():
    """Retourne l'unique configuration de l'établissement (créée si absente)."""
    return Etablissement.obtenir()


def coefficient_matiere_classe(classe, matiere):
    """Coefficient d'une matière pour une classe précise (défaut : 1).

    Source unique de vérité : ``ClasseMatiereCoefficient``. Aucun coefficient
    n'est stocké sur la matière elle-même.
    """
    cmc = ClasseMatiereCoefficient.objects.filter(classe=classe, matiere=matiere).first()
    return cmc.coefficient if cmc else Decimal("1")


def _data_uri(fichier):
    """Transforme un fichier image (ImageFieldFile) en URI data:image/png;base64,...

    Les PDF (WeasyPrint) et l'aperçu temps réel de l'éditeur affichent les images
    de façon fiable via des data URIs, quel que soit l'hébergement des fichiers
    (MEDIA_ROOT local, CDN...).
    """
    if not fichier or not fichier.name:
        return ""
    try:
        contenu = fichier.read()
    except (OSError, ValueError):
        return ""
    return "data:image/png;base64," + base64.b64encode(contenu).decode()


def contexte_etablissement():
    """Contexte à injecter dans les rendus PDF : ``{"etab": ..., "logos_entete": [...]}``.

    Ajouté automatiquement par le moteur PDF (``documents.pdf``) à tous les
    gabarits — logo(s), nom officiel, adresse, IFU, signataires, mentions légales.

    ``logos_entete`` est une liste de dicts ``{"libelle", "data_uri"}`` : tous les
    logos cochés « en-tête », triés. ``logo_principal`` est l'ancien champ unique
    (repli si aucun logo multiple n'est défini).
    """
    etab = Etablissement.obtenir()
    logos = [
        {"libelle": logo.libelle or "Logo", "data_uri": _data_uri(logo.image)}
        for logo in etab.logos_en_tete
    ]
    return {
        "etab": etab,
        "logos_entete": logos,
        "logo_principal": _data_uri(etab.logo),
    }
