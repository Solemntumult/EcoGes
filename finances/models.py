from decimal import Decimal

from django.db import models

from eleves.models import Inscription
from parametrage.models import TypeFrais


class Echeance(models.Model):
    class Statut(models.TextChoices):
        IMPAYE = "IMPAYE", "Impayé"
        PARTIEL = "PARTIEL", "Partiellement payé"
        PAYE = "PAYE", "Payé"

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="echeances")
    type_frais = models.ForeignKey(TypeFrais, on_delete=models.PROTECT)
    libelle = models.CharField(max_length=150)
    montant_du = models.DecimalField(max_digits=12, decimal_places=2)
    date_echeance = models.DateField()
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.IMPAYE)

    class Meta:
        ordering = ["date_echeance"]
        indexes = [
            models.Index(fields=["inscription", "statut"]),
            models.Index(fields=["date_echeance", "statut"]),
        ]

    def __str__(self):
        return f"{self.libelle} - {self.inscription.eleve} : {self.montant_du}"

    @property
    def montant_paye(self):
        return sum(imp.montant_impute for imp in self.imputations.all())

    @property
    def solde(self):
        return self.montant_du - self.montant_paye


class Remise(models.Model):
    class Type(models.TextChoices):
        BOURSE = "BOURSE", "Bourse"
        EXONERATION = "EXONERATION", "Exonération partielle"
        REDUCTION = "REDUCTION", "Réduction commerciale"

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="remises")
    type_remise = models.CharField(max_length=15, choices=Type.choices)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    motif = models.TextField()
    accorde_par = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="remises_accordees"
    )
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_type_remise_display()} - {self.inscription.eleve} : {self.montant}"


class Paiement(models.Model):
    class ModePaiement(models.TextChoices):
        ESPECES = "ESPECES", "Espèces"
        CHEQUE = "CHEQUE", "Chèque"
        VIREMENT = "VIREMENT", "Virement bancaire"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"

    class Statut(models.TextChoices):
        VALIDE = "VALIDE", "Validé"
        ANNULE = "ANNULE", "Annulé"
        REMBOURSE = "REMBOURSE", "Remboursé"

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="paiements")
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    mode_paiement = models.CharField(max_length=15, choices=ModePaiement.choices)
    reference = models.CharField(max_length=100, blank=True)
    encaisse_par = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="paiements_encaisses"
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.VALIDE)
    motif_annulation = models.TextField(blank=True)
    date_paiement = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_paiement"]
        indexes = [
            models.Index(fields=["inscription", "date_paiement"]),
            models.Index(fields=["mode_paiement", "statut"]),
        ]

    def __str__(self):
        return f"Paiement {self.montant} - {self.inscription.eleve} ({self.date_paiement:%d/%m/%Y})"


class ImputationPaiement(models.Model):
    """Répartition d'un paiement sur une ou plusieurs échéances (imputation FIFO ou manuelle)."""

    paiement = models.ForeignKey(Paiement, on_delete=models.CASCADE, related_name="imputations")
    echeance = models.ForeignKey(Echeance, on_delete=models.CASCADE, related_name="imputations")
    montant_impute = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.paiement} -> {self.echeance} : {self.montant_impute}"


class Facture(models.Model):
    class Statut(models.TextChoices):
        EMISE = "EMISE", "Émise"
        SOLDEE = "SOLDEE", "Soldée"
        ANNULEE = "ANNULEE", "Annulée (avoir)"

    numero = models.CharField(max_length=30, unique=True, editable=False)
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="factures")
    date_emission = models.DateTimeField(auto_now_add=True)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.EMISE)
    fichier_pdf = models.FileField(upload_to="factures/", blank=True, null=True)

    class Meta:
        ordering = ["-date_emission"]

    def __str__(self):
        return f"Facture {self.numero} - {self.inscription.eleve}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generer_numero()
        super().save(*args, **kwargs)

    def _generer_numero(self):
        from django.utils import timezone

        annee = timezone.now().year
        dernier = Facture.objects.filter(numero__startswith=f"FA-{annee}-").order_by("-numero").first()
        prochain = int(dernier.numero.split("-")[-1]) + 1 if dernier else 1
        return f"FA-{annee}-{prochain:06d}"


class LigneFacture(models.Model):
    facture = models.ForeignKey(Facture, on_delete=models.CASCADE, related_name="lignes")
    libelle = models.CharField(max_length=150)
    montant = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.libelle} : {self.montant}"


