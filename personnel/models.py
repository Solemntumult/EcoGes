from decimal import Decimal

from django.conf import settings
from django.db import models

from parametrage.models import AnneeScolaire, Classe, Matiere


class Personnel(models.Model):
    class Fonction(models.TextChoices):
        ENSEIGNANT = "ENSEIGNANT", "Enseignant"
        CENSEUR = "CENSEUR", "Censeur / Direction des études"
        SECRETAIRE = "SECRETAIRE", "Secrétaire"
        COMPTABLE = "COMPTABLE", "Comptable"
        SURVEILLANT = "SURVEILLANT", "Surveillant"
        AUTRE = "AUTRE", "Autre"

    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fiche_personnel",
        null=True, blank=True,
    )
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=150)
    fonction = models.CharField(max_length=15, choices=Fonction.choices)
    qualification = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    date_embauche = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        ordering = ["nom", "prenoms"]
        verbose_name_plural = "Personnel"

    def __str__(self):
        return f"{self.nom} {self.prenoms} - {self.get_fonction_display()}"


class Affectation(models.Model):
    """Affectation d'un enseignant à une classe/matière pour une année scolaire."""

    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name="affectations")
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="affectations")
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="affectations")
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="affectations")
    tarif_horaire = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0"),
        help_text="Montant payé par heure de cours pour cet enseignant sur cette classe/matière.",
    )

    class Meta:
        unique_together = ("personnel", "classe", "matiere", "annee_scolaire")

    def __str__(self):
        return f"{self.personnel} -> {self.matiere} ({self.classe})"


class CreneauEmploiDuTemps(models.Model):
    class Jour(models.TextChoices):
        LUNDI = "LUN", "Lundi"
        MARDI = "MAR", "Mardi"
        MERCREDI = "MER", "Mercredi"
        JEUDI = "JEU", "Jeudi"
        VENDREDI = "VEN", "Vendredi"
        SAMEDI = "SAM", "Samedi"

    affectation = models.ForeignKey(
        Affectation, on_delete=models.CASCADE, related_name="creneaux"
    )
    jour = models.CharField(max_length=3, choices=Jour.choices)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    salle = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["jour", "heure_debut"]
        verbose_name = "Créneau d'emploi du temps"
        verbose_name_plural = "Emploi du temps"

    def __str__(self):
        return f"{self.affectation} - {self.get_jour_display()} {self.heure_debut}-{self.heure_fin}"

    @property
    def duree_heures(self):
        """Durée du cours en heures (arrondie à 0,01) — ex. 07:00–09:00 → 2.00."""
        from datetime import date, datetime
        from decimal import Decimal

        debut = datetime.combine(date.min, self.heure_debut)
        fin = datetime.combine(date.min, self.heure_fin)
        return Decimal(str((fin - debut).total_seconds() / 3600)).quantize(Decimal("0.01"))


class DisponibiliteEnseignant(models.Model):
    """Créneau durant lequel un enseignant est disponible dans la semaine."""
    
    personnel = models.ForeignKey(Personnel, on_delete=models.CASCADE, related_name="disponibilites")
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="disponibilites_enseignants")
    jour = models.CharField(max_length=3, choices=CreneauEmploiDuTemps.Jour.choices)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()

    class Meta:
        ordering = ["jour", "heure_debut"]
        verbose_name = "Disponibilité Enseignant"
        verbose_name_plural = "Disponibilités Enseignants"

    def __str__(self):
        return f"{self.personnel} - {self.get_jour_display()} {self.heure_debut:%H:%M}-{self.heure_fin:%H:%M}"
