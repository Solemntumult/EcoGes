"""Tests du module Personnel : horaires, heures/rémunération, fiche de paie, éditeur d'EDT."""

from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from finances.models import FicheDePaie
from finances.services import annuler_fiche_paie, creer_fiche_paie, marquer_fiche_payee
from parametrage.models import (
    AnneeScolaire, Classe, HoraireJournalier, Matiere, Niveau, PauseHoraire,
)
from personnel.models import Affectation, CreneauEmploiDuTemps, Personnel
from personnel.services import detail_remuneration, heures_hebdo_affectation


class BasePersonnelTest(TestCase):
    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            libelle="2026-2027", date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31), est_courante=True,
        )
        self.niveau = Niveau.objects.create(libelle="6ème", cycle="COLLEGE", ordre=1)
        self.classe = Classe.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee, libelle="6ème A"
        )
        self.matiere = Matiere.objects.create(
            libelle="Mathématiques", niveau=self.niveau
        )
        self.enseignant = Personnel.objects.create(
            nom="HOUNSOU", prenoms="Koffi", fonction="ENSEIGNANT"
        )
        self.affectation = Affectation.objects.create(
            personnel=self.enseignant, classe=self.classe, matiere=self.matiere,
            annee_scolaire=self.annee, tarif_horaire=Decimal("4000"),
        )
        self.admin = Utilisateur.objects.create(
            username="admin_test", role="ADMIN", actif=True
        )
        self.admin.set_password("Admin123!")
        self.admin.save()


class HoraireSegmentsTest(TestCase):
    def test_decoupage_avec_pauses(self):
        horaire = HoraireJournalier.objects.create(
            libelle="Continu", actif=True,
            heure_debut_journee=time(7, 0), heure_fin_journee=time(15, 35),
        )
        PauseHoraire.objects.create(horaire=horaire, libelle="Récréation",
                                    heure_debut=time(10, 0), heure_fin=time(10, 15))
        PauseHoraire.objects.create(horaire=horaire, libelle="Déjeuner",
                                    heure_debut=time(12, 0), heure_fin=time(13, 0))
        attendus = [(time(7, 0), time(10, 0)), (time(10, 15), time(12, 0)),
                    (time(13, 0), time(15, 35))]
        self.assertEqual(horaire.segments(), attendus)

    def test_obtenir_actif(self):
        actif = HoraireJournalier.objects.create(
            libelle="A", actif=True,
            heure_debut_journee=time(7), heure_fin_journee=time(17),
        )
        HoraireJournalier.objects.create(
            libelle="B", actif=False,
            heure_debut_journee=time(8), heure_fin_journee=time(18),
        )
        self.assertEqual(HoraireJournalier.obtenir_actif(), actif)


class PlagesHorairesTest(TestCase):
    def test_plages_1h_dans_segments(self):
        horaire = HoraireJournalier.objects.create(
            libelle="Continu", actif=True,
            heure_debut_journee=time(7, 0), heure_fin_journee=time(15, 35),
        )
        PauseHoraire.objects.create(horaire=horaire, libelle="Récréation",
                                    heure_debut=time(10, 0), heure_fin=time(10, 15))
        PauseHoraire.objects.create(horaire=horaire, libelle="Déjeuner",
                                    heure_debut=time(12, 0), heure_fin=time(13, 0))
        attendus = [
            (time(7, 0), time(8, 0)), (time(8, 0), time(9, 0)), (time(9, 0), time(10, 0)),
            (time(10, 15), time(11, 15)), (time(11, 15), time(12, 0)),
            (time(13, 0), time(14, 0)), (time(14, 0), time(15, 0)), (time(15, 0), time(15, 35)),
        ]
        self.assertEqual(horaire.plages_horaires(), attendus)


