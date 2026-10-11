from decimal import Decimal
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
from .models import Bulletin, Evaluation, Note, NoteModification, ValidationNotesPP

ROLES_PEDAGO = ["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT", "ENSEIGNANT"]


def _annee_active(request=None):
    """Retourne l'année scolaire active."""
    return AnneeScolaire.objects.filter(est_courante=True).first()


def _affectations_enseignant(utilisateur):
    """Affectations (classe/matière) de l'utilisateur connecté s'il est enseignant."""
    personnel = getattr(utilisateur, "fiche_personnel", None)
    if personnel is None:
        return None
    return personnel.affectations.all()


@login_required
@roles_requis(ROLES_PEDAGO)
def mes_evaluations(request):
    """Hub principal des Notes : Arborescence par niveau et classe, adaptée au rôle utilisateur."""
    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    user = request.user
    est_prof = (user.role == "ENSEIGNANT")
    personnel = getattr(user, "fiche_personnel", None)

    # Déterminer les classes accessibles
    toutes_classes = Classe.objects.select_related("niveau", "niveau__serie", "enseignant_principal").order_by("niveau__ordre", "libelle")
    if annee:
        toutes_classes = toutes_classes.filter(Q(annee_scolaire=annee) | Q(annee_scolaire__isnull=True))

    mes_classes_ids = set()
    classes_pp_ids = set()
    affectations_prof = []

    if est_prof and personnel:
        affectations_prof = list(personnel.affectations.select_related("classe", "matiere").all())
        mes_classes_ids = {a.classe_id for a in affectations_prof}
        classes_pp_ids = set(Classe.objects.filter(enseignant_principal=personnel).values_list("id", flat=True))
        classes_visibles = [c for c in toutes_classes if c.id in mes_classes_ids or c.id in classes_pp_ids]
    else:
        # Administrateur, Censeur, Secrétariat : vue globale sur toutes les classes
        classes_visibles = list(toutes_classes)

    # Regroupement par niveau d'enseignement
    niveaux_dict = {}
    for cl in classes_visibles:
        niv_nom = cl.niveau.libelle
        if cl.niveau.serie:
            niv_nom = f"{cl.niveau.libelle} {cl.niveau.serie.code}"
        if niv_nom not in niveaux_dict:
            niveaux_dict[niv_nom] = {
                "niveau": cl.niveau,
                "nom": niv_nom,
                "cycle": cl.niveau.get_cycle_display(),
                "classes": [],
            }
        cl.est_pp = (cl.id in classes_pp_ids) if est_prof else False
        niveaux_dict[niv_nom]["classes"].append(cl)

    periodes = list(Periode.objects.filter(annee_scolaire=annee).order_by("ordre")) if annee else []

    return render(request, "evaluations/mes_evaluations.html", {
        "niveaux_groupes": list(niveaux_dict.values()),
        "classes_visibles": classes_visibles,
        "periodes": periodes,
        "annee": annee,
        "est_enseignant": est_prof,
        "affectations_prof": affectations_prof,
    })


