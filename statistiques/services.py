"""Services du module Statistiques : agrégations pour le tableau de bord (UC-40)."""

from collections import OrderedDict
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from eleves.models import Eleve, Inscription
from evaluations.models import Bulletin
from finances.models import Echeance, ImputationPaiement, Paiement
from parametrage.models import AnneeScolaire, Classe, Periode


def effectifs_par_classe(annee=None):
    """Effectifs actifs par classe pour une année (ou la courante)."""
    if annee is None:
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
    if annee is None:
        return []
    classes = Classe.objects.filter(annee_scolaire=annee).select_related("niveau").order_by("niveau__ordre")
    resultat = []
    for classe in classes:
        effectif = Inscription.objects.filter(classe=classe, statut="ACTIVE").count()
        if effectif:
            resultat.append({"libelle": classe.libelle, "effectif": effectif})
    return resultat


def effectifs_par_annee():
    """Évolution des effectifs inscrits par année scolaire."""
    resultat = []
    for annee in AnneeScolaire.objects.all().order_by("date_debut"):
        effectif = Inscription.objects.filter(annee_scolaire=annee, statut="ACTIVE").count()
        resultat.append({"annee": str(annee), "effectif": effectif})
    return resultat


def recettes_par_mois(nb_mois=12):
    """Encaissements validés par mois (12 derniers mois)."""
    from datetime import date

    resultat = OrderedDict()
    aujourdhui = timezone.localdate()
    annee, mois = aujourdhui.year, aujourdhui.month

    # (année, mois) des 12 derniers mois, du plus ancien au plus récent
    liste = []
    for i in range(nb_mois - 1, -1, -1):
        m = mois - i
        a = annee
        while m <= 0:
            m += 12
            a -= 1
        liste.append((a, m))

    paiements = Paiement.objects.filter(statut=Paiement.Statut.VALIDE)
    for a, m in liste:
        debut = date(a, m, 1)
        fin = date(a + 1, 1, 1) if m == 12 else date(a, m + 1, 1)
        total = (
            paiements.filter(date_paiement__date__gte=debut, date_paiement__date__lt=fin)
            .aggregate(t=Sum("montant"))["t"]
            or Decimal("0")
        )
        resultat[f"{m:02d}/{a}"] = total
    return resultat


def moyennes_par_classe(periode=None):
    """Moyenne générale par classe pour une période (ou la première courante)."""
    if periode is None:
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        periode = Periode.objects.filter(annee_scolaire=annee).order_by("ordre").first() if annee else None
    if periode is None:
        return []

    from evaluations.services import calculer_moyennes
    resultat = []
    classes = Classe.objects.filter(annee_scolaire=periode.annee_scolaire).order_by("niveau__ordre")
    for classe in classes:
        moyennes = []
        for inscription in Inscription.objects.filter(classe=classe, statut="ACTIVE"):
            _, moyenne = calculer_moyennes(inscription, periode)
            if moyenne is not None:
                moyennes.append(moyenne)
        if moyennes:
            resultat.append({
                "libelle": classe.libelle,
                "moyenne": float(sum(moyennes, Decimal("0")) / len(moyennes)),
            })
    return resultat


def taux_recouvrement():
    """Taux de recouvrement global (%) et impayés totaux."""
    total_du = Echeance.objects.aggregate(t=Sum("montant_du"))["t"] or Decimal("0")
    total_paye = ImputationPaiement.objects.aggregate(t=Sum("montant_impute"))["t"] or Decimal("0")
    taux = (total_paye / total_du * 100) if total_du else Decimal("0")
    return {
        "total_du": total_du,
        "total_paye": total_paye,
        "reste_du": total_du - total_paye,
        "taux": round(taux, 1),
    }


def tableau_effectifs():
    """Effectifs par cycle et par sexe pour l'année courante."""
    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    lignes = []
    if annee:
        for cycle, libelle in [("PRIMAIRE", "Primaire"), ("COLLEGE", "Collège"), ("LYCEE", "Lycée")]:
            inscriptions = Inscription.objects.filter(
                annee_scolaire=annee, statut="ACTIVE", classe__niveau__cycle=cycle
            )
            hommes = inscriptions.filter(eleve__sexe="M").count()
            femmes = inscriptions.filter(eleve__sexe="F").count()
            lignes.append({"cycle": libelle, "hommes": hommes, "femmes": femmes, "total": hommes + femmes})
    return lignes
