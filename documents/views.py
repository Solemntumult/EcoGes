"""Vues du module Documents administratifs (UC-35 à UC-39)."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.validators import ValidationError, validate_email
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from comptes.mixins import roles_requis
from eleves.models import Eleve

from .forms import CourrierForm, DocumentEleveForm, ListeClasseForm
from .models import DocumentAdministratif, ModeleDocument
from .pdf import rendre_html, reponse_pdf
from .services import (
    CONTENUS_PAR_DEFAUT,
    EnvoiEmailException,
    assainir_html,
    contexte_placeholders,
    en_tete_texte,
    envoyer_document_par_email,
    exporter_docx,
    generer_attestation_reussite,
    generer_certificat_scolarite,
    generer_courrier,
    generer_liste_classe,
    remplacer_placeholders,
    sujet_corps_document,
)

ROLES_DOCS = ["ADMIN", "SUPERADMIN", "SECRETARIAT", "CENSEUR", "COMPTABLE"]


@login_required
@roles_requis(ROLES_DOCS)
def accueil(request):
    """Page d'accueil : génération de documents et historique récent."""
    form = DocumentEleveForm()
    historique = DocumentAdministratif.objects.select_related("eleve", "genere_par")[:10]
    return render(request, "documents/accueil.html", {"form": form, "historique": historique})


@login_required
@roles_requis(ROLES_DOCS)
def generer(request):
    """Génère un document à la demande pour un élève (UC-35, UC-36, UC-16)."""
    from eleves.models import Eleve

    form = DocumentEleveForm(request.POST or None)
    if not form.is_valid():
        messages.error(request, "Sélection invalide.")
        return redirect("documents:accueil")

    eleve = form.cleaned_data["eleve"]
    type_document = form.cleaned_data["type_document"]

    if type_document == "CERTIFICAT_SCOLARITE":
        return generer_certificat_scolarite(eleve, utilisateur=request.user)
    if type_document == "ATTESTATION_REUSSITE":
        return generer_attestation_reussite(eleve, utilisateur=request.user)
    if type_document == "CARTE_SCOLAIRE":
        from eleves.views import carte_scolaire
        return carte_scolaire(request, eleve.pk)
    if type_document == "RELEVE_NOTES":
        inscription = eleve.inscriptions.filter(statut="ACTIVE").first()
        if inscription:
            return redirect("evaluations:releve_annuel", pk=inscription.pk)
        messages.error(request, "Aucune inscription active pour cet élève.")
        return redirect("documents:accueil")

    messages.error(request, "Type de document non pris en charge ici.")
    return redirect("documents:accueil")


@login_required
@roles_requis(ROLES_DOCS)
def pour_eleve(request, pk):
    """Formulaire de génération pré-rempli pour un élève donné."""
    from eleves.models import Eleve
    eleve = get_object_or_404(Eleve, pk=pk)
    form = DocumentEleveForm(initial={"eleve": eleve.pk})
    historique = eleve.documents.select_related("genere_par").order_by("-date_generation")
    return render(request, "documents/accueil.html", {
        "form": form,
        "historique": historique,
        "eleve_cible": eleve,
    })


@login_required
@roles_requis(ROLES_DOCS)
def liste_classe(request):
    """Liste de classe avec filtres (UC-37)."""
    form = ListeClasseForm(request.POST or request.GET or None)
    if request.method == "POST" and form.is_valid():
        classe = form.cleaned_data["classe"]
        return generer_liste_classe(
            classe,
            sexe=form.cleaned_data.get("sexe", ""),
            statut_paiement=form.cleaned_data.get("statut_paiement", ""),
            utilisateur=request.user,
        )
    return render(request, "documents/liste_classe_form.html", {"form": form})


@login_required
@roles_requis(ROLES_DOCS)
def courrier(request):
    """Courriers types (UC-38)."""
    form = CourrierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        return generer_courrier(
            form.cleaned_data["inscription"],
            form.cleaned_data["type_courrier"],
            motif=form.cleaned_data.get("motif", ""),
            utilisateur=request.user,
        )
    return render(request, "documents/courrier_form.html", {"form": form})


