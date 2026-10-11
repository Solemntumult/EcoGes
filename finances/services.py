"""Services du module Finances : échéanciers, imputation FIFO, reçus, factures.

Toutes les fonctions ici sont conçues pour être testables unitairement
et appelables depuis les vues ou des scripts.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from parametrage.models import GrilleTarifaire

from .models import Echeance, Facture, FicheDePaie, ImputationPaiement, LigneFacture, Recu


def generer_echeancier(inscription, nb_versements=1):
    """Génère l'échéancier d'un élève à partir de la grille tarifaire (UC-26).

    Crée une échéance par type de frais (Inscription, Scolarité, Examen...)
    tel que paramétré dans GrilleTarifaire pour le niveau et l'année scolaire
    de l'inscription. Si ``nb_versements`` > 1, le montant est réparti sur
    plusieurs échéances mensuelles.
    """
    grilles = GrilleTarifaire.objects.filter(
        niveau=inscription.classe.niveau,
        annee_scolaire=inscription.annee_scolaire,
    )
    if not grilles.exists():
        return []

    creees = []
    for grille in grilles:
        total = grille.montant
        nb = max(1, nb_versements)
        base = (total / nb).quantize(Decimal("0.01"))
        for i in range(nb):
            if nb == 1:
                montant = total
            else:
                montant = base if i < nb - 1 else total - base * (nb - 1)
            echeance = Echeance.objects.create(
                inscription=inscription,
                type_frais=grille.type_frais,
                libelle=f"{grille.type_frais} — versement {i + 1}/{nb}",
                montant_du=montant,
                date_echeance=inscription.date_inscription + timedelta(days=30 * (i + 1)),
            )
            creees.append(echeance)
    return creees


def maj_statuts_echeances(inscription):
    """Re-calcule le statut (IMPAYE / PARTIEL / PAYE) de chaque échéance."""
    for echeance in Echeance.objects.filter(inscription=inscription):
        paye = echeance.montant_paye
        if paye >= echeance.montant_du:
            echeance.statut = Echeance.Statut.PAYE
        elif paye > 0:
            echeance.statut = Echeance.Statut.PARTIEL
        else:
            echeance.statut = Echeance.Statut.IMPAYE
        echeance.save(update_fields=["statut"])


def imputer_paiement(paiement, cibles=None, utilisateur=None):
    """Impute un paiement sur les échéances dues (UC-27).

    - Mode par défaut : FIFO — les échéances les plus anciennes sont soldées
      en priorité (``order_by('date_echeance')``).
    - ``cibles`` : liste optionnelle d'ids d'échéances pour une imputation
      manuelle.

    Retourne la liste des imputations créées. Ne ré-impute jamais un
    paiement déjà imputé.
    """
    if paiement.imputations.exists():
        return list(paiement.imputations.all())

    with transaction.atomic():
        echeances = (
            Echeance.objects.filter(inscription=paiement.inscription)
            .exclude(statut=Echeance.Statut.PAYE)
            .order_by("date_echeance")
        )
        if cibles:
            echeances = echeances.filter(pk__in=[int(c) for c in cibles])

        reste = paiement.montant
        imputations = []
        for echeance in echeances:
            if reste <= 0:
                break
            solde = echeance.solde
            if solde <= 0:
                continue
            a_imputer = min(reste, solde)
            ImputationPaiement.objects.create(
                paiement=paiement, echeance=echeance, montant_impute=a_imputer
            )
            reste -= a_imputer
            imputations.append((echeance, a_imputer))

        maj_statuts_echeances(paiement.inscription)
        # Excédent non imputable (compte soldé) : conservé pour information
        paiement.excedent = reste
        if utilisateur is not None:
            from comptes.services import journaliser
            detail = f"{paiement.montant} F — {paiement.get_mode_paiement_display()} — {paiement.inscription.eleve}"
            if reste > 0:
                detail += f" (surpaiement de {reste} F non imputable)"
            journaliser(utilisateur, "Encaissement", "Paiement", detail)
    return imputations


def generer_recu(paiement, utilisateur=None):
    """Crée le reçu numéroté d'un paiement (UC-29)."""
    recu = Recu.objects.get_or_create(paiement=paiement)[0]
    if utilisateur is not None:
        from comptes.services import journaliser
        journaliser(utilisateur, "Émission de reçu", "Reçu", f"Reçu {recu.numero}")
    return recu


