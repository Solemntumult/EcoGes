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
