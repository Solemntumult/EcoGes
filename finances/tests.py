from datetime import date
from decimal import Decimal

from django.test import TestCase

from eleves.models import Eleve, Inscription
from parametrage.models import AnneeScolaire, Classe, GrilleTarifaire, Niveau, TypeFrais

from .models import Echeance, Facture, Paiement, Recu
from .services import (
    annuler_paiement,
    generer_echeancier,
    generer_facture,
    generer_recu,
    imputer_paiement,
)


class BaseFinanceTest(TestCase):
    def setUp(self):
        self.annee = AnneeScolaire.objects.create(
            libelle="2026-2027", date_debut=date(2026, 9, 1),
            date_fin=date(2027, 7, 31), est_courante=True,
        )
        self.niveau = Niveau.objects.create(libelle="6ème", cycle="COLLEGE", ordre=1)
        self.classe = Classe.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee, libelle="6ème A"
        )
        eleve = Eleve.objects.create(
            nom="Dupont", prenoms="Jean", sexe="M", date_naissance=date(2010, 1, 1)
        )
        self.inscription = Inscription.objects.create(
            eleve=eleve, classe=self.classe, annee_scolaire=self.annee,
            statut_inscription="NOUVEAU",
        )
        self.frais_scolarite = TypeFrais.objects.create(libelle="Scolarité")
        self.frais_inscription = TypeFrais.objects.create(libelle="Inscription")


class EcheancierTest(BaseFinanceTest):
    def test_generation_depuis_grille_tarifaire(self):
        GrilleTarifaire.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee,
            type_frais=self.frais_scolarite, montant=Decimal("60000"),
        )
        GrilleTarifaire.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee,
            type_frais=self.frais_inscription, montant=Decimal("10000"),
        )
        echeances = generer_echeancier(self.inscription)
        self.assertEqual(len(echeances), 2)
        total = sum((e.montant_du for e in echeances), Decimal("0"))
        self.assertEqual(total, Decimal("70000"))

    def test_repartition_en_plusieurs_versements(self):
        GrilleTarifaire.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee,
            type_frais=self.frais_scolarite, montant=Decimal("90000"),
        )
        echeances = generer_echeancier(self.inscription, nb_versements=3)
        self.assertEqual(len(echeances), 3)
        total = sum((e.montant_du for e in echeances), Decimal("0"))
        self.assertEqual(total, Decimal("90000"))


class ImputationFifoTTest(BaseFinanceTest):
    def setUp(self):
        super().setUp()
        GrilleTarifaire.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee,
            type_frais=self.frais_scolarite, montant=Decimal("30000"),
        )
        self.echeances = generer_echeancier(self.inscription)

    def _payer(self, montant):
        return Paiement.objects.create(
            inscription=self.inscription, montant=montant, mode_paiement="ESPECES",
        )

    def test_imputation_fifo_sur_plus_ancienne(self):
        paiement = self._payer(Decimal("12000"))
        imputations = imputer_paiement(paiement)
        self.assertEqual(len(imputations), 1)
        echeance = self.echeances[0]
        echeance.refresh_from_db()
        self.assertEqual(echeance.montant_paye, Decimal("12000"))
        self.assertEqual(echeance.statut, Echeance.Statut.PARTIEL)

    def test_paiement_complet_marque_paye(self):
        paiement = self._payer(Decimal("30000"))
        imputer_paiement(paiement)
        self.echeances[0].refresh_from_db()
        self.assertEqual(self.echeances[0].statut, Echeance.Statut.PAYE)

    def test_imputation_manuelle_ciblee(self):
        # Une seule échéance de 30000 : on cible la seconde (inexistante -> rien)
        from finances.models import Echeance
        autre = Echeance.objects.create(
            inscription=self.inscription, type_frais=self.frais_scolarite,
            libelle="Frais annexe", montant_du=Decimal("5000"),
            date_echeance=date(2027, 3, 1),
        )
        paiement = self._payer(Decimal("5000"))
        imputer_paiement(paiement, cibles=[autre.pk])
        autre.refresh_from_db()
        self.assertEqual(autre.statut, Echeance.Statut.PAYE)
        self.assertEqual(self.echeances[0].statut, Echeance.Statut.IMPAYE)

    def test_annulation_restaure_les_echeances(self):
        paiement = self._payer(Decimal("30000"))
        imputer_paiement(paiement)
        annuler_paiement(paiement, "Test erreur de caisse")
        self.echeances[0].refresh_from_db()
        self.assertEqual(self.echeances[0].statut, Echeance.Statut.IMPAYE)
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, Paiement.Statut.ANNULE)


class MontantEnToutesLettresTest(TestCase):
    """Conversion des montants en toutes lettres (reçus, standard comptable)."""

    def _lettres(self, montant):
        from .services import montant_en_toutes_lettres
        return montant_en_toutes_lettres(montant)

    def test_montants_entiers(self):
        self.assertEqual(self._lettres(Decimal("25000")), "vingt-cinq mille francs")
        self.assertEqual(self._lettres(Decimal("1000")), "mille francs")
        self.assertEqual(self._lettres(Decimal("100")), "cent francs")
        self.assertEqual(self._lettres(Decimal("200")), "deux cents francs")
        self.assertEqual(self._lettres(Decimal("80")), "quatre-vingts francs")
        self.assertEqual(self._lettres(Decimal("71")), "soixante et onze francs")
        self.assertEqual(self._lettres(Decimal("91")), "quatre-vingt-onze francs")
        self.assertEqual(self._lettres(Decimal("125000")), "cent vingt-cinq mille francs")
        self.assertEqual(self._lettres(Decimal("1000000")), "un million francs")

    def test_montant_avec_centimes(self):
        self.assertEqual(
            self._lettres(Decimal("1250.50")),
            "mille deux cent cinquante francs et cinquante centimes",
        )

    def test_zero(self):
        self.assertEqual(self._lettres(Decimal("0")), "zéro franc")


class NumerotationTest(BaseFinanceTest):
    def test_numero_recu_unique(self):
        paiement = Paiement.objects.create(
            inscription=self.inscription, montant=Decimal("1000"),
            mode_paiement="ESPECES",
        )
        recu1 = generer_recu(paiement)
        paiement2 = Paiement.objects.create(
            inscription=self.inscription, montant=Decimal("2000"),
            mode_paiement="CHEQUE",
        )
        recu2 = generer_recu(paiement2)
        self.assertNotEqual(recu1.numero, recu2.numero)
        self.assertTrue(recu1.numero.startswith(f"RC-{date.today().year}-"))

    def test_numero_facture_unique(self):
        GrilleTarifaire.objects.create(
            niveau=self.niveau, annee_scolaire=self.annee,
            type_frais=self.frais_scolarite, montant=Decimal("30000"),
        )
        generer_echeancier(self.inscription)
        facture1 = generer_facture(self.inscription)
        facture2 = generer_facture(self.inscription)
        self.assertIsNotNone(facture1)
        self.assertNotEqual(facture1.numero, facture2.numero)
        self.assertTrue(facture1.numero.startswith(f"FA-{date.today().year}-"))
        self.assertEqual(facture1.statut, Facture.Statut.EMISE)