def generer_facture(inscription, types_frais=None, utilisateur=None):
    """Émet une facture récapitulative des montants dus (UC-28).

    La facture est créée avec statut EMISE — non modifiable ensuite,
    seulement annulable via un avoir (voir annuler_facture).
    """
    echeances = Echeance.objects.filter(inscription=inscription).order_by("date_echeance")
    if types_frais:
        echeances = echeances.filter(type_frais_id__in=[int(t) for t in types_frais])

    lignes = [(e.libelle, e.solde) for e in echeances if e.solde > 0]
    if not lignes:
        return None

    with transaction.atomic():
        montant_total = sum((m for _, m in lignes), Decimal("0"))
        facture = Facture.objects.create(
            inscription=inscription, montant_total=montant_total
        )
        for libelle, montant in lignes:
            LigneFacture.objects.create(facture=facture, libelle=libelle, montant=montant)
    if utilisateur is not None:
        from comptes.services import journaliser
        journaliser(utilisateur, "Émission de facture", "Facture",
                    f"Facture {facture.numero} — {montant_total} F")
    return facture


def annuler_paiement(paiement, motif, utilisateur=None):
    """Annule un paiement, supprime ses imputations, restaure les échéances (UC-34)."""
    with transaction.atomic():
        paiement.imputations.all().delete()
        paiement.statut = paiement.Statut.ANNULE
        paiement.motif_annulation = motif
        paiement.save(update_fields=["statut", "motif_annulation"])
        maj_statuts_echeances(paiement.inscription)
    if utilisateur is not None:
        from comptes.services import journaliser
        journaliser(utilisateur, "Annulation de paiement", "Paiement",
                    f"Paiement {paiement.pk} annulé — {motif}")
    return paiement


def rembourser_paiement(paiement, motif, utilisateur=None):
    """Marque un paiement comme remboursé (sans recréer d'imputations)."""
    with transaction.atomic():
        paiement.imputations.all().delete()
        paiement.statut = paiement.Statut.REMBOURSE
        paiement.motif_annulation = motif
        paiement.save(update_fields=["statut", "motif_annulation"])
        maj_statuts_echeances(paiement.inscription)
    if utilisateur is not None:
        from comptes.services import journaliser
        journaliser(utilisateur, "Remboursement", "Paiement", motif)
    return paiement


def annuler_facture(facture, motif, utilisateur=None):
    """Annule une facture émise (avoir) — elle devient non payable (UC-28)."""
    facture.statut = Facture.Statut.ANNULEE
    facture.save(update_fields=["statut"])
    if utilisateur is not None:
        from comptes.services import journaliser
        journaliser(utilisateur, "Annulation de facture", "Facture",
                    f"Facture {facture.numero} annulée — {motif}")
    return facture


# ---------------------------------------------------------------------------
# Montant en toutes lettres (standard comptable — reçus)
# ---------------------------------------------------------------------------

_UNITES = ["", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
           "dix", "onze", "douze", "treize", "quatorze", "quinze", "seize",
           "dix-sept", "dix-huit", "dix-neuf"]
_DIZAINES = ["", "dix", "vingt", "trente", "quarante", "cinquante", "soixante",
             "soixante", "quatre-vingt", "quatre-vingt"]


