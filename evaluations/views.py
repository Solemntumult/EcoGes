"""Vues du module Évaluations & Bulletins (UC-20 à UC-25)."""

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from comptes.mixins import roles_requis
from comptes.services import journaliser
from parametrage.models import AnneeScolaire, Classe, Periode

from .forms import BulletinsMasseForm, DecisionsForm, EvaluationForm, FormSaisieNotes
from .models import Bulletin, Evaluation, Note, NoteModification

ROLES_PEDAGO = ["ADMIN", "SUPERADMIN", "CENSEUR", "ENSEIGNANT"]


def _affectations_enseignant(utilisateur):
    """Affectations (classe/matière) de l'utilisateur connecté s'il est enseignant."""
    personnel = getattr(utilisateur, "fiche_personnel", None)
    if personnel is None:
        return None
    return personnel.affectations.all()


@login_required
@roles_requis(ROLES_PEDAGO)
def mes_evaluations(request):
    """Liste des évaluations — restreinte aux classes/matières de l'enseignant (UC-20)."""
    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    qs = Evaluation.objects.select_related("matiere", "classe", "periode").all()
    if annee:
        qs = qs.filter(classe__annee_scolaire=annee)

    if request.user.role == "ENSEIGNANT":
        affectations = _affectations_enseignant(request.user)
        if affectations is not None:
            classe_ids = affectations.values_list("classe_id", flat=True)
            matiere_ids = affectations.values_list("matiere_id", flat=True)
            qs = qs.filter(classe_id__in=classe_ids, matiere_id__in=matiere_ids)
        else:
            qs = qs.none()

    periode = request.GET.get("periode", "")
    if periode:
        qs = qs.filter(periode_id=periode)

    return render(request, "evaluations/mes_evaluations.html", {
        "evaluations": qs.order_by("-date"),
        "periodes": Periode.objects.all() if annee else Periode.objects.none(),
        "annee": annee,
        "periode": periode,
        "est_enseignant": request.user.role == "ENSEIGNANT",
    })


@login_required
@roles_requis(ROLES_PEDAGO)
def creer_evaluation(request):
    if request.method == "POST":
        form = EvaluationForm(request.POST, user=request.user)
        if form.is_valid():
            evaluation = form.save()
            journaliser(request.user, "Création d'évaluation", "Évaluation", str(evaluation))
            messages.success(request, "Évaluation créée — vous pouvez saisir les notes.")
            return redirect("evaluations:saisie_notes", pk=evaluation.pk)
    else:
        form = EvaluationForm(user=request.user)
    return render(request, "evaluations/evaluation_form.html", {"form": form})


@login_required
@roles_requis(ROLES_PEDAGO)
def par_classe(request, pk):
    """Évaluations d'une classe (accès depuis le tableau de bord enseignant)."""
    classe = get_object_or_404(Classe, pk=pk)
    qs = Evaluation.objects.filter(classe=classe).select_related("matiere", "periode")
    if request.user.role == "ENSEIGNANT":
        affectations = _affectations_enseignant(request.user)
        if affectations is not None:
            qs = qs.filter(matiere_id__in=affectations.values_list("matiere_id", flat=True))
    return render(request, "evaluations/mes_evaluations.html", {
        "evaluations": qs.order_by("-date"),
        "classe": classe,
        "est_enseignant": request.user.role == "ENSEIGNANT",
    })


def _verifier_acces_notes(request, evaluation):
    """Un enseignant ne peut saisir que dans ses classes/matières assignées."""
    if request.user.role != "ENSEIGNANT":
        return True
    affectations = _affectations_enseignant(request.user)
    if affectations is None:
        return False
    return affectations.filter(
        classe=evaluation.classe, matiere=evaluation.matiere
    ).exists()


