from django.db import models
from personnel.models import Affectation


class SeanceCours(models.Model):
    """Enregistrement d'une séance de cours dans le cahier de textes numérique."""
    affectation = models.ForeignKey(Affectation, on_delete=models.CASCADE, related_name="seances_cahier_texte")
    date = models.DateField()
    creneau = models.CharField(max_length=50, help_text="Ex. 08:00 - 10:00")
    titre_chapitre = models.CharField(max_length=200)
    contenu_dispense = models.TextField(help_text="Notions abordées, cours, exercices effectués en classe")
    objectifs_vises = models.TextField(blank=True, help_text="Objectifs pédagogiques de la séance")
    fichier_support = models.FileField(upload_to="cahier_texte/supports/", blank=True, null=True)
    date_saisie = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Séance de cours"
        verbose_name_plural = "Séances de cours"
        ordering = ["-date", "creneau"]
        indexes = [
            models.Index(fields=["affectation", "date"]),
        ]

    def __str__(self):
        return f"{self.affectation.classe} - {self.affectation.matiere} ({self.date}) : {self.titre_chapitre}"


class DevoirMaison(models.Model):
    """Devoir ou travail de maison prescrit aux élèves."""
    seance = models.ForeignKey(
        SeanceCours, on_delete=models.CASCADE, related_name="devoirs", null=True, blank=True
    )
    affectation = models.ForeignKey(Affectation, on_delete=models.CASCADE, related_name="devoirs_maison")
    titre = models.CharField(max_length=200)
    date_prescription = models.DateField()
    date_limite = models.DateField(help_text="Date d'échéance pour rendre le devoir")
    consignes = models.TextField()
    fichier_sujet = models.FileField(upload_to="cahier_texte/devoirs/", blank=True, null=True)
    est_note = models.BooleanField(default=False)
    bareme = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)

    class Meta:
        verbose_name = "Devoir de maison"
        verbose_name_plural = "Devoirs de maison"
        ordering = ["-date_limite"]
        indexes = [
            models.Index(fields=["affectation", "date_limite"]),
        ]

    def __str__(self):
        return f"{self.affectation.classe} - {self.titre} (pour le {self.date_limite.strftime('%d/%m/%Y')})"
