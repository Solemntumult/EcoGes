"""Vues du module Paramétrage : horaires journaliers (modes + pauses)."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render

from comptes.mixins import roles_requis
from comptes.services import journaliser

from .forms import (
    AjouterMatiereClasseForm,
    CoefficientForm,
    EtablissementForm,
    HoraireForm,
    LogoEtablissementForm,
    MatiereForm,
    NiveauForm,
    PauseHoraireForm,
    QuotaHoraireForm,
)
from .models import (
    AnneeScolaire,
    Classe,
    ClasseMatiereCoefficient,
    Etablissement,
    HoraireJournalier,
    LogoEtablissement,
    Matiere,
    Niveau,
    PauseHoraire,
    QuotaHoraireMatiere,
)

ROLES = ["ADMIN", "SUPERADMIN", "CENSEUR"]
ROLES_MATIERES = ["ADMIN", "SUPERADMIN", "CENSEUR"]


LogoFormSet = inlineformset_factory(
    Etablissement, LogoEtablissement,
    form=LogoEtablissementForm, extra=2, can_delete=True,
)


@login_required
@roles_requis(["ADMIN", "SUPERADMIN"])
def etablissement(request):
    """Paramètres de l'établissement (identité, IFU, signataires, logos, mentions)."""
    instance = Etablissement.obtenir()
    if request.method == "POST":
        form = EtablissementForm(request.POST, request.FILES, instance=instance)
        # Le formset des logos n'est validé que si la section a été soumise
        # (POST sans les champs de gestion = pas de modification des logos)
        if "logos-TOTAL_FORMS" in request.POST:
            formset = LogoFormSet(request.POST, request.FILES, instance=instance)
            formset_valide = formset.is_valid()
        else:
            formset = None
            formset_valide = True
        if form.is_valid() and formset_valide:
            form.save()
            if formset:
                formset.save()
            journaliser(request.user, "Modification de l'établissement", "Paramétrage",
                        str(instance))
            messages.success(request, "Paramètres de l'établissement enregistrés.")
            return redirect("parametrage:etablissement")
    else:
        form = EtablissementForm(instance=instance)
        formset = LogoFormSet(instance=instance)
    from parametrage.services import contexte_etablissement
    return render(request, "parametrage/etablissement.html", {
        "form": form, "etab": instance, "formset": formset,
        **contexte_etablissement(),
    })

PauseFormSet = inlineformset_factory(
    HoraireJournalier, PauseHoraire,
    form=PauseHoraireForm, extra=1, can_delete=True,
)


# ---------------------------------------------------------------------------
# Gestionnaire de matières & coefficients (matière, classe)
# ---------------------------------------------------------------------------

def _erreurs_formulaire(formulaire):
    """Messages d'erreur lisibles (champs + global) pour un formulaire invalide."""
    messages_erreur = []
    for champ, erreurs in formulaire.errors.as_data().items():
        libelle = formulaire.fields[champ].label if champ in formulaire.fields else champ
        for erreur in erreurs:
            messages_erreur.append(f"{libelle} : {erreur.message}")
    return messages_erreur


@login_required
@roles_requis(ROLES_MATIERES)
def matieres(request):
    """Vue de contrôle : niveaux/séries, matières et accès au coefficient par classe."""
    if request.method == "POST" and request.POST.get("creer_niveau"):
        form_niveau = NiveauForm(request.POST)
        if form_niveau.is_valid():
            niveau = form_niveau.save()
            journaliser(request.user, "Création de niveau", "Matières", str(niveau))
            messages.success(request, f"Niveau « {niveau} » créé.")
        else:
            for erreur in _erreurs_formulaire(form_niveau):
                messages.error(request, f"⚠️ Niveau — {erreur}")
        return redirect("parametrage:matieres")
    if request.method == "POST" and request.POST.get("creer_matiere"):
        form_matiere = MatiereForm(request.POST)
        if form_matiere.is_valid():
            matiere = form_matiere.save()
            journaliser(request.user, "Création de matière", "Matières", str(matiere))
            if matiere.tronc_commun:
                nb_liees = matiere.coefficients_par_classe.count()
                messages.success(
                    request,
                    f"Matière « {matiere.libelle} » créée et liée automatiquement à "
                    f"{nb_liees} classe(s) de {matiere.niveau} (tronc commun).",
                )
            else:
                messages.success(request, f"Matière « {matiere.libelle} » créée (le coefficient se règle par classe).")
        else:
            for erreur in _erreurs_formulaire(form_matiere):
                messages.error(request, f"⚠️ Matière — {erreur}")
        return redirect("parametrage:matieres")

    form_niveau = NiveauForm()
    form_matiere = MatiereForm()
    niveaux = list(Niveau.objects.select_related("serie").prefetch_related("matieres"))
    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    classes = (
        Classe.objects.filter(annee_scolaire=annee).select_related("niveau__serie").order_by("niveau__ordre", "libelle")
        if annee else Classe.objects.none()
    )
    return render(request, "parametrage/matieres.html", {
        "niveaux": niveaux,
        "classes": classes,
        "form_niveau": form_niveau,
        "form_matiere": form_matiere,
    })