class Recu(models.Model):
    numero = models.CharField(max_length=30, unique=True, editable=False)
    paiement = models.OneToOneField(Paiement, on_delete=models.CASCADE, related_name="recu")
    date_emission = models.DateTimeField(auto_now_add=True)
    fichier_pdf = models.FileField(upload_to="recus/", blank=True, null=True)

    def __str__(self):
        return f"Reçu {self.numero}"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generer_numero()
        super().save(*args, **kwargs)

    def _generer_numero(self):
        from django.utils import timezone

        annee = timezone.now().year
        dernier = Recu.objects.filter(numero__startswith=f"RC-{annee}-").order_by("-numero").first()
        prochain = int(dernier.numero.split("-")[-1]) + 1 if dernier else 1
        return f"RC-{annee}-{prochain:06d}"


class FicheDePaie(models.Model):
    """Bulletin de paie mensuel d'un membre du personnel.

    Le montant est calculé automatiquement à partir des heures de cours
    (issues de l'emploi du temps) × le tarif horaire de chaque affectation.
    """

    class Statut(models.TextChoices):
        CALCULEE = "CALCULEE", "Calculée"
        PAYEE = "PAYEE", "Payée"
        ANNULEE = "ANNULEE", "Annulée"

    numero = models.CharField(max_length=30, unique=True, editable=False)
    personnel = models.ForeignKey(
        "personnel.Personnel", on_delete=models.CASCADE, related_name="fiches_de_paie"
    )
    mois = models.PositiveSmallIntegerField(help_text="1 à 12")
    annee = models.PositiveSmallIntegerField()
    heures_total = models.DecimalField(max_digits=8, decimal_places=2, help_text="Heures du mois (heures hebdo × 4,33)")
    montant_brut = models.DecimalField(max_digits=12, decimal_places=2, help_text="Heures × tarifs horaires des affectations")
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.CALCULEE)
    mode_paiement = models.CharField(
        max_length=15, choices=Paiement.ModePaiement.choices, default=Paiement.ModePaiement.ESPECES
    )
    date_paiement = models.DateField(null=True, blank=True)
    fichier_pdf = models.FileField(upload_to="fiches_paie/", blank=True, null=True)

    class Meta:
        ordering = ["-annee", "-mois"]
        unique_together = ("personnel", "mois", "annee")
        verbose_name = "Fiche de paie"
        verbose_name_plural = "Fiches de paie"

    def __str__(self):
        return f"Fiche de paie {self.numero} — {self.personnel} ({self.mois:02d}/{self.annee})"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generer_numero()
        super().save(*args, **kwargs)

    def _generer_numero(self):
        from django.utils import timezone

        annee = timezone.now().year
        dernier = FicheDePaie.objects.filter(numero__startswith=f"FP-{annee}-").order_by("-numero").first()
        prochain = int(dernier.numero.split("-")[-1]) + 1 if dernier else 1
        return f"FP-{annee}-{prochain:06d}"


# ==============================================================================
# Finances Avancées : Mobile Money, Dépenses & Journal de Caisse
# ==============================================================================