@login_required
@roles_requis(ROLES_DOCS)
def editeur(request):
    """Éditeur de documents : édition à gauche, aperçu temps réel à droite."""
    type_initial = request.GET.get("type_document", "CERTIFICAT_SCOLARITE")
    eleve_id = request.GET.get("eleve", "")
    eleve = Eleve.objects.filter(pk=eleve_id).first() if eleve_id else None

    contexte, _ = contexte_placeholders(eleve)
    modele = ModeleDocument.objects.filter(type_document=type_initial).first()
    from parametrage.services import contexte_etablissement
    from parametrage.models import Etablissement
    etab = Etablissement.obtenir()
    ctx_etab = contexte_etablissement()

    return render(request, "documents/editeur.html", {
        "types": ModeleDocument.TypeDocument.choices,
        "eleves": Eleve.objects.order_by("nom", "prenoms"),
        "type_initial": type_initial,
        "eleve_selectionne": eleve_id,
        "contenu_initial": CONTENUS_PAR_DEFAUT.get(type_initial, ""),
        "donnees_json": json.dumps(contexte, ensure_ascii=False),
        "destinataire_initial": contexte.get("tuteur_email", ""),
        "titres_json": json.dumps(dict(ModeleDocument.TypeDocument.choices), ensure_ascii=False),
        "mentions_json": json.dumps((modele.mentions_legales if modele else "") or "", ensure_ascii=False),
        "en_tete_json": json.dumps(en_tete_texte(modele), ensure_ascii=False),
        "etab_json": json.dumps({
            "nom_officiel": etab.nom_officiel,
            "sigle": etab.sigle,
            "logos": ctx_etab["logos_entete"],
            "logo_url": ctx_etab["logo_principal"],
        }, ensure_ascii=False),
        "variables_aide": "{{eleve_nom}}, {{eleve_prenoms}}, {{eleve_matricule}}, {{eleve_date_naissance}}, "
                          "{{eleve_lieu_naissance}}, {{eleve_classe}}, {{eleve_regime}}, {{annee_scolaire}}, {{date_jour}}",
    })


@login_required
@roles_requis(ROLES_DOCS)
def exporter(request):
    """Export du document édité : PDF, Word (.docx) ou HTML."""
    if request.method != "POST":
        return redirect("documents:editeur")

    types_valides = dict(ModeleDocument.TypeDocument.choices)
    type_document = request.POST.get("type_document", "")
    if type_document not in types_valides:
        messages.error(request, "Type de document invalide.")
        return redirect("documents:editeur")

    format_export = request.POST.get("format", "pdf")
    if format_export not in ("pdf", "docx", "html", "email"):
        format_export = "pdf"
    eleve_id = request.POST.get("eleve", "")
    contenu = request.POST.get("contenu", "")

    eleve = Eleve.objects.filter(pk=eleve_id).first() if eleve_id else None
    contexte, infos = contexte_placeholders(eleve)
    # Neutralisation des scripts/attributs on* avant diffusion externe
    contenu_final = assainir_html(remplacer_placeholders(contenu, contexte))

    titre = types_valides[type_document]
    modele = ModeleDocument.objects.filter(type_document=type_document).first()
    en_tete = en_tete_texte(modele)

    nom_fichier = f"document_{type_document.lower()}"
    if eleve:
        nom_fichier += f"_{eleve.matricule}"

    if format_export == "email":
        destinataire = request.POST.get("destinataire", "").strip()
        try:
            validate_email(destinataire)
        except ValidationError:
            messages.error(request, "Adresse e-mail du destinataire invalide.")
            return redirect("documents:editeur")
        sujet, corps = sujet_corps_document(titre, contexte.get("annee_scolaire"))
        try:
            extension = envoyer_document_par_email(
                destinataire, sujet, corps,
                contenu_final, infos, titre, en_tete, nom_fichier, modele,
            )
        except EnvoiEmailException:
            messages.error(request, "L'envoi de l'e-mail a échoué (serveur SMTP ou identifiants invalides). Vérifiez la configuration dans le fichier .env.")
            return redirect("documents:editeur")
        if eleve:
            DocumentAdministratif.objects.create(
                type_document=type_document, eleve=eleve, genere_par=request.user
            )
        from comptes.services import journaliser
        journaliser(request.user, "Envoi de document", "Document",
                    f"{titre} envoyé par e-mail à {destinataire} (pièce jointe {extension.upper()})")
        messages.success(request, f"Document envoyé à {destinataire} (pièce jointe {extension.upper()}).")
        return redirect("documents:editeur")

    contexte_rendu = {
        "titre": titre,
        "contenu": contenu_final,
        "infos": infos,
        "date_jour": contexte["date_jour"],
        "modele": modele,
        "en_tete_texte": en_tete,
        "en_tete_personnalise": bool(modele and modele.en_tete_html),
    }

    if format_export == "docx":
        return exporter_docx(titre, contenu_final, infos, en_tete, nom_fichier)

    if format_export == "html":
        html = rendre_html("documents/document_pdf.html", contexte_rendu)
        reponse = HttpResponse(html, content_type="text/html; charset=utf-8")
        reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}.html"'
        return reponse

    # PDF — archivage du document émis (avant rendu pour afficher son n° d'enregistrement)
    doc = None
    if eleve:
        doc = DocumentAdministratif.objects.create(
            type_document=type_document, eleve=eleve, genere_par=request.user
        )
    contexte_rendu["doc"] = doc
    from comptes.services import journaliser
    journaliser(request.user, "Édition de document", "Document",
                f"{titre} exporté en PDF{(' — ' + eleve.matricule) if eleve else ''}")
    return reponse_pdf("documents/document_pdf.html", contexte_rendu, nom_fichier)


