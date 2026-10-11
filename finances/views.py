"""Vues du module Finances (UC-26 à UC-34)."""

from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from comptes.mixins import roles_requis
from comptes.services import journaliser
from eleves.models import Inscription

from .forms import EtatCaisseForm, PaiementForm, RemiseForm
from .models import Echeance, Facture, Paiement, Recu, Remise
from .services import (
    annuler_facture,
    annuler_paiement,
    generer_facture,
    generer_recu,
    imputer_paiement,
    rembourser_paiement,
)

ROLES_COMPTA = ["ADMIN", "SUPERADMIN", "COMPTABLE"]


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "COMPTABLE", "SECRETARIAT"])
def impayes(request):
    """Tableau de suivi des frais de scolarité par classe et élève avec encaissement direct."""
    from parametrage.models import AnneeScolaire, Classe
    from eleves.models import Inscription

    annee = AnneeScolaire.objects.filter(est_courante=True).first()
    classes = Classe.objects.all().order_by("niveau__ordre", "libelle")

    classe_id = request.GET.get("classe", "")
    recherche = request.GET.get("q", "").strip()
    statut_filtre = request.GET.get("statut", "")

    inscriptions_qs = (
        Inscription.objects.filter(statut="ACTIVE")
        .select_related("eleve", "classe", "annee_scolaire")
        .prefetch_related("echeances")
    )
    if annee:
        inscriptions_qs = inscriptions_qs.filter(annee_scolaire=annee)

    if classe_id:
        inscriptions_qs = inscriptions_qs.filter(classe_id=classe_id)

    if recherche:
        inscriptions_qs = inscriptions_qs.filter(
            Q(eleve__nom__icontains=recherche)
            | Q(eleve__prenoms__icontains=recherche)
            | Q(eleve__matricule__icontains=recherche)
        )

    lignes = []
    total_general_du = Decimal("0")
    total_general_paye = Decimal("0")
    total_general_reste = Decimal("0")

    for insc in inscriptions_qs.order_by("classe__niveau__ordre", "classe__libelle", "eleve__nom", "eleve__prenoms"):
        echs = list(insc.echeances.all())
        du = sum((e.montant_du for e in echs), Decimal("0"))
        paye = sum((e.montant_paye for e in echs), Decimal("0"))
        reste = sum((e.solde for e in echs), Decimal("0"))

        a_jour = (reste <= Decimal("0"))

        if statut_filtre == "RETARD" and a_jour:
            continue
        if statut_filtre == "A_JOUR" and not a_jour:
            continue

        total_general_du += du
        total_general_paye += paye
        total_general_reste += reste

        lignes.append({
            "inscription": insc,
            "eleve": insc.eleve,
            "classe": insc.classe,
            "total_du": du,
            "montant_paye": paye,
            "reste_a_payer": reste,
            "a_jour": a_jour,
            "nb_echeances": len(echs),
        })

    paginator = Paginator(lignes, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    contexte = {
        "page_obj": page_obj,
        "classes": classes,
        "classe_selectionnee": classe_id,
        "recherche": recherche,
        "statut_filtre": statut_filtre,
        "total_general_du": total_general_du,
        "total_general_paye": total_general_paye,
        "total_general_reste": total_general_reste,
        "annee": annee,
    }
    return render(request, "finances/impayes.html", contexte)


@login_required
@roles_requis(ROLES_COMPTA)
def encaisser(request):
    """Encaissement avec imputation FIFO ou manuelle (UC-27, UC-29)."""
    inscription_preselect = request.GET.get("inscription")
    initial = {}
    if inscription_preselect:
        initial["inscription"] = inscription_preselect

    form = PaiementForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        paiement = form.save(commit=False)
        paiement.encaisse_par = request.user
        paiement.save()
        cibles = None
        if form.cleaned_data["imputation_manuelle"]:
            cibles = form.cleaned_data["echeances"].values_list("pk", flat=True)
        imputations = imputer_paiement(paiement, cibles=cibles, utilisateur=request.user)
        if not imputations:
            messages.warning(request, "Aucune échéance à imputer pour cet élève (compte soldé ?).")
        excedent = getattr(paiement, "excedent", Decimal("0"))
        if excedent > 0:
            messages.warning(
                request,
                f"Surpaiement de {excedent} F non imputable (compte soldé) — rapprochez-vous de la comptabilité.",
            )
        generer_recu(paiement, utilisateur=request.user)
        messages.success(request, f"Paiement de {paiement.montant} F enregistré.")
        return redirect("finances:recu", pk=paiement.recu.pk)

    return render(request, "finances/encaisser.html", {"form": form})


@login_required
@roles_requis(ROLES_COMPTA)
def compte_eleve(request, inscription_pk):
    """Solde et historique financier d'un élève (UC-31)."""
    inscription = get_object_or_404(
        Inscription.objects.select_related("eleve", "classe", "annee_scolaire"), pk=inscription_pk
    )
    from .services import situation_inscription
    situation = situation_inscription(inscription)
    echeances = inscription.echeances.select_related("type_frais").order_by("date_echeance")
    paiements = inscription.paiements.select_related("recu", "encaisse_par").order_by("-date_paiement")
    factures = inscription.factures.all()
    contexte = {
        "inscription": inscription,
        "situation": situation,
        "echeances": echeances,
        "paiements": paiements,
        "factures": factures,
    }
    return render(request, "finances/compte_eleve.html", contexte)


@login_required
@roles_requis(["ADMIN", "SUPERADMIN", "COMPTABLE", "PARENT"])
def recu(request, pk):
    """PDF du reçu de paiement (UC-29).

    Un parent n'accède qu'aux reçus de ses propres enfants (UC-44).
    """
    recu_objet = get_object_or_404(
        Recu.objects.select_related(
            "paiement__inscription__eleve",
            "paiement__inscription__classe",
            "paiement__encaisse_par",
        ),
        pk=pk,
    )
    if request.user.role == "PARENT":
        from portail.views import _enfants_du_parent
        eleve_ids = _enfants_du_parent(request.user).values_list("pk", flat=True)
        if recu_objet.paiement.inscription.eleve_id not in eleve_ids:
            raise PermissionDenied
    imputations = recu_objet.paiement.imputations.select_related("echeance__type_frais").all()
    from .services import montant_en_toutes_lettres, situation_inscription
    inscription = recu_objet.paiement.inscription
    tuteur = (
        inscription.eleve.tuteurs.filter(contact_urgence=True).first()
        or inscription.eleve.tuteurs.first()
    )
    contexte = {
        "recu": recu_objet,
        "imputations": imputations,
        "montant_lettres": montant_en_toutes_lettres(recu_objet.paiement.montant),
        "tuteur": tuteur,
        "situation": situation_inscription(inscription),
    }

    from documents.pdf import reponse_pdf
    return reponse_pdf("finances/recu_pdf.html", contexte, f"recu_{recu_objet.numero}")


@login_required
@roles_requis(ROLES_COMPTA)
def emettre_facture(request, inscription_pk):
    """Émission d'une facture pour un élève (UC-28)."""
    inscription = get_object_or_404(Inscription, pk=inscription_pk)
    facture = generer_facture(inscription, utilisateur=request.user)
    if facture is None:
        messages.info(request, "Aucun montant dû — facture non générée.")
    else:
        messages.success(request, f"Facture {facture.numero} émise ({facture.montant_total} F).")
    return redirect("finances:compte_eleve", inscription_pk=inscription.pk)


@login_required
@roles_requis(ROLES_COMPTA)
def facture_pdf(request, pk):
    """Rendu PDF d'une facture émise."""
    facture = get_object_or_404(
        Facture.objects.select_related("inscription__eleve", "inscription__classe"), pk=pk
    )
    from .services import montant_en_toutes_lettres
    inscription = facture.inscription
    tuteur = (
        inscription.eleve.tuteurs.filter(contact_urgence=True).first()
        or inscription.eleve.tuteurs.first()
    )
    from documents.pdf import reponse_pdf
    return reponse_pdf("finances/facture_pdf.html", {
        "facture": facture,
        "montant_lettres": montant_en_toutes_lettres(facture.montant_total),
        "tuteur": tuteur,
    }, f"facture_{facture.numero}")


@login_required
@roles_requis(ROLES_COMPTA)
def annuler_paiement_vue(request, pk):
    """Annulation d'un paiement avec motif (UC-34)."""
    paiement = get_object_or_404(Paiement, pk=pk)
    if request.method == "POST":
        motif = request.POST.get("motif", "").strip()
        if not motif:
            messages.error(request, "Le motif est obligatoire.")
        else:
            annuler_paiement(paiement, motif, utilisateur=request.user)
            messages.success(request, "Paiement annulé et imputations restaurées.")
            return redirect("finances:compte_eleve", inscription_pk=paiement.inscription.pk)
    return render(request, "finances/annuler_paiement.html", {"paiement": paiement})


@login_required
@roles_requis(ROLES_COMPTA)
def annuler_facture_vue(request, pk):
    """Annulation d'une facture (avoir) — UC-28."""
    facture = get_object_or_404(Facture, pk=pk)
    if request.method == "POST":
        motif = request.POST.get("motif", "").strip()
        annuler_facture(facture, motif or "Avoir sans motif", utilisateur=request.user)
        messages.success(request, f"Facture {facture.numero} annulée (avoir).")
        return redirect("finances:compte_eleve", inscription_pk=facture.inscription.pk)
    return render(request, "finances/annuler_facture.html", {"facture": facture})


@login_required
@roles_requis(ROLES_COMPTA)
def relance(request, inscription_pk):
    """Lettre de relance PDF pour un élève en retard (UC-30)."""
    inscription = get_object_or_404(
        Inscription.objects.select_related("eleve", "classe", "annee_scolaire"), pk=inscription_pk
    )
    impayees = list(inscription.echeances.exclude(statut=Echeance.Statut.PAYE).order_by("date_echeance"))
    if not impayees:
        messages.info(request, "Aucun impayé pour cet élève.")
        return redirect("finances:compte_eleve", inscription_pk=inscription.pk)

    tuteur = (
        inscription.eleve.tuteurs.filter(contact_urgence=True).first()
        or inscription.eleve.tuteurs.first()
    )
    solde = sum((e.solde for e in impayees), Decimal("0"))
    journaliser(request.user, "Lettre de relance", "Élève",
                f"Relance de paiement ({solde} F) pour {inscription.eleve}")

    from documents.pdf import reponse_pdf
    return reponse_pdf("finances/relance_pdf.html", {
        "inscription": inscription,
        "impayees": impayees,
        "solde": solde,
        "tuteur": tuteur,
        "aujourdhui": timezone.localdate(),
    }, f"relance_{inscription.eleve.matricule}")


@login_required
@roles_requis(ROLES_COMPTA)
def remises(request):
    """Gestion des remises / bourses (UC-33)."""
    if request.method == "POST":
        form = RemiseForm(request.POST)
        if form.is_valid():
            remise = form.save(commit=False)
            remise.accorde_par = request.user
            remise.save()
            journaliser(request.user, "Octroi de remise/bourse", "Remise",
                        f"{remise.get_type_remise_display()} de {remise.montant} F — {remise.inscription.eleve}")
            messages.success(request, "Remise enregistrée.")
            return redirect("finances:remises")
    else:
        form = RemiseForm()

    remises_objet = Remise.objects.select_related("inscription__eleve", "accorde_par").order_by("-date")
    return render(request, "finances/remises.html", {"form": form, "remises": remises_objet})


@login_required
@roles_requis(ROLES_COMPTA)
def etats_caisse(request):
    """États de caisse journaliers / mensuels exportables (UC-32)."""
    form = EtatCaisseForm(request.GET or None)
    paiements = Paiement.objects.filter(statut=Paiement.Statut.VALIDE)
    jour = request.GET.get("jour")
    if jour:
        paiements = paiements.filter(date_paiement__date=jour)
        total = paiements.aggregate(t=Sum("montant"))["t"] or Decimal("0")
        par_mode = list(
            paiements.values("mode_paiement")
            .annotate(total=Sum("montant"))
            .order_by("mode_paiement")
        )
        return render(request, "finances/etats_caisse.html", {
            "jour": jour, "total": total, "par_mode": par_mode, "form": form, "modele": dict(Paiement.ModePaiement.choices),
        })

    if form.is_valid():
        paiements = paiements.filter(
            date_paiement__date__gte=form.cleaned_data["date_debut"],
            date_paiement__date__lte=form.cleaned_data["date_fin"],
        )
        total = paiements.aggregate(t=Sum("montant"))["t"] or Decimal("0")
        par_mode = list(paiements.values("mode_paiement").annotate(total=Sum("montant")))
        contexte = {
            "form": form,
            "date_debut": form.cleaned_data["date_debut"],
            "date_fin": form.cleaned_data["date_fin"],
            "total": total,
            "par_mode": par_mode,
            "modele": dict(Paiement.ModePaiement.choices),
            "paiements": paiements.select_related("inscription__eleve", "encaisse_par").order_by("-date_paiement")[:200],
        }
        return render(request, "finances/etats_caisse.html", contexte)

    return render(request, "finances/etats_caisse.html", {"form": form})


@login_required
@roles_requis(ROLES_COMPTA)
def export_caisse(request):
    """Export Excel (openpyxl) des encaissements d'une période (UC-32, UC-41)."""
    import openpyxl
    from openpyxl.styles import Font

    jour = request.GET.get("jour")
    date_debut = request.GET.get("date_debut")
    date_fin = request.GET.get("date_fin")

    paiements = Paiement.objects.filter(statut=Paiement.Statut.VALIDE)
    if jour:
        paiements = paiements.filter(date_paiement__date=jour)
    elif date_debut and date_fin:
        paiements = paiements.filter(
            date_paiement__date__gte=date_debut, date_paiement__date__lte=date_fin
        )

    classeur = openpyxl.Workbook()
    feuille = classeur.active
    feuille.title = "État de caisse"
    entetes = ["Date", "Élève", "Matricule", "Montant", "Mode", "Référence", "Encaissé par"]
    feuille.append(entetes)
    for cellule in feuille[1]:
        cellule.font = Font(bold=True)

    for paiement in paiements.select_related("inscription__eleve", "encaisse_par").order_by("date_paiement"):
        feuille.append([
            paiement.date_paiement.strftime("%d/%m/%Y %H:%M"),
            str(paiement.inscription.eleve),
            paiement.inscription.eleve.matricule,
            float(paiement.montant),
            paiement.get_mode_paiement_display(),
            paiement.reference,
            str(paiement.encaisse_par or ""),
        ])

    total = paiements.aggregate(t=Sum("montant"))["t"] or Decimal("0")
    feuille.append([])
    feuille.append(["TOTAL", "", "", float(total), "", "", ""])

    reponse = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    reponse["Content-Disposition"] = 'attachment; filename="etat_caisse.xlsx"'
    classeur.save(reponse)
    return reponse


# ==============================================================================
# Endpoint HTMX : Chargement dynamique des échéances (Section 5 & 13)
# ==============================================================================

@login_required
@roles_requis(ROLES_COMPTA)
def charger_echeances(request):
    """Charge dynamiquement via HTMX les échéances dues de l'élève choisi."""
    inscription_id = request.GET.get("inscription")
    echeances = []
    situation = None

    if inscription_id:
        inscription = Inscription.objects.filter(pk=inscription_id).first()
        if inscription:
            from .services import situation_inscription
            situation = situation_inscription(inscription)
            echeances = (
                Echeance.objects.filter(inscription=inscription)
                .exclude(statut=Echeance.Statut.PAYE)
                .order_by("date_echeance")
            )

    return render(
        request,
        "finances/_echeances_options.html",
        {"echeances": echeances, "situation": situation},
    )


# ==============================================================================
# Comptabilité Générale en Partie Double (Section 13)
# ==============================================================================

@login_required
@roles_requis(ROLES_COMPTA)
def journal_comptable(request):
    """Journal des écritures comptables avec filtres et contrôles d'équilibre."""
    from .models import EcritureComptable, JournalComptable

    journaux = JournalComptable.objects.all()
    journal_id = request.GET.get("journal")
    statut = request.GET.get("statut")

    qs = (
        EcritureComptable.objects.prefetch_related("lignes__compte")
        .select_related("journal", "valide_par")
        .order_by("-date_piece", "-numero")
    )
    if journal_id:
        qs = qs.filter(journal_id=journal_id)
    if statut:
        qs = qs.filter(statut=statut)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "finances/journal_comptable.html",
        {
            "ecritures": page_obj,
            "journaux": journaux,
            "journal_selectionne": int(journal_id) if journal_id else None,
            "statut_selectionne": statut,
        },
    )