class TransactionMobileMoney(models.Model):
    """Enregistrement et réconciliation des paiements Mobile Money (MTN, Moov, Kkiapay, FedaPay)."""
    class Operateur(models.TextChoices):
        MTN_MOMO = "MTN", "MTN Mobile Money"
        MOOV_MONEY = "MOOV", "Moov Money"
        KKIAPAY = "KKIAPAY", "Kkiapay (Agrégateur)"
        FEDAPAY = "FEDAPAY", "FedaPay (Agrégateur)"
        AUTRE = "AUTRE", "Autre opérateur"

    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de validation"
        SUCCES = "SUCCES", "Paiement confirmé"
        ECHOUE = "ECHOUE", "Échoué / Annulé"

    paiement = models.OneToOneField(Paiement, on_delete=models.CASCADE, related_name="transaction_momo", null=True, blank=True)
    operateur = models.CharField(max_length=15, choices=Operateur.choices, default=Operateur.MTN_MOMO)
    reference_externe = models.CharField(max_length=150, unique=True, help_text="ID transaction de l'opérateur")
    numero_client = models.CharField(max_length=30)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)
    signature_hmac = models.CharField(max_length=255, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_confirmation = models.DateTimeField(null=True, blank=True)
    donnees_webhook = models.JSONField(blank=True, default=dict)

    class Meta:
        verbose_name = "Transaction Mobile Money"
        verbose_name_plural = "Transactions Mobile Money"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"Momo {self.get_operateur_display()} - {self.reference_externe} ({self.montant} FCFA)"


class CategorieDepense(models.Model):
    """Catégorie pour le suivi des dépenses et charges de l'établissement."""
    class Nature(models.TextChoices):
        FONCTIONNEMENT = "FONCTIONNEMENT", "Fonctionnement courant (eau, élec, fournitures)"
        INVESTISSEMENT = "INVESTISSEMENT", "Investissement & Équipements"
        MAINTENANCE = "MAINTENANCE", "Entretien & Maintenance"
        PEDAGOGIE = "PEDAGOGIE", "Activités pédagogiques & sorties"
        AUTRE = "AUTRE", "Autre dépense"

    libelle = models.CharField(max_length=150)
    nature = models.CharField(max_length=20, choices=Nature.choices, default=Nature.FONCTIONNEMENT)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Catégorie de dépense"
        verbose_name_plural = "Catégories de dépenses"

    def __str__(self):
        return f"{self.libelle} ({self.get_nature_display()})"


class Depense(models.Model):
    """Enregistrement d'une dépense / décaissement de l'établissement."""
    numero = models.CharField(max_length=30, unique=True, editable=False)
    categorie = models.ForeignKey(CategorieDepense, on_delete=models.PROTECT, related_name="depenses")
    libelle = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    date_depense = models.DateField()
    beneficiaire = models.CharField(max_length=150, help_text="Fournisseur ou prestataire payé")
    justificatif_facture = models.FileField(upload_to="finances/justificatifs_depenses/", blank=True, null=True)
    mode_paiement = models.CharField(
        max_length=15, choices=Paiement.ModePaiement.choices, default=Paiement.ModePaiement.ESPECES
    )
    enregistre_par = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="depenses_enregistrees"
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Dépense / Décaissement"
        verbose_name_plural = "Dépenses / Décaissements"
        ordering = ["-date_depense", "-date_creation"]

    def __str__(self):
        return f"{self.numero} - {self.libelle} : {self.montant} FCFA"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generer_numero()
        super().save(*args, **kwargs)

    def _generer_numero(self):
        from django.utils import timezone
        annee = timezone.now().year
        dernier = Depense.objects.filter(numero__startswith=f"DEP-{annee}-").order_by("-numero").first()
        prochain = int(dernier.numero.split("-")[-1]) + 1 if dernier else 1
        return f"DEP-{annee}-{prochain:06d}"


class ClotureCaisse(models.Model):
    """Arrêté et clôture journalière de la caisse physique."""
    date = models.DateField(unique=True)
    solde_ouverture = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_encaissements = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_decaissements = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    solde_theorique = models.DecimalField(max_digits=12, decimal_places=2, help_text="Ouverture + Encaissements - Décaissements")
    solde_physique = models.DecimalField(max_digits=12, decimal_places=2, help_text="Montant réel compté dans le coffre/tiroir")
    ecart = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    justification_ecart = models.TextField(blank=True)
    cloture_par = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="clotures_caisse"
    )
    date_validation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Clôture de caisse journalière"
        verbose_name_plural = "Clôtures de caisse journalières"
        ordering = ["-date"]

    def __str__(self):
        return f"Clôture caisse du {self.date.strftime('%d/%m/%Y')} (Écart : {self.ecart} FCFA)"


# ==============================================================================
# Primes et compléments de rémunération (Section 12.7)
# ==============================================================================

class PrimePersonnel(models.Model):
    """Prime ou indemnité attribuée au personnel (Section 12.7)."""

    personnel = models.ForeignKey(
        "personnel.Personnel", on_delete=models.CASCADE, related_name="primes"
    )
    mois = models.PositiveSmallIntegerField(help_text="1 à 12")
    annee = models.PositiveSmallIntegerField()
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    motif = models.CharField(max_length=255, help_text="Ex. Surveillance examens, assiduité, transport")
    date_attribution = models.DateField(auto_now_add=True)
    accorde_par = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = "Prime de personnel"
        verbose_name_plural = "Primes de personnel"
        ordering = ["-annee", "-mois", "-date_attribution"]

    def __str__(self):
        return f"Prime {self.montant} F — {self.personnel} ({self.motif})"


