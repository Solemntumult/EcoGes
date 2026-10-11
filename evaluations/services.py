"""Moteur de calcul des notes et bulletins (UC-22, UC-23, UC-24).

Toutes les moyennes sont pondérées par le coefficient des évaluations
puis par le coefficient de la matière. Les fonctions sont indépendantes
de Django HTTP et donc directement testables.
"""

from decimal import Decimal

from eleves.models import Inscription
from parametrage.models import BaremeEvaluation, ClasseMatiereCoefficient

from .models import Bulletin, Note


def notes_par_matiere(inscription, periode=None):
    """Regroupe les notes d'un élève par matière avec moyenne pondérée.

    Retourne un dict {matiere_id: {matiere, notes, moyenne}} où la moyenne
    tient compte du coefficient de chaque évaluation.
    """
    notes = Note.objects.filter(inscription=inscription).select_related(
        "evaluation__matiere"
    )
    if periode is not None:
        notes = notes.filter(evaluation__periode=periode)

    resultat = {}
    for note in notes.order_by("evaluation__date"):
        matiere = note.evaluation.matiere
        coef = note.evaluation.coefficient
        entree = resultat.setdefault(
            matiere.pk,
            {
                "matiere": matiere,
                "notes": [],
                "total_coef": Decimal("0"),
                "total_pondere": Decimal("0"),
            },
        )
        entree["notes"].append(note)
        entree["total_coef"] += coef
        entree["total_pondere"] += note.valeur * coef

    for entree in resultat.values():
        entree["moyenne"] = (
            (entree["total_pondere"] / entree["total_coef"]).quantize(Decimal("0.01"))
            if entree["total_coef"]
            else None
        )
    return resultat


def calculer_moyennes(inscription, periode=None):
    """Calcule la moyenne générale pondérée d'un élève.

    Retourne (lignes_par_matiere, moyenne_generale) :
    - lignes : liste de dicts {matiere, moyenne, coef_matiere}
    - moyenne_generale : Decimal ou None si aucune note.
    """
    par_matiere = notes_par_matiere(inscription, periode)
    # Coefficients (matière, classe) — un coefficient appartient au couple,
    # jamais à la matière seule (cf. ClasseMatiereCoefficient).
    coeffs = {
        cmc.matiere_id: cmc.coefficient
        for cmc in ClasseMatiereCoefficient.objects.filter(classe=inscription.classe)
    }
    total_pondere = Decimal("0")
    total_coef = Decimal("0")
    lignes = []
    for entree in par_matiere.values():
        if entree["moyenne"] is None:
            continue
        coef_matiere = coeffs.get(entree["matiere"].pk, Decimal("1"))
        total_pondere += entree["moyenne"] * coef_matiere
        total_coef += coef_matiere
        lignes.append({
            "matiere": entree["matiere"],
            "moyenne": entree["moyenne"],
            "coef": coef_matiere,
            "notes": entree["notes"],
        })

    moyenne_generale = (
        (total_pondere / total_coef).quantize(Decimal("0.01")) if total_coef else None
    )
    return lignes, moyenne_generale


def mention_pour(moyenne, annee_scolaire=None):
    """Mention selon les seuils du barème (UC-10 / UC-22)."""
    bareme = None
    if annee_scolaire is not None:
        bareme = getattr(annee_scolaire, "bareme", None)
    if bareme is None:
        bareme = BaremeEvaluation(seuil_passage=10, seuil_mention_bien=14, seuil_mention_tres_bien=16)

    if moyenne >= bareme.seuil_mention_tres_bien:
        return "Très bien"
    if moyenne >= bareme.seuil_mention_bien:
        return "Bien"
    if moyenne >= Decimal("12"):
        return "Assez bien"
    if moyenne >= bareme.seuil_passage:
        return "Passable"
    return "Insuffisant"


def rangs_classe(classe, periode=None):
    """Classement des élèves d'une classe : {inscription_id: rang}."""
    moyennes = {}
    for inscription in Inscription.objects.filter(classe=classe, statut="ACTIVE"):
        _, moyenne = calculer_moyennes(inscription, periode)
        if moyenne is not None:
            moyennes[inscription.pk] = moyenne
    triees = sorted(moyennes.items(), key=lambda item: -item[1])
    return {pk: rang for rang, (pk, _) in enumerate(triees, start=1)}


def generer_bulletin(inscription, periode=None, est_annuel=False):
    """Calcule et enregistre le bulletin (BD + PDF) d'un élève.

    Retourne le Bulletin créé/mis à jour, ou None si aucune note.
    """
    lignes, moyenne = calculer_moyennes(inscription, periode)
    if moyenne is None:
        return None

    rangs = rangs_classe(inscription.classe, periode)
    rang = rangs.get(inscription.pk)
    mention = mention_pour(moyenne, inscription.annee_scolaire)

    bulletin, _ = Bulletin.objects.update_or_create(
        inscription=inscription,
        periode=periode,
        est_annuel=est_annuel,
        defaults={
            "moyenne_generale": moyenne,
            "rang": rang,
            "mention": mention,
        },
    )

    _ecrire_pdf_bulletin(bulletin, lignes, moyenne, rang, mention, est_annuel)
    return bulletin