@login_required
@roles_requis(ROLES_PEDAGO)
def carnet_notes_classe(request, pk):
    """Carnet de notes d'une classe : tableau par matière avec colonnes Interros, Devoirs, Compo, Moyenne."""
    classe = get_object_or_404(Classe.objects.select_related("niveau", "enseignant_principal"), pk=pk)
    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    user = request.user
    personnel = getattr(user, "fiche_personnel", None)

    # Contrôle d'accès : enseignant limité à ses matières ou classe où il est PP
    est_prof = (user.role == "ENSEIGNANT")
    est_pp = bool(est_prof and personnel and classe.enseignant_principal_id == personnel.id)

    periodes = list(Periode.objects.filter(annee_scolaire=annee).order_by("ordre")) if annee else []
    periode_id = request.GET.get("periode")
    periode_active = Periode.objects.filter(pk=periode_id).first() if periode_id else (periodes[0] if periodes else None)

    # Récupération des matières de la classe
    from parametrage.models import ClasseMatiereCoefficient
    cmcs = list(ClasseMatiereCoefficient.objects.filter(classe=classe).select_related("matiere").order_by("matiere__libelle"))

    # Si prof non PP : restreindre aux matières qu'il enseigne dans cette classe
    if est_prof and not est_pp and personnel:
        matiere_ids = set(personnel.affectations.filter(classe=classe).values_list("matiere_id", flat=True))
        cmcs = [cmc for cmc in cmcs if cmc.matiere_id in matiere_ids]

    # Matière active sélectionnée
    matiere_id = request.GET.get("matiere")
    matiere_active = None
    if matiere_id:
        matiere_active = next((cmc.matiere for cmc in cmcs if str(cmc.matiere_id) == matiere_id), None)
    if not matiere_active and cmcs:
        matiere_active = cmcs[0].matiere

    # Élèves inscrits
    from eleves.models import Inscription
    inscriptions = list(Inscription.objects.filter(classe=classe, statut="ACTIVE").select_related("eleve").order_by("eleve__nom", "eleve__prenoms"))

    evaluations_interros = []
    evaluations_devoirs = []
    evaluation_compo = None
    lignes_notes = []

    peut_ajouter_interro = False
    if matiere_active and periode_active:
        # Contrôle droit ajout interro : enseignant de la matière ou admin/direction
        if est_prof:
            peut_ajouter_interro = cmcs_matiere_ids = True if not personnel else personnel.affectations.filter(classe=classe, matiere=matiere_active).exists()
        else:
            peut_ajouter_interro = True

        # On ne conserve dans le tableau que les évaluations qui ont au moins une note saisie
        # ou les évaluations d'interrogations créées pour saisie
        from django.db.models import Count
        evals_avec_notes_ids = set(Note.objects.filter(evaluation__in=Evaluation.objects.filter(
            classe=classe, matiere=matiere_active, periode=periode_active
        )).values_list("evaluation_id", flat=True))

        qs_evals = list(Evaluation.objects.filter(
            classe=classe, matiere=matiere_active, periode=periode_active, id__in=evals_avec_notes_ids
        ).order_by("date", "id"))

        # Récupération du coefficient de la matière pour cette classe
        cmc_active = next((c for c in cmcs if c.matiere_id == matiere_active.id), None)
        coef_matiere = cmc_active.coefficient if cmc_active else Decimal("1.0")
        est_second_cycle = bool(classe.niveau and classe.niveau.cycle == "SECOND_CYCLE")

        evaluations_interros = [e for e in qs_evals if e.type_evaluation == Evaluation.Type.INTERROGATION]
        devoirs_liste = [e for e in qs_evals if e.type_evaluation == Evaluation.Type.DEVOIR]
        # Un seul devoir pour la colonne Devoir
        evaluation_devoir = devoirs_liste[0] if devoirs_liste else None
        compos = [e for e in qs_evals if e.type_evaluation == Evaluation.Type.COMPOSITION]
        evaluation_compo = compos[0] if compos else None

        # Associer à chaque interro un label séquentiel automatique I1, I2, I3...
        for idx, ev in enumerate(evaluations_interros, start=1):
            ev.code_colonne = f"I{idx}"

        notes_map = {}
        for n in Note.objects.filter(evaluation__in=qs_evals).select_related("evaluation", "inscription"):
            notes_map[(n.inscription_id, n.evaluation_id)] = n.valeur

        for insc in inscriptions:
            # 1. Notes Interrogations et Moyenne Interrogations (MI)
            notes_i = []
            somme_i = Decimal("0")
            count_i = Decimal("0")
            for ev in evaluations_interros:
                val = notes_map.get((insc.id, ev.id))
                notes_i.append({"evaluation": ev, "valeur": val})
                if val is not None:
                    somme_i += val
                    count_i += Decimal("1")
            moyenne_i = (somme_i / count_i).quantize(Decimal("0.01")) if count_i > 0 else None

            # 2. Note unique du Devoir (D)
            note_d = notes_map.get((insc.id, evaluation_devoir.id)) if evaluation_devoir else None

            # 3. Moyenne Devoir (MD) = (MI + D) / 2
            moyenne_d = None
            if moyenne_i is not None and note_d is not None:
                moyenne_d = ((moyenne_i + note_d) / Decimal("2")).quantize(Decimal("0.01"))
            elif note_d is not None:
                moyenne_d = note_d
            elif moyenne_i is not None:
                moyenne_d = moyenne_i

            # 4. Note Composition (Compo)
            note_c = notes_map.get((insc.id, evaluation_compo.id)) if evaluation_compo else None

            # 5. Moyenne sur 20 = (MD + Compo) / 2 (ou MD si pas de compo, ou Compo si pas de MD)
            moyenne_sur_20 = None
            if moyenne_d is not None and note_c is not None:
                moyenne_sur_20 = ((moyenne_d + note_c) / Decimal("2")).quantize(Decimal("0.01"))
            elif note_c is not None:
                moyenne_sur_20 = note_c
            elif moyenne_d is not None:
                moyenne_sur_20 = moyenne_d

            # 6. Moyenne coefficientée = Moyenne sur 20 * Coef matière
            moyenne_coef = None
            if moyenne_sur_20 is not None:
                moyenne_coef = (moyenne_sur_20 * coef_matiere).quantize(Decimal("0.01"))

            lignes_notes.append({
                "inscription": insc,
                "eleve": insc.eleve,
                "notes_i": notes_i,
                "moyenne_i": moyenne_i,
                "note_devoir": note_d,
                "moyenne_d": moyenne_d,
                "note_compo": note_c,
                "moyenne_sur_20": moyenne_sur_20,
                "moyenne_coef": moyenne_coef,
            })
    else:
        coef_matiere = Decimal("1.0")
        est_second_cycle = bool(classe.niveau and classe.niveau.cycle == "SECOND_CYCLE")
        evaluation_devoir = None

    # Statut de validation PP pour cette classe et période
    val_pp = ValidationNotesPP.objects.filter(classe=classe, periode=periode_active).first() if periode_active else None

    return render(request, "evaluations/carnet_notes_classe.html", {
        "classe": classe,
        "periodes": periodes,
        "periode_active": periode_active,
        "cmcs": cmcs,
        "matiere_active": matiere_active,
        "coef_matiere": coef_matiere,
        "est_second_cycle": est_second_cycle,
        "evaluations_interros": evaluations_interros,
        "evaluation_devoir": evaluation_devoir,
        "evaluation_compo": evaluation_compo,
        "lignes_notes": lignes_notes,
        "val_pp": val_pp,
        "est_pp": est_pp,
        "est_enseignant": est_prof,
        "peut_ajouter_interro": peut_ajouter_interro,
    })