class RemunerationTest(BasePersonnelTest):
    def test_heures_et_montants(self):
        CreneauEmploiDuTemps.objects.create(
            affectation=self.affectation, jour="LUN",
            heure_debut=time(7), heure_fin=time(8),
        )
        CreneauEmploiDuTemps.objects.create(
            affectation=self.affectation, jour="MAR",
            heure_debut=time(7), heure_fin=time(9),
        )
        self.assertEqual(heures_hebdo_affectation(self.affectation), Decimal("3.00"))
        detail = detail_remuneration(self.enseignant)
        self.assertEqual(detail["total_hebdo"], Decimal("3.00"))
        # 3 h × 4 000 F × 4,33
        self.assertEqual(detail["montant_mensuel"], Decimal("51960.00"))

    def test_sans_heures_pas_de_remuneration(self):
        detail = detail_remuneration(self.enseignant)
        self.assertEqual(detail["lignes"], [])
        self.assertEqual(detail["montant_mensuel"], Decimal("0.00"))


class FicheDePaieTest(BasePersonnelTest):
    def test_creation_et_idempotence(self):
        CreneauEmploiDuTemps.objects.create(
            affectation=self.affectation, jour="LUN",
            heure_debut=time(7), heure_fin=time(8),
        )
        fiche, creee = creer_fiche_paie(self.enseignant, mois=9, annee=2026)
        self.assertTrue(creee)
        self.assertEqual(fiche.montant_brut, Decimal("17320.00"))  # 1 h × 4 000 × 4,33
        self.assertEqual(fiche.heures_total, Decimal("4.33"))
        fiche2, creee2 = creer_fiche_paie(self.enseignant, mois=9, annee=2026)
        self.assertFalse(creee2)
        self.assertEqual(fiche2.pk, fiche.pk)

    def test_payer_puis_annuler_interdit(self):
        CreneauEmploiDuTemps.objects.create(
            affectation=self.affectation, jour="LUN",
            heure_debut=time(7), heure_fin=time(8),
        )
        fiche, _ = creer_fiche_paie(self.enseignant, mois=9, annee=2026)
        marquer_fiche_payee(fiche, "VIREMENT", date_paiement=date(2026, 10, 5))
        fiche.refresh_from_db()
        self.assertEqual(fiche.statut, FicheDePaie.Statut.PAYEE)
        self.assertEqual(fiche.date_paiement, date(2026, 10, 5))
        with self.assertRaises(ValueError):
            annuler_fiche_paie(fiche)