def _moins_100(n):
    if n == 0:
        return ""
    if n == 71:
        return "soixante et onze"
    if n < 20:
        return _UNITES[n]
    dizaine, unite = divmod(n, 10)
    if dizaine in (7, 9):
        return _DIZAINES[dizaine] + "-" + _UNITES[unite + 10]
    if dizaine == 8:
        return "quatre-vingts" if unite == 0 else "quatre-vingt-" + _UNITES[unite]
    if unite == 0:
        return _DIZAINES[dizaine]
    if dizaine == 6 and unite == 1:
        return "soixante et un"
    if unite == 1:
        return _DIZAINES[dizaine] + " et un"
    return _DIZAINES[dizaine] + "-" + _UNITES[unite]


def _moins_1000(n):
    if n == 0:
        return ""
    centaines, reste = divmod(n, 100)
    if centaines == 0:
        return _moins_100(reste)
    if centaines == 1:
        return "cent" if reste == 0 else "cent " + _moins_100(reste)
    return (_UNITES[centaines] + " cents") if reste == 0 else _UNITES[centaines] + " cent " + _moins_100(reste)


def _en_toutes_lettres_entier(n):
    if n == 0:
        return "zéro"
    if n < 0:
        return "moins " + _en_toutes_lettres_entier(-n)
    milliards, n = divmod(n, 1_000_000_000)
    millions, n = divmod(n, 1_000_000)
    milliers, n = divmod(n, 1_000)
    parties = []
    if milliards:
        parties.append(("un" if milliards == 1 else _moins_1000(milliards))
                       + " milliard" + ("" if milliards == 1 else "s"))
    if millions:
        parties.append(("un" if millions == 1 else _moins_1000(millions))
                       + " million" + ("" if millions == 1 else "s"))
    if milliers:
        parties.append("mille" if milliers == 1 else _moins_1000(milliers) + " mille")
    if n:
        parties.append(_moins_1000(n))
    return " ".join(parties)


def montant_en_toutes_lettres(montant):
    """Montant en toutes lettres (français), ex. 25000 → « vingt-cinq mille francs »."""
    montant = Decimal(str(montant))
    entiers = int(montant)
    centimes = int(round((montant - entiers) * 100))
    texte = _en_toutes_lettres_entier(entiers) + " franc" + ("s" if entiers > 1 else "")
    if centimes:
        texte += " et " + _en_toutes_lettres_entier(centimes) + " centime" + ("s" if centimes > 1 else "")
    return texte


def situation_inscription(inscription):
    """Résumé financier d'une inscription : total dû, payé, solde (UC-31)."""
    echeances = list(Echeance.objects.filter(inscription=inscription))
    total_du = sum((e.montant_du for e in echeances), Decimal("0"))
    total_paye = sum((e.montant_paye for e in echeances), Decimal("0"))
    return {
        "total_du": total_du,
        "total_paye": total_paye,
        "solde": total_du - total_paye,
        "nb_impayees": sum(1 for e in echeances if e.statut != Echeance.Statut.PAYE),
    }


# ---------------------------------------------------------------------------
# Fiches de paie du personnel (rémunération des enseignants)
# ---------------------------------------------------------------------------

