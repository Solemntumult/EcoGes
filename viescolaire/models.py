from django.db import models
from django.conf import settings
from eleves.models import Inscription, Eleve
from parametrage.models import AnneeScolaire
from personnel.models import Affectation


class StatutPresence(models.TextChoices):
    PRESENT = "PRESENT", "Présent(e)"
    ABSENT = "ABSENT", "Absent(e)"
    RETARD = "RETARD", "En retard"
    INFIRMERIE = "INFIRMERIE", "À l'infirmerie"


class Appel(models.Model):
    """Enregistrement de présence/assiduité pour un élève lors d'une séance ou journée."""
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="appels")
    date = models.DateField()
    creneau = models.CharField(max_length=50, blank=True, help_text="Ex. 08:00 - 09:00 ou Matin")
    affectation = models.ForeignKey(Affectation, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels")
    statut = models.CharField(max_length=15, choices=StatutPresence.choices, default=StatutPresence.PRESENT)
    justifie = models.BooleanField(default=False)
    motif = models.CharField(max_length=255, blank=True)
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="appels_enregistres"
    )
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pointage d'assiduité / Appel"
        verbose_name_plural = "Pointages d'assiduité / Appels"
        unique_together = ("inscription", "date", "creneau")
        ordering = ["-date", "inscription__classe", "inscription__eleve"]
        indexes = [
            models.Index(fields=["date", "statut"]),
            models.Index(fields=["inscription", "date"]),
        ]

    def __str__(self):
        return f"{self.inscription.eleve} - {self.date} ({self.get_statut_display()})"


class JustificatifAbsence(models.Model):
    """Justificatif fourni par un parent pour régulariser une absence ou un retard."""
    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente de validation"
        VALIDE = "VALIDE", "Validé"
        REFUSE = "REFUSE", "Refusé"

    appel = models.ForeignKey(Appel, on_delete=models.CASCADE, related_name="justificatifs")
    fichier = models.FileField(upload_to="viescolaire/justificatifs/", blank=True, null=True)
    motif = models.TextField()
    date_depot = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="justificatifs_valides"
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    commentaire = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Justificatif d'absence"
        verbose_name_plural = "Justificatifs d'absence"

    def __str__(self):
        return f"Justificatif pour {self.appel} ({self.get_statut_display()})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.statut == self.Statut.VALIDE:
            self.appel.justifie = True
            self.appel.motif = self.motif
            self.appel.save(update_fields=["justifie", "motif"])


class IncidentDisciplinaire(models.Model):
    """Incident ou manquement disciplinaire signalé."""
    class Gravite(models.TextChoices):
        FAIBLE = "FAIBLE", "Faible (avertissement verbal)"
        MOYENNE = "MOYENNE", "Moyenne (perturbation, insolence)"
        GRAVE = "GRAVE", "Grave (bagarre, triche, dégradation)"
        TRES_GRAVE = "TRES_GRAVE", "Très grave (violence, vol, stupéfiants)"

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="incidents_disciplinaires")
    date_incident = models.DateTimeField()
    type_incident = models.CharField(max_length=150)
    gravite = models.CharField(max_length=15, choices=Gravite.choices, default=Gravite.MOYENNE)
    description = models.TextField()
    lieu = models.CharField(max_length=100, blank=True)
    signale_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="incidents_signales"
    )
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Incident disciplinaire"
        verbose_name_plural = "Incidents disciplinaires"
        ordering = ["-date_incident"]
        indexes = [
            models.Index(fields=["eleve", "date_incident"]),
        ]

    def __str__(self):
        return f"{self.eleve} - {self.type_incident} ({self.date_incident.strftime('%d/%m/%Y')})"


class Sanction(models.Model):
    """Sanction prononcée suite à un incident disciplinaire."""
    class TypeSanction(models.TextChoices):
        AVERTISSEMENT_TRAVAIL = "AVERT_TRAVAIL", "Avertissement travail"
        AVERTISSEMENT_CONDUITE = "AVERT_CONDUITE", "Avertissement conduite"
        BLAME = "BLAME", "Blâme"
        RETENUE = "RETENUE", "Retenue / Heure de colle"
        EXCLUSION_TEMP = "EXCL_TEMP", "Exclusion temporaire"
        EXCLUSION_DEF = "EXCL_DEF", "Exclusion définitive"

    incident = models.ForeignKey(
        IncidentDisciplinaire, on_delete=models.CASCADE, related_name="sanctions", null=True, blank=True
    )
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="sanctions")
    type_sanction = models.CharField(max_length=20, choices=TypeSanction.choices)
    motif = models.TextField()
    date_decision = models.DateField(auto_now_add=True)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="sanctions_decidees"
    )

    class Meta:
        verbose_name = "Sanction disciplinaire"
        verbose_name_plural = "Sanctions disciplinaires"

    def __str__(self):
        return f"{self.get_type_sanction_display()} - {self.eleve}"


class Retenue(models.Model):
    """Détail pratique d'une heure de retenue ou de colle."""
    sanction = models.OneToOneField(Sanction, on_delete=models.CASCADE, related_name="retenue")
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    salle = models.CharField(max_length=50)
    surveillant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="retenues_surveillees"
    )
    travail_a_faire = models.TextField(blank=True)
    effectuee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Retenue / Colle"
        verbose_name_plural = "Retenues / Colles"

    def __str__(self):
        return f"Retenue {self.sanction.eleve} le {self.date} ({self.heure_debut} - {self.heure_fin})"


class ConseilDiscipline(models.Model):
    """Conseil de discipline réuni pour les fautes graves."""
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="conseils_discipline")
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    date_conseil = models.DateField()
    motif = models.TextField()
    composition_membres = models.TextField(help_text="Liste des membres présents")
    proces_verbal = models.TextField(blank=True)
    decision = models.TextField()
    convocation_envoyee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Conseil de discipline"
        verbose_name_plural = "Conseils de discipline"

    def __str__(self):
        return f"Conseil de discipline - {self.eleve} ({self.date_conseil})"