@login_required
@roles_requis(ROLES_DOCS)
def envoyer_existant(request):
    """Régénère un document archivé et l'envoie par e-mail (UC-39)."""
    if request.method != "POST":
        return redirect("documents:historique")

    doc = get_object_or_404(DocumentAdministratif, pk=request.POST.get("document"))
    destinataire = request.POST.get("destinataire", "").strip()
    try:
        validate_email(destinataire)
    except ValidationError:
        messages.error(request, "Adresse e-mail du destinataire invalide.")
        return redirect("documents:historique")

    contenu = CONTENUS_PAR_DEFAUT.get(doc.type_document)
    if not contenu:
        messages.error(request, "Ce type de document ne peut pas être renvoyé par e-mail.")
        return redirect("documents:historique")

    contexte, infos = contexte_placeholders(doc.eleve)
    contenu_final = assainir_html(remplacer_placeholders(contenu, contexte))
    titre = dict(ModeleDocument.TypeDocument.choices).get(doc.type_document, doc.type_document)
    modele = ModeleDocument.objects.filter(type_document=doc.type_document).first()
    nom_fichier = f"document_{doc.type_document.lower()}"
    if doc.eleve:
        nom_fichier += f"_{doc.eleve.matricule}"

    sujet, corps = sujet_corps_document(titre, contexte.get("annee_scolaire"))
    try:
        extension = envoyer_document_par_email(
            destinataire, sujet, corps,
            contenu_final, infos, titre, en_tete_texte(modele), nom_fichier, modele,
        )
    except EnvoiEmailException:
        messages.error(request, "L'envoi de l'e-mail a échoué (serveur SMTP ou identifiants invalides). Vérifiez la configuration dans le fichier .env.")
        return redirect("documents:historique")
    from comptes.services import journaliser
    journaliser(request.user, "Envoi de document", "Document",
                f"{titre} renvoyé à {destinataire} (pièce jointe {extension.upper()})")
    messages.success(request, f"Document renvoyé à {destinataire} (pièce jointe {extension.upper()}).")
    return redirect("documents:historique")


@login_required
@roles_requis(ROLES_DOCS)
def historique(request):
    """Historique des documents émis (UC-35 à UC-39)."""
    qs = DocumentAdministratif.objects.select_related("eleve", "genere_par").order_by("-date_generation")
    type_document = request.GET.get("type_document", "")
    if type_document:
        qs = qs.filter(type_document=type_document)
    paginator = Paginator(qs, 25)
    return render(request, "documents/historique.html", {
        "documents": paginator.get_page(request.GET.get("page")),
        "types": DocumentAdministratif._meta.get_field("type_document").choices,
        "type_document": type_document,
    })
