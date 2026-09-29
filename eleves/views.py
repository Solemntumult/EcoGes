"""Vues du module Élèves (UC-11 à UC-16)."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from comptes.mixins import roles_requis
from comptes.services import journaliser
from parametrage.models import AnneeScolaire, Classe

from .forms import (
    EleveForm,
    InscriptionForm,
    RechercheEleveForm,
    ReinscriptionMasseForm,
    TransfertForm,
    TuteurFormSet,
)
from .models import Eleve, Inscription
from .services import classe_suggeree, reinscrire

ROLES_ADMIN = ["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT"]


@login_required
@roles_requis(ROLES_ADMIN)
def liste(request):
    """Liste + recherche multicritère des élèves (UC-15)."""
    qs = Eleve.objects.prefetch_related("inscriptions__classe").all().order_by("nom", "prenoms")
    form = RechercheEleveForm(request.GET or None)

    if form.is_valid():
        nom = form.cleaned_data["nom"]
        matricule = form.cleaned_data["matricule"]
        classe = form.cleaned_data["classe"]
        statut = form.cleaned_data["statut"]
        if nom:
            qs = qs.filter(Q(nom__icontains=nom) | Q(prenoms__icontains=nom))
        if matricule:
            qs = qs.filter(matricule__icontains=matricule)
        if statut:
            qs = qs.filter(statut=statut)
        if classe:
            qs = qs.filter(inscriptions__classe=classe, inscriptions__statut="ACTIVE").distinct()

    paginator = Paginator(qs, 25)
    contexte = {
        "eleves": paginator.get_page(request.GET.get("page")),
        "form": form,
    }
    return render(request, "eleves/liste.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def creation(request):
    """Inscription d'un nouvel élève + tuteurs + échéancier (UC-11)."""
    annee_courante = AnneeScolaire.objects.filter(est_courante=True).first()
    if annee_courante is None:
        messages.warning(request, "Aucune année scolaire n'est définie comme courante. "
                                  "Paramétrez d'abord l'année scolaire dans l'administration.")
        return redirect("eleves:liste")

    if request.method == "POST":
        form_eleve = EleveForm(request.POST, request.FILES)
        form_inscription = InscriptionForm(request.POST)
        formset_tuteurs = TuteurFormSet(request.POST)

        if form_eleve.is_valid() and form_inscription.is_valid() and formset_tuteurs.is_valid():
            with transaction.atomic():
                eleve = form_eleve.save()
                formset_tuteurs.instance = eleve
                formset_tuteurs.save()
                inscription = Inscription.objects.create(
                    eleve=eleve,
                    classe=form_inscription.cleaned_data["classe"],
                    annee_scolaire=annee_courante,
                    statut_inscription=form_inscription.cleaned_data["statut_inscription"],
                )
                from finances.services import generer_echeancier
                generer_echeancier(inscription)
            journaliser(
                request.user, "Inscription", "Élève",
                f"{eleve} inscrit en {inscription.classe} ({annee_courante}) — "
                f"échéancier généré automatiquement.",
            )
            messages.success(request, f"Élève {eleve.matricule} inscrit avec succès. "
                                      f"L'échéancier de scolarité a été généré.")
            return redirect("eleves:detail", pk=eleve.pk)
    else:
        form_eleve = EleveForm()
        form_inscription = InscriptionForm()
        formset_tuteurs = TuteurFormSet()

    contexte = {
        "form_eleve": form_eleve,
        "form_inscription": form_inscription,
        "formset_tuteurs": formset_tuteurs,
        "annee_courante": annee_courante,
    }
    return render(request, "eleves/creation.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def detail(request, pk):
    """Dossier élève consolidé (UC-15) : scolarité + finances + documents."""
    eleve = get_object_or_404(
        Eleve.objects.prefetch_related("tuteurs", "documents"),
        pk=pk,
    )
    inscriptions = eleve.inscriptions.select_related("classe__niveau", "annee_scolaire").all()
    inscription_courante = inscriptions.filter(statut="ACTIVE").first()

    notes = []
    bulletins = []
    situation = None
    echeances = []
    paiements = []
    factures = []
    remises = []

    if inscription_courante:
        from evaluations.models import Bulletin, Note
        notes = Note.objects.filter(inscription=inscription_courante).select_related(
            "evaluation__matiere", "evaluation__periode"
        )
        bulletins = Bulletin.objects.filter(inscription=inscription_courante)
        from finances.models import Echeance as ModEcheance
        echeances = ModEcheance.objects.filter(inscription=inscription_courante).order_by("date_echeance")
        paiements = inscription_courante.paiements.select_related("recu").order_by("-date_paiement")
        factures = inscription_courante.factures.all()
        remises = inscription_courante.remises.all()
        from finances.services import situation_inscription
        situation = situation_inscription(inscription_courante)

    total_du = sum((e.montant_du for e in echeances), Decimal("0"))

    contexte = {
        "eleve": eleve,
        "inscriptions": inscriptions,
        "inscription_courante": inscription_courante,
        "notes": notes,
        "bulletins": bulletins,
        "echeances": echeances,
        "paiements": paiements,
        "factures": factures,
        "remises": remises,
        "situation": situation,
        "total_du": total_du,
    }
    return render(request, "eleves/detail.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def modifier(request, pk):
    """Mise à jour du dossier (infos perso + tuteurs) (UC-13)."""
    eleve = get_object_or_404(Eleve, pk=pk)
    if request.method == "POST":
        form_eleve = EleveForm(request.POST, request.FILES, instance=eleve)
        formset_tuteurs = TuteurFormSet(request.POST, instance=eleve)
        if form_eleve.is_valid() and formset_tuteurs.is_valid():
            form_eleve.save()
            formset_tuteurs.save()
            journaliser(request.user, "Modification du dossier", "Élève", str(eleve))
            messages.success(request, "Dossier mis à jour.")
            return redirect("eleves:detail", pk=eleve.pk)
    else:
        form_eleve = EleveForm(instance=eleve)
        formset_tuteurs = TuteurFormSet(instance=eleve)
    contexte = {"form_eleve": form_eleve, "formset_tuteurs": formset_tuteurs, "eleve": eleve}
    return render(request, "eleves/modifier.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def transferer(request, pk):
    """Transfert / radiation avec archivage (UC-14)."""
    eleve = get_object_or_404(Eleve, pk=pk)
    if request.method == "POST":
        form = TransfertForm(request.POST)
        if form.is_valid():
            nouveau_statut = form.cleaned_data["nouveau_statut"]
            motif = form.cleaned_data["motif"]
            eleve.statut = nouveau_statut
            eleve.save(update_fields=["statut"])
            # Archivage : clôture des inscriptions actives
            Inscription.objects.filter(eleve=eleve, statut="ACTIVE").update(statut="TERMINEE")
            journaliser(
                request.user,
                f"{'Transfert' if nouveau_statut == 'TRANSFERE' else 'Radiation'}",
                "Élève",
                f"{eleve} — motif : {motif}",
            )
            messages.success(request, f"{eleve} a été archivé (statut « {eleve.get_statut_display()} »).")
            return redirect("eleves:detail", pk=eleve.pk)
    else:
        form = TransfertForm()
    contexte = {"form": form, "eleve": eleve}
    return render(request, "eleves/transferer.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def reinscription_masse(request):
    """Réinscription en masse par classe avec passage suggéré (UC-12)."""
    annee_cible = None
    classe_source = None
    eleves_a_reinscrire = []

    if "classe_source" in request.GET:
        form = ReinscriptionMasseForm(request.GET)
        if form.is_valid():
            annee_cible = form.cleaned_data["annee_cible"]
            classe_source = form.cleaned_data["classe_source"]
            inscriptions = Inscription.objects.filter(
                classe=classe_source, statut="ACTIVE", annee_scolaire__est_courante=True
            ).select_related("eleve")
            eleves_a_reinscrire = [
                {
                    "inscription": ins,
                    "suggeree": classe_suggeree(ins, annee_cible),
                }
                for ins in inscriptions
                if not Inscription.objects.filter(eleve=ins.eleve, annee_scolaire=annee_cible).exists()
            ]
    else:
        form = ReinscriptionMasseForm()

    if request.method == "POST" and request.POST.get("confirmer"):
        eleve_ids = request.POST.getlist("eleves")
        compteur = 0
        for eleve_id in eleve_ids:
            classe_id = request.POST.get(f"classe_{eleve_id}")
            if not classe_id:
                continue
            eleve = Eleve.objects.filter(pk=eleve_id).first()
            classe = Classe.objects.filter(pk=classe_id, annee_scolaire_id=request.POST.get("annee_cible")).first()
            if eleve and classe:
                if reinscrire(eleve, classe, classe.annee_scolaire, "ANCIEN", request.user):
                    compteur += 1
        messages.success(request, f"{compteur} élève(s) réinscrit(s) avec succès.")
        return redirect("eleves:liste")

    contexte = {
        "form": form,
        "annee_cible": annee_cible,
        "classe_source": classe_source,
        "eleves_a_reinscrire": eleves_a_reinscrire,
    }
    return render(request, "eleves/reinscription.html", contexte)


@login_required
@roles_requis(ROLES_ADMIN)
def carte_scolaire(request, pk):
    """Génération de la carte scolaire PDF avec QR code (UC-16)."""
    eleve = get_object_or_404(Eleve, pk=pk)
    inscription = eleve.inscriptions.filter(statut="ACTIVE").first()
    contexte = {"eleve": eleve, "inscription": inscription}

    from documents.pdf import qr_data_uri, reponse_pdf
    contexte["qr_code"] = qr_data_uri(f"{eleve.matricule}|{eleve.nom} {eleve.prenoms}")
    contexte["photo_data_uri"] = eleve.photo_data_uri()

    from documents.models import DocumentAdministratif
    doc = DocumentAdministratif.objects.create(
        type_document="CARTE_SCOLAIRE", eleve=eleve, genere_par=request.user
    )
    contexte["doc"] = doc
    journaliser(request.user, "Édition de carte scolaire", "Élève", str(eleve))
    return reponse_pdf("documents/carte_scolaire.html", contexte, f"carte_scolaire_{eleve.matricule}")
