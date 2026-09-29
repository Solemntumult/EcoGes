"""Services du module Documents : génération des documents administratifs.

Chaque fonction rend un gabarit HTML → PDF (WeasyPrint via documents.pdf),
trace le document dans DocumentAdministratif et journalise l'action.
"""

import html as _html
import re

from django.http import HttpResponse
from django.utils import timezone

from comptes.services import journaliser

from .models import DocumentAdministratif, ModeleDocument
from .pdf import PdvNonDisponible, pdf_bytes, rendre_html, reponse_pdf


class EnvoiEmailException(Exception):
    """Échec de l'envoi d'un e-mail (SMTP indisponible, identifiants invalides...)."""


# ---------------------------------------------------------------------------
# Éditeur de documents : placeholders, contenus par défaut, exports
# ---------------------------------------------------------------------------

# Contenus types (gabarits) modifiables dans l'éditeur — variables entre {{ }}.
CONTENUS_PAR_DEFAUT = {
    "CERTIFICAT_SCOLARITE": (
        "<p>Nous, soussignés, Directeur de l'établissement <strong>GESTION SCOLAIRE</strong>, certifions que l'élève "
        "<strong>{{eleve_prenoms}} {{eleve_nom}}</strong>, né(e) le {{eleve_date_naissance}} à {{eleve_lieu_naissance}}, "
        "matricule {{eleve_matricule}}, est régulièrement inscrit(e) en classe de <strong>{{eleve_classe}}</strong> "
        "pour l'année scolaire {{annee_scolaire}}.</p>"
        "<p>Le présent certificat est délivré à l'intéressé(e) pour servir et valoir ce que de droit.</p>"
    ),
    "ATTESTATION_REUSSITE": (
        "<p>Nous attestons que l'élève <strong>{{eleve_prenoms}} {{eleve_nom}}</strong> "
        "(matricule {{eleve_matricule}}), de la classe de {{eleve_classe}}, "
        "a validé le niveau d'études de l'année scolaire {{annee_scolaire}}.</p>"
        "<p>La présente attestation est délivrée pour servir et valoir ce que de droit.</p>"
    ),
    "RELEVE_NOTES": (
        "<p>Relevé de notes de l'élève <strong>{{eleve_prenoms}} {{eleve_nom}}</strong> "
        "({{eleve_matricule}}), classe de {{eleve_classe}}, année scolaire {{annee_scolaire}}.</p>"
        "<p>Moyenne générale : <strong>…</strong> — Mention : <strong>…</strong></p>"
    ),
    "LISTE_CLASSE": (
        "<p>Liste nominative des élèves de la classe <strong>{{eleve_classe}}</strong> "
        "pour l'année scolaire {{annee_scolaire}}.</p>"
    ),
    "CONVOCATION": (
        "<p>Madame, Monsieur,</p>"
        "<p>Nous vous prions de bien vouloir vous présenter à l'établissement concernant la scolarité de l'élève "
        "<strong>{{eleve_prenoms}} {{eleve_nom}}</strong> (classe de {{eleve_classe}}).</p>"
        "<p>Nous vous remercions de votre présence.</p>"
    ),
    "AVIS_RELANCE": (
        "<p>Madame, Monsieur,</p>"
        "<p>Le solde de la scolarité de l'élève <strong>{{eleve_prenoms}} {{eleve_nom}}</strong> "
        "({{eleve_matricule}}, classe de {{eleve_classe}}) reste dû pour l'année scolaire {{annee_scolaire}}.</p>"
        "<p>Nous vous remercions de bien vouloir régulariser votre situation dans les meilleurs délais.</p>"
    ),
    "CARTE_SCOLAIRE": (
        "<p><strong>{{eleve_prenoms}} {{eleve_nom}}</strong> — {{eleve_matricule}} — {{eleve_classe}} "
        "({{annee_scolaire}})</p>"
    ),
}

_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def assainir_html(html):
    """Retire scripts, styles, iframes et attributs on* d'un contenu édité.

    L'éditeur accepte du HTML libre (personnel de confiance), mais les
    documents sont exportés (HTML/PDF) vers des destinataires externes :
    on neutralise les vecteurs d'exécution (XSS) avant export.
    """
    html = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", html)
    html = re.sub(r"(?is)<style\b[^>]*>.*?</style>", "", html)
    html = re.sub(r"(?is)<(?:iframe|object|embed|link|meta)\b[^>]*>.*?</(?:iframe|object|embed)>", "", html)
    html = re.sub(r"(?is)<(?:iframe|object|embed|link|meta)\b[^>]*>", "", html)
    html = re.sub(r"(?is)\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", "", html)
    return html


def remplacer_placeholders(contenu, donnees):
    """Remplace les variables {{nom}} d'un contenu par les valeurs fournies.

    Les variables inconnues sont conservées telles quelles.
    """

    def _remplacer(match):
        cle = match.group(1)
        return str(donnees.get(cle, match.group(0)))

    return _PLACEHOLDER.sub(_remplacer, contenu)


