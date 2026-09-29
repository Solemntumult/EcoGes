"""Moteur de génération PDF (WeasyPrint) partagé par toutes les apps.

WeasyPrint nécessite la bibliothèque système GTK pour fonctionner sur
Windows. Pour rester robuste, ``reponse_pdf`` bascule sur un rendu HTML
téléchargeable si WeasyPrint n'est pas disponible.
"""

import base64
import io

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string


class PdvNonDisponible(Exception):
    """Levée quand WeasyPrint ne peut pas rendre de PDF."""


def _injecter_etablissement(contexte):
    """Ajoute l'identité de l'établissement à tout contexte de rendu.

    Un seul point d'injection : tous les gabarits PDF (bulletins, factures,
    reçus, certificats...) accèdent alors à ``{{ etab.nom_officiel }}``,
    ``{{ etab.logo.url }}``, ``{{ etab.ifu }}``, etc.
    """
    if "etab" not in contexte:
        from parametrage.services import contexte_etablissement
        contexte.update(contexte_etablissement())
    return contexte


def rendre_html(template, contexte):
    return render_to_string(template, _injecter_etablissement(contexte))


def _activer_runtime_gtk():
    """Windows : rend les DLL GTK3 (Pango/Cairo) accessibles à WeasyPrint.

    Le runtime GTK est installé hors du PATH Python. On ajoute son dossier
    ``bin`` via ``os.add_dll_directory`` (et le PATH) pour que cffi/WeasyPrint
    trouvent les bibliothèques natives, quel que soit le PATH du shell qui a
    démarré le serveur (souvent lancé avant l'installation du runtime).
    """
    import os
    import sys

    if sys.platform != "win32":
        return
    candidats = [
        r"C:\Program Files\GTK3-Runtime Win64\bin",
        r"C:\Program Files (x86)\GTK3-Runtime Win32\bin",
        os.path.expandvars(r"%USERPROFILE%\gtk-runtime\bin"),
    ]
    ajoutes = set()
    for dossier in candidats:
        if dossier and os.path.isdir(dossier) and dossier not in ajoutes:
            ajoutes.add(dossier)
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(dossier)
                except OSError:
                    pass
            os.environ["PATH"] = dossier + os.pathsep + os.environ.get("PATH", "")


def pdf_bytes(template, contexte):
    """Rend un gabarit HTML en PDF (octets). Lève PdvNonDisponible sinon."""
    html = rendre_html(template, contexte)
    try:
        _activer_runtime_gtk()
        from weasyprint import HTML
    except ImportError as exc:
        raise PdvNonDisponible(str(exc))
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


def reponse_pdf(template, contexte, nom_fichier):
    """Retourne une HttpResponse PDF (fallback HTML si WeasyPrint absent)."""
    try:
        data = pdf_bytes(template, contexte)
        content_type = "application/pdf"
        suffixe = ".pdf"
    except PdvNonDisponible:
        data = rendre_html(template, contexte)
        content_type = "text/html; charset=utf-8"
        suffixe = ".html"
    reponse = HttpResponse(data, content_type=content_type)
    reponse["Content-Disposition"] = f'inline; filename="{nom_fichier}{suffixe}"'
    return reponse


def qr_data_uri(donnees):
    """Génère un QR code PNG (base64) pour les cartes scolaires."""
    import qrcode
    qr = qrcode.make(donnees)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
