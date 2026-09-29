from datetime import date

from django.test import TestCase

from .models import Eleve, Tuteur


def _eleve(nom="Dupont", prenoms="Jean", sexe="M"):
    return Eleve.objects.create(
        nom=nom, prenoms=prenoms, sexe=sexe,
        date_naissance=date(2010, 5, 1),
    )


class MatriculeTest(TestCase):
    """Génération automatique du matricule (UC-16)."""

    def test_premier_matricule(self):
        eleve = _eleve()
        self.assertEqual(eleve.matricule, f"ELV-{eleve.date_creation.year}-00001")

    def test_matricules_sequentiels(self):
        eleve1 = _eleve()
        eleve2 = _eleve(nom="Martin", prenoms="Marie", sexe="F")
        self.assertNotEqual(eleve1.matricule, eleve2.matricule)
        numero2 = int(eleve2.matricule.split("-")[-1])
        numero1 = int(eleve1.matricule.split("-")[-1])
        self.assertEqual(numero2, numero1 + 1)

    def test_matricule_unique(self):
        e1 = _eleve()
        e2 = _eleve(nom="Autre")
        self.assertNotEqual(e1.matricule, e2.matricule)
        self.assertTrue(Eleve.objects.filter(matricule=e1.matricule).count() == 1)


class TuteurTest(TestCase):
    def test_creation_tuteur(self):
        eleve = _eleve()
        tuteur = Tuteur.objects.create(
            eleve=eleve, nom_complet="Marie Dupont", lien_parente="MERE",
            telephone="+229 90 00 00 00", contact_urgence=True,
        )
        self.assertEqual(eleve.tuteurs.count(), 1)
        self.assertTrue(tuteur.contact_urgence)
