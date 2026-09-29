"""Test de parcours intégré : connexion → inscription → paiement → pages clés.

Valide l'enchaînement des cas d'utilisation principaux ainsi que le rendu
des gabarits métier.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from finances.models import Echeance, Paiement, Recu
from parametrage.models import (
    AnneeScolaire,
    BaremeEvaluation,
    Classe,
    ClasseMatiereCoefficient,
    GrilleTarifaire,
    Matiere,
    Niveau,
    Periode,
    TypeFrais,
)

from .models import Eleve, Inscription


class ParcoursCompletTest(TestCase):
    def setUp(self):
        # Paramétrage de base (UC-06 à UC-10)
        self.annee = AnneeScolaire.objects.create(
            libelle="2026-2027", date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31), est_courante=True,
        )
        BaremeEvaluation.objects.create(annee_scolaire=self.annee)
        self.niveau = Niveau.objects.create(libelle="6ème", cycle="COLLEGE", ordre=1)
        self.classe = Classe.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee, libelle="6ème A"
        )
        self.maths = Matiere.objects.create(libelle="Mathématiques", niveau=self.niveau)
        ClasseMatiereCoefficient.objects.create(
            classe=self.classe, matiere=self.maths, coefficient=3
        )
        self.periode = Periode.objects.create(
            annee_scolaire=self.annee, libelle="1er trimestre", ordre=1,
            date_debut=date(2026, 9, 1), date_fin=date(2026, 12, 20),
        )
        TypeFrais.objects.create(libelle="Inscription")
        self.frais_scolarite = TypeFrais.objects.create(libelle="Scolarité")
        GrilleTarifaire.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee,
            type_frais=self.frais_scolarite, montant=Decimal("60000"),
        )

        # Utilisateurs par rôle
        self.secretariat = Utilisateur.objects.create_user(
            username="secre", password="mot-de-passe", role="SECRETARIAT",
        )
        self.comptable = Utilisateur.objects.create_user(
            username="caissier", password="mot-de-passe", role="COMPTABLE",
        )

    def _inscrire_eleve(self):
        """Inscription complète via le formulaire (UC-11) + échéancier auto."""
        self.client.login(username="secre", password="mot-de-passe")
        donnees = {
            "nom": "Dupont", "prenoms": "Jean", "sexe": "M",
            "date_naissance": "2010-05-01", "lieu_naissance": "Cotonou",
            "regime": "EXTERNE", "adresse": "Cotonou",
            "classe": self.classe.pk, "statut_inscription": "NOUVEAU",
            "tuteurs-TOTAL_FORMS": "1", "tuteurs-INITIAL_FORMS": "0",
            "tuteurs-MIN_NUM_FORMS": "0", "tuteurs-MAX_NUM_FORMS": "1000",
            "tuteurs-0-nom_complet": "Marie Dupont", "tuteurs-0-lien_parente": "MERE",
            "tuteurs-0-telephone": "+22990000000", "tuteurs-0-contact_urgence": "on",
        }
        reponse = self.client.post(reverse("eleves:creation"), donnees)
        self.assertEqual(reponse.status_code, 302)
        eleve = Eleve.objects.get(nom="Dupont")
        self.assertTrue(eleve.matricule.startswith("ELV-"))
        inscription = Inscription.objects.get(eleve=eleve)
        self.assertEqual(inscription.echeances.count(), 1)
        return eleve, inscription

    def test_parcours_inscription_et_paiement(self):
        eleve, inscription = self._inscrire_eleve()

        # Dossier élève consolidé (UC-15)
        reponse = self.client.get(reverse("eleves:detail", args=[eleve.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, eleve.matricule)

        # Encaissement FIFO par la comptabilité (UC-27, UC-29)
        self.client.logout()
        self.client.login(username="caissier", password="mot-de-passe")
        reponse = self.client.post(reverse("finances:encaisser"), {
            "inscription": inscription.pk,
            "montant": "25000", "mode_paiement": "MOBILE_MONEY",
            "reference": "TX-123", "imputation_manuelle": "",
        })
        self.assertEqual(reponse.status_code, 302)

        paiement = Paiement.objects.get(inscription=inscription)
        self.assertEqual(paiement.montant, Decimal("25000"))
        self.assertTrue(Recu.objects.filter(paiement=paiement).exists())
        echeance = Echeance.objects.get(inscription=inscription)
        self.assertEqual(echeance.montant_paye, Decimal("25000"))
        self.assertEqual(echeance.statut, Echeance.Statut.PARTIEL)

        # Reçu PDF (fallback HTML si WeasyPrint absent)
        recu = Recu.objects.get(paiement=paiement)
        reponse = self.client.get(reverse("finances:recu", args=[recu.pk]))
        self.assertEqual(reponse.status_code, 200)

        # Pages clés rendues sans erreur (accès comptable)
        for url_name in ["finances:impayes", "finances:etats_caisse", "finances:compte_eleve"]:
            args = [inscription.pk] if url_name.endswith("compte_eleve") else []
            reponse = self.client.get(reverse(url_name, args=args))
            self.assertEqual(reponse.status_code, 200, f"{url_name} a échoué")

        # Tableau de bord (comptable)
        reponse = self.client.get(reverse("accueil"))
        self.assertEqual(reponse.status_code, 200)

    def test_pages_principales_roles(self):
        self.client.login(username="secre", password="mot-de-passe")
        for url_name in [
            "eleves:liste", "eleves:creation", "eleves:reinscription",
            "documents:accueil", "documents:liste_classe", "documents:courrier",
            "personnel:liste", "personnel:edt_par_classe",
            "evaluations:bulletins_classe",
        ]:
            reponse = self.client.get(reverse(url_name))
            self.assertEqual(reponse.status_code, 200, f"{url_name} a échoué")

        self.client.logout()
        self.client.login(username="caissier", password="mot-de-passe")
        for url_name in ["finances:impayes", "finances:encaisser", "finances:remises"]:
            reponse = self.client.get(reverse(url_name))
            self.assertEqual(reponse.status_code, 200, f"{url_name} a échoué")

    def test_acces_refuse_par_role(self):
        # Un comptable ne doit pas accéder à la gestion des élèves
        self.client.login(username="caissier", password="mot-de-passe")
        reponse = self.client.get(reverse("eleves:liste"))
        self.assertEqual(reponse.status_code, 403)

        # Un comptable ne doit pas voir le journal
        reponse = self.client.get(reverse("journal"))
        self.assertEqual(reponse.status_code, 403)
