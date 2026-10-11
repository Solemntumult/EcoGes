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
    ClasseForm,
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
    """Vue de contrôle des matières et accès aux coefficients par classe."""
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
                messages.success(request, f"Matière « {matiere.libelle} » créée pour le niveau {matiere.niveau}.")
        else:
            for erreur in _erreurs_formulaire(form_matiere):
                messages.error(request, f"⚠️ Matière — {erreur}")
        return redirect("parametrage:matieres")

    form_matiere = MatiereForm()
    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    classes_qs = (
        Classe.objects.filter(annee_scolaire=annee)
        .select_related("niveau__serie", "enseignant_principal")
        .prefetch_related("matiere_coefficients", "quotas_horaires")
        .order_by("niveau__ordre", "libelle")
        if annee else Classe.objects.none()
    )

    classes_premier_cycle = []
    classes_second_cycle = []
    classes_autres = []

    for c in classes_qs:
        c.nb_matieres = c.matiere_coefficients.count()
        c.total_coef = sum((cmc.coefficient for cmc in c.matiere_coefficients.all()), Decimal("0"))
        c.total_heures = sum((q.heures_par_semaine for q in c.quotas_horaires.all()), Decimal("0"))

        cycle = getattr(c.niveau, "cycle", "")
        libelle = c.niveau.libelle.lower() if c.niveau else ""
        if cycle == "COLLEGE" or any(k in libelle for k in ["6", "5", "4", "3"]):
            classes_premier_cycle.append(c)
        elif cycle == "LYCEE" or any(k in libelle for k in ["2nd", "seconde", "1ère", "première", "tle", "terminale"]):
            classes_second_cycle.append(c)
        else:
            classes_autres.append(c)

    matieres_globales = Matiere.objects.select_related("niveau__serie").prefetch_related("coefficients_par_classe").order_by("libelle")
    niveaux = list(Niveau.objects.select_related("serie").prefetch_related("matieres"))

    return render(request, "parametrage/matieres.html", {
        "annee": annee,
        "classes_premier_cycle": classes_premier_cycle,
        "classes_second_cycle": classes_second_cycle,
        "classes_autres": classes_autres,
        "total_classes": len(classes_qs),
        "matieres_globales": matieres_globales,
        "niveaux": niveaux,
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
    """Coefficients et quotas horaires (matière, classe) d'une classe précise — édition unifiée."""
    classe = get_object_or_404(
        Classe.objects.select_related("niveau__serie", "annee_scolaire"), pk=pk
    )
    coeffs = list(
        ClasseMatiereCoefficient.objects.filter(classe=classe)
        .select_related("matiere").order_by("matiere__libelle")
    )
    quotas_dict = {
        q.matiere_id: q.heures_par_semaine
        for q in QuotaHoraireMatiere.objects.filter(classe=classe)
    }
    for c in coeffs:
        c.quota_heures = quotas_dict.get(c.matiere_id, Decimal("0"))

    total_coef = sum((c.coefficient for c in coeffs), Decimal("0"))
    total_heures = sum(quotas_dict.values(), Decimal("0"))
    form_ajout = AjouterMatiereClasseForm(classe=classe)
    return render(request, "parametrage/classe_matieres.html", {
        "classe": classe,
        "coeffs": coeffs,
        "total_coef": total_coef,
        "total_heures": total_heures,
        "form_ajout": form_ajout,
    })


@login_required
@roles_requis(ROLES_MATIERES)
def ajouter_matiere_classe(request, pk):
    """Ajoute une nouvelle matière à une classe, avec coefficient et quota horaire."""
    classe = get_object_or_404(Classe, pk=pk)
    if request.method == "POST":
        form = AjouterMatiereClasseForm(request.POST, classe=classe)
        if form.is_valid():
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

            h_sem = form.cleaned_data.get("heures_par_semaine")
            if h_sem is not None:
                QuotaHoraireMatiere.objects.update_or_create(
                    classe=classe, matiere=matiere,
                    defaults={"heures_par_semaine": h_sem},
                )

            journaliser(
                request.user, "Ajout de matière à une classe", "Matières",
                f"{matiere.libelle} → {classe} (coef {cmc.coefficient}, {h_sem or 0}h/sem)",
            )
            messages.success(
                request, f"Nouvelle matière « {matiere.libelle} » ajoutée à {classe.libelle} avec succès."
            )
            return redirect("parametrage:classe_matieres", pk=classe.pk)
        for erreur in form.non_field_errors():
            messages.error(request, f"⚠️ {erreur}")
        for champ, erreurs in form.errors.items():
            for err in erreurs:
                messages.error(request, f"⚠️ {err}")
    return redirect("parametrage:classe_matieres", pk=classe.pk)


@login_required
@roles_requis(ROLES_MATIERES)
def modifier_coefficient(request, pk, matiere_pk):
    """Modifie simultanément le coefficient et le quota horaire d'une matière pour UNE classe précise."""
    cmc = get_object_or_404(ClasseMatiereCoefficient, classe_id=pk, matiere_id=matiere_pk)
    if request.method == "POST":
        coef_raw = request.POST.get("coefficient", "").strip()
        heures_raw = request.POST.get("heures_par_semaine", "").strip()
        msg_parts = []
        if coef_raw:
            try:
                val = Decimal(coef_raw)
                if Decimal("0.5") <= val <= Decimal("20"):
                    cmc.coefficient = val
                    cmc.save(update_fields=["coefficient"])
                    msg_parts.append(f"coefficient {cmc.coefficient}")
            except Exception:
                pass
        if heures_raw:
            try:
                h_val = Decimal(heures_raw)
                if Decimal("0") <= h_val <= Decimal("40"):
                    QuotaHoraireMatiere.objects.update_or_create(
                        classe=cmc.classe, matiere=cmc.matiere,
                        defaults={"heures_par_semaine": h_val},
                    )
                    msg_parts.append(f"quota {h_val}h/sem")
            except Exception:
                pass
        journaliser(
            request.user, "Modification matière-classe", "Matières",
            f"{cmc.matiere.libelle} ({cmc.classe.libelle}) → {', '.join(msg_parts)}",
        )
        messages.success(
            request, f"« {cmc.matiere.libelle} » ({cmc.classe.libelle}) : {', '.join(msg_parts)} enregistré."
        )
    return redirect("parametrage:classe_matieres", pk=pk)


@login_required
@roles_requis(ROLES_MATIERES)
def retirer_matiere_classe(request, pk, matiere_pk):
    """Retire la liaison matière ↔ classe (coefficient et quota horaire supprimés)."""
    cmc = get_object_or_404(ClasseMatiereCoefficient, classe_id=pk, matiere_id=matiere_pk)
    if request.method == "POST":
        journaliser(
            request.user, "Retrait de matière d'une classe", "Matières",
            f"{cmc.matiere.libelle} retirée de {cmc.classe.libelle}",
        )
        cmc.delete()
        QuotaHoraireMatiere.objects.filter(classe_id=pk, matiere_id=matiere_pk).delete()
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


# ---------------------------------------------------------------------------
# Gestion des classes de l'établissement (Premier cycle et Second cycle)
# ---------------------------------------------------------------------------

@login_required
@roles_requis(ROLES)
def classes(request):
    """Liste complète des classes par année scolaire avec distinction des cycles."""
    annee_courante = AnneeScolaire.objects.filter(est_courante=True).first()
    annee_id = request.GET.get("annee")
    if annee_id:
        annee = get_object_or_404(AnneeScolaire, pk=annee_id)
    else:
        annee = annee_courante

    annees = AnneeScolaire.objects.order_by("-date_debut")
    cycle_filtre = request.GET.get("cycle", "")

    if annee:
        classes_qs = Classe.objects.filter(annee_scolaire=annee)
    else:
        classes_qs = Classe.objects.all()

    classes_qs = (
        classes_qs.select_related("niveau", "niveau__serie", "enseignant_principal")
        .prefetch_related("inscriptions")
        .order_by("niveau__ordre", "libelle")
    )

    if cycle_filtre in ("PREMIER_CYCLE", "SECOND_CYCLE"):
        classes_qs = classes_qs.filter(niveau__cycle=cycle_filtre)

    classes_premier_cycle = [c for c in classes_qs if c.niveau.cycle == "PREMIER_CYCLE"]
    classes_second_cycle = [c for c in classes_qs if c.niveau.cycle == "SECOND_CYCLE"]

    total_classes = len(classes_qs)
    total_eleves = sum(c.effectif_actuel for c in classes_qs)

    return render(
        request,
        "parametrage/classes.html",
        {
            "annee": annee,
            "annee_courante": annee_courante,
            "annees": annees,
            "cycle_filtre": cycle_filtre,
            "classes": classes_qs,
            "classes_premier_cycle": classes_premier_cycle,
            "classes_second_cycle": classes_second_cycle,
            "total_classes": total_classes,
            "total_eleves": total_eleves,
        },
    )


@login_required
@roles_requis(ROLES)
def classe_creer(request):
    """Création d'une nouvelle classe (indépendante ou associée à l'année courante si active)."""
    annee = AnneeScolaire.objects.filter(est_courante=True).first()

    if request.method == "POST":
        form = ClasseForm(request.POST)
        if form.is_valid():
            classe = form.save(commit=False)
            if annee:
                classe.annee_scolaire = annee
            # Vérification de doublon (niveau, libelle)
            filtre_doublon = {"niveau": classe.niveau, "libelle": classe.libelle}
            if annee:
                filtre_doublon["annee_scolaire"] = annee
            if Classe.objects.filter(**filtre_doublon).exists():
                form.add_error("libelle", f"La classe {classe.libelle} existe déjà pour ce niveau.")
            else:
                classe.save()
                journaliser(request.user, "Création de classe", "Paramétrage", f"{classe} créée")
                messages.success(request, f"La classe {classe.libelle} a été créée avec succès.")
                return redirect("parametrage:classes")
    else:
        form = ClasseForm()

    return render(request, "parametrage/classe_form.html", {"form": form, "titre": "Créer une nouvelle classe", "annee": annee})


@login_required
@roles_requis(ROLES)
def classe_modifier(request, pk):
    """Modification d'une classe existante."""
    classe = get_object_or_404(Classe.objects.select_related("niveau", "annee_scolaire"), pk=pk)

    if request.method == "POST":
        form = ClasseForm(request.POST, instance=classe)
        if form.is_valid():
            classe_modifiee = form.save(commit=False)
            # Vérification de doublon
            if Classe.objects.filter(
                niveau=classe_modifiee.niveau,
                annee_scolaire=classe.annee_scolaire,
                libelle=classe_modifiee.libelle
            ).exclude(pk=classe.pk).exists():
                form.add_error("libelle", f"Une classe {classe_modifiee.libelle} existe déjà pour ce niveau.")
            else:
                classe_modifiee.save()
                journaliser(request.user, "Modification de classe", "Paramétrage", f"{classe} modifiée")
                messages.success(request, f"La classe {classe.libelle} a été mise à jour.")
                return redirect("parametrage:classes")
    else:
        form = ClasseForm(instance=classe)

    return render(request, "parametrage/classe_form.html", {"form": form, "classe": classe, "titre": f"Modifier la classe {classe.libelle}", "annee": classe.annee_scolaire})


@login_required
@roles_requis(ROLES)
def classe_supprimer(request, pk):
    """Suppression d'une classe (bloquée si des élèves ou des notes y sont rattachés)."""
    classe = get_object_or_404(Classe, pk=pk)
    if classe.inscriptions.exists():
        messages.error(request, f"Impossible de supprimer {classe.libelle} : {classe.inscriptions.count()} élève(s) y sont rattaché(s).")
        return redirect("parametrage:classes")

    if request.method == "POST":
        libelle = str(classe)
        classe.delete()
        journaliser(request.user, "Suppression de classe", "Paramétrage", libelle)
        messages.success(request, f"La classe {libelle} a été supprimée.")
        return redirect("parametrage:classes")

    return render(request, "parametrage/classe_supprimer.html", {"classe": classe})

