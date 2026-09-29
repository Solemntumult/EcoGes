from datetime import date

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from eleves.models import Eleve

from .services import assainir_html, html_en_paragraphes, remplacer_placeholders


class PlaceholdersTest(TestCase):
    """Remplacement des variables {{...}} dans le contenu des documents."""

    def test_remplacement_des_variables(self):
        contenu = "Bonjour {{ eleve_nom }} {{eleve_prenoms}}."
        resultat = remplacer_placeholders(contenu, {"eleve_nom": "DUPONT", "eleve_prenoms": "Jean"})
        self.assertEqual(resultat, "Bonjour DUPONT Jean.")

    def test_variable_inconnue_conservee(self):
        resultat = remplacer_placeholders("{{ inconnu }}", {})
        self.assertEqual(resultat, "{{ inconnu }}")

    def test_html_en_paragraphes(self):
        paragraphes = html_en_paragraphes(
            "<p>Premier <strong>paragraphe</strong>.</p><div>Deuxième.</div><p>Troisième.</p>"
        )
        self.assertEqual(paragraphes, ["Premier paragraphe.", "Deuxième.", "Troisième."])

    def test_assainissement_html(self):
        sale = '<p>Texte</p><script>alert(1)</script><img src=x onerror=alert(2)>'
        propre = assainir_html(sale)
        self.assertNotIn("<script", propre)
        self.assertNotIn("onerror", propre)
        self.assertIn("<p>Texte</p>", propre)

    def test_assainissement_conserve_le_contenu_legitime(self):
        propre = assainir_html("<p>Bonjour <strong>monde</strong>.</p>")
        self.assertEqual(propre, "<p>Bonjour <strong>monde</strong>.</p>")


class ExportEditeurTest(TestCase):
    """Exports PDF / Word / HTML depuis l'éditeur de documents."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="secre", password="mot-de-passe", role="SECRETARIAT"
        )
        self.eleve = Eleve.objects.create(
            nom="Dupont", prenoms="Jean", sexe="M", date_naissance=date(2010, 1, 1)
        )
        self.client.login(username="secre", password="mot-de-passe")

    def _exporter(self, format_export):
        return self.client.post(reverse("documents:exporter"), {
            "type_document": "CERTIFICAT_SCOLARITE",
            "eleve": str(self.eleve.pk),
            "contenu": "<p>Certificat de {{eleve_prenoms}} {{eleve_nom}}.</p>",
            "format": format_export,
        })

    def test_page_editeur(self):
        reponse = self.client.get(reverse("documents:editeur"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "apercu")

    def test_export_docx(self):
        reponse = self._exporter("docx")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(
            reponse["Content-Type"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertIn("attachment", reponse["Content-Disposition"])
        self.assertIn(".docx", reponse["Content-Disposition"])

    def test_export_html(self):
        reponse = self._exporter("html")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("text/html", reponse["Content-Type"])
        self.assertIn("Dupont", reponse.content.decode())

    def test_export_pdf_fallback(self):
        # Sans WeasyPrint, le PDF bascule sur un HTML téléchargeable (jamais d'erreur)
        reponse = self._exporter("pdf")
        self.assertEqual(reponse.status_code, 200)

    def test_acces_restreint(self):
        self.client.logout()
        reponse = self.client.get(reverse("documents:editeur"))
        self.assertRedirects(reponse, f"{reverse('connexion')}?next={reverse('documents:editeur')}")


class NumeroDocumentTest(TestCase):
    """Numérotation d'enregistrement des documents administratifs (anti-fraude)."""

    def test_numero_par_type_et_unique(self):
        from .models import DocumentAdministratif

        cer1 = DocumentAdministratif.objects.create(type_document="CERTIFICAT_SCOLARITE")
        cer2 = DocumentAdministratif.objects.create(type_document="CERTIFICAT_SCOLARITE")
        att = DocumentAdministratif.objects.create(type_document="ATTESTATION_REUSSITE")
        self.assertTrue(cer1.numero.startswith(f"CER-{date.today().year}-"))
        self.assertTrue(att.numero.startswith(f"ATT-{date.today().year}-"))
        self.assertNotEqual(cer1.numero, cer2.numero)
        self.assertNotEqual(cer1.numero, att.numero)


