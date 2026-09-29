from django.db import models

from eleves.models import Inscription
from parametrage.models import Classe, Matiere, Periode


class Evaluation(models.Model):
    class Type(models.TextChoices):
        DEVOIR = "DEVOIR", "Devoir"
        COMPOSITION = "COMPOSITION", "Composition"
        INTERROGATION = "INTERROGATION", "Interrogation"

    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="evaluations")
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="evaluations")
    periode = models.ForeignKey(Periode, on_delete=models.CASCADE, related_name="evaluations")
    type_evaluation = models.CharField(max_length=15, choices=Type.choices, default=Type.DEVOIR)
    coefficient = models.DecimalField(max_digits=4, decimal_places=1, default=1)
    date = models.DateField()
    saisie_verrouillee = models.BooleanField(default=False)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.matiere} - {self.classe} - {self.get_type_evaluation_display()} ({self.date})"


class Note(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="notes")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="notes")
    valeur = models.DecimalField(max_digits=4, decimal_places=2)
    saisi_par = models.ForeignKey(
        "personnel.Personnel", on_delete=models.SET_NULL, null=True, related_name="notes_saisies"
    )
    date_saisie = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("evaluation", "inscription")

    def __str__(self):
        return f"{self.inscription.eleve} - {self.evaluation} : {self.valeur}"


class NoteModification(models.Model):
    """Traçabilité des modifications de notes après verrouillage (UC-21).

    Alimentée par un signal post_save sur Note : qui a modifié, quand,
    et quelles étaient les anciennes et nouvelles valeurs.
    """

    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name="modifications")
    modifie_par = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="modifications_notes"
    )
    ancienne_valeur = models.DecimalField(max_digits=4, decimal_places=2)
    nouvelle_valeur = models.DecimalField(max_digits=4, decimal_places=2)
    date_modification = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_modification"]
        verbose_name = "Modification de note"
        verbose_name_plural = "Modifications de notes"

    def __str__(self):
        return f"{self.note} : {self.ancienne_valeur} → {self.nouvelle_valeur} ({self.modifie_par})"


class Bulletin(models.Model):
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="bulletins")
    periode = models.ForeignKey(Periode, on_delete=models.CASCADE, related_name="bulletins", null=True, blank=True)
    est_annuel = models.BooleanField(default=False)
    moyenne_generale = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rang = models.PositiveSmallIntegerField(null=True, blank=True)
    mention = models.CharField(max_length=50, blank=True)
    appreciation_generale = models.TextField(blank=True)
    date_generation = models.DateTimeField(auto_now_add=True)
    fichier_pdf = models.FileField(upload_to="bulletins/", blank=True, null=True)

    class Meta:
        unique_together = ("inscription", "periode", "est_annuel")

    def __str__(self):
        periode_str = "Annuel" if self.est_annuel else str(self.periode)
        return f"Bulletin {self.inscription.eleve} - {periode_str}"