@login_required
@roles_requis(ROLES_PEDAGO)
def ajouter_interrogation_carnet(request, pk):
    """Permet au professeur de la matière d'ajouter rapidement une interrogation I3, I4..."""
    classe = get_object_or_404(Classe, pk=pk)
    user = request.user
    personnel = getattr(user, "fiche_personnel", None)

    matiere_id = request.POST.get("matiere") or request.GET.get("matiere")
    periode_id = request.POST.get("periode") or request.GET.get("periode")
    from parametrage.models import Matiere
    matiere = get_object_or_404(Matiere, pk=matiere_id)
    periode = get_object_or_404(Periode, pk=periode_id)

    # Vérification des droits enseignant
    if user.role == "ENSEIGNANT":
        if not personnel or not personnel.affectations.filter(classe=classe, matiere=matiere).exists():
            messages.error(request, "Seul l'enseignant assigné à cette matière peut ajouter une interrogation.")
            return redirect(f"/evaluations/carnet/classe/{classe.pk}/?matiere={matiere.pk}&periode={periode.pk}")

    # Calcul du numéro de la nouvelle interrogation
    nb_existantes = Evaluation.objects.filter(
        classe=classe, matiere=matiere, periode=periode,
        type_evaluation=Evaluation.Type.INTERROGATION
    ).count()
    num_nouvelle = nb_existantes + 1

    from django.utils import timezone
    nouvelle_interro = Evaluation.objects.create(
        classe=classe,
        matiere=matiere,
        periode=periode,
        type_evaluation=Evaluation.Type.INTERROGATION,
        coefficient=Decimal("1.0"),
        date=timezone.localdate(),
    )

    journaliser(user, "Ajout d'interrogation", "Évaluation", f"Interrogation {num_nouvelle} créée pour {classe} - {matiere}")
    messages.success(request, f"Interrogation {num_nouvelle} (I{num_nouvelle}) créée. Vous pouvez saisir les notes.")
    return redirect(f"/evaluations/{nouvelle_interro.pk}/saisie/")


