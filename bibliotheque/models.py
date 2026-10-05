from django.db import models
from eleves.models import Eleve, Inscription
from parametrage.models import AnneeScolaire


class EtatLivre(models.TextChoices):
    NEUF = "NEUF", "Neuf"
    BON = "BON", "Bon état"
    USE = "USE", "Usagé"
    DEGRADE = "DEGRADE", "Dégradé / Abîmé"


class Ouvrage(models.Model):
    """Livre ou manuel répertorié au catalogue du CDI."""
    class Categorie(models.TextChoices):
        MANUEL = "MANUEL", "Manuel scolaire"
        ROMAN = "ROMAN", "Roman / Littérature"
        DICTIONNAIRE = "DICTIONNAIRE", "Dictionnaire / Encyclopédie"
        BD = "BD", "Bande dessinée"
        REVUE = "REVUE", "Revue / Périodique"
        AUTRE = "AUTRE", "Autre"

    titre = models.CharField(max_length=200)
    auteur = models.CharField(max_length=150)
    isbn = models.CharField(max_length=30, blank=True)
    categorie = models.CharField(max_length=20, choices=Categorie.choices, default=Categorie.MANUEL)
    editeur = models.CharField(max_length=100, blank=True)
    annee_publication = models.PositiveSmallIntegerField(null=True, blank=True)
    emplacement = models.CharField(max_length=50, blank=True, help_text="Rayon, étagère")

    class Meta:
        verbose_name = "Ouvrage"
        verbose_name_plural = "Ouvrages"
        ordering = ["titre"]

    def __str__(self):
        return f"{self.titre} ({self.auteur})"


class Exemplaire(models.Model):
    """Exemplaire physique identifié par un code-barres."""
    ouvrage = models.ForeignKey(Ouvrage, on_delete=models.CASCADE, related_name="exemplaires")
    code_barre = models.CharField(max_length=50, unique=True)
    etat = models.CharField(max_length=10, choices=EtatLivre.choices, default=EtatLivre.BON)
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Exemplaire physique"
        verbose_name_plural = "Exemplaires physiques"

    def __str__(self):
        return f"{self.ouvrage.titre} [#{self.code_barre}]"


class Emprunt(models.Model):
    """Prêt individuel d'un livre à un élève."""
    exemplaire = models.ForeignKey(Exemplaire, on_delete=models.CASCADE, related_name="emprunts")
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="emprunts_bibliotheque")
    date_emprunt = models.DateField(auto_now_add=True)
    date_retour_prevue = models.DateField()
    date_retour_effective = models.DateField(null=True, blank=True)
    etat_retour = models.CharField(max_length=10, choices=EtatLivre.choices, blank=True)

    class Meta:
        verbose_name = "Emprunt de livre"
        verbose_name_plural = "Emprunts de livres"
        ordering = ["-date_emprunt"]

    def __str__(self):
        return f"{self.eleve} emprunte {self.exemplaire}"


class PretManuel(models.Model):
    """Prêt de manuel scolaire pour l'année complète sous caution."""
    exemplaire = models.ForeignKey(Exemplaire, on_delete=models.CASCADE, related_name="prets_manuels")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="manuels_pretes")
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    caution_versee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    etat_depart = models.CharField(max_length=10, choices=EtatLivre.choices, default=EtatLivre.BON)
    etat_retour = models.CharField(max_length=10, choices=EtatLivre.choices, blank=True)
    restitue = models.BooleanField(default=False)
    date_pret = models.DateField(auto_now_add=True)
    date_restitution = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Prêt de manuel scolaire"
        verbose_name_plural = "Prêts de manuels scolaires"

    def __str__(self):
        return f"Manuel {self.exemplaire} prêté à {self.inscription.eleve}"
