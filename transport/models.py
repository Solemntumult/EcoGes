from django.db import models
from eleves.models import Inscription


class LigneTransport(models.Model):
    """Ligne de ramassage ou circuit de bus scolaire."""
    libelle = models.CharField(max_length=150, help_text="Ex. Ligne Nord - Akpakpa / Cotonou")
    chauffeur = models.CharField(max_length=150)
    telephone_chauffeur = models.CharField(max_length=30)
    immatriculation_vehicule = models.CharField(max_length=50)
    capacite_places = models.PositiveSmallIntegerField(default=30)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Ligne de transport"
        verbose_name_plural = "Lignes de transport"

    def __str__(self):
        return f"{self.libelle} ({self.immatriculation_vehicule})"


class ArretTransport(models.Model):
    """Point d'arrêt et horaire sur le circuit."""
    ligne = models.ForeignKey(LigneTransport, on_delete=models.CASCADE, related_name="arrets")
    nom_arret = models.CharField(max_length=150)
    heure_passage_matin = models.TimeField()
    heure_passage_soir = models.TimeField(null=True, blank=True)
    ordre = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = "Arrêt de bus"
        verbose_name_plural = "Arrêts de bus"
        ordering = ["ligne", "ordre"]

    def __str__(self):
        return f"{self.nom_arret} ({self.ligne.libelle}) - Matin : {self.heure_passage_matin}"


class InscriptionTransport(models.Model):
    """Abonnement d'un élève au ramassage scolaire."""
    class Formule(models.TextChoices):
        ALLER_RETOUR = "ALLER_RETOUR", "Aller et Retour"
        ALLER_SIMPLE = "ALLER_SIMPLE", "Aller simple uniquement"

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="inscriptions_transport")
    ligne = models.ForeignKey(LigneTransport, on_delete=models.CASCADE, related_name="inscriptions")
    arret = models.ForeignKey(ArretTransport, on_delete=models.PROTECT)
    formule = models.CharField(max_length=15, choices=Formule.choices, default=Formule.ALLER_RETOUR)
    tarif_mensuel = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    actif = models.BooleanField(default=True)
    date_inscription = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Abonnement transport"
        verbose_name_plural = "Abonnements transport"

    def __str__(self):
        return f"{self.inscription.eleve} - {self.ligne.libelle} ({self.arret.nom_arret})"