def contexte_placeholders(eleve=None):
    """Données disponibles pour les variables d'un document (avec ou sans élève).

    Retourne (contexte, infos) où ``infos`` est une liste (libellé, valeur)
    utile pour l'export Word.
    """
    contexte = {
        "eleve_nom": "", "eleve_prenoms": "", "eleve_matricule": "",
        "eleve_sexe": "", "eleve_date_naissance": "", "eleve_lieu_naissance": "",
        "eleve_classe": "", "eleve_regime": "", "annee_scolaire": "",
        "tuteur_nom": "", "tuteur_email": "",
        "date_jour": timezone.localdate().strftime("%d/%m/%Y"),
    }

    if eleve is not None:
        contexte.update({
            "eleve_nom": eleve.nom,
            "eleve_prenoms": eleve.prenoms,
            "eleve_matricule": eleve.matricule,
            "eleve_sexe": eleve.get_sexe_display(),
            "eleve_date_naissance": eleve.date_naissance.strftime("%d/%m/%Y"),
            "eleve_lieu_naissance": eleve.lieu_naissance,
            "eleve_regime": eleve.get_regime_display(),
        })
        inscription = (
            eleve.inscriptions.filter(statut="ACTIVE")
            .select_related("classe", "annee_scolaire")
            .first()
        )
        if inscription:
            contexte["eleve_classe"] = inscription.classe.libelle
            contexte["annee_scolaire"] = str(inscription.annee_scolaire)
        tuteur = eleve.tuteurs.filter(contact_urgence=True).first() or eleve.tuteurs.first()
        if tuteur:
            contexte["tuteur_nom"] = tuteur.nom_complet
            contexte["tuteur_email"] = tuteur.email or ""

    infos = [
        ("Élève", f"{contexte['eleve_prenoms']} {contexte['eleve_nom']}".strip()),
        ("Matricule", contexte["eleve_matricule"]),
        ("Classe", contexte["eleve_classe"]),
        ("Année scolaire", contexte["annee_scolaire"]),
    ]
    return contexte, infos


def html_en_paragraphes(html):
    """Découpe un contenu HTML en paragraphes de texte brut (export Word)."""
    blocs = re.split(
        r"</?(?:p|div|h[1-6]|li|table|tr|td|br)\s*/?\s*>",
        html,
        flags=re.IGNORECASE,
    )
    paragraphes = []
    for bloc in blocs:
        texte = re.sub(r"<[^>]+>", "", bloc)  # retire les balises restantes (strong, em...)
        texte = _html.unescape(texte).strip()
        if texte:
            paragraphes.append(texte)
    return paragraphes


def exporter_docx(titre, contenu_html, infos, en_tete_texte="GESTION SCOLAIRE", nom_fichier="document"):
    """Génère un document Word (.docx) téléchargeable depuis un contenu HTML."""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    document = Document()
    en_tete = document.add_heading(en_tete_texte, level=0)
    en_tete.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.add_heading(titre, level=1)

    for label, valeur in infos:
        if valeur:
            document.add_paragraph(f"{label} : {valeur}")
    if any(v for _, v in infos):
        document.add_paragraph("")

    for paragraphe in html_en_paragraphes(contenu_html):
        document.add_paragraph(paragraphe)

    document.add_paragraph("")
    signature = document.add_paragraph(f"Fait le {timezone.localdate():%d/%m/%Y} — Le Directeur")
    signature.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    reponse = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    reponse["Content-Disposition"] = f'attachment; filename="{nom_fichier}.docx"'
    document.save(reponse)
    return reponse


def sujet_corps_document(titre, annee_scolaire=""):
    """Sujet et corps d'un e-mail d'envoi de document (partagé par les vues)."""
    sujet = f"{titre} — {annee_scolaire or 'Gestion Scolaire'}"
    corps = (
        "Bonjour,\n\nVeuillez trouver ci-joint le document : "
        f"{titre}.\n\nCordialement,\nL'administration."
    )
    return sujet, corps


def envoyer_document_par_email(
    destinataire, sujet, corps, contenu_html, infos, titre,
    en_tete="GESTION SCOLAIRE", nom_fichier="document", modele=None,
):
    """Génère le document (PDF, sinon HTML) et l'envoie en pièce jointe.

    Retourne l'extension du fichier envoyé ("pdf" ou "html") pour traçabilité.
    WeasyPrint absent → la version HTML du document est envoyée à la place.
    """
    from django.conf import settings
    from django.core.mail import EmailMessage

    contexte_rendu = {
        "titre": titre,
        "contenu": contenu_html,
        "infos": infos,
        "date_jour": timezone.localdate().strftime("%d/%m/%Y"),
        "modele": modele,
        "en_tete_texte": en_tete,
        "en_tete_personnalise": bool(modele and modele.en_tete_html),
    }
    try:
        piece = pdf_bytes("documents/document_pdf.html", contexte_rendu)
        extension, mime = "pdf", "application/pdf"
    except PdvNonDisponible:
        piece = rendre_html("documents/document_pdf.html", contexte_rendu).encode("utf-8")
        extension, mime = "html", "text/html"

    message = EmailMessage(sujet, corps, settings.DEFAULT_FROM_EMAIL, [destinataire])
    message.attach(f"{nom_fichier}.{extension}", piece, mime)
    try:
        message.send()
    except Exception as exc:  # SMTP down, identifiants invalides, réseau...
        raise EnvoiEmailException(str(exc)) from exc
    return extension