class EditeurGrilleTest(BasePersonnelTest):
    def setUp(self):
        super().setUp()
        HoraireJournalier.objects.create(
            libelle="Continu", actif=True,
            heure_debut_journee=time(7, 0), heure_fin_journee=time(15, 35),
        )
        PauseHoraire.objects.create(
            horaire=HoraireJournalier.obtenir_actif(), libelle="Récréation",
            heure_debut=time(10, 0), heure_fin=time(10, 15),
        )
        PauseHoraire.objects.create(
            horaire=HoraireJournalier.obtenir_actif(), libelle="Déjeuner",
            heure_debut=time(12, 0), heure_fin=time(13, 0),
        )
        # Créneaux horaires d'1 h : 07-08(0), 08-09(1), 09-10(2),
        # 10:15-11:15(3), 11:15-12:00(4), 13-14(5), 14-15(6), 15-15:35(7)
        self.client.login(username="admin_test", password="Admin123!")

    def test_creation_duree_2h_et_suppression(self):
        url = reverse("personnel:edt_classe", args=[self.classe.pk])
        reponse = self.client.post(url, {
            "cell_LUN_1": str(self.affectation.pk),
            "duree_LUN_1": "2",
            "salle_LUN_1": "Salle 5",
        })
        self.assertRedirects(reponse, url)
        creneau = CreneauEmploiDuTemps.objects.get(affectation=self.affectation, jour="LUN")
        self.assertEqual(creneau.heure_debut, time(8, 0))
        self.assertEqual(creneau.heure_fin, time(10, 0))  # 2 h : 08:00-10:00
        self.assertEqual(creneau.salle, "Salle 5")
        self.assertEqual(CreneauEmploiDuTemps.objects.count(), 1)

        # Ré-enregistrement identique : aucun doublon
        self.client.post(url, {
            "cell_LUN_1": str(self.affectation.pk),
            "duree_LUN_1": "2",
            "salle_LUN_1": "Salle 5",
        })
        self.assertEqual(CreneauEmploiDuTemps.objects.count(), 1)

        # Retrait : on vide la cellule de départ
        self.client.post(url, {"cell_LUN_1": "", "salle_LUN_1": ""})
        self.assertFalse(
            CreneauEmploiDuTemps.objects.filter(affectation=self.affectation).exists()
        )

    def test_duree_4h_occupe_plusieurs_colonnes(self):
        url = reverse("personnel:edt_classe", args=[self.classe.pk])
        self.client.post(url, {
            "cell_LUN_0": str(self.affectation.pk),
            "duree_LUN_0": "3",  # 07:00-10:00 (segment de 3 h)
            "salle_LUN_0": "",
        })
        creneau = CreneauEmploiDuTemps.objects.get(affectation=self.affectation)
        self.assertEqual(creneau.heure_debut, time(7, 0))
        self.assertEqual(creneau.heure_fin, time(10, 0))

    def test_duree_plafonnee_au_segment(self):
        """Une durée demandée de 5 h ne peut pas franchir la pause : limitée à 2 h
        dans le segment 10:15-12:00."""
        url = reverse("personnel:edt_classe", args=[self.classe.pk])
        self.client.post(url, {
            "cell_LUN_3": str(self.affectation.pk),
            "duree_LUN_3": "5",
            "salle_LUN_3": "",
        })
        creneau = CreneauEmploiDuTemps.objects.get(affectation=self.affectation)
        self.assertEqual(creneau.heure_debut, time(10, 15))
        self.assertEqual(creneau.heure_fin, time(12, 0))

    def test_chevauchement_entre_cours_proposes_refuse(self):
        """Deux cours proposés qui se chevauchent dans la même grille sont refusés."""
        autre_enseignant = Personnel.objects.create(
            nom="ADJAKOSSA", prenoms="Mireille", fonction="ENSEIGNANT"
        )
        autre_affectation = Affectation.objects.create(
            personnel=autre_enseignant, classe=self.classe, matiere=self.matiere,
            annee_scolaire=self.annee,
        )
        url = reverse("personnel:edt_classe", args=[self.classe.pk])
        reponse = self.client.post(url, {
            "cell_LUN_1": str(self.affectation.pk),
            "duree_LUN_1": "2",   # 08:00-10:00
            "cell_LUN_2": str(autre_affectation.pk),
            "duree_LUN_2": "1",   # 09:00-10:00 → chevauche
        })
        self.assertContains(reponse, "occupe déjà cet horaire")
        self.assertFalse(CreneauEmploiDuTemps.objects.exists())

    def test_remplacement_enseignant_dans_cellule(self):
        """Changer l'enseignant d'une cellule ne doit pas créer de faux conflit
        avec l'ancien créneau (qui est remplacé dans la même transaction)."""
        autre_enseignant = Personnel.objects.create(
            nom="ADJAKOSSA", prenoms="Mireille", fonction="ENSEIGNANT"
        )
        autre_affectation = Affectation.objects.create(
            personnel=autre_enseignant, classe=self.classe, matiere=self.matiere,
            annee_scolaire=self.annee,
        )
        CreneauEmploiDuTemps.objects.create(
            affectation=self.affectation, jour="LUN",
            heure_debut=time(7, 0), heure_fin=time(10, 0), salle="Salle 1",
        )
        url = reverse("personnel:edt_classe", args=[self.classe.pk])
        reponse = self.client.post(url, {
            "cell_LUN_0": str(autre_affectation.pk),
            "duree_LUN_0": "3",
            "salle_LUN_0": "Salle 1",
        })
        self.assertRedirects(reponse, url)
        self.assertEqual(CreneauEmploiDuTemps.objects.count(), 1)
        creneau = CreneauEmploiDuTemps.objects.get()
        self.assertEqual(creneau.affectation, autre_affectation)
        self.assertEqual(creneau.heure_debut, time(7, 0))
        self.assertEqual(creneau.heure_fin, time(10, 0))

    def test_conflit_enseignant_refuse(self):
        autre_classe = Classe.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee, libelle="6ème B"
        )
        autre_affectation = Affectation.objects.create(
            personnel=self.enseignant, classe=autre_classe, matiere=self.matiere,
            annee_scolaire=self.annee,
        )
        # L'enseignant est déjà occupé le lundi 07:00-10:00 dans l'autre classe
        CreneauEmploiDuTemps.objects.create(
            affectation=autre_affectation, jour="LUN",
            heure_debut=time(7, 0), heure_fin=time(10, 0),
        )
        url = reverse("personnel:edt_classe", args=[self.classe.pk])
        reponse = self.client.post(url, {
            "cell_LUN_0": str(self.affectation.pk),
            "duree_LUN_0": "3",
            "salle_LUN_0": "",
        })
        self.assertContains(reponse, "déjà en cours")
        self.assertFalse(
            CreneauEmploiDuTemps.objects.filter(affectation=self.affectation).exists()
        )


