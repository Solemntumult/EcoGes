"""Vues du Portail parents/élèves (UC-43 à UC-45) — lecture seule.

Restriction stricte : un parent ne voit que les données des élèves dont
il est tuteur (appariement par l'e-mail du compte utilisateur).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from comptes.mixins import roles_requis
from eleves.models import Eleve, Tuteur

from documents.models import DocumentAdministratif


def _enfants_du_parent(utilisateur):
    """Élèves dont l'utilisateur est tuteur (par e-mail)."""
    if not utilisateur.email:
        return Eleve.objects.none()
    return Eleve.objects.filter(
        tuteurs__email__iexact=utilisateur.email
    ).distinct().order_by("nom", "prenoms")


@login_required
@roles_requis(["PARENT", "ADMIN", "SUPERADMIN"])
def accueil(request):
    eleves = _enfants_du_parent(request.user)
    return render(request, "portail/accueil.html", {"eleves": eleves})


@login_required
@roles_requis(["PARENT", "ADMIN", "SUPERADMIN"])
def dossier(request, eleve_pk):
    """Consultation du dossier en lecture seule (UC-43)."""
    eleve = _enfants_du_parent(request.user)
    if request.user.role != "ADMIN" and request.user.role != "SUPERADMIN":
        eleve = eleve.filter(pk=eleve_pk)
        if not eleve.exists():
            messages.error(request, "Vous n'êtes pas autorisé à consulter ce dossier.")
            return redirect("portail:accueil")

    eleve = get_object_or_404(
        Eleve.objects.prefetch_related("tuteurs"), pk=eleve_pk
    )
    inscription = eleve.inscriptions.filter(statut="ACTIVE").select_related(
        "classe", "annee_scolaire"
    ).first()

    bulletins = []
    paiements = []
    echeances = []
    situation = None
    documents = eleve.documents.all()

    if inscription:
        from evaluations.models import Bulletin
        bulletins = Bulletin.objects.filter(inscription=inscription)
        from finances.models import Echeance
        echeances = Echeance.objects.filter(inscription=inscription).order_by("date_echeance")
        paiements = inscription.paiements.select_related("recu").filter(statut="VALIDE")
        from finances.services import situation_inscription
        situation = situation_inscription(inscription)

    return render(request, "portail/dossier.html", {
        "eleve": eleve,
        "inscription": inscription,
        "bulletins": bulletins,
        "echeances": echeances,
        "paiements": paiements,
        "situation": situation,
        "documents": documents,
    })


@login_required
@roles_requis(["PARENT", "ADMIN", "SUPERADMIN"])
def document(request, doc_pk):
    """Téléchargement d'un document officiel (UC-45)."""
    doc = get_object_or_404(DocumentAdministratif, pk=doc_pk)
    if doc.eleve_id:
        eleve_ids = _enfants_du_parent(request.user).values_list("pk", flat=True)
        if request.user.role not in ("ADMIN", "SUPERADMIN") and doc.eleve_id not in eleve_ids:
            messages.error(request, "Accès refusé à ce document.")
            return redirect("portail:accueil")
    if doc.fichier_pdf:
        return redirect(doc.fichier_pdf.url)
    messages.warning(request, "Aucun fichier PDF enregistré pour ce document.")
    return redirect("portail:accueil")