def creer_fiche_paie(personnel, mois, annee, utilisateur=None):
    """Calcule et enregistre la fiche de paie d'un membre du personnel (Section 12).

    Règles conformes au cahier des charges :
    1. Si des séances dispensées sont validées dans le cahier de textes pour ce
       mois civil, la paie se base sur les heures réelles effectivement données.
    2. Sinon, calcul calendaire sur les occurrences réelles des créneaux dans le mois.
    3. Prise en compte automatique des primes (PrimePersonnel) accordées pour ce mois.
    """
    import calendar
    from cahier_texte.models import SeanceCours
    from .models import PrimePersonnel

    # 1. Vérification des séances réellement dispensées dans le cahier de textes
    seances_reelles = SeanceCours.objects.filter(
        affectation__personnel=personnel,
        date__year=annee,
        date__month=mois,
        statut=SeanceCours.Statut.DISPENSE,
    ).select_related("affectation")

    if seances_reelles.exists():
        heures_mensuelles = sum((s.heures for s in seances_reelles), Decimal("0")).quantize(Decimal("0.01"))
        montant_cours = sum((s.heures * s.affectation.tarif_horaire for s in seances_reelles), Decimal("0")).quantize(Decimal("0.01"))
    else:
        # Fallback calendaire : comptage exact des occurrences des créneaux dans le mois civil
        from personnel.services import FACTEUR_HEURES_MENSUEL, detail_remuneration
        detail = detail_remuneration(personnel)
        heures_mensuelles = (detail["total_hebdo"] * FACTEUR_HEURES_MENSUEL).quantize(Decimal("0.01"))
        montant_cours = detail["montant_mensuel"]

    # 2. Primes validées pour ce mois
    primes = PrimePersonnel.objects.filter(personnel=personnel, mois=mois, annee=annee)
    total_primes = sum((p.montant for p in primes), Decimal("0")).quantize(Decimal("0.01"))

    montant_total = montant_cours + total_primes

    fiche, creee = FicheDePaie.objects.get_or_create(
        personnel=personnel,
        mois=mois,
        annee=annee,
        defaults={"heures_total": heures_mensuelles, "montant_brut": montant_total},
    )
    if not creee and fiche.statut == FicheDePaie.Statut.CALCULEE:
        fiche.heures_total = heures_mensuelles
        fiche.montant_brut = montant_total
        fiche.save(update_fields=["heures_total", "montant_brut"])

    if utilisateur is not None:
        from comptes.services import journaliser
        journaliser(
            utilisateur,
            "Fiche de paie",
            "Personnel",
            f"{fiche} — {montant_total} F brut ({heures_mensuelles}h, primes : {total_primes} F)",
        )
    return fiche, creee


def marquer_fiche_payee(fiche, mode_paiement, date_paiement=None, utilisateur=None):
    """Marque une fiche comme payée et archive son bulletin PDF (si possible)."""
    from django.utils import timezone

    from comptes.services import journaliser
    from personnel.services import detail_remuneration

    fiche.statut = FicheDePaie.Statut.PAYEE
    fiche.mode_paiement = mode_paiement
    fiche.date_paiement = date_paiement or timezone.localdate()
    try:
        from django.core.files.base import ContentFile

        from documents.pdf import PdvNonDisponible, pdf_bytes

        # Lignes de l'année scolaire de la fiche (pas de l'année courante)
        from parametrage.models import AnneeScolaire
        annee_scolaire = AnneeScolaire.objects.filter(date_debut__year=fiche.annee).first()
        lignes = detail_remuneration(fiche.personnel, annee=annee_scolaire)["lignes"]
        data = pdf_bytes("finances/fiche_paie_pdf.html", {"fiche": fiche, "lignes": lignes})
        fiche.fichier_pdf.save(f"bulletin_{fiche.numero}.pdf", ContentFile(data), save=False)
    except PdvNonDisponible:
        pass  # WeasyPrint indisponible → fiche sans PDF archivé (téléchargeable à la volée)
    fiche.save()
    if utilisateur is not None:
        journaliser(utilisateur, "Paiement fiche de paie", "Personnel",
                    f"{fiche} payée le {fiche.date_paiement:%d/%m/%Y}")
    return fiche


def annuler_fiche_paie(fiche, utilisateur=None):
    """Annule une fiche calculée (une fiche payée ne peut pas être annulée)."""
    if fiche.statut == FicheDePaie.Statut.PAYEE:
        raise ValueError("Une fiche de paie déjà payée ne peut pas être annulée.")
    fiche.statut = FicheDePaie.Statut.ANNULEE
    fiche.save(update_fields=["statut"])
    if utilisateur is not None:
        from comptes.services import journaliser
        journaliser(utilisateur, "Annulation fiche de paie", "Personnel", str(fiche))
    return fiche