class InjectionEtablissementTest(TestCase):
    """L'identité de l'établissement est injectée dans tous les rendus PDF."""

    def test_contexte_pdf_contient_etablissement(self):
        from parametrage.models import Etablissement

        etab = Etablissement.obtenir()
        etab.nom_officiel = "Collège d'Essai"
        etab.ifu = "1234567890"
        etab.save()

        from .pdf import rendre_html

        html = rendre_html("documents/document_pdf.html", {
            "titre": "Test", "contenu": "<p>Contenu</p>",
            "infos": [], "date_jour": "12/08/2026", "en_tete_texte": "COLLEGE D'ESSAI",
        })
        # L'apostrophe est échappée en HTML (&#x27;) — on vérifie la présence du nom
        self.assertIn("Collège d", html)
        self.assertIn("Essai", html)

    def test_numero_affiche_sur_le_certificat(self):
        from eleves.models import Eleve
        from parametrage.models import Etablissement

        Etablissement.obtenir()
        eleve = Eleve.objects.create(
            nom="Dupont", prenoms="Jean", sexe="M", date_naissance=date(2010, 1, 1)
        )
        from .models import DocumentAdministratif
        from .services import generer_certificat_scolarite

        generer_certificat_scolarite(eleve)
        doc = DocumentAdministratif.objects.get(
            eleve=eleve, type_document="CERTIFICAT_SCOLARITE"
        )
        self.assertTrue(doc.numero.startswith("CER-"))

        # Le n° d'enregistrement figure bien dans le gabarit du certificat
        from .pdf import rendre_html
        html = rendre_html("documents/certificat_scolarite.html", {
            "eleve": eleve, "inscription": None, "modele": None, "doc": doc,
        })
        self.assertIn(doc.numero, html)


class EnvoiEmailTest(TestCase):
    """Envoi de documents par e-mail (éditeur + document archivé, UC-39)."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="secre", password="mot-de-passe", role="SECRETARIAT"
        )
        self.eleve = Eleve.objects.create(
            nom="Dupont", prenoms="Jean", sexe="M", date_naissance=date(2010, 1, 1)
        )
        self.eleve.tuteurs.create(
            nom_complet="Mère Dupont", lien_parente="MERE",
            telephone="+22990000000", email="mere@exemple.com", contact_urgence=True,
        )
        self.client.login(username="secre", password="mot-de-passe")

    def test_envoi_depuis_lediteur(self):
        reponse = self.client.post(reverse("documents:exporter"), {
            "type_document": "CERTIFICAT_SCOLARITE",
            "eleve": str(self.eleve.pk),
            "contenu": "<p>Certificat de {{eleve_prenoms}} {{eleve_nom}}.</p>",
            "format": "email",
            "destinataire": "mere@exemple.com",
        })
        self.assertRedirects(reponse, reverse("documents:editeur"))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["mere@exemple.com"])
        self.assertIn("Certificat de scolarité", message.subject)
        self.assertIn("ci-joint", message.body)
        self.assertEqual(len(message.attachments), 1)
        nom_piece, _, _ = message.attachments[0]
        self.assertTrue(nom_piece.startswith("document_certificat_scolarite_"))
        self.assertTrue(nom_piece.endswith(".pdf") or nom_piece.endswith(".html"))

    def test_envoi_adresse_invalide(self):
        reponse = self.client.post(reverse("documents:exporter"), {
            "type_document": "CERTIFICAT_SCOLARITE",
            "eleve": str(self.eleve.pk),
            "contenu": "<p>Test</p>",
            "format": "email",
            "destinataire": "pas-une-adresse",
        })
        self.assertRedirects(reponse, reverse("documents:editeur"))
        self.assertEqual(len(mail.outbox), 0)

    def test_echec_smtp_message_utilisateur(self):
        from unittest import mock

        import django.core.mail
        with mock.patch.object(django.core.mail.EmailMessage, "send", side_effect=OSError("connexion refusée")):
            reponse = self.client.post(reverse("documents:exporter"), {
                "type_document": "CERTIFICAT_SCOLARITE",
                "eleve": str(self.eleve.pk),
                "contenu": "<p>Test</p>",
                "format": "email",
                "destinataire": "mere@exemple.com",
            }, follow=True)
        # Pas de 500 : message d'erreur propre à l'utilisateur
        self.assertContains(reponse, "SMTP")
        self.assertEqual(len(mail.outbox), 0)

    def test_renvoi_document_archive(self):
        from .models import DocumentAdministratif
        doc = DocumentAdministratif.objects.create(
            type_document="CERTIFICAT_SCOLARITE", eleve=self.eleve, genere_par=self.utilisateur
        )
        reponse = self.client.post(reverse("documents:envoyer_existant"), {
            "document": str(doc.pk),
            "destinataire": "mere@exemple.com",
        })
        self.assertRedirects(reponse, reverse("documents:historique"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mere@exemple.com"])
        self.assertEqual(len(mail.outbox[0].attachments), 1)

    def test_renvoi_document_sans_eleve_echoue_gracieusement(self):
        from .models import DocumentAdministratif
        doc = DocumentAdministratif.objects.create(
            type_document="LISTE_CLASSE", eleve=None, genere_par=self.utilisateur
        )
        reponse = self.client.post(reverse("documents:envoyer_existant"), {
            "document": str(doc.pk),
            "destinataire": "mere@exemple.com",
        })
        self.assertRedirects(reponse, reverse("documents:historique"))
        # LISTE_CLASSE dispose d'un contenu par défaut : l'envoi fonctionne
        self.assertEqual(len(mail.outbox), 1)
