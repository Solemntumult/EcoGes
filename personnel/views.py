"""Vues du module Personnel (UC-17 à UC-19 + rémunération des enseignants)."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comptes.mixins import roles_requis
from comptes.services import journaliser
from finances.models import FicheDePaie, Paiement
from finances.services import annuler_fiche_paie, creer_fiche_paie, marquer_fiche_payee

from .forms import AffectationForm, CreneauForm, PersonnelForm
from .models import Affectation, CreneauEmploiDuTemps, Personnel
from .services import detail_remuneration, suivi_quotas, verifier_conflits

ROLES_GESTION = ["ADMIN", "SUPERADMIN", "CENSEUR"]
ROLES_EDITION_EDT = ["ADMIN", "SUPERADMIN", "CENSEUR"]
ROLES_PAIE = ["ADMIN", "SUPERADMIN", "COMPTABLE"]

MOIS_LIBELLES = ["janvier", "février", "mars", "avril", "mai", "juin",
                 "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def mois_libelle(mois):
    return MOIS_LIBELLES[mois - 1] if 1 <= mois <= 12 else str(mois)


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"])
def liste(request):
    qs = Personnel.objects.all().order_by("nom", "prenoms")
    fonction = request.GET.get("fonction", "")
    if fonction:
        qs = qs.filter(fonction=fonction)
    paginator = Paginator(qs, 25)
    contexte = {
        "personnel": paginator.get_page(request.GET.get("page")),
        "fonctions": Personnel.Fonction.choices,
        "fonction": fonction,
    }
    return render(request, "personnel/liste.html", contexte)


@login_required
@roles_requis(ROLES_GESTION)
def fiche(request, pk=None):
    instance = get_object_or_404(Personnel, pk=pk) if pk else None
    if request.method == "POST":
        form = PersonnelForm(request.POST, instance=instance)
        if form.is_valid():
            fiche_objet = form.save()
            action = "Création de fiche personnel" if instance is None else "Modification de fiche personnel"
            journaliser(request.user, action, "Personnel", str(fiche_objet))
            messages.success(request, "Fiche personnel enregistrée.")
            return redirect("personnel:liste")
    else:
        form = PersonnelForm(instance=instance)
    return render(request, "personnel/fiche.html", {"form": form, "instance": instance})


@login_required
@roles_requis(ROLES_GESTION)
def affectations(request):
    if request.method == "POST":
        form = AffectationForm(request.POST)
        if form.is_valid():
            affectation = form.save()
            journaliser(request.user, "Affectation", "Personnel", str(affectation))
            messages.success(request, "Affectation enregistrée.")
            return redirect("personnel:affectations")
    else:
        form = AffectationForm()

    from parametrage.models import AnneeScolaire
    annee_courante = AnneeScolaire.objects.filter(est_courante=True).first()
    affectations = Affectation.objects.select_related("personnel", "classe", "matiere", "annee_scolaire")
    if annee_courante:
        affectations = affectations.filter(annee_scolaire=annee_courante)
    contexte = {"form": form, "affectations": affectations, "annee_courante": annee_courante}
    return render(request, "personnel/affectations.html", contexte)


@login_required
@roles_requis(ROLES_GESTION)
def supprimer_affectation(request, pk):
    affectation = get_object_or_404(Affectation, pk=pk)
    journaliser(request.user, "Suppression d'affectation", "Personnel", str(affectation))
    affectation.delete()
    messages.success(request, "Affectation supprimée.")
    return redirect("personnel:affectations")


# ---------------------------------------------------------------------------
# Emploi du temps (UC-19)
# ---------------------------------------------------------------------------

JOURS = [c[0] for c in CreneauEmploiDuTemps.Jour.choices]


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT", "ENSEIGNANT"])
def edt_par_classe(request):
    from parametrage.models import AnneeScolaire, Classe
    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    classes = Classe.objects.filter(annee_scolaire=annee).select_related("niveau") if annee else Classe.objects.none()
    return render(request, "personnel/edt_classes.html", {"classes": classes, "annee": annee})


def _aligner_creneau(creneau, plages):
    """Alignement d'un créneau sur la grille horaire : (idx_debut, span).

    ``plages`` = créneaux horaires d'1 h. Le span est le nombre de colonnes
    occupées (un cours de 2 h couvre deux colonnes, etc.).
    """
    idx_debut = None
    span = 0
    for idx, (debut, fin) in enumerate(plages):
        if creneau.heure_debut < fin and creneau.heure_fin > debut:
            if idx_debut is None:
                idx_debut = idx
            span += 1
    return idx_debut, span


def _durees_max(plages):
    """Durée maximale (en colonnes d'1 h) possible à chaque index de la grille.

    Un cours ne franchit jamais une pause : la durée est plafonnée au segment
    horaire courant. Le premier créneau de chaque segment propose la durée
    totale du segment, les suivants décroissent.
    """
    groupes = []  # index de début de chaque segment
    dernier_fin = None
    for idx, (debut, fin) in enumerate(plages):
        if dernier_fin is None or debut != dernier_fin:
            groupes.append(idx)
        dernier_fin = fin
    durees = [1] * len(plages)
    for g, debut_groupe in enumerate(groupes):
        fin_groupe = groupes[g + 1] - 1 if g + 1 < len(groupes) else len(plages) - 1
        for i in range(debut_groupe, fin_groupe + 1):
            durees[i] = fin_groupe - i + 1
    return durees

@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR"])
def generer_edt(request, pk):
    from parametrage.models import Classe
    from .services import generer_emploi_du_temps_classe
    classe = get_object_or_404(Classe, pk=pk)
    nb_crees = generer_emploi_du_temps_classe(classe)
    messages.success(request, f"L'algorithme a généré {nb_crees} blocs de cours provisoires.")
    return redirect("personnel:edt_classe", pk=classe.pk)


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR"])
def envoyer_edt(request, pk):
    from parametrage.models import Classe
    classe = get_object_or_404(Classe, pk=pk)
    # Dans un projet complet, on appellerait un service d'envoi d'e-mail ou de génération PDF ici.
    # Pour simuler :
    messages.success(request, f"L'emploi du temps de la classe {classe.libelle} a été envoyé aux parents avec succès (simulation).")
    return redirect("personnel:edt_classe", pk=classe.pk)


def _construire_grille(classe, plages, valeurs=None):
    """Grille horaire × jour en créneaux d'1 h de la classe (durées 1-4 h).

    ``valeurs`` : dict {(jour, idx): (affectation_pk, salle, duree)} issu du POST
    (ré-affichage après erreur). Sinon les valeurs proviennent de la base.
    Retourne (grille, autres) où ``autres`` sont les créneaux hors grille
    standard (ajoutés via le formulaire libre, en dehors de la grille horaire).
    """
    durees_max = _durees_max(plages)
    creneaux = list(
        CreneauEmploiDuTemps.objects.filter(affectation__classe=classe)
        .select_related("affectation__matiere", "affectation__personnel")
    )
    par_debut = {}  # (jour, idx_debut) -> creneau
    span_par = {}  # (jour, idx_debut) -> span
    for c in creneaux:
        idx_debut, span = _aligner_creneau(c, plages)
        if idx_debut is not None:
            par_debut[(c.jour, idx_debut)] = c
            span_par[(c.jour, idx_debut)] = max(1, span)

    grille = []
    skip_cells = {jour: 0 for jour in JOURS}

    for idx, (debut, fin) in enumerate(plages):
        ligne = {
            "idx": idx,
            "debut": debut,
            "fin": fin,
            "cellules": []
        }
        for jour in JOURS:
            if skip_cells[jour] > 0:
                skip_cells[jour] -= 1
                continue
            
            creneau = par_debut.get((jour, idx))
            if valeurs is not None:
                aff_pk, salle, duree = valeurs.get((jour, idx), ("", "", 1))
                if aff_pk:
                    try:
                        duree = int(duree)
                    except (TypeError, ValueError):
                        duree = 1
                    duree = max(1, min(duree, durees_max[idx]))
                    ligne["cellules"].append({
                        "jour": jour, "idx": idx, "debut": plages[idx][0], "fin": plages[idx + duree - 1][1],
                        "affectation_id": aff_pk, "salle": salle, "creneau": None,
                        "span": duree, "duree_max": durees_max[idx],
                    })
                    if duree > 1:
                        skip_cells[jour] = duree - 1
                    continue
                
                ligne["cellules"].append({
                    "jour": jour, "idx": idx, "debut": plages[idx][0], "fin": plages[idx][1],
                    "affectation_id": "", "salle": "", "creneau": None,
                    "span": 1, "duree_max": durees_max[idx],
                })
                continue

            if creneau:
                span = span_par.get((jour, idx), 1)
                ligne["cellules"].append({
                    "jour": jour, "idx": idx, "debut": plages[idx][0], "fin": plages[idx + span - 1][1],
                    "affectation_id": str(creneau.affectation_id), "salle": creneau.salle,
                    "creneau": creneau, "span": span, "duree_max": durees_max[idx],
                })
                if span > 1:
                    skip_cells[jour] = span - 1
            else:
                ligne["cellules"].append({
                    "jour": jour, "idx": idx, "debut": plages[idx][0], "fin": plages[idx][1],
                    "affectation_id": "", "salle": "", "creneau": None,
                    "span": 1, "duree_max": durees_max[idx],
                })
        grille.append(ligne)

    autres = [c for c in creneaux if _aligner_creneau(c, plages)[0] is None]
    return grille, autres


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT", "ENSEIGNANT"])
def edt_classe(request, pk):
    from parametrage.models import Classe, HoraireJournalier
    classe = get_object_or_404(Classe.objects.select_related("niveau", "annee_scolaire"), pk=pk)
    horaire = HoraireJournalier.obtenir_actif()
    # Grille en créneaux d'1 h (un cours peut occuper 1, 2, 3 ou 4 créneaux)
    plages = horaire.plages_horaires() if horaire else []
    
    # Si mode consultation, on masque les outils d'édition
    mode_consultation = request.GET.get('mode') == 'consultation'
    peut_editer = not mode_consultation and (request.user.is_superuser or request.user.role in ROLES_EDITION_EDT)

    affectations = list(
        Affectation.objects.filter(classe=classe, annee_scolaire=classe.annee_scolaire)
        .select_related("personnel", "matiere").order_by("matiere__libelle")
    )

    if request.method == "POST" and peut_editer:
        return _enregistrer_grille(request, classe, horaire, plages, affectations)

    grille, autres = _construire_grille(classe, plages)
    return render(request, "personnel/edt_classe.html", {
        "classe": classe, "jours": JOURS, "horaire": horaire,
        "plages": plages, "grille": grille, "autres": autres,
        "affectations": affectations, "peut_editer": peut_editer,
        "mode_consultation": mode_consultation,
        "quotas": suivi_quotas(classe),
        "duree_base_minutes": horaire.duree_creneau_base if horaire else 60,
    })


def _chevauche_temps(debut_a, fin_a, debut_b, fin_b):
    """True si deux plages horaires du même jour se chevauchent."""
    return debut_a < fin_b and debut_b < fin_a


def _enregistrer_grille(request, classe, horaire, plages, affectations):
    """Enregistre la grille éditée (durée 1-4 h, création / modification / retrait).

    Chaque cellule de départ (ou vide) envoie ``cell_<jour>_<idx>``,
    ``duree_<jour>_<idx>`` (en heures) et ``salle_<jour>_<idx>``. Les colonnes
    couvertes par un cours de plusieurs heures n'envoient aucun champ.
    """
    if not plages:
        messages.error(request, "Aucun horaire actif — définissez d'abord un horaire "
                                "dans Paramétrage → Horaires scolaires.")
        return redirect("personnel:edt_classe", pk=classe.pk)

    par_pk = {a.pk: a for a in affectations}
    durees_max = _durees_max(plages)

    valeurs = {}
    propositions = []  # (jour, idx, duree, debut, fin, aff, salle)
    for jour in JOURS:
        for idx, (debut, fin) in enumerate(plages):
            aff_pk = request.POST.get(f"cell_{jour}_{idx}", "").strip()
            salle = request.POST.get(f"salle_{jour}_{idx}", "").strip()
            if not aff_pk:
                valeurs[(jour, idx)] = ("", "", 1)
                continue
            duree = 1
            duree_str = request.POST.get(f"duree_{jour}_{idx}", "").strip()
            if duree_str.isdigit():
                duree = int(duree_str)
            duree = max(1, min(duree, durees_max[idx]))  # pas de franchissement de pause
            fin_reelle = plages[idx + duree - 1][1]
            propositions.append((jour, idx, duree, debut, fin_reelle, aff_pk, salle))
            valeurs[(jour, idx)] = (aff_pk, salle, duree)

    # Créneaux existants alignés sur la grille (par colonne de départ)
    par_debut = {}
    for c in CreneauEmploiDuTemps.objects.filter(affectation__classe=classe):
        idx_debut, _ = _aligner_creneau(c, plages)
        if idx_debut is not None:
            par_debut[(c.jour, idx_debut)] = c

    a_creer, a_modifier, a_supprimer, erreurs = [], [], [], []
    occupes = []  # (jour, debut, fin) des cours déjà proposés dans cette grille
    for jour, idx, duree, debut, fin, aff_pk, salle in propositions:
        existant = par_debut.get((jour, idx))
        aff = par_pk.get(int(aff_pk)) if aff_pk.isdigit() else None
        if aff is None:
            erreurs.append(f"{jour} {debut:%H:%M} : affectation invalide.")
            continue
        # Chevauchement avec un autre cours proposé dans la même grille
        if any(j == jour and _chevauche_temps(debut, fin, d, f) for j, d, f in occupes):
            erreurs.append(f"{jour} {debut:%H:%M} : un autre cours occupe déjà cet horaire dans la grille.")
            continue
        meme = (existant and existant.affectation_id == aff.pk
                and existant.heure_debut == debut and existant.heure_fin == fin)
        if meme:
            if existant.salle != salle:
                existant.salle = salle
                a_modifier.append(existant)
            continue
        nouveau = CreneauEmploiDuTemps(
            affectation=aff, jour=jour, heure_debut=debut, heure_fin=fin, salle=salle
        )
        # Le créneau existant (remplacé) est exclu du contrôle : il sera
        # supprimé dans la même transaction — sinon faux conflit « classe déjà occupée ».
        conflits = verifier_conflits(nouveau, exclure={existant.pk} if existant else None)
        if conflits:
            erreurs.extend(f"{jour} {debut:%H:%M} : {m}" for m in conflits)
        else:
            if existant:
                a_supprimer.append(existant)
            a_creer.append(nouveau)
            occupes.append((jour, debut, fin))

    # Retraits : cellules de départ rendues vides
    for jour in JOURS:
        for idx in range(len(plages)):
            cle = f"cell_{jour}_{idx}"
            if cle in request.POST and not request.POST.get(cle, "").strip():
                existant = par_debut.get((jour, idx))
                if existant and existant not in a_supprimer:
                    a_supprimer.append(existant)

    if erreurs:
        for erreur in erreurs[:25]:
            messages.error(request, f"⚠️ {erreur}")
        grille, autres = _construire_grille(classe, plages, valeurs)
        return render(request, "personnel/edt_classe.html", {
            "classe": classe, "jours": JOURS, "horaire": horaire,
            "plages": plages, "grille": grille, "autres": autres,
            "affectations": affectations, "peut_editer": True,
            "erreurs_sauvegarde": True,
        })

    with transaction.atomic():
        for c in a_supprimer:
            c.delete()
        for c in a_modifier:
            c.save(update_fields=["salle"])
        for c in a_creer:
            c.save()
            journaliser(request.user, "Créneau emploi du temps", "Emploi du temps", str(c))

    if a_creer or a_modifier or a_supprimer:
        messages.success(request,
            f"Emploi du temps de {classe.libelle} enregistré — "
            f"{len(a_creer)} créé(s), {len(a_modifier)} modifié(s), {len(a_supprimer)} retiré(s).")
    else:
        messages.info(request, "Aucun changement.")
    return redirect("personnel:edt_classe", pk=classe.pk)


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT", "ENSEIGNANT"])
def edt_enseignant(request):
    enseignant_id = request.GET.get("enseignant", "")
    enseignant = None
    creneaux = []
    if enseignant_id:
        enseignant = get_object_or_404(Personnel, pk=enseignant_id)
        creneaux = list(
            CreneauEmploiDuTemps.objects.filter(affectation__personnel=enseignant)
            .select_related("affectation__matiere", "affectation__classe")
            .order_by("heure_debut")
        )
    enseignants = Personnel.objects.filter(fonction="ENSEIGNANT", actif=True)
    return render(request, "personnel/edt_enseignant.html", {
        "enseignants": enseignants,
        "enseignant": enseignant,
        "jours": JOURS,
        **grille_creneaux(creneaux, "enseignant"),
    })


def grille_creneaux(creneaux, mode):
    """Construit une grille horaire × jour alignée (lignes = horaires).

    Retourne : horaires (liste de tuples début/fin) et lignes (liste de
    couples (horaire, cellules)) où chaque cellule est un créneau ou None.
    """
    horaires = sorted({(c.heure_debut, c.heure_fin) for c in creneaux}, key=lambda h: (h[0], h[1]))
    cellules = {jour: {horaire: None for horaire in horaires} for jour in JOURS}
    for c in creneaux:
        cellules[c.jour][(c.heure_debut, c.heure_fin)] = c
    lignes = [((debut, fin), [cellules[jour][(debut, fin)] for jour in JOURS]) for debut, fin in horaires]
    return {"horaires": horaires, "lignes": lignes}


@login_required
@roles_requis(ROLES_GESTION)
def creer_creneau(request):
    if request.method == "POST":
        form = CreneauForm(request.POST)
        if form.is_valid():
            creneau = form.save(commit=False)
            conflits = verifier_conflits(creneau)
            if conflits:
                for message in conflits:
                    messages.warning(request, f"⚠️ {message}")
                form.add_error(None, "Conflit d'horaire détecté — vérifiez la grille.")
            else:
                creneau.save()
                journaliser(request.user, "Créneau emploi du temps", "Emploi du temps", str(creneau))
                messages.success(request, "Créneau ajouté sans conflit.")
                return redirect("personnel:edt_par_classe")
    else:
        form = CreneauForm()
    return render(request, "personnel/creneau_form.html", {"form": form})


@login_required
@roles_requis(ROLES_GESTION)
def modifier_creneau(request, pk):
    creneau = get_object_or_404(
        CreneauEmploiDuTemps.objects.select_related("affectation__classe"), pk=pk
    )
    if request.method == "POST":
        form = CreneauForm(request.POST, instance=creneau)
        if form.is_valid():
            conflits = verifier_conflits(creneau)
            if conflits:
                for message in conflits:
                    messages.warning(request, f"⚠️ {message}")
                form.add_error(None, "Conflit d'horaire détecté — vérifiez la grille.")
            else:
                form.save()
                journaliser(request.user, "Modification de créneau", "Emploi du temps", str(creneau))
                messages.success(request, "Créneau modifié.")
                return redirect("personnel:edt_classe", pk=creneau.affectation.classe.pk)
    else:
        form = CreneauForm(instance=creneau)
    return render(request, "personnel/creneau_form.html", {"form": form, "creneau": creneau})


@login_required
@roles_requis(ROLES_GESTION)
def supprimer_creneau(request, pk):
    creneau = get_object_or_404(CreneauEmploiDuTemps, pk=pk)
    journaliser(request.user, "Suppression de créneau", "Emploi du temps", str(creneau))
    creneau.delete()
    messages.success(request, "Créneau supprimé.")
    return redirect("personnel:edt_par_classe")


@login_required
def api_recherche_affectations(request):
    """Endpoint JSON pour l'autocomplétion des affectations dans l'éditeur EDT."""
    from django.http import JsonResponse
    from parametrage.models import AnneeScolaire, Classe

    classe_pk = request.GET.get("classe", "")
    terme = request.GET.get("q", "").strip().lower()
    if not classe_pk:
        return JsonResponse([], safe=False)

    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    affectations_qs = (
        Affectation.objects.filter(classe_id=classe_pk, annee_scolaire=annee)
        .select_related("personnel", "matiere")
        .order_by("matiere__libelle")
    ) if annee else Affectation.objects.none()

    resultats = []
    for aff in affectations_qs:
        label = f"{aff.matiere.libelle} — {aff.personnel.prenoms[0]}. {aff.personnel.nom}"
        if terme and terme not in label.lower():
            continue
        resultats.append({
            "id": aff.pk,
            "matiere": aff.matiere.libelle,
            "professeur": f"{aff.personnel.prenoms[0]}. {aff.personnel.nom}",
            "label": label,
        })
    return JsonResponse(resultats, safe=False)


# ---------------------------------------------------------------------------
# Rémunération des enseignants & fiches de paie
# ---------------------------------------------------------------------------

@login_required
@roles_requis(ROLES_PAIE)
def remunerations(request):
    aujourdhui = timezone.localdate()
    try:
        mois = int(request.GET.get("mois", aujourdhui.month))
        annee = int(request.GET.get("annee", aujourdhui.year))
    except (TypeError, ValueError):
        mois, annee = aujourdhui.month, aujourdhui.year

    if request.method == "POST":
        personnel_id = request.POST.get("personnel", "")
        try:
            personnel = Personnel.objects.get(pk=personnel_id, fonction="ENSEIGNANT")
            fiche, creee = creer_fiche_paie(personnel, mois, annee, utilisateur=request.user)
        except (Personnel.DoesNotExist, ValueError, TypeError):
            messages.error(request, "Enseignant invalide.")
            return redirect("personnel:remunerations")
        if fiche.statut == FicheDePaie.Statut.PAYEE:
            messages.info(request, f"Une fiche déjà payée existe pour ce mois : {fiche}")
        else:
            messages.success(request,
                ("Fiche de paie générée : " if creee else "Fiche recalculée : ") + str(fiche))
        return redirect("personnel:fiche_paie", pk=fiche.pk)

    enseignants = Personnel.objects.filter(fonction="ENSEIGNANT", actif=True).order_by("nom", "prenoms")
    lignes = []
    total_hebdo = Decimal("0")
    masse_mensuelle = Decimal("0")
    for pers in enseignants:
        detail = detail_remuneration(pers)
        total_hebdo += detail["total_hebdo"]
        masse_mensuelle += detail["montant_mensuel"]
        fiche = FicheDePaie.objects.filter(personnel=pers, mois=mois, annee=annee).first()
        lignes.append({"personnel": pers, **detail, "fiche": fiche})

    return render(request, "personnel/remunerations.html", {
        "lignes": lignes,
        "mois": mois, "annee": annee,
        "mois_choix": MOIS_LIBELLES,
        "annees": list(range(annee - 2, annee + 3)),
        "mois_libelle": mois_libelle(mois),
        "total_hebdo": total_hebdo,
        "masse_mensuelle": masse_mensuelle,
    })


@login_required
@roles_requis(ROLES_PAIE)
def fiche_paie(request, pk):
    fiche = get_object_or_404(FicheDePaie.objects.select_related("personnel"), pk=pk)
    lignes = _lignes_remuneration(fiche)
    return render(request, "personnel/fiche_paie.html", {
        "fiche": fiche,
        "lignes": lignes,
        "mois_libelle": mois_libelle(fiche.mois),
        "modes": Paiement.ModePaiement.choices,
    })


@login_required
@roles_requis(ROLES_PAIE)
def fiche_paie_pdf(request, pk):
    fiche = get_object_or_404(FicheDePaie.objects.select_related("personnel"), pk=pk)
    lignes = _lignes_remuneration(fiche)
    from documents.pdf import reponse_pdf
    return reponse_pdf(
        "finances/fiche_paie_pdf.html",
        {"fiche": fiche, "lignes": lignes, "mois_libelle": mois_libelle(fiche.mois)},
        f"bulletin_paie_{fiche.numero}",
    )


@login_required
@roles_requis(ROLES_PAIE)
def fiche_paie_payer(request, pk):
    fiche = get_object_or_404(FicheDePaie, pk=pk)
    if request.method == "POST":
        mode = request.POST.get("mode_paiement", Paiement.ModePaiement.ESPECES)
        date_paiement = request.POST.get("date_paiement") or None
        marquer_fiche_payee(fiche, mode, date_paiement, utilisateur=request.user)
        messages.success(request, f"Fiche {fiche.numero} marquée comme payée.")
    return redirect("personnel:fiche_paie", pk=fiche.pk)


def _lignes_remuneration(fiche):
    """Lignes de rémunération de l'année scolaire de la fiche (pas de l'année courante)."""
    from parametrage.models import AnneeScolaire
    annee_scolaire = AnneeScolaire.objects.filter(date_debut__year=fiche.annee).first()
    return detail_remuneration(fiche.personnel, annee=annee_scolaire)["lignes"]


@login_required
@roles_requis(ROLES_PAIE)
def fiche_paie_annuler(request, pk):
    fiche = get_object_or_404(FicheDePaie, pk=pk)
    if request.method == "POST":
        try:
            annuler_fiche_paie(fiche, utilisateur=request.user)
            messages.success(request, f"Fiche {fiche.numero} annulée.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("personnel:fiche_paie", pk=fiche.pk)

@login_required
@roles_requis(['ADMIN', 'SUPERADMIN'])
def disponibilites(request, pk):
    personnel = get_object_or_404(Personnel, pk=pk)
    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    if request.method == 'POST':
        if 'supprimer' in request.POST:
            personnel.disponibilites.filter(pk=request.POST.get('supprimer')).delete()
            messages.success(request, 'Disponibilité supprimée.')
            return redirect('personnel:disponibilites', pk=pk)
        from .forms import DisponibiliteForm
        form = DisponibiliteForm(request.POST)
        if form.is_valid():
            dispo = form.save(commit=False)
            dispo.personnel = personnel
            dispo.annee_scolaire = annee
            dispo.save()
            messages.success(request, 'Disponibilité ajoutée.')
            return redirect('personnel:disponibilites', pk=pk)
    else:
        from .forms import DisponibiliteForm
        form = DisponibiliteForm()
    dispos = personnel.disponibilites.filter(annee_scolaire=annee) if annee else []
    return render(request, 'personnel/disponibilites.html', {'personnel': personnel, 'dispos': dispos, 'form': form, 'annee': annee})
