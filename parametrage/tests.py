"""Tests du module Paramétrage : établissement (configuration unique des documents)."""

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from comptes.models import Utilisateur

from .models import (
    AnneeScolaire,
    Classe,
    ClasseMatiereCoefficient,
    Etablissement,
    LogoEtablissement,
    Matiere,
    Niveau,
    Serie,
)
from .services import coefficient_matiere_classe, contexte_etablissement


def _petit_png():
    """Un vrai petit PNG valide (Pillow) pour les tests de fichiers image."""
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (8, 8), "#1d4ed8").save(buf, format="PNG")
    return buf.getvalue()


class EtablissementTest(TestCase):
    def test_singleton_obtenir(self):
        etab1 = Etablissement.obtenir()
        etab2 = Etablissement.obtenir()
        self.assertEqual(etab1.pk, 1)
        self.assertEqual(etab1.pk, etab2.pk)
        self.assertEqual(Etablissement.objects.count(), 1)

    def test_vue_etablissement_enregistre_les_donnees(self):
        utilisateur = Utilisateur.objects.create_user(
            username="admin", password="Admin123!", role="ADMIN"
        )
        self.client.login(username="admin", password="Admin123!")
        url = reverse("parametrage:etablissement")

        reponse = self.client.get(url)
        self.assertEqual(reponse.status_code, 200)

        reponse = self.client.post(url, {
            "nom_officiel": "Collège de Test",
            "sigle": "CT",
            "pays": "Bénin",
            "ville": "Cotonou",
            "ifu": "4202301234567",
            "nom_directeur": "M. Jean BOKO",
            "statut_juridique": "PRIVE_LAIC",
            "categorie": "COLLEGE",
        })
        self.assertRedirects(reponse, url)
        etab = Etablissement.obtenir()
        self.assertEqual(etab.nom_officiel, "Collège de Test")
        self.assertEqual(etab.ifu, "4202301234567")

    def test_acces_restreint(self):
        reponse = self.client.get(reverse("parametrage:etablissement"))
        self.assertEqual(reponse.status_code, 302)


class LogoEtablissementTest(TestCase):
    def test_logos_multiples_et_contexte_data_uri(self):
        etab = Etablissement.obtenir()
        for ordre, libelle in ((1, "Logo de la République"), (2, "Logo du collège")):
            logo = LogoEtablissement.objects.create(
                etablissement=etab, libelle=libelle, ordre=ordre, en_tete=True
            )
            logo.image.save(f"logo_test_{ordre}.png", ContentFile(_petit_png()), save=True)
        # Un logo désactivé pour l'en-tête n'apparaît pas
        LogoEtablissement.objects.create(
            etablissement=etab, libelle="Logo interne", ordre=3, en_tete=False
        )

        self.assertEqual(etab.logos.count(), 3)
        self.assertEqual([l.libelle for l in etab.logos_en_tete],
                         ["Logo de la République", "Logo du collège"])

        ctx = contexte_etablissement()
        self.assertEqual(len(ctx["logos_entete"]), 2)
        for logo in ctx["logos_entete"]:
            self.assertTrue(logo["data_uri"].startswith("data:image/png;base64,"))

    def test_vue_etablissement_enregistre_les_logos(self):
        utilisateur = Utilisateur.objects.create_user(
            username="admin_logo", password="Admin123!", role="ADMIN"
        )
        self.client.login(username="admin_logo", password="Admin123!")
        url = reverse("parametrage:etablissement")
        etab = Etablissement.obtenir()

        reponse = self.client.post(url, {
            "nom_officiel": etab.nom_officiel,
            "pays": etab.pays,
            "statut_juridique": etab.statut_juridique,
            "categorie": etab.categorie,
            # formset des logos
            "logos-TOTAL_FORMS": "1", "logos-INITIAL_FORMS": "0",
            "logos-MIN_NUM_FORMS": "0", "logos-MAX_NUM_FORMS": "1000",
            "logos-0-libelle": "Logo du collège", "logos-0-ordre": "1",
            "logos-0-en_tete": "on",
            "logos-0-image": SimpleUploadedFile("logo.png", _petit_png(), content_type="image/png"),
        })
        self.assertRedirects(reponse, url)
        self.assertEqual(etab.logos.count(), 1)
        self.assertEqual(etab.logos.first().libelle, "Logo du collège")


