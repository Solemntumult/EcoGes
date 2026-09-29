from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from .models import JournalActivite, Utilisateur


class VerrouillageCompteTest(TestCase):
    """Verrouillage après tentatives de connexion échouées (UC-02)."""

    def setUp(self):
        self.utilisateur = Utilisateur.objects.create_user(
            username="secretariat", password="mot-de-passe-solide"
        )

    def test_connexion_reussie_journalise(self):
        reponse = self.client.post(reverse("connexion"), {
            "username": "secretariat", "password": "mot-de-passe-solide",
        })
        self.assertRedirects(reponse, reverse("eleves:liste"))
        self.assertTrue(JournalActivite.objects.filter(action="Connexion").exists())

    def test_verrouillage_apres_tentatives_repetees(self):
        for _ in range(settings.VERROUILLAGE_TENTATIVES):
            self.client.post(reverse("connexion"), {
                "username": "secretariat", "password": "mauvais",
            })
        self.utilisateur.refresh_from_db()
        self.assertIsNotNone(self.utilisateur.bloque_jusqua)
        self.assertTrue(self.utilisateur.est_bloque)

        # Même avec le bon mot de passe, le compte reste bloqué
        reponse = self.client.post(reverse("connexion"), {
            "username": "secretariat", "password": "mot-de-passe-solide",
        })
        self.assertEqual(reponse.status_code, 200)
        self.utilisateur.refresh_from_db()
        self.assertTrue(self.utilisateur.est_bloque)

    def test_deconnexion(self):
        self.client.login(username="secretariat", password="mot-de-passe-solide")
        reponse = self.client.post(reverse("deconnexion"))
        self.assertRedirects(reponse, reverse("connexion"))


class CommandeCreerDemoTest(TestCase):
    """Le jeu de données de démonstration se construit intégralement."""

    def test_creer_demo(self):
        from django.core.management import call_command

        from eleves.models import Eleve, Inscription
        from evaluations.models import Bulletin, Evaluation, Note
        from finances.models import Echeance, Paiement, Recu
        from parametrage.models import AnneeScolaire, Classe

        call_command("creer_demo", eleves=3)

        self.assertTrue(AnneeScolaire.objects.filter(est_courante=True).exists())
        # 5 classes du premier cycle + 3 classes du second cycle (série D)
        self.assertEqual(Classe.objects.count(), 8)
        self.assertEqual(Eleve.objects.count(), 24)  # 8 classes × 3 élèves
        self.assertEqual(Inscription.objects.count(), 24)
        self.assertTrue(Echeance.objects.exists())          # échéanciers générés
        self.assertTrue(Evaluation.objects.exists())
        self.assertTrue(Note.objects.count() > 0)
        self.assertTrue(Bulletin.objects.exists())          # bulletins calculés
        self.assertTrue(Paiement.objects.exists())
        self.assertTrue(Recu.objects.exists())

        # Scénarios financiers variés : au moins un élève totalement payé
        # et au moins un élève en impayé (aucun paiement)
        inscrits = list(Inscription.objects.all())
        self.assertTrue(any(not i.paiements.exists() for i in inscrits))
        self.assertTrue(any(i.paiements.exists() for i in inscrits))

    def test_creer_demo_idempotent_sans_reset(self):
        from django.core.management import call_command

        from eleves.models import Eleve

        call_command("creer_demo", eleves=3)
        nombre = Eleve.objects.count()
        call_command("creer_demo", eleves=3)  # ne doit pas dupliquer
        self.assertEqual(Eleve.objects.count(), nombre)

    def test_creer_demo_reset_reconstruit_sans_doublon(self):
        from django.core.management import CommandError, call_command

        from eleves.models import Eleve, Inscription
        from personnel.models import CreneauEmploiDuTemps

        call_command("creer_demo", eleves=3)
        premier_passage = Eleve.objects.count()

        # --reset sans --yes en non-interactif → refus (aucune suppression)
        with self.assertRaises((CommandError, SystemExit)):
            call_command("creer_demo", reset=True)
        self.assertEqual(Eleve.objects.count(), premier_passage)

        call_command("creer_demo", reset=True, yes=True, eleves=3)
        self.assertEqual(Eleve.objects.count(), premier_passage)
        self.assertEqual(Inscription.objects.count(), premier_passage)
        # L'emploi du temps n'a aucun conflit d'horaires pour un même enseignant
        creneaux = list(
            CreneauEmploiDuTemps.objects.values_list(
                "affectation__personnel_id", "jour", "heure_debut"
            )
        )
        self.assertEqual(len(creneaux), len(set(creneaux)))


class SuperutilisateurAccesTotalTest(TestCase):
    """Un superuser Django accède à tout, même avec un rôle métier restreint."""

    def setUp(self):
        # createsuperuser laisse `role` à sa valeur par défaut (SECRETARIAT)
        self.superuser = Utilisateur.objects.create_superuser(
            username="racine", password="mot-de-passe-solide", role="SECRETARIAT"
        )
        self.client.login(username="racine", password="mot-de-passe-solide")

    def test_acces_statistiques_et_journal(self):
        reponse = self.client.get(reverse("statistiques:dashboard"))
        self.assertEqual(reponse.status_code, 200)
        reponse = self.client.get(reverse("journal"))
        self.assertEqual(reponse.status_code, 200)

    def test_redirection_accueil(self):
        from .services import redirection_apres_connexion
        self.assertEqual(redirection_apres_connexion(self.superuser), reverse("accueil"))
