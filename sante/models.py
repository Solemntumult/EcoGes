from django.db import models
from django.conf import settings
from eleves.models import Eleve


class FicheMedicale(models.Model):
    """Fiche médicale confidentielle de l'élève."""
    class GroupeSanguin(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"
        INCONNU = "INCONNU", "Inconnu"

    eleve = models.OneToOneField(Eleve, on_delete=models.CASCADE, related_name="fiche_medicale")
    groupe_sanguin = models.CharField(max_length=10, choices=GroupeSanguin.choices, default=GroupeSanguin.INCONNU)
    allergies = models.TextField(blank=True, help_text="Allergies médicamenteuses ou alimentaires connues")
    affections_chroniques = models.TextField(blank=True, help_text="Ex. Asthme, diabète, drépanocytose, épilepsie")
    medecin_traitant = models.CharField(max_length=150, blank=True)
    telephone_medecin = models.CharField(max_length=30, blank=True)
    remarques_urgences = models.TextField(blank=True, help_text="Instructions spéciales en cas de crise ou d'accident")

    class Meta:
        verbose_name = "Fiche médicale"
        verbose_name_plural = "Fiches médicales"

    def __str__(self):
        return f"Fiche médicale : {self.eleve}"


class Vaccination(models.Model):
    """Enregistrement vaccinal d'un élève."""
    fiche_medicale = models.ForeignKey(FicheMedicale, on_delete=models.CASCADE, related_name="vaccinations")
    nom_vaccin = models.CharField(max_length=100)
    date_administration = models.DateField()
    rappel_prevu = models.DateField(null=True, blank=True)
    centre_ou_medecin = models.CharField(max_length=150, blank=True)

    class Meta:
        verbose_name = "Vaccination"
        verbose_name_plural = "Vaccinations"

    def __str__(self):
        return f"{self.nom_vaccin} - {self.fiche_medicale.eleve}"


class PassageInfirmerie(models.Model):
    """Registre des visites à l'infirmerie de l'école."""
    class Issue(models.TextChoices):
        RETOUR_CLASSE = "RETOUR_CLASSE", "Retour en classe"
        REPOS = "REPOS", "Repos à l'infirmerie"
        RETOUR_DOMICILE = "RETOUR_DOMICILE", "Retour au domicile (parents prévenus)"
        EVACUATION = "EVACUATION", "Évacuation vers un centre hospitalier"

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="visites_infirmerie")
    date_heure_entree = models.DateTimeField(auto_now_add=True)
    date_heure_sortie = models.DateTimeField(null=True, blank=True)
    motif = models.CharField(max_length=200, help_text="Ex. Céphalées, plaie légère, fièvre, malaise")
    soins_administres = models.TextField(help_text="Pansement, prise de température, repos, paracétamol...")
    issue = models.CharField(max_length=20, choices=Issue.choices, default=Issue.RETOUR_CLASSE)
    parent_prevenu = models.BooleanField(default=False)
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="soins_infirmerie_dispenses"
    )

    class Meta:
        verbose_name = "Passage à l'infirmerie"
        verbose_name_plural = "Passages à l'infirmerie"
        ordering = ["-date_heure_entree"]

    def __str__(self):
        return f"{self.eleve} ({self.date_heure_entree.strftime('%d/%m/%Y %H:%M')}) : {self.motif}"
