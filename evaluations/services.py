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
        "stats_classe": stats_pour_bulletin(bulletin.inscription.classe, bulletin.periode),
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
        "mentions": mentions,
    }


def stats_pour_bulletin(classe, periode=None):
    """Statistiques affichées sur le bulletin : effectif, moyennes extrêmes et de classe."""
    moyennes = []
    for inscription in Inscription.objects.filter(classe=classe, statut="ACTIVE"):
        _, moyenne = calculer_moyennes(inscription, periode)
        if moyenne is not None:
            moyennes.append(moyenne)
    if not moyennes:
        return None
    return {
        "effectif": len(moyennes),
        "moyenne_classe": (sum(moyennes, Decimal("0")) / len(moyennes)).quantize(Decimal("0.01")),
        "plus_forte": max(moyennes),
        "plus_faible": min(moyennes),
    }