@login_required
@roles_requis(ROLES_MATIERES)
def basculer_tronc_commun(request, pk):
    """Active/désactive le statut « tronc commun » d'une matière.

    L'activation déclenche la liaison automatique de la matière à toutes les
    classes du niveau (via le signal post_save).
    """
    matiere = get_object_or_404(Matiere, pk=pk)
    if request.method == "POST":
        matiere.tronc_commun = not matiere.tronc_commun
        matiere.save(update_fields=["tronc_commun"])
        if matiere.tronc_commun:
            nb_liees = matiere.coefficients_par_classe.count()
            journaliser(request.user, "Activation tronc commun", "Matières",
                        f"{matiere.libelle} ({matiere.niveau})")
            messages.success(
                request,
                f"« {matiere.libelle} » est maintenant du tronc commun : liée à {nb_liees} classe(s) de {matiere.niveau}.",
            )
        else:
            journaliser(request.user, "Désactivation tronc commun", "Matières",
                        f"{matiere.libelle} ({matiere.niveau})")
            messages.success(request, f"« {matiere.libelle} » n'est plus du tronc commun (les liaisons existantes sont conservées).")
    return redirect("parametrage:matieres")


@login_required
@roles_requis(ROLES_MATIERES)
def classe_matieres(request, pk):
    """Coefficients (matière, classe) d'une classe précise — édition et contrôle."""
    classe = get_object_or_404(
        Classe.objects.select_related("niveau__serie", "annee_scolaire"), pk=pk
    )
    coeffs = list(
        ClasseMatiereCoefficient.objects.filter(classe=classe)
        .select_related("matiere").order_by("matiere__libelle")
    )
    total_coef = sum((c.coefficient for c in coeffs), Decimal("0"))
    form_ajout = AjouterMatiereClasseForm(classe=classe)
    return render(request, "parametrage/classe_matieres.html", {
        "classe": classe,
        "coeffs": coeffs,
        "total_coef": total_coef,
        "form_ajout": form_ajout,
    })


@login_required
@roles_requis(ROLES_MATIERES)
def ajouter_matiere_classe(request, pk):
    """Ajoute une matière (existante ou nouvelle) à une classe, avec coefficient."""
    classe = get_object_or_404(Classe, pk=pk)
    if request.method == "POST":
        form = AjouterMatiereClasseForm(request.POST, classe=classe)
        if form.is_valid():
            matiere = form.cleaned_data.get("matiere")
            if matiere is None:
                libelle = form.cleaned_data["libelle"].strip()
                matiere, _ = Matiere.objects.get_or_create(
                    libelle=libelle, niveau=classe.niveau
                )
            cmc, creee = ClasseMatiereCoefficient.objects.get_or_create(
                classe=classe, matiere=matiere,
                defaults={"coefficient": form.cleaned_data["coefficient"]},
            )
            if not creee:
                cmc.coefficient = form.cleaned_data["coefficient"]
                cmc.save(update_fields=["coefficient"])
            journaliser(
                request.user, "Ajout de matière à une classe", "Matières",
                f"{matiere.libelle} → {classe} (coef {cmc.coefficient})",
            )
            messages.success(
                request, f"Matière « {matiere.libelle} » ajoutée à {classe.libelle} — coefficient {cmc.coefficient}."
            )
            return redirect("parametrage:classe_matieres", pk=classe.pk)
        for erreur in form.non_field_errors():
            messages.error(request, f"⚠️ {erreur}")
        for erreur in _erreurs_formulaire(form):
            messages.error(request, f"⚠️ {erreur}")
    return redirect("parametrage:classe_matieres", pk=classe.pk)


@login_required
@roles_requis(ROLES_MATIERES)
def modifier_coefficient(request, pk, matiere_pk):
    """Modifie le coefficient d'une matière pour UNE classe précise (sans effet de bord)."""
    cmc = get_object_or_404(ClasseMatiereCoefficient, classe_id=pk, matiere_id=matiere_pk)
    if request.method == "POST":
        form = CoefficientForm(request.POST)
        if form.is_valid():
            cmc.coefficient = form.cleaned_data["coefficient"]
            cmc.save(update_fields=["coefficient"])
            journaliser(
                request.user, "Modification de coefficient", "Matières",
                f"{cmc.matiere.libelle} ({cmc.classe.libelle}) → {cmc.coefficient}",
            )
            messages.success(
                request, f"Coefficient de « {cmc.matiere.libelle} » ({cmc.classe.libelle}) mis à {cmc.coefficient}."
            )
    return redirect("parametrage:classe_matieres", pk=pk)


