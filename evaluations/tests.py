from datetime import date
from decimal import Decimal

from django.test import TestCase

from eleves.models import Eleve, Inscription
from parametrage.models import (
    AnneeScolaire, Classe, ClasseMatiereCoefficient, Matiere, Niveau, Periode,
)

from .models import Evaluation, Note
from .services import calculer_moyennes, mention_pour, rangs_classe


class BaseEvaluationTest(TestCase):
    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            libelle="2026-2027",
            date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31),
            est_courante=True,
        )
        self.niveau = Niveau.objects.create(libelle="6ème", cycle="COLLEGE", ordre=1)
        self.classe = Classe.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee, libelle="6ème A"
        )
        self.maths = Matiere.objects.create(libelle="Mathématiques", niveau=self.niveau)
        self.francais = Matiere.objects.create(libelle="Français", niveau=self.niveau)
        # Le coefficient appartient au couple (matière, classe)
        ClasseMatiereCoefficient.objects.create(
            classe=self.classe, matiere=self.maths, coefficient=3
        )
        ClasseMatiereCoefficient.objects.create(
            classe=self.classe, matiere=self.francais, coefficient=2
        )
        self.periode = Periode.objects.create(
            annee_scolaire=self.annee, libelle="1er trimestre", ordre=1,
            date_debut=date(2026, 9, 1), date_fin=date(2026, 12, 20),
        )

    def _inscrire(self, nom, prenoms):
        eleve = Eleve.objects.create(
            nom=nom, prenoms=prenoms, sexe="M", date_naissance=date(2010, 1, 1)
        )
        return Inscription.objects.create(
            eleve=eleve, classe=self.classe, annee_scolaire=self.annee,
            statut_inscription="NOUVEAU",
        )

    def _note(self, inscription, matiere, valeur, coef_eval=1):
        evaluation = Evaluation.objects.create(
            matiere=matiere, classe=self.classe, periode=self.periode,
            type_evaluation="DEVOIR", coefficient=coef_eval, date=date(2026, 10, 5),
        )
        Note.objects.create(evaluation=evaluation, inscription=inscription, valeur=valeur)
        return evaluation


class CalculMoyennesTest(BaseEvaluationTest):
    """Calcul des moyennes pondérées (UC-22)."""

    def test_moyenne_ponderee_par_coefficient_d_evaluation(self):
        inscription = self._inscrire("Dupont", "Jean")
        # Maths : 12 (coef 1) et 16 (coef 2) -> (12+32)/3 = 14,67
        self._note(inscription, self.maths, 12, 1)
        self._note(inscription, self.maths, 16, 2)

        lignes, moyenne_generale = calculer_moyennes(inscription, self.periode)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]["moyenne"], Decimal("14.67"))
        self.assertEqual(lignes[0]["coef"], Decimal("3"))
        # moyenne générale = 14,67 × coef matière 3 / 3 = 14,67
        self.assertEqual(moyenne_generale, Decimal("14.67"))

    def test_moyenne_generale_ponderee_par_coefficient_matiere(self):
        inscription = self._inscrire("Dupont", "Jean")
        self._note(inscription, self.maths, 15, 1)       # coef matière 3
        self._note(inscription, self.francais, 10, 1)    # coef matière 2

        _, moyenne_generale = calculer_moyennes(inscription, self.periode)
        # (15×3 + 10×2) / 5 = 65/5 = 13,00
        self.assertEqual(moyenne_generale, Decimal("13.00"))

    def test_pas_de_note_pas_de_moyenne(self):
        inscription = self._inscrire("SansNote", "Ada")
        _, moyenne_generale = calculer_moyennes(inscription, self.periode)
        self.assertIsNone(moyenne_generale)


class MentionTest(BaseEvaluationTest):
    def test_mentions_selon_seuils(self):
        self.assertEqual(mention_pour(Decimal("9.50"), self.annee), "Insuffisant")
        self.assertEqual(mention_pour(Decimal("10.50"), self.annee), "Passable")
        self.assertEqual(mention_pour(Decimal("14.50"), self.annee), "Bien")
        self.assertEqual(mention_pour(Decimal("16.50"), self.annee), "Très bien")


class RangClasseTest(BaseEvaluationTest):
    def test_rang_dans_la_classe(self):
        insc1 = self._inscrire("Alpha", "A")
        insc2 = self._inscrire("Bravo", "B")
        self._note(insc1, self.maths, 18, 1)
        self._note(insc2, self.maths, 8, 1)

        rangs = rangs_classe(self.classe, self.periode)
        self.assertEqual(rangs[insc1.pk], 1)
        self.assertEqual(rangs[insc2.pk], 2)
