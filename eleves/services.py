"""Services du module Élèves : réinscription, passage de classe suggéré."""

from django.db import transaction

from parametrage.models import Classe, Niveau

from .models import Inscription


def classe_suggeree(inscription, nouvelle_annee):
    """Classe proposée pour la réinscription (UC-12).

    - Décision « Admis » (ou absence de décision) : niveau supérieur du même
      cycle, si une classe existe sur l'année cible.
    - Décision « Redouble » : même niveau.
    Retourne la première classe correspondante, ou None.
    """
    decision = (inscription.decision_fin_annee or "").lower()
    niveau_actuel = inscription.classe.niveau

    if "redouble" in decision or "redoubl" in decision:
        niveau_cible = niveau_actuel
    else:
        niveau_cible = (
            Niveau.objects.filter(cycle=niveau_actuel.cycle, ordre=niveau_actuel.ordre + 1)
            .order_by("ordre")
            .first()
        ) or niveau_actuel

    return (
        Classe.objects.filter(annee_scolaire=nouvelle_annee, niveau=niveau_cible)
        .order_by("libelle")
        .first()
    )


def reinscrire(eleve, classe, annee, statut_inscription="ANCIEN", utilisateur=None):
    """Réinscrit un élève sur une année (crée l'inscription + l'échéancier).

    Retourne l'inscription créée, ou None si l'élève est déjà inscrit sur
    cette année (contrainte d'unicité eleve/année).
    """
    if Inscription.objects.filter(eleve=eleve, annee_scolaire=annee).exists():
        return None

    with transaction.atomic():
        inscription = Inscription.objects.create(
            eleve=eleve,
            classe=classe,
            annee_scolaire=annee,
            statut_inscription=statut_inscription,
        )
        from finances.services import generer_echeancier
        generer_echeancier(inscription)

    if utilisateur is not None:
        from comptes.services import journaliser
        journaliser(utilisateur, "Réinscription", "Élève",
                    f"{eleve} réinscrit en {classe} ({annee})")

    return inscription