def _ecrire_pdf_bulletin(bulletin, lignes, moyenne, rang, mention, est_annuel):
    """Enregistre le PDF du bulletin sur le champ fichier_pdf.

    Seule l'absence de WeasyPrint est tolérée (le bulletin reste consultable
    sans PDF) ; toute autre erreur (gabarit, rendu) remonte pour être corrigée.
    """
    from django.core.files.base import ContentFile

    from documents.pdf import PdvNonDisponible, pdf_bytes

    contexte = {
        "bulletin": bulletin,
        "inscription": bulletin.inscription,
        "eleve": bulletin.inscription.eleve,
        "lignes": lignes,
        "moyenne": moyenne,
        "rang": rang,
        "mention": mention,
        "est_annuel": est_annuel,
        "stats_classe": statistiques_classe(bulletin.inscription.classe, bulletin.periode),
    }
    try:
        data = pdf_bytes("evaluations/bulletin_pdf.html", contexte)
    except PdvNonDisponible:
        return
    periode_tag = "annuel" if est_annuel else f"p{bulletin.periode_id}"
    bulletin.fichier_pdf.save(
        f"bulletin_{bulletin.inscription.eleve.matricule}_{periode_tag}.pdf",
        ContentFile(data),
        save=True,
    )


def statistiques_classe(classe, periode=None):
    """Moyenne générale de la classe et répartition des mentions (UC-40)."""
    moyennes = []
    mentions = {}
    for inscription in Inscription.objects.filter(classe=classe, statut="ACTIVE"):
        _, moyenne = calculer_moyennes(inscription, periode)
        if moyenne is not None:
            moyennes.append(moyenne)
            m = mention_pour(moyenne, inscription.annee_scolaire)
            mentions[m] = mentions.get(m, 0) + 1
    moyenne_classe = (
        (sum(moyennes, Decimal("0")) / len(moyennes)).quantize(Decimal("0.01"))
        if moyennes else None
    )
    return {
        "effectif": len(moyennes),
        "moyenne_classe": moyenne_classe,
        "plus_forte": max(moyennes) if moyennes else None,
        "plus_faible": min(moyennes) if moyennes else None,
        "mentions": mentions,
    }


stats_pour_bulletin = statistiques_classe


def verifier_completude_bulletins(classe, periode):
    """Vérifie la complétude des notes et le respect des dates pour la génération des bulletins.

    Critères métier stricts :
    1. Calendrier : La période doit être dans sa dernière phase (au plus 14 jours avant date_fin ou terminée).
    2. Complétude : Pour chaque matière ayant un coefficient, il faut au moins :
       - 2 interrogations
       - 2 devoirs
       - 1 composition / examen
    3. Chaque élève actif doit avoir une note reportée pour chaque évaluation créée.
    """
    from datetime import date, timedelta
    from django.utils import timezone
    from parametrage.models import ClasseMatiereCoefficient
    from .models import Evaluation, Note, ValidationNotesPP

    if not periode:
        return {
            "peut_generer": False,
            "date_autorisee": False,
            "jours_avant_fin": 0,
            "est_complet": False,
            "pp_valide": False,
            "val_pp": None,
            "anomalies": ["Période non spécifiée."],
        }

    aujourdhui = timezone.localdate()
    jours_avant_fin = (periode.date_fin - aujourdhui).days if periode.date_fin else 0
    date_autorisee = (jours_avant_fin <= 14) if periode.date_fin else True

    anomalies = []
    cmcs = ClasseMatiereCoefficient.objects.filter(classe=classe).select_related("matiere")
    inscriptions = list(Inscription.objects.filter(classe=classe, statut="ACTIVE"))
    nb_eleves = len(inscriptions)

    if not cmcs.exists():
        anomalies.append(f"Aucune matière ni coefficient configuré pour la classe {classe.libelle}.")

    for cmc in cmcs:
        evals = Evaluation.objects.filter(classe=classe, matiere=cmc.matiere, periode=periode)
        nb_interros = evals.filter(type_evaluation=Evaluation.Type.INTERROGATION).count()
        nb_devoirs = evals.filter(type_evaluation=Evaluation.Type.DEVOIR).count()
        nb_compos = evals.filter(type_evaluation=Evaluation.Type.COMPOSITION).count()

        if nb_interros < 2:
            anomalies.append(
                f"{cmc.matiere.libelle} : {nb_interros}/2 interrogation(s) saisie(s)."
            )
        if nb_devoirs < 2:
            anomalies.append(
                f"{cmc.matiere.libelle} : {nb_devoirs}/2 devoir(s) saisi(s)."
            )
        if nb_compos < 1:
            anomalies.append(
                f"{cmc.matiere.libelle} : examen/composition de fin de période non encore saisi(e)."
            )

        # Vérifier que tous les élèves ont une note saisie
        for ev in evals:
            nb_notes = Note.objects.filter(evaluation=ev).count()
            if nb_notes < nb_eleves:
                date_str = ev.date.strftime("%d/%m") if ev.date else ""
                anomalies.append(
                    f"{cmc.matiere.libelle} ({ev.get_type_evaluation_display()} du {date_str}) : "
                    f"notes manquantes ({nb_notes}/{nb_eleves} élèves notés)."
                )

    val_pp = ValidationNotesPP.objects.filter(classe=classe, periode=periode).first()
    pp_valide = bool(val_pp and val_pp.est_valide)
    if not pp_valide:
        anomalies.append(f"Validation du Professeur Principal (PP) en attente pour {classe.libelle}.")

    est_complet = (len(anomalies) == 0)
    peut_generer = date_autorisee and est_complet

    return {
        "peut_generer": peut_generer,
        "date_autorisee": date_autorisee,
        "jours_avant_fin": jours_avant_fin,
        "est_complet": est_complet,
        "pp_valide": pp_valide,
        "val_pp": val_pp,
        "anomalies": anomalies,
    }
