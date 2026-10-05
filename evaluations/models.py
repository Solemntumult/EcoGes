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


# ==============================================================================
# Spécificités Primaire : Évaluation par compétences (APC) & Garderie
# ==============================================================================

class CompetenceAPC(models.Model):
    """Compétence du référentiel pédagogique par compétences (APC - Primaire)."""
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name="competences_apc")
    niveau = models.ForeignKey("parametrage.Niveau", on_delete=models.CASCADE, related_name="competences_apc")
    code = models.CharField(max_length=20, help_text="Ex. C1.1, C2.3")
    libelle = models.CharField(max_length=255)

    class Meta:
        verbose_name = "Compétence (APC)"
        verbose_name_plural = "Compétences (APC)"
        ordering = ["niveau", "matiere", "code"]

    def __str__(self):
        return f"[{self.code}] {self.libelle} ({self.matiere})"


class EvaluationCompetence(models.Model):
    """Évaluation d'une compétence pour un élève (Livret d'acquisitions)."""
    class NiveauMaitrise(models.TextChoices):
        NA = "NA", "Non Acquis"
        ECA = "ECA", "En Cours d'Acquisition"
        A = "A", "Acquis"
        E = "E", "Expert"

    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="evaluations_competences")
    competence = models.ForeignKey(CompetenceAPC, on_delete=models.CASCADE, related_name="evaluations")
    periode = models.ForeignKey(Periode, on_delete=models.CASCADE)
    niveau_maitrise = models.CharField(max_length=5, choices=NiveauMaitrise.choices)
    observations = models.CharField(max_length=255, blank=True)
    date_evaluation = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Évaluation de compétence"
        verbose_name_plural = "Évaluations de compétences"
        unique_together = ("inscription", "competence", "periode")

    def __str__(self):
        return f"{self.inscription.eleve} - {self.competence.code} : {self.get_niveau_maitrise_display()}"


class InscriptionGarderie(models.Model):
    """Inscription aux activités périscolaires / garderie / études surveillées."""
    class Formule(models.TextChoices):
        MATIN = "MATIN", "Garderie matinale (6h30 - 7h30)"
        SOIR = "SOIR", "Étude surveillée / Garderie du soir (17h - 18h30)"
        COMPLETE = "COMPLETE", "Garderie complète (Matin & Soir)"

    eleve = models.ForeignKey("eleves.Eleve", on_delete=models.CASCADE, related_name="inscriptions_garderie")
    annee_scolaire = models.ForeignKey("parametrage.AnneeScolaire", on_delete=models.CASCADE)
    formule = models.CharField(max_length=15, choices=Formule.choices)
    tarif_mensuel = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Inscription Garderie / Périscolaire"
        verbose_name_plural = "Inscriptions Garderie / Périscolaire"

    def __str__(self):
        return f"{self.eleve} - Garderie {self.get_formule_display()}"


# ==============================================================================
# Spécificités Collège : Conseils de classe, Mentions & Délégués
# ==============================================================================

class ConseilDeClasse(models.Model):
    """Conseil de classe trimestriel ou semestriel."""
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="conseils_de_classe")
    periode = models.ForeignKey(Periode, on_delete=models.CASCADE, related_name="conseils_de_classe")
    date_conseil = models.DateField()
    president = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="conseils_presides"
    )
    secretaire = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, blank=True, related_name="conseils_secretaires"
    )
    synthese_generale = models.TextField(blank=True, help_text="Bilan global de la classe sur la période")

    class Meta:
        verbose_name = "Conseil de classe"
        verbose_name_plural = "Conseils de classe"
        unique_together = ("classe", "periode")

    def __str__(self):
        return f"Conseil de classe : {self.classe} ({self.periode})"


class MentionConseil(models.Model):
    """Distinctions et avis attribués lors du conseil de classe."""
    class TypeMention(models.TextChoices):
        FELICITATIONS = "FELICITATIONS", "Félicitations du conseil"
        TABLEAU_HONNEUR = "TABLEAU_HONNEUR", "Tableau d'honneur"
        ENCOURAGEMENTS = "ENCOURAGEMENTS", "Encouragements"
        AVERTISSEMENT_TRAVAIL = "AVERT_TRAVAIL", "Avertissement travail"
        AVERTISSEMENT_CONDUITE = "AVERT_CONDUITE", "Avertissement conduite"

    conseil = models.ForeignKey(ConseilDeClasse, on_delete=models.CASCADE, related_name="mentions")
    inscription = models.ForeignKey(Inscription, on_delete=models.CASCADE, related_name="mentions_conseil")
    type_mention = models.CharField(max_length=20, choices=TypeMention.choices)
    avis = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Mention / Avis du conseil"
        verbose_name_plural = "Mentions / Avis du conseil"
        unique_together = ("conseil", "inscription")

    def __str__(self):
        return f"{self.inscription.eleve} : {self.get_type_mention_display()}"


class DelegueClasse(models.Model):
    """Délégués d'élèves élus pour la classe."""
    class Role(models.TextChoices):
        TITULAIRE = "TITULAIRE", "Délégué(e) titulaire"
        SUPPLEANT = "SUPPLEANT", "Délégué(e) suppléant(e)"

    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name="delegues")
    annee_scolaire = models.ForeignKey("parametrage.AnneeScolaire", on_delete=models.CASCADE)
    eleve = models.ForeignKey("eleves.Eleve", on_delete=models.CASCADE, related_name="mandats_delegue")
    type_delegue = models.CharField(max_length=15, choices=Role.choices, default=Role.TITULAIRE)

    class Meta:
        verbose_name = "Délégué de classe"
        verbose_name_plural = "Délégués de classe"
        unique_together = ("classe", "annee_scolaire", "eleve")

    def __str__(self):
        return f"{self.eleve} ({self.get_type_delegue_display()} - {self.classe})"

