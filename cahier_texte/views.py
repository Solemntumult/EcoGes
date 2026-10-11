from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from comptes.mixins import roles_requis
from comptes.services import journaliser
from parametrage.models import Classe
from personnel.models import Affectation
from .forms import DevoirMaisonForm, SeanceCoursForm
from .models import DevoirMaison, SeanceCours

ROLES_CAHIER_VOIR = ["ADMIN", "SUPERADMIN", "CENSEUR", "ENSEIGNANT", "SECRETARIAT", "PARENT"]
ROLES_CAHIER_ECRIRE = ["ADMIN", "SUPERADMIN", "CENSEUR", "ENSEIGNANT"]


@login_required
@roles_requis(ROLES_CAHIER_VOIR)
def index(request):
    """Consultation du cahier de textes avec sélection de la classe."""
    classes = Classe.objects.all().order_by("niveau", "libelle")
    classe_id = request.GET.get("classe")
    classe_selectionnee = None
    seances = []
    devoirs = []

    if classe_id:
        classe_selectionnee = get_object_or_404(Classe, pk=classe_id)
        seances = (
            SeanceCours.objects.filter(affectation__classe=classe_selectionnee)
            .select_related("affectation__matiere", "affectation__personnel")
            .order_by("-date", "creneau")[:30]
        )
        devoirs = (
            DevoirMaison.objects.filter(affectation__classe=classe_selectionnee)
            .select_related("affectation__matiere", "affectation__personnel")
            .order_by("-date_limite")[:20]
        )
    elif request.user.role == "ENSEIGNANT":
        seances = (
            SeanceCours.objects.filter(affectation__personnel__utilisateur=request.user)
            .select_related("affectation__classe", "affectation__matiere")
            .order_by("-date", "creneau")[:30]
        )
        devoirs = (
            DevoirMaison.objects.filter(affectation__personnel__utilisateur=request.user)
            .select_related("affectation__classe", "affectation__matiere")
            .order_by("-date_limite")[:20]
        )

    contexte = {
        "classes": classes,
        "classe_selectionnee": classe_selectionnee,
        "seances": seances,
        "devoirs": devoirs,
        "peut_ecrire": request.user.role in ROLES_CAHIER_ECRIRE,
    }
    return render(request, "cahier_texte/index.html", contexte)


@login_required
@roles_requis(ROLES_CAHIER_ECRIRE)
def seance_creer(request):
    """Enregistrement d'une nouvelle séance de cours."""
    classe_id = request.GET.get("classe")
    initial = {}
    if classe_id:
        classe = get_object_or_404(Classe, pk=classe_id)
        aff = Affectation.objects.filter(classe=classe).first()
        if aff:
            initial["affectation"] = aff

    if request.method == "POST":
        form = SeanceCoursForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            seance = form.save()
            journaliser(
                request.user,
                "Saisie séance",
                "Cahier de textes",
                f"{seance.affectation.classe} - {seance.affectation.matiere} : {seance.titre_chapitre} ({seance.get_statut_display()})",
            )
            messages.success(request, "Séance enregistrée dans le cahier de textes.")
            return redirect(f"{redirect('cahier_texte:index').url}?classe={seance.affectation.classe_id}")
    else:
        form = SeanceCoursForm(initial=initial, user=request.user)

    return render(request, "cahier_texte/seance_form.html", {"form": form, "titre": "Ajouter une séance de cours"})


@login_required
@roles_requis(ROLES_CAHIER_ECRIRE)
def seance_modifier(request, pk):
    """Modification d'une séance de cours existante."""
    seance = get_object_or_404(SeanceCours, pk=pk)
    if request.method == "POST":
        form = SeanceCoursForm(request.POST, request.FILES, instance=seance, user=request.user)
        if form.is_valid():
            form.save()
            journaliser(request.user, "Modification séance", "Cahier de textes", str(seance))
            messages.success(request, "Séance mise à jour avec succès.")
            return redirect(f"{redirect('cahier_texte:index').url}?classe={seance.affectation.classe_id}")
    else:
        form = SeanceCoursForm(instance=seance, user=request.user)

    return render(
        request,
        "cahier_texte/seance_form.html",
        {"form": form, "seance": seance, "titre": f"Modifier la séance — {seance.titre_chapitre}"},
    )


@login_required
@roles_requis(ROLES_CAHIER_ECRIRE)
def seance_supprimer(request, pk):
    """Suppression d'une séance."""
    seance = get_object_or_404(SeanceCours, pk=pk)
    classe_id = seance.affectation.classe_id
    if request.method == "POST":
        titre = str(seance)
        seance.delete()
        journaliser(request.user, "Suppression séance", "Cahier de textes", titre)
        messages.success(request, "Séance supprimée.")
        return redirect(f"{redirect('cahier_texte:index').url}?classe={classe_id}")
    return render(request, "cahier_texte/seance_supprimer.html", {"seance": seance})


@login_required
@roles_requis(ROLES_CAHIER_ECRIRE)
def devoir_creer(request):
    """Prescription d'un nouveau travail à domicile."""
    classe_id = request.GET.get("classe")
    initial = {}
    if classe_id:
        classe = get_object_or_404(Classe, pk=classe_id)
        aff = Affectation.objects.filter(classe=classe).first()
        if aff:
            initial["affectation"] = aff

    if request.method == "POST":
        form = DevoirMaisonForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            devoir = form.save()
            journaliser(request.user, "Prescription devoir", "Cahier de textes", str(devoir))
            messages.success(request, "Devoir de maison publié avec succès.")
            return redirect(f"{redirect('cahier_texte:index').url}?classe={devoir.affectation.classe_id}")
    else:
        form = DevoirMaisonForm(initial=initial, user=request.user)

    return render(request, "cahier_texte/devoir_form.html", {"form": form})


@login_required
@roles_requis(ROLES_CAHIER_ECRIRE)
def devoir_supprimer(request, pk):
    """Suppression d'un devoir."""
    devoir = get_object_or_404(DevoirMaison, pk=pk)
    classe_id = devoir.affectation.classe_id
    if request.method == "POST":
        titre = str(devoir)
        devoir.delete()
        journaliser(request.user, "Suppression devoir", "Cahier de textes", titre)
        messages.success(request, "Devoir supprimé.")
        return redirect(f"{redirect('cahier_texte:index').url}?classe={classe_id}")
    return render(request, "cahier_texte/devoir_supprimer.html", {"devoir": devoir})