@login_required
@roles_requis(ROLES_PEDAGO)
def saisie_notes(request, pk):
    """Saisie des notes d'une évaluation avec contrôle 0-20 (UC-20)."""
    evaluation = get_object_or_404(
        Evaluation.objects.select_related("matiere", "classe", "periode"), pk=pk
    )
    if not _verifier_acces_notes(request, evaluation):
        messages.error(request, "Vous n'êtes pas autorisé à saisir les notes de cette classe/matière.")
        return redirect("evaluations:mes_evaluations")

    verrouillee = evaluation.saisie_verrouillee
    form = FormSaisieNotes(evaluation, request.POST or None)

    if request.method == "POST" and not verrouillee and form.is_valid():
        saisi_par = getattr(request.user, "fiche_personnel", None)
        nb = form.enregistrer(saisi_par=saisi_par, utilisateur=request.user)
        journaliser(
            request.user, "Saisie de notes", "Évaluation",
            f"{nb} note(s) pour {evaluation}",
        )
        messages.success(request, f"{nb} note(s) enregistrée(s).")
        return redirect("evaluations:saisie_notes", pk=evaluation.pk)

    modifications = NoteModification.objects.filter(note__evaluation=evaluation).select_related(
        "modifie_par"
    )[:20]

    contexte = {
        "evaluation": evaluation,
        "form": form,
        "verrouillee": verrouillee,
        "modifications": modifications,
    }
    return render(request, "evaluations/saisie_notes.html", contexte)


@login_required
@roles_requis(ROLES_PEDAGO)
def verrouiller(request, pk):
    """Verrouille les notes d'une période/évaluation avant édition des bulletins (UC-21)."""
    evaluation = get_object_or_404(Evaluation, pk=pk)
    if not _verifier_acces_notes(request, evaluation):
        messages.error(request, "Vous n'êtes pas autorisé à verrouiller les notes de cette évaluation.")
        return redirect("evaluations:mes_evaluations")
        
    evaluation.saisie_verrouillee = True
    evaluation.save(update_fields=["saisie_verrouillee"])
    journaliser(request.user, "Verrouillage des notes", "Évaluation", str(evaluation))
    messages.success(request, f"Les notes de « {evaluation} » sont verrouillées et validées définitivement.")
    return redirect("evaluations:saisie_notes", pk=evaluation.pk)


# ---------------------------------------------------------------------------
# Bulletins (UC-23, UC-24)
# ---------------------------------------------------------------------------

