from django.db import models
from parametrage.models import AnneeScolaire, Niveau


class DemandeAdmission(models.Model):
    """Candidature ou pré-inscription en ligne d'un nouvel élève."""
    class Statut(models.TextChoices):
        RECUE = "RECUE", "Dossier reçu"
        EN_EXAMEN = "EN_EXAMEN", "En cours d'examen"
        TEST_PROGRAMME = "TEST_PROGRAMME", "Convoqué au test d'entrée"
        ADMIS = "ADMIS", "Admis(e)"
        REFUSE = "REFUSE", "Non retenu(e)"
        INSCRIT = "INSCRIT", "Inscription définitive validée"

    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE)
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=150)
    sexe = models.CharField(max_length=1, choices=[("M", "Masculin"), ("F", "Féminin")])
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=150, blank=True)
    niveau_souhaite = models.ForeignKey(Niveau, on_delete=models.CASCADE)
    etablissement_origine = models.CharField(max_length=200, blank=True)
    classe_precedente = models.CharField(max_length=50, blank=True)
    nom_parent = models.CharField(max_length=200)
    telephone_parent = models.CharField(max_length=30)
    email_parent = models.EmailField(blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.RECUE)
    date_soumission = models.DateTimeField(auto_now_add=True)
    observations_direction = models.TextField(blank=True)

    class Meta:
        verbose_name = "Demande d'admission"
        verbose_name_plural = "Demandes d'admission"
        ordering = ["-date_soumission"]
        indexes = [
            models.Index(fields=["statut", "date_soumission"]),
        ]

    def __str__(self):
        return f"{self.nom} {self.prenoms} ({self.niveau_souhaite}) - {self.get_statut_display()}"


class PieceJointeAdmission(models.Model):
    """Document justificatif téléversé lors de la candidature."""
    class TypePiece(models.TextChoices):
        ACTE_NAISSANCE = "ACTE", "Acte de naissance"
        BULLETIN = "BULLETIN", "Dernier bulletin scolaire"
        CERTIFICAT_SCOLARITE = "CERTIF", "Certificat de scolarité / Radiation"
        PHOTO = "PHOTO", "Photo d'identité"
        AUTRE = "AUTRE", "Autre pièce"

    demande = models.ForeignKey(DemandeAdmission, on_delete=models.CASCADE, related_name="pieces_jointes")
    type_piece = models.CharField(max_length=15, choices=TypePiece.choices)
    fichier = models.FileField(upload_to="admissions/dossiers/")
    verifie = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Pièce justificative d'admission"
        verbose_name_plural = "Pièces justificatives d'admission"

    def __str__(self):
        return f"{self.get_type_piece_display()} - {self.demande.nom}"


class TestAdmission(models.Model):
    """Évaluation ou test de niveau pour les nouveaux candidats."""
    demande = models.ForeignKey(DemandeAdmission, on_delete=models.CASCADE, related_name="tests")
    date_test = models.DateField()
    matiere = models.CharField(max_length=100, help_text="Ex. Français, Mathématiques")
    note = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    note_sur = models.DecimalField(max_digits=4, decimal_places=2, default=20.00)
    appreciation = models.CharField(max_length=255, blank=True)
    admis = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Test d'admission"
        verbose_name_plural = "Tests d'admission"

    def __str__(self):
        return f"Test {self.matiere} : {self.demande.nom} ({self.note}/{self.note_sur})"