@login_required
@roles_requis(ROLES_PEDAGO)
def supprimer_interrogation(request, pk):
    """Supprime une interrogation du carnet de notes."""
    evaluation = get_object_or_404(Evaluation.objects.select_related("classe", "matiere", "periode"), pk=pk)
    classe = evaluation.classe
    matiere = evaluation.matiere
    periode = evaluation.periode

    if evaluation.type_evaluation != Evaluation.Type.INTERROGATION:
        messages.error(request, "Seules les interrogations peuvent être supprimées.")
        return redirect(f"/evaluations/carnet/classe/{classe.pk}/?matiere={matiere.pk}&periode={periode.pk}")

    user = request.user
    personnel = getattr(user, "fiche_personnel", None)
    if user.role == "ENSEIGNANT":
        if not personnel or not personnel.affectations.filter(classe=classe, matiere=matiere).exists():
            messages.error(request, "Vous n'êtes pas autorisé à supprimer cette interrogation.")
            return redirect(f"/evaluations/carnet/classe/{classe.pk}/?matiere={matiere.pk}&periode={periode.pk}")

    if request.method == "POST":
        libelle = str(evaluation)
        evaluation.notes.all().delete()
        evaluation.delete()
        journaliser(user, "Suppression d'interrogation", "Évaluation", f"Suppression de l'évaluation {libelle}")
        messages.success(request, "L'interrogation a été supprimée avec succès. Les colonnes ont été réordonnées.")

    return redirect(f"/evaluations/carnet/classe/{classe.pk}/?matiere={matiere.pk}&periode={periode.pk}")


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "ENSEIGNANT"])
def valider_notes_pp(request, pk):
    """Action de validation / dévalidation du carnet de notes par le Professeur Principal."""
    classe = get_object_or_404(Classe, pk=pk)
    periode_id = request.POST.get("periode")
    periode = get_object_or_404(Periode, pk=periode_id)
    user = request.user
    personnel = getattr(user, "fiche_personnel", None)

    # Vérification d'autorisation : le PP de la classe ou la direction
    if user.role == "ENSEIGNANT" and (not personnel or classe.enseignant_principal_id != personnel.id):
        messages.error(request, "Seul le Professeur Principal assigné à cette classe peut valider les notes.")
        return redirect("evaluations:carnet_notes_classe", pk=classe.pk)

    action = request.POST.get("action", "valider")
    est_valide = (action == "valider")

    val_pp, _ = ValidationNotesPP.objects.update_or_create(
        classe=classe,
        periode=periode,
        defaults={
            "valide_par": personnel,
            "est_valide": est_valide,
            "commentaire": request.POST.get("commentaire", "").strip(),
        },
    )

    if est_valide:
        messages.success(request, f"Notes validées par le Professeur Principal pour {classe.libelle} ({periode.libelle}).")
    else:
        messages.info(request, f"Validation annulée pour {classe.libelle} ({periode.libelle}).")

    return redirect(f"/evaluations/carnet/classe/{classe.pk}/?periode={periode.pk}")



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
        initial = {}
        if request.GET.get("classe"):
            initial["classe"] = request.GET["classe"]
        if request.GET.get("matiere"):
            initial["matiere"] = request.GET["matiere"]
        if request.GET.get("periode"):
            initial["periode"] = request.GET["periode"]
        form = EvaluationForm(user=request.user, initial=initial)
    return render(request, "evaluations/evaluation_form.html", {"form": form})


@login_required
@roles_requis(ROLES_PEDAGO)
def par_classe(request, pk):
    """Accès direct au carnet de notes de la classe."""
    return redirect("evaluations:carnet_notes_classe", pk=pk)