@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"])
def bulletins_classe(request):
    """Génération des bulletins d'une classe, en masse (PDF + ZIP)."""
    from eleves.models import Inscription

    form = BulletinsMasseForm(request.GET or None)
    bulletins = []
    classe = None
    periode = None

    if request.method == "GET" and form.is_valid():
        classe = form.cleaned_data["classe"]
        periode = form.cleaned_data["periode"]
        for inscription in Inscription.objects.filter(classe=classe, statut="ACTIVE"):
            from .services import generer_bulletin
            bulletin = generer_bulletin(inscription, periode)
            if bulletin:
                bulletins.append(bulletin)

    return render(request, "evaluations/bulletins_classe.html", {
        "form": form,
        "bulletins": bulletins,
        "classe": classe,
        "periode": periode,
    })


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"])
def telecharger_bulletin(request, pk):
    """Téléchargement du PDF d'un bulletin enregistré."""
    bulletin = get_object_or_404(Bulletin.objects.select_related("inscription__eleve"), pk=pk)
    if bulletin.fichier_pdf:
        return redirect(bulletin.fichier_pdf.url)
    messages.warning(request, "Aucun PDF n'a pu être généré pour ce bulletin.")
    return redirect("evaluations:bulletins_classe")


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"])
def bulletins_zip(request):
    """Génère les bulletins d'une classe et les regroupe dans une archive ZIP."""
    from eleves.models import Inscription

    form = BulletinsMasseForm(request.GET)
    if not form.is_valid():
        messages.error(request, "Sélection invalide.")
        return redirect("evaluations:bulletins_classe")

    classe = form.cleaned_data["classe"]
    periode = form.cleaned_data["periode"]
    archive = BytesIO()

    from documents.pdf import PdvNonDisponible, pdf_bytes
    from .services import calculer_moyennes, generer_bulletin, mention_pour, rangs_classe

    with ZipFile(archive, "w", ZIP_DEFLATED) as zipf:
        for inscription in Inscription.objects.filter(classe=classe, statut="ACTIVE").select_related("eleve"):
            bulletin = generer_bulletin(inscription, periode)
            if bulletin is None:
                continue
            lignes, moyenne = calculer_moyennes(inscription, periode)
            rangs = rangs_classe(classe, periode)
            contexte = {
                "bulletin": bulletin, "inscription": inscription, "eleve": inscription.eleve,
                "lignes": lignes, "moyenne": moyenne,
                "rang": rangs.get(inscription.pk),
                "mention": mention_pour(moyenne, inscription.annee_scolaire),
                "est_annuel": False,
            }
            nom_base = f"{inscription.eleve.matricule}_{inscription.eleve.nom}_{inscription.eleve.prenoms}"
            try:
                zipf.writestr(f"{nom_base}.pdf", pdf_bytes("evaluations/bulletin_pdf.html", contexte))
            except PdvNonDisponible:
                from django.template.loader import render_to_string
                zipf.writestr(
                    f"{nom_base}.html",
                    render_to_string("evaluations/bulletin_pdf.html", contexte),
                )

    journaliser(request.user, "Génération en masse de bulletins", "Bulletins",
                f"Classe {classe} — {periode} (ZIP)")
    reponse = HttpResponse(archive.getvalue(), content_type="application/zip")
    reponse["Content-Disposition"] = (
        f'attachment; filename="bulletins_{classe.pk}_{periode.pk}.zip"'
    )
    return reponse


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"])
def releve_annuel(request, pk):
    """Relevé de notes annuel consolidé d'un élève (UC-24)."""
    from collections import OrderedDict

    from eleves.models import Inscription
    from .services import calculer_moyennes, generer_bulletin

    inscription = get_object_or_404(
        Inscription.objects.select_related("eleve", "classe"), pk=pk
    )
    periodes = list(Periode.objects.filter(annee_scolaire=inscription.annee_scolaire).order_by("ordre"))

    # Matrice : matière -> {periode_id: moyenne}
    matrice = OrderedDict()
    moyennes_periodes = {}
    for periode in periodes:
        lignes, moyenne = calculer_moyennes(inscription, periode)
        moyennes_periodes[periode.pk] = moyenne
        for ligne in lignes:
            matiere = ligne["matiere"]
            matrice.setdefault(matiere, {})[periode.pk] = ligne["moyenne"]
    matrice_lignes = [(m, moyennes) for m, moyennes in matrice.items()]

    bulletin_annuel = generer_bulletin(inscription, est_annuel=True)
    return render(request, "evaluations/releve_annuel.html", {
        "inscription": inscription,
        "periodes": periodes,
        "matrice_lignes": matrice_lignes,
        "moyennes_periodes": moyennes_periodes,
        "bulletin_annuel": bulletin_annuel,
    })


# ---------------------------------------------------------------------------
# Décisions du conseil de classe (UC-25)
# ---------------------------------------------------------------------------

@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR"])
def decisions(request):
    """Saisie de la décision de passage (admis / redouble / exclu)."""
    from eleves.models import Inscription

    form = DecisionsForm(request.GET or None)
    inscriptions = []

    if request.method == "POST":
        inscription_ids = request.POST.getlist("inscriptions")
        for inscription_id in inscription_ids:
            decision = request.POST.get(f"decision_{inscription_id}", "").strip()
            if not decision:
                continue
            Inscription.objects.filter(pk=inscription_id).update(decision_fin_annee=decision)
        journaliser(request.user, "Décisions du conseil de classe", "Inscriptions",
                    f"{len(inscription_ids)} décision(s) enregistrée(s)")
        messages.success(request, "Décisions enregistrées.")
        return redirect("evaluations:decisions")

    classe = None
    if form.is_valid():
        classe = form.cleaned_data["classe"]
        inscriptions = Inscription.objects.filter(
            classe=classe, statut="ACTIVE"
        ).select_related("eleve").order_by("eleve__nom")

    return render(request, "evaluations/decisions.html", {
        "form": form,
        "inscriptions": inscriptions,
        "classe": classe,
        "choix": ["Admis(e)", "Redouble", "Exclu(e)", "Passage conditionnel"],
    })