@login_required
@roles_requis(ROLES_COMPTA)
def grand_livre(request):
    """Grand livre des comptes avec solde progressif (Section 13.5)."""
    from .models import CompteComptable, LigneEcriture

    comptes = CompteComptable.objects.filter(actif=True).order_by("numero")
    compte_id = request.GET.get("compte")
    lignes = []
    compte_selectionne = None
    total_debit = Decimal("0")
    total_credit = Decimal("0")

    if compte_id:
        compte_selectionne = get_object_or_404(CompteComptable, pk=compte_id)
        lignes = (
            LigneEcriture.objects.filter(
                compte=compte_selectionne, ecriture__statut="VALIDEE"
            )
            .select_related("ecriture__journal")
            .order_by("ecriture__date_piece")
        )
        total_debit = sum((l.debit for l in lignes), Decimal("0"))
        total_credit = sum((l.credit for l in lignes), Decimal("0"))

    return render(
        request,
        "finances/grand_livre.html",
        {
            "comptes": comptes,
            "compte_selectionne": compte_selectionne,
            "lignes": lignes,
            "total_debit": total_debit,
            "total_credit": total_credit,
            "solde": total_debit - total_credit,
        },
    )


@login_required
@roles_requis(ROLES_COMPTA)
def balance_comptable(request):
    """Balance générale des comptes (Section 13.5)."""
    from .models import CompteComptable, LigneEcriture

    comptes = CompteComptable.objects.filter(actif=True).order_by("numero")
    lignes_balance = []
    cumul_debit = Decimal("0")
    cumul_credit = Decimal("0")

    for c in comptes:
        mouvements = LigneEcriture.objects.filter(compte=c, ecriture__statut="VALIDEE")
        d = mouvements.aggregate(s=Sum("debit"))["s"] or Decimal("0")
        cr = mouvements.aggregate(s=Sum("credit"))["s"] or Decimal("0")
        if d > 0 or cr > 0:
            solde = d - cr
            lignes_balance.append({
                "compte": c,
                "debit": d,
                "credit": cr,
                "solde_debiteur": solde if solde > 0 else Decimal("0"),
                "solde_crediteur": -solde if solde < 0 else Decimal("0"),
            })
            cumul_debit += d
            cumul_credit += cr

    return render(
        request,
        "finances/balance_comptable.html",
        {
            "lignes": lignes_balance,
            "cumul_debit": cumul_debit,
            "cumul_credit": cumul_credit,
        },
    )