@login_required
@roles_requis(ROLES_MATIERES)
def retirer_matiere_classe(request, pk, matiere_pk):
    """Retire la liaison matière ↔ classe (le coefficient associé disparaît)."""
    cmc = get_object_or_404(ClasseMatiereCoefficient, classe_id=pk, matiere_id=matiere_pk)
    if request.method == "POST":
        journaliser(
            request.user, "Retrait de matière d'une classe", "Matières",
            f"{cmc.matiere.libelle} retirée de {cmc.classe.libelle}",
        )
        cmc.delete()
        messages.success(request, f"Matière « {cmc.matiere.libelle} » retirée de {cmc.classe.libelle}.")
    return redirect("parametrage:classe_matieres", pk=pk)


@login_required
@roles_requis(ROLES)
def horaires(request):
    """Liste des modes d'horaire avec bascule de l'horaire actif."""
    if request.method == "POST":
        pk = request.POST.get("activer")
        horaire = get_object_or_404(HoraireJournalier, pk=pk)
        HoraireJournalier.objects.update(actif=False)
        horaire.actif = True
        horaire.save(update_fields=["actif"])
        journaliser(request.user, "Horaire scolaire activé", "Paramétrage", str(horaire))
        messages.success(request, f"Horaire « {horaire.libelle} » appliqué à l'établissement.")
        return redirect("parametrage:horaires")

    horaires_liste = list(HoraireJournalier.objects.prefetch_related("pauses"))
    actif = next((h for h in horaires_liste if h.actif), None)
    return render(request, "parametrage/horaires.html", {
        "horaires": horaires_liste,
        "actif": actif,
    })


@login_required
@roles_requis(ROLES)
def horaire_editer(request, pk=None):
    """Crée ou modifie un mode d'horaire et ses pauses (récréation, déjeuner...)."""
    instance = get_object_or_404(HoraireJournalier, pk=pk) if pk else None
    if request.method == "POST":
        form = HoraireForm(request.POST, instance=instance)
        formset = PauseFormSet(request.POST, instance=instance)
        if form.is_valid() and formset.is_valid():
            horaire = form.save(commit=False)
            if instance is None and not HoraireJournalier.objects.filter(actif=True).exists():
                horaire.actif = True  # premier horaire → appliqué par défaut
            horaire.save()
            if horaire.actif:
                # Un seul horaire actif à la fois (robustesse même via l'admin)
                HoraireJournalier.objects.exclude(pk=horaire.pk).update(actif=False)
            formset.instance = horaire
            formset.save()
            action = "Modification d'horaire scolaire" if instance else "Création d'horaire scolaire"
            journaliser(request.user, action, "Paramétrage", str(horaire))
            messages.success(request, "Horaire enregistré.")
            return redirect("parametrage:horaires")
    else:
        form = HoraireForm(instance=instance)
        formset = PauseFormSet(instance=instance)
    return render(request, "parametrage/horaire_form.html", {
        "form": form, "formset": formset, "instance": instance,
    })


@login_required
@roles_requis(ROLES)
def horaire_supprimer(request, pk):
    horaire = get_object_or_404(HoraireJournalier, pk=pk)
    journaliser(request.user, "Suppression d'horaire scolaire", "Paramétrage", str(horaire))
    horaire.delete()
    messages.success(request, "Horaire supprimé.")
    return redirect("parametrage:horaires")


@login_required
@roles_requis(ROLES)
def quotas_horaires(request, pk):
    """Gestion des quotas horaires par matière pour une classe."""
    from parametrage.models import Classe
    classe = get_object_or_404(Classe.objects.select_related("niveau", "annee_scolaire"), pk=pk)
    quotas = QuotaHoraireMatiere.objects.filter(classe=classe).select_related("matiere")

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "supprimer":
            quota_pk = request.POST.get("quota_pk")
            quota = get_object_or_404(QuotaHoraireMatiere, pk=quota_pk, classe=classe)
            quota.delete()
            messages.success(request, "Quota supprimé.")
            return redirect("parametrage:quotas_horaires", pk=pk)

        form = QuotaHoraireForm(request.POST)
        if form.is_valid():
            quota = form.save(commit=False)
            quota.classe = classe
            quota.save()
            journaliser(request.user, "Quota horaire défini", "Paramétrage",
                        f"{quota.matiere.libelle} : {quota.heures_par_semaine}h/sem ({classe.libelle})")
            messages.success(request, "Quota horaire enregistré.")
            return redirect("parametrage:quotas_horaires", pk=pk)
    else:
        form = QuotaHoraireForm()

    # Filtrer les matières disponibles pour cette classe (via son niveau)
    from parametrage.models import Matiere
    form.fields["matiere"].queryset = Matiere.objects.filter(niveau=classe.niveau)
    # Masquer le champ classe (on le force côté serveur)
    del form.fields["classe"]

    return render(request, "parametrage/quotas_horaires.html", {
        "classe": classe, "quotas": quotas, "form": form,
    })