def en_tete_texte(modele):
    """En-tête du modèle converti en texte brut (pour l'export Word)."""
    if modele and modele.en_tete_html:
        return re.sub(r"<[^>]+>", "", modele.en_tete_html).strip() or "GESTION SCOLAIRE"
    return "GESTION SCOLAIRE"


# ---------------------------------------------------------------------------
# Générations existantes (certificat, attestation, liste, courrier)
# ---------------------------------------------------------------------------


def _gabarit(type_document):
    """Retourne le modèle personnalisable (en-tête/logo) ou None."""
    return ModeleDocument.objects.filter(type_document=type_document).first()


def generer_certificat_scolarite(eleve, utilisateur=None):
    """Certificat de scolarité (UC-35)."""
    inscription = eleve.inscriptions.filter(statut="ACTIVE").select_related("classe", "annee_scolaire").first()
    modele = _gabarit("CERTIFICAT_SCOLARITE")
    doc = DocumentAdministratif.objects.create(
        type_document="CERTIFICAT_SCOLARITE", eleve=eleve, genere_par=utilisateur
    )
    if utilisateur is not None:
        journaliser(utilisateur, "Certificat de scolarité", "Élève", str(eleve))
    return reponse_pdf(
        "documents/certificat_scolarite.html",
        {"eleve": eleve, "inscription": inscription, "modele": modele, "doc": doc},
        f"certificat_scolarite_{eleve.matricule}",
    )


def generer_attestation_reussite(eleve, utilisateur=None):
    """Attestation de réussite / de niveau (UC-36)."""
    from evaluations.services import generer_bulletin
    inscription = eleve.inscriptions.filter(statut="ACTIVE").select_related("classe", "annee_scolaire").first()
    bulletin_annuel = None
    if inscription:
        bulletin_annuel = generer_bulletin(inscription, est_annuel=True)
    modele = _gabarit("ATTESTATION_REUSSITE")
    doc = DocumentAdministratif.objects.create(
        type_document="ATTESTATION_REUSSITE", eleve=eleve, genere_par=utilisateur
    )
    if utilisateur is not None:
        journaliser(utilisateur, "Attestation de réussite", "Élève", str(eleve))
    return reponse_pdf(
        "documents/attestation.html",
        {"eleve": eleve, "inscription": inscription, "bulletin": bulletin_annuel,
         "modele": modele, "doc": doc},
        f"attestation_{eleve.matricule}",
    )


def generer_liste_classe(classe, sexe="", statut_paiement="", utilisateur=None):
    """Liste nominative de classe avec filtres (UC-37)."""
    from finances.models import Echeance

    inscriptions = (
        classe.inscriptions.filter(statut="ACTIVE")
        .select_related("eleve")
        .order_by("eleve__nom", "eleve__prenoms")
    )
    if sexe:
        inscriptions = inscriptions.filter(eleve__sexe=sexe)

    eleves_a_jour = set(
        Echeance.objects.exclude(statut=Echeance.Statut.PAYE)
        .filter(inscription__classe=classe)
        .values_list("inscription__eleve_id", flat=True)
    )
    lignes = []
    for inscription in inscriptions:
        en_impaye = inscription.eleve_id in eleves_a_jour
        if statut_paiement == "A_JOUR" and en_impaye:
            continue
        if statut_paiement == "IMPAYE" and not en_impaye:
            continue
        lignes.append((inscription.eleve, en_impaye))

    doc = DocumentAdministratif.objects.create(
        type_document="LISTE_CLASSE", eleve=None, genere_par=utilisateur
    )
    if utilisateur is not None:
        journaliser(utilisateur, "Liste de classe", "Classe",
                    f"{classe} — {len(lignes)} élève(s)")

    return reponse_pdf(
        "documents/liste_classe_pdf.html",
        {"classe": classe, "lignes": lignes, "doc": doc},
        f"liste_classe_{classe.pk}",
    )


def generer_courrier(inscription, type_courrier, motif="", utilisateur=None):
    """Courrier type (convocation, avertissement, mise en demeure) (UC-38)."""
    tuteur = (
        inscription.eleve.tuteurs.filter(contact_urgence=True).first()
        or inscription.eleve.tuteurs.first()
    )
    from finances.services import situation_inscription
    situation = situation_inscription(inscription)

    doc = DocumentAdministratif.objects.create(
        type_document="CONVOCATION", eleve=inscription.eleve, genere_par=utilisateur
    )
    if utilisateur is not None:
        journaliser(utilisateur, f"Courrier ({type_courrier})", "Élève", str(inscription.eleve))

    return reponse_pdf(
        "documents/courrier_pdf.html",
        {
            "inscription": inscription,
            "tuteur": tuteur,
            "type_courrier": type_courrier,
            "motif": motif,
            "situation": situation,
            "doc": doc,
        },
        f"courrier_{type_courrier.lower()}_{inscription.eleve.matricule}",
    )