@login_required
@roles_requis(ROLES_PEDAGO)
def saisir_notes_classe(request, pk):
    """Saisie directe des notes d'une classe : aucune programmation d'évaluation requise."""
    from eleves.models import Inscription
    from parametrage.models import ClasseMatiereCoefficient
    from django.utils import timezone

    classe = get_object_or_404(Classe, pk=pk)
    annee = _annee_active(request)
    user = request.user
    personnel = getattr(user, "fiche_personnel", None)

    cmcs = list(ClasseMatiereCoefficient.objects.filter(classe=classe).select_related("matiere").order_by("matiere__libelle"))
    est_prof = (user.role == "ENSEIGNANT")
    est_pp = bool(est_prof and personnel and classe.enseignant_principal_id == personnel.id)
    if est_prof and not est_pp and personnel:
        matiere_ids = set(personnel.affectations.filter(classe=classe).values_list("matiere_id", flat=True))
        cmcs = [cmc for cmc in cmcs if cmc.matiere_id in matiere_ids]

    matiere_id = request.POST.get("matiere") or request.GET.get("matiere")
    matiere = None
    if matiere_id:
        matiere = next((cmc.matiere for cmc in cmcs if str(cmc.matiere_id) == str(matiere_id)), None)
    if not matiere and cmcs:
        matiere = cmcs[0].matiere

    periodes = list(Periode.objects.filter(annee_scolaire=annee).order_by("ordre")) if annee else []
    periode_id = request.POST.get("periode") or request.GET.get("periode")
    periode = None
    if periode_id:
        periode = next((p for p in periodes if str(p.id) == str(periode_id)), None)
    if not periode and periodes:
        periode = periodes[0]

    inscriptions = list(
        Inscription.objects.filter(classe=classe, statut="ACTIVE")
        .select_related("eleve")
        .order_by("eleve__nom", "eleve__prenoms")
    )

    if request.method == "POST":
        if not matiere or not periode:
            messages.error(request, "Veuillez sélectionner une matière et une période valides.")
            return redirect(f"/evaluations/carnet/classe/{classe.pk}/")

        type_eval = request.POST.get("type_evaluation", "INTERROGATION")
        if type_eval not in Evaluation.Type.values:
            type_eval = "INTERROGATION"

        coef_defaut = Decimal("1.0") if type_eval == "INTERROGATION" else (Decimal("2.0") if type_eval == "DEVOIR" else Decimal("3.0"))
        try:
            coef = Decimal(str(request.POST.get("coefficient", coef_defaut)))
        except Exception:
            coef = coef_defaut

        date_eval = request.POST.get("date") or timezone.now().date()

        # Enregistrement automatique de la colonne d'évaluation
        evaluation = Evaluation.objects.create(
            classe=classe,
            matiere=matiere,
            periode=periode,
            type_evaluation=type_eval,
            coefficient=coef,
            date=date_eval,
        )

        from comptes.context_user import get_current_user, set_current_user
        precedent = get_current_user()
        set_current_user(user)
        nb_notes = 0
        try:
            for insc in inscriptions:
                cle = f"note_{insc.pk}"
                val_str = request.POST.get(cle, "").strip().replace(",", ".")
                if val_str:
                    try:
                        val = Decimal(val_str)
                        if Decimal("0") <= val <= Decimal("20"):
                            Note.objects.create(
                                evaluation=evaluation,
                                inscription=insc,
                                valeur=val,
                                saisi_par=personnel,
                            )
                            nb_notes += 1
                    except Exception:
                        pass
        finally:
            set_current_user(precedent)

        journaliser(user, "Saisie directe de notes", "Notes", f"{nb_notes} notes pour {classe} - {matiere} ({type_eval})")
        messages.success(request, f"{nb_notes} note(s) enregistrée(s) avec succès pour {classe.libelle}.")
        return redirect(f"/evaluations/carnet/classe/{classe.pk}/?matiere={matiere.pk}&periode={periode.pk}")

    return render(request, "evaluations/saisie_directe_classe.html", {
        "classe": classe,
        "cmcs": cmcs,
        "matiere": matiere,
        "periodes": periodes,
        "periode": periode,
        "inscriptions": inscriptions,
        "types_eval": Evaluation.Type.choices,
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
        messages.success(request, f"{nb} note(s) enregistrée(s) avec succès.")
        return redirect(f"/evaluations/carnet/classe/{evaluation.classe_id}/?matiere={evaluation.matiere_id}&periode={evaluation.periode_id}")

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
    """Génération des bulletins d'une classe soumise aux vérifications de complétude et calendrier."""
    from eleves.models import Inscription
    from .services import generer_bulletin, verifier_completude_bulletins
    from parametrage.models import AnneeScolaire, Classe, Periode

    annee = _annee_active(request)
    periodes = (
        list(Periode.objects.filter(annee_scolaire=annee).order_by("ordre"))
        if annee
        else list(Periode.objects.all().order_by("ordre"))
    )

    periode_par_defaut = periodes[0] if periodes else None
    periode_id_get = request.GET.get("periode")

    if not request.GET:
        form = BulletinsMasseForm(initial={"periode": periode_par_defaut.pk if periode_par_defaut else None})
    else:
        form = BulletinsMasseForm(request.GET)

    bulletins = []
    classe = None
    periode = None
    verification = None

    if request.method == "GET" and form.is_valid():
        classe = form.cleaned_data.get("classe")
        periode = form.cleaned_data.get("periode")

    if not periode and periode_id_get:
        periode = next((p for p in periodes if str(p.id) == str(periode_id_get)), None)

    if not periode:
        periode = periode_par_defaut

    # Si une classe est sélectionnée
    if classe and periode:
        verification = verifier_completude_bulletins(classe, periode)
        action_generer = request.GET.get("action") == "generer"

        if action_generer:
            if verification["peut_generer"]:
                for inscription in Inscription.objects.filter(classe=classe, statut="ACTIVE"):
                    bulletin = generer_bulletin(inscription, periode)
                    if bulletin:
                        bulletins.append(bulletin)
                messages.success(request, f"{len(bulletins)} bulletin(s) généré(s) avec succès pour {classe.libelle}.")
            else:
                messages.error(request, "Impossible de générer : les conditions de complétude ou de calendrier ne sont pas remplies.")
        else:
            # Simple consultation des bulletins déjà existants
            bulletins = list(
                Bulletin.objects.filter(inscription__classe=classe, periode=periode)
                .select_related("inscription__eleve")
                .order_by("rang", "inscription__eleve__nom")
            )

    # État global de l'établissement pour la période
    etat_global_etablissement = None
    if annee and periode:
        classes_toutes = list(
            Classe.objects.filter(Q(annee_scolaire=annee) | Q(annee_scolaire__isnull=True))
            .select_related("niveau")
            .order_by("niveau__ordre", "libelle")
        )
        classes_pretes = 0
        classes_bloquees = 0
        for cl in classes_toutes:
            v = verifier_completude_bulletins(cl, periode)
            if v["peut_generer"]:
                classes_pretes += 1
            else:
                classes_bloquees += 1
        etat_global_etablissement = {
            "total_classes": len(classes_toutes),
            "classes_pretes": classes_pretes,
            "classes_bloquees": classes_bloquees,
            "toutes_validees": (classes_bloquees == 0 and len(classes_toutes) > 0),
        }

        # Action génération globale de tout l'établissement
        if request.GET.get("action") == "generer_tout":
            if etat_global_etablissement["toutes_validees"]:
                total_bulletins_crees = 0
                for cl in classes_toutes:
                    for inscription in Inscription.objects.filter(classe=cl, statut="ACTIVE"):
                        bulletin = generer_bulletin(inscription, periode)
                        if bulletin:
                            total_bulletins_crees += 1
                messages.success(request, f"Génération globale terminée : {total_bulletins_crees} bulletins générés pour les {len(classes_toutes)} classes.")
            else:
                messages.error(request, "Impossible de générer pour tout l'établissement : certaines classes ont des notes manquantes ou n'ont pas encore été validées par leur Professeur Principal.")

    return render(request, "evaluations/bulletins_classe.html", {
        "form": form,
        "bulletins": bulletins,
        "classe": classe,
        "periode": periode,
        "periodes": periodes,
        "verification": verification,
        "etat_global": etat_global_etablissement,
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
    """Génère les bulletins d'une classe ou de tout l'établissement et les regroupe dans une archive ZIP hiérarchisée (Niveau / Classe)."""
    from eleves.models import Inscription
    from documents.pdf import PdvNonDisponible, pdf_bytes
    from .services import calculer_moyennes, generer_bulletin, mention_pour, rangs_classe

    archive = BytesIO()
    periode_id = request.GET.get("periode")
    classe_id = request.GET.get("classe")
    tout = request.GET.get("tout") == "1"

    if not periode_id:
        messages.error(request, "Période non spécifiée.")
        return redirect("evaluations:bulletins_classe")

    periode = get_object_or_404(Periode, pk=periode_id)

    if tout:
        annee = _annee_active(request)
        classes = list(Classe.objects.filter(Q(annee_scolaire=annee) | Q(annee_scolaire__isnull=True)).select_related("niveau"))
        with ZipFile(archive, "w", ZIP_DEFLATED) as zipf:
            for cl in classes:
                dossier_niveau = cl.niveau.libelle if cl.niveau else "Sans_Niveau"
                dossier_classe = cl.libelle
                rangs = rangs_classe(cl, periode)
                for inscription in Inscription.objects.filter(classe=cl, statut="ACTIVE").select_related("eleve"):
                    bulletin = generer_bulletin(inscription, periode)
                    if not bulletin:
                        continue
                    lignes, moyenne = calculer_moyennes(inscription, periode)
                    contexte = {
                        "bulletin": bulletin, "inscription": inscription, "eleve": inscription.eleve,
                        "lignes": lignes, "moyenne": moyenne,
                        "rang": rangs.get(inscription.pk),
                        "mention": mention_pour(moyenne, inscription.annee_scolaire),
                        "est_annuel": False,
                    }
                    nom_base = f"{inscription.eleve.matricule}_{inscription.eleve.nom}_{inscription.eleve.prenoms}"
                    chemin_zip = f"{dossier_niveau}/{dossier_classe}/{nom_base}.pdf"
                    try:
                        zipf.writestr(chemin_zip, pdf_bytes("evaluations/bulletin_pdf.html", contexte))
                    except PdvNonDisponible:
                        from django.template.loader import render_to_string
                        zipf.writestr(
                            f"{dossier_niveau}/{dossier_classe}/{nom_base}.html",
                            render_to_string("evaluations/bulletin_pdf.html", contexte),
                        )

        journaliser(request.user, "Export ZIP global des bulletins", "Bulletins", f"Période {periode} — Établissement complet")
        reponse = HttpResponse(archive.getvalue(), content_type="application/zip")
        reponse["Content-Disposition"] = f'attachment; filename="bulletins_etablissement_{periode.pk}.zip"'
        return reponse

    if not classe_id:
        messages.error(request, "Veuillez sélectionner une classe.")
        return redirect("evaluations:bulletins_classe")

    classe = get_object_or_404(Classe.objects.select_related("niveau"), pk=classe_id)
    dossier_niveau = classe.niveau.libelle if classe.niveau else "Sans_Niveau"
    dossier_classe = classe.libelle

    with ZipFile(archive, "w", ZIP_DEFLATED) as zipf:
        rangs = rangs_classe(classe, periode)
        for inscription in Inscription.objects.filter(classe=classe, statut="ACTIVE").select_related("eleve"):
            bulletin = generer_bulletin(inscription, periode)
            if bulletin is None:
                continue
            lignes, moyenne = calculer_moyennes(inscription, periode)
            contexte = {
                "bulletin": bulletin, "inscription": inscription, "eleve": inscription.eleve,
                "lignes": lignes, "moyenne": moyenne,
                "rang": rangs.get(inscription.pk),
                "mention": mention_pour(moyenne, inscription.annee_scolaire),
                "est_annuel": False,
            }
            nom_base = f"{inscription.eleve.matricule}_{inscription.eleve.nom}_{inscription.eleve.prenoms}"
            chemin_zip = f"{dossier_niveau}/{dossier_classe}/{nom_base}.pdf"
            try:
                zipf.writestr(chemin_zip, pdf_bytes("evaluations/bulletin_pdf.html", contexte))
            except PdvNonDisponible:
                from django.template.loader import render_to_string
                zipf.writestr(
                    f"{dossier_niveau}/{dossier_classe}/{nom_base}.html",
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