# ==============================================================================
# Comptabilité Générale en Partie Double (Section 13)
# ==============================================================================

class CompteComptable(models.Model):
    """Compte du plan comptable général (Section 13.2)."""

    class Nature(models.TextChoices):
        ACTIF = "ACTIF", "Actif (classe 2, 3, 4, 5)"
        PASSIF = "PASSIF", "Passif (classe 1, 4)"
        CHARGE = "CHARGE", "Charge (classe 6)"
        PRODUIT = "PRODUIT", "Produit (classe 7)"

    numero = models.CharField(max_length=20, unique=True, help_text="Ex. 411000, 512000, 706000")
    intitule = models.CharField(max_length=150)
    nature = models.CharField(max_length=10, choices=Nature.choices, default=Nature.CHARGE)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Compte comptable"
        verbose_name_plural = "Plan de comptes"
        ordering = ["numero"]

    def __str__(self):
        return f"{self.numero} - {self.intitule}"


class JournalComptable(models.Model):
    """Journal auxiliaire de saisie comptable."""

    code = models.CharField(max_length=10, unique=True, help_text="Ex. VT, CA, BQ, OD")
    intitule = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Journal comptable"
        verbose_name_plural = "Journaux comptables"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.intitule}"


class EcritureComptable(models.Model):
    """Pièce comptable regroupant des lignes équilibrées en débit / crédit."""

    class Statut(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon (modifiable)"
        VALIDEE = "VALIDEE", "Validée (clôturée et irréversible)"

    numero = models.CharField(max_length=30, unique=True, editable=False)
    journal = models.ForeignKey(JournalComptable, on_delete=models.PROTECT, related_name="ecritures")
    date_piece = models.DateField()
    libelle = models.CharField(max_length=255)
    reference_piece = models.CharField(max_length=100, blank=True, help_text="N° facture, reçu ou pièce justificative")
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    date_validation = models.DateTimeField(null=True, blank=True)
    valide_par = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, blank=True, related_name="ecritures_validees"
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Écriture comptable"
        verbose_name_plural = "Écritures comptables"
        ordering = ["-date_piece", "-date_creation"]

    def __str__(self):
        return f"{self.numero} ({self.date_piece}) : {self.libelle} [{self.get_statut_display()}]"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generer_numero()
        super().save(*args, **kwargs)

    def _generer_numero(self):
        from django.utils import timezone
        annee = timezone.now().year
        code_j = self.journal.code if self.journal_id else "ECR"
        dernier = EcritureComptable.objects.filter(numero__startswith=f"{code_j}-{annee}-").order_by("-numero").first()
        prochain = int(dernier.numero.split("-")[-1]) + 1 if dernier else 1
        return f"{code_j}-{annee}-{prochain:06d}"

    @property
    def total_debit(self):
        return sum((l.debit for l in self.lignes.all()), Decimal("0"))

    @property
    def total_credit(self):
        return sum((l.credit for l in self.lignes.all()), Decimal("0"))

    @property
    def est_equilibree(self):
        return self.total_debit == self.total_credit and self.total_debit > 0


class LigneEcriture(models.Model):
    """Mouvement unitaire sur un compte (débit ou crédit)."""

    class CentreCout(models.TextChoices):
        SCOLARITE = "SCOLARITE", "Scolarité générale"
        CANTINE = "CANTINE", "Restauration / Cantine"
        INFIRMERIE = "INFIRMERIE", "Santé / Infirmerie"
        BIBLIOTHEQUE = "BIBLIOTHEQUE", "Bibliothèque"
        ADMINISTRATION = "ADMIN", "Administration générale"

    ecriture = models.ForeignKey(EcritureComptable, on_delete=models.CASCADE, related_name="lignes")
    compte = models.ForeignKey(CompteComptable, on_delete=models.PROTECT, related_name="lignes")
    libelle = models.CharField(max_length=200)
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    centre_cout = models.CharField(max_length=20, choices=CentreCout.choices, default=CentreCout.SCOLARITE)

    class Meta:
        verbose_name = "Ligne d'écriture"
        verbose_name_plural = "Lignes d'écriture"

    def __str__(self):
        return f"{self.compte.numero} | D:{self.debit} C:{self.credit} — {self.libelle}"


