from django.db import models
from eleves.models import Inscription


class InscriptionCantine(models.Model):
    """Souscription au service de cantine ou demi-pension."""
    class Formule(models.TextChoices):
        ANNUEL = "ANNUEL", "Abonnement annuel"
        MENSUEL = "MENSUEL", "Abonnement mensuel"
        TICKET = "TICKET", "Tickets repas au coup par coup"

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="inscriptions_cantine")
    formule = models.CharField(max_length=15, choices=Formule.choices, default=Formule.MENSUEL)
    tarif = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    allergies = models.CharField(max_length=255, blank=True, help_text="Ex. Arachides, gluten, lactose")
    regime_special = models.CharField(max_length=100, blank=True, help_text="Ex. Sans porc, végétarien")
    actif = models.BooleanField(default=True)
    date_inscription = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Inscription Cantine"
        verbose_name_plural = "Inscriptions Cantine"

    def __str__(self):
        return f"{self.inscription.eleve} - Cantine ({self.get_formule_display()})"


class PresenceRepas(models.Model):
    """Pointage d'accès au réfectoire."""
    inscription_cantine = models.ForeignKey(InscriptionCantine, on_delete=models.CASCADE, related_name="presences")
    date = models.DateField()
    present = models.BooleanField(default=True)
    heure_passage = models.TimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Présence au réfectoire"
        verbose_name_plural = "Présences au réfectoire"
        unique_together = ("inscription_cantine", "date")

    def __str__(self):
        return f"{self.inscription_cantine.inscription.eleve} le {self.date}"


class MenuSemaine(models.Model):
    """Affichage du menu de la semaine."""
    date_debut = models.DateField(help_text="Lundi de la semaine")
    date_fin = models.DateField(help_text="Vendredi de la semaine")
    lundi = models.TextField()
    mardi = models.TextField()
    mercredi = models.TextField()
    jeudi = models.TextField()
    vendredi = models.TextField()

    class Meta:
        verbose_name = "Menu de la semaine"
        verbose_name_plural = "Menus de la semaine"
        ordering = ["-date_debut"]

    def __str__(self):
        return f"Menu du {self.date_debut.strftime('%d/%m')} au {self.date_fin.strftime('%d/%m/%Y')}"