class ParametrageHoraireTest(TestCase):
    def setUp(self):
        self.admin = Utilisateur.objects.create(
            username="admin_param", role="ADMIN", actif=True
        )
        self.admin.set_password("Admin123!")
        self.admin.save()
        self.client.login(username="admin_param", password="Admin123!")

    def test_creation_horaire_avec_pauses(self):
        url = reverse("parametrage:horaire_creer")
        donnees = {
            "libelle": "Mode test", "actif": "on",
            "heure_debut_journee": "07:00", "heure_fin_journee": "15:35",
            "duree_creneau_base": "60", "affichage_cellule": "MATIERE_PROF",
            "pauses-TOTAL_FORMS": "2", "pauses-INITIAL_FORMS": "0",
            "pauses-MIN_NUM_FORMS": "0", "pauses-MAX_NUM_FORMS": "1000",
            "pauses-0-libelle": "Récréation", "pauses-0-heure_debut": "10:00",
            "pauses-0-heure_fin": "10:15",
            "pauses-1-libelle": "Déjeuner", "pauses-1-heure_debut": "12:00",
            "pauses-1-heure_fin": "13:00",
        }
        reponse = self.client.post(url, donnees)
        self.assertRedirects(reponse, reverse("parametrage:horaires"))
        horaire = HoraireJournalier.objects.get(libelle="Mode test")
        self.assertTrue(horaire.actif)
        self.assertEqual(horaire.pauses.count(), 2)


class PlagesHoraires45minTest(TestCase):
    """Vérification du découpage avec durée de créneau de base configurable."""

    def test_plages_45_min_sans_pause(self):
        horaire = HoraireJournalier.objects.create(
            libelle="45min", actif=True, duree_creneau_base=45,
            heure_debut_journee=time(7, 0), heure_fin_journee=time(10, 0),
        )
        plages = horaire.plages_horaires()
        attendus = [
            (time(7, 0), time(7, 45)),
            (time(7, 45), time(8, 30)),
            (time(8, 30), time(9, 15)),
            (time(9, 15), time(10, 0)),
        ]
        self.assertEqual(plages, attendus)

    def test_plages_45_min_avec_pause(self):
        horaire = HoraireJournalier.objects.create(
            libelle="45min+pause", actif=True, duree_creneau_base=45,
            heure_debut_journee=time(7, 0), heure_fin_journee=time(11, 0),
        )
        PauseHoraire.objects.create(
            horaire=horaire, libelle="Récréation",
            heure_debut=time(8, 30), heure_fin=time(8, 45),
        )
        plages = horaire.plages_horaires()
        # 7:00-8:30 → 2 créneaux de 45min (7:00-7:45, 7:45-8:30)
        # 8:45-11:00 → 3 créneaux (8:45-9:30, 9:30-10:15, 10:15-11:00)
        self.assertEqual(len(plages), 5)
        self.assertEqual(plages[0], (time(7, 0), time(7, 45)))
        self.assertEqual(plages[1], (time(7, 45), time(8, 30)))
        self.assertEqual(plages[2], (time(8, 45), time(9, 30)))
        self.assertEqual(plages[3], (time(9, 30), time(10, 15)))
        self.assertEqual(plages[4], (time(10, 15), time(11, 0)))

    def test_plages_55_min_dernier_creneau_tronque(self):
        """Le dernier créneau d'un segment peut être plus court que 55 min."""
        horaire = HoraireJournalier.objects.create(
            libelle="55min", actif=True, duree_creneau_base=55,
            heure_debut_journee=time(7, 0), heure_fin_journee=time(9, 0),
        )
        plages = horaire.plages_horaires()
        # 7:00-7:55, 7:55-8:50, 8:50-9:00 (10 min, tronqué)
        self.assertEqual(len(plages), 3)
        self.assertEqual(plages[2], (time(8, 50), time(9, 0)))