class GestionnaireMatieresTest(TestCase):
    """Coefficient (matière, classe) : modèle, helper et CRUD du gestionnaire."""

    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            libelle="2026-2027", date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31), est_courante=True,
        )
        self.serie_d = Serie.objects.create(code="D", libelle="Biologie-Géologie")
        self.sixieme = Niveau.objects.create(libelle="6ème", cycle="COLLEGE", ordre=1)
        self.seconde_d = Niveau.objects.create(
            libelle="2nde", cycle="LYCEE", ordre=5, serie=self.serie_d
        )
        self.terminale_d = Niveau.objects.create(
            libelle="Terminale", cycle="LYCEE", ordre=7, serie=self.serie_d
        )
        self.classe_6a = Classe.objects.create(
            niveau=self.sixieme, annee_scolaire=self.annee, libelle="6ème A"
        )
        self.classe_2d = Classe.objects.create(
            niveau=self.seconde_d, annee_scolaire=self.annee, libelle="2nde D"
        )
        self.classe_td = Classe.objects.create(
            niveau=self.terminale_d, annee_scolaire=self.annee, libelle="Terminale D"
        )
        self.maths_6e = Matiere.objects.create(libelle="Mathématiques", niveau=self.sixieme)
        self.maths_2nde = Matiere.objects.create(libelle="Mathématiques", niveau=self.seconde_d)
        self.maths_term = Matiere.objects.create(libelle="Mathématiques", niveau=self.terminale_d)
        self.admin = Utilisateur.objects.create_user(
            username="admin_mat", password="Admin123!", role="ADMIN"
        )
        self.client.login(username="admin_mat", password="Admin123!")

    def test_coefficient_appartient_au_couple(self):
        """La même matière peut avoir un coefficient différent par classe,
        même au sein d'une même série (2nde D ≠ Terminale D)."""
        ClasseMatiereCoefficient.objects.create(classe=self.classe_2d, matiere=self.maths_2nde, coefficient=4)
        ClasseMatiereCoefficient.objects.create(classe=self.classe_td, matiere=self.maths_term, coefficient=5)
        self.assertEqual(coefficient_matiere_classe(self.classe_2d, self.maths_2nde), Decimal("4"))
        self.assertEqual(coefficient_matiere_classe(self.classe_td, self.maths_term), Decimal("5"))
        # Aucune liaison : défaut 1 (jamais de coefficient porté par la matière)
        self.assertFalse(hasattr(self.maths_2nde, "coefficient"))
        self.assertEqual(coefficient_matiere_classe(self.classe_6a, self.maths_6e), Decimal("1"))

    def test_classe_creee_lie_les_matieres_tronc_commun(self):
        """À la création d'une classe, les matières tronc commun du niveau sont liées."""
        self.maths_6e.tronc_commun = True
        self.maths_6e.save(update_fields=["tronc_commun"])
        # le signal lie la matière aux classes déjà existantes du niveau
        self.assertTrue(
            ClasseMatiereCoefficient.objects.filter(classe=self.classe_6a, matiere=self.maths_6e).exists()
        )

        # nouvelle classe du même niveau → maths_6e (tronc commun) liée automatiquement
        classe_6b = Classe.objects.create(
            niveau=self.sixieme, annee_scolaire=self.annee, libelle="6ème B"
        )
        self.assertTrue(
            ClasseMatiereCoefficient.objects.filter(classe=classe_6b, matiere=self.maths_6e).exists()
        )

        # une matière non tronc commun n'est jamais liée automatiquement
        non_tronc = Matiere.objects.create(libelle="Éducation Physique", niveau=self.sixieme)
        self.assertFalse(
            ClasseMatiereCoefficient.objects.filter(classe=classe_6b, matiere=non_tronc).exists()
        )

    def test_matiere_tronc_commun_liee_aux_classes_existantes(self):
        """Une matière tronc commun créée est liée à toutes les classes du niveau (pas aux autres)."""
        matiere = Matiere.objects.create(
            libelle="SVT", niveau=self.sixieme, tronc_commun=True
        )
        self.assertTrue(
            ClasseMatiereCoefficient.objects.filter(classe=self.classe_6a, matiere=matiere).exists()
        )
        self.assertFalse(
            ClasseMatiereCoefficient.objects.filter(classe=self.classe_2d, matiere=matiere).exists()
        )

    def test_basculer_tronc_commun_depuis_interface(self):
        """Le bouton tronc commun lie la matière aux classes du niveau, et la
        désactivation conserve les liaisons existantes."""
        url = reverse("parametrage:basculer_tronc_commun", args=[self.maths_6e.pk])
        reponse = self.client.post(url)
        self.assertRedirects(
            reponse, reverse("parametrage:matieres"), fetch_redirect_response=False
        )
        self.maths_6e.refresh_from_db()
        self.assertTrue(self.maths_6e.tronc_commun)
        self.assertTrue(
            ClasseMatiereCoefficient.objects.filter(classe=self.classe_6a, matiere=self.maths_6e).exists()
        )

        # désactivation : les liaisons déjà créées sont conservées
        self.client.post(url)
        self.maths_6e.refresh_from_db()
        self.assertFalse(self.maths_6e.tronc_commun)
        self.assertTrue(
            ClasseMatiereCoefficient.objects.filter(classe=self.classe_6a, matiere=self.maths_6e).exists()
        )

    def test_unicite_classe_matiere(self):
        ClasseMatiereCoefficient.objects.create(classe=self.classe_6a, matiere=self.maths_6e, coefficient=3)
        with self.assertRaises(Exception):
            ClasseMatiereCoefficient.objects.create(
                classe=self.classe_6a, matiere=self.maths_6e, coefficient=2
            )

    def test_vues_crud_ajout_modification_retrait(self):
        # Ajout d'une matière à une classe (1er cycle)
        url_ajout = reverse("parametrage:ajouter_matiere_classe", args=[self.classe_6a.pk])
        reponse = self.client.post(url_ajout, {
            "matiere": str(self.maths_6e.pk), "libelle": "", "coefficient": "3",
        })
        self.assertRedirects(reponse, reverse("parametrage:classe_matieres", args=[self.classe_6a.pk]))
        cmc = ClasseMatiereCoefficient.objects.get(classe=self.classe_6a, matiere=self.maths_6e)
        self.assertEqual(cmc.coefficient, Decimal("3"))

        # Création d'une nouvelle matière directement pour une classe
        reponse = self.client.post(url_ajout, {
            "matiere": "", "libelle": "Éducation Physique", "coefficient": "1",
        })
        self.assertEqual(reponse.status_code, 302)
        ep = Matiere.objects.get(libelle="Éducation Physique", niveau=self.sixieme)
        self.assertTrue(ClasseMatiereCoefficient.objects.filter(classe=self.classe_6a, matiere=ep).exists())

        # Modification du coefficient (sans effet de bord sur les autres classes)
        ClasseMatiereCoefficient.objects.create(classe=self.classe_2d, matiere=self.maths_2nde, coefficient=4)
        url_modif = reverse("parametrage:modifier_coefficient", args=[self.classe_2d.pk, self.maths_2nde.pk])
        self.client.post(url_modif, {"coefficient": "6"})
        cmc.refresh_from_db()
        self.assertEqual(cmc.coefficient, Decimal("3"))  # la classe 6e n'est pas touchée
        cmc_2d = ClasseMatiereCoefficient.objects.get(classe=self.classe_2d, matiere=self.maths_2nde)
        self.assertEqual(cmc_2d.coefficient, Decimal("6"))

        # Retrait de la liaison
        url_retrait = reverse("parametrage:retirer_matiere_classe", args=[self.classe_2d.pk, self.maths_2nde.pk])
        self.client.post(url_retrait)
        self.assertFalse(
            ClasseMatiereCoefficient.objects.filter(classe=self.classe_2d, matiere=self.maths_2nde).exists()
        )

    def test_vue_controle_par_classe(self):
        ClasseMatiereCoefficient.objects.create(classe=self.classe_6a, matiere=self.maths_6e, coefficient=3)
        reponse = self.client.get(reverse("parametrage:classe_matieres", args=[self.classe_6a.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Mathématiques")
        self.assertContains(reponse, "3")

        reponse = self.client.get(reverse("parametrage:matieres"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "2nde")
        self.assertContains(reponse, "Biologie-Géologie")  # série D affichée

    def test_coefficient_hors_plage_refuse_avec_message(self):
        """Un coefficient hors plage (0,5-20) est refusé AVEC un message (pas d'échec silencieux)."""
        url_ajout = reverse("parametrage:ajouter_matiere_classe", args=[self.classe_6a.pk])
        reponse = self.client.post(url_ajout, {
            "matiere": str(self.maths_6e.pk), "libelle": "", "coefficient": "25",
        })
        self.assertRedirects(
            reponse, reverse("parametrage:classe_matieres", args=[self.classe_6a.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(
            ClasseMatiereCoefficient.objects.filter(classe=self.classe_6a, matiere=self.maths_6e).exists()
        )
        reponse = self.client.get(reverse("parametrage:classe_matieres", args=[self.classe_6a.pk]))
        self.assertContains(reponse, "ne peut pas dépasser 20")

    def test_niveau_lycee_sans_serie_refuse(self):
        """Un niveau du second cycle doit avoir une série."""
        url = reverse("parametrage:matieres")
        reponse = self.client.post(url, {
            "creer_niveau": "1", "libelle": "1ère", "cycle": "LYCEE", "serie": "",
        })
        self.assertRedirects(reponse, url, fetch_redirect_response=False)
        # Aucun nouveau niveau Lycée sans série créé (celui du setUp a une série)
        self.assertFalse(
            Niveau.objects.filter(libelle="1ère", cycle="LYCEE", serie__isnull=True).exists()
        )
        reponse = self.client.get(url)
        self.assertContains(reponse, "doit avoir une série")

    def test_acces_restreint(self):
        self.client.logout()
        self.client.login(username="admin_mat", password="Admin123!")
        # SECRETARIAT n'a pas accès
        from comptes.models import Utilisateur
        secre = Utilisateur.objects.create_user(
            username="secre_mat", password="secre123!", role="SECRETARIAT"
        )
        self.client.logout()
        self.client.login(username="secre_mat", password="secre123!")
        reponse = self.client.get(reverse("parametrage:matieres"))
        self.assertEqual(reponse.status_code, 403)