class SuiviQuotasTest(BasePersonnelTest):
    """Vérification du calcul des quotas horaires (heures planifiées vs quota)."""

    def test_suivi_quotas_sans_creneaux(self):
        from parametrage.models import QuotaHoraireMatiere
        from personnel.services import suivi_quotas

        QuotaHoraireMatiere.objects.create(
            matiere=self.matiere, classe=self.classe, heures_par_semaine=Decimal("4")
        )
        resultat = suivi_quotas(self.classe)
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[0]["matiere"], "Mathématiques")
        self.assertEqual(resultat[0]["heures_planifiees"], Decimal("0"))
        self.assertEqual(resultat[0]["quota"], Decimal("4"))
        self.assertFalse(resultat[0]["atteint"])

    def test_suivi_quotas_avec_creneaux(self):
        from parametrage.models import QuotaHoraireMatiere
        from personnel.services import suivi_quotas

        QuotaHoraireMatiere.objects.create(
            matiere=self.matiere, classe=self.classe, heures_par_semaine=Decimal("3")
        )
        CreneauEmploiDuTemps.objects.create(
            affectation=self.affectation, jour="LUN",
            heure_debut=time(7), heure_fin=time(9),  # 2h
        )
        CreneauEmploiDuTemps.objects.create(
            affectation=self.affectation, jour="MAR",
            heure_debut=time(7), heure_fin=time(8),  # 1h
        )
        resultat = suivi_quotas(self.classe)
        self.assertEqual(resultat[0]["heures_planifiees"], Decimal("3.00"))
        self.assertTrue(resultat[0]["atteint"])
        self.assertFalse(resultat[0]["depasse"])

    def test_suivi_quotas_depasse(self):
        from parametrage.models import QuotaHoraireMatiere
        from personnel.services import suivi_quotas

        QuotaHoraireMatiere.objects.create(
            matiere=self.matiere, classe=self.classe, heures_par_semaine=Decimal("2")
        )
        CreneauEmploiDuTemps.objects.create(
            affectation=self.affectation, jour="LUN",
            heure_debut=time(7), heure_fin=time(10),  # 3h > 2h quota
        )
        resultat = suivi_quotas(self.classe)
        self.assertTrue(resultat[0]["depasse"])


class ApiRechercheAffectationsTest(BasePersonnelTest):
    """Test de l'endpoint JSON de recherche d'affectations."""

    def test_recherche_par_terme(self):
        self.client.login(username="admin_test", password="Admin123!")
        url = reverse("personnel:api_recherche_affectations")
        reponse = self.client.get(url, {"classe": self.classe.pk, "q": "Math"})
        self.assertEqual(reponse.status_code, 200)
        data = reponse.json()
        self.assertEqual(len(data), 1)
        self.assertIn("Mathématiques", data[0]["matiere"])

    def test_recherche_sans_resultat(self):
        self.client.login(username="admin_test", password="Admin123!")
        url = reverse("personnel:api_recherche_affectations")
        reponse = self.client.get(url, {"classe": self.classe.pk, "q": "Zzzzz"})
        self.assertEqual(reponse.status_code, 200)
        data = reponse.json()
        self.assertEqual(len(data), 0)
