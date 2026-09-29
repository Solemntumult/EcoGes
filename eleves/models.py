from django.db import models

from parametrage.models import AnneeScolaire, Classe


class Eleve(models.Model):
    class Sexe(models.TextChoices):
        M = "M", "Masculin"
        F = "F", "Féminin"

    class Regime(models.TextChoices):
        INTERNE = "INTERNE", "Interne"
        EXTERNE = "EXTERNE", "Externe"
        DEMI_PENSIONNAIRE = "DEMI", "Demi-pensionnaire"

    class Statut(models.TextChoices):
        ACTIF = "ACTIF", "Actif"
        TRANSFERE = "TRANSFERE", "Transféré"
        RADIE = "RADIE", "Radié"
        DIPLOME = "DIPLOME", "Diplômé"

    matricule = models.CharField(max_length=20, unique=True, editable=False)
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=150)
    sexe = models.CharField(max_length=1, choices=Sexe.choices)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=150, blank=True)
    photo = models.ImageField(upload_to="eleves/photos/", blank=True, null=True)
    adresse = models.CharField(max_length=255, blank=True)
    regime = models.CharField(max_length=10, choices=Regime.choices, default=Regime.EXTERNE)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.ACTIF)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "prenoms"]

    def __str__(self):
        return f"{self.matricule} - {self.nom} {self.prenoms}"

    def save(self, *args, **kwargs):
        if not self.matricule:
            self.matricule = self._generer_matricule()
        super().save(*args, **kwargs)

    def photo_data_uri(self):
        """Data URI de la photo de l'élève (silhouette par défaut si absente).

        Les PDF (WeasyPrint) affichent les images de façon fiable via des data
        URIs — utilisé notamment sur la carte scolaire.
        """
        from parametrage.services import _data_uri

        if self.photo:
            data = _data_uri(self.photo)
            if data:
                return data
        # Silhouette par défaut (aucune photo fournie)
        from django.conf import settings
        chemin = settings.BASE_DIR / "static" / "img" / "silhouette.png"
        try:
            with open(chemin, "rb") as f:
                import base64
                return "data:image/png;base64," + base64.b64encode(f.read()).decode()
        except OSError:
            return ""

    def _generer_matricule(self):
        """Génère un matricule unique du type ELV-2026-00001."""
        from django.utils import timezone

        annee = timezone.now().year
        dernier = Eleve.objects.filter(matricule__startswith=f"ELV-{annee}-").order_by("-matricule").first()
        prochain_numero = 1
        if dernier:
            prochain_numero = int(dernier.matricule.split("-")[-1]) + 1
        return f"ELV-{annee}-{prochain_numero:05d}"


class Tuteur(models.Model):
    class LienParente(models.TextChoices):
        PERE = "PERE", "Père"
        MERE = "MERE", "Mère"
        TUTEUR = "TUTEUR", "Tuteur légal"
        AUTRE = "AUTRE", "Autre"

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="tuteurs")
    nom_complet = models.CharField(max_length=200)
    lien_parente = models.CharField(max_length=10, choices=LienParente.choices)
    telephone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    contact_urgence = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Tuteur / Parent"

    def __str__(self):
        return f"{self.nom_complet} ({self.get_lien_parente_display()}) - {self.eleve}"


class Inscription(models.Model):
    class StatutInscription(models.TextChoices):
        NOUVEAU = "NOUVEAU", "Nouvel élève"
        REDOUBLANT = "REDOUBLANT", "Redoublant"
        TRANSFERT = "TRANSFERT", "Transfert entrant"
        ANCIEN = "ANCIEN", "Ancien (réinscription)"

    class StatutActivite(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ANNULEE = "ANNULEE", "Annulée"
        TERMINEE = "TERMINEE", "Terminée"

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="inscriptions")
    classe = models.ForeignKey(Classe, on_delete=models.PROTECT, related_name="inscriptions")
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name="inscriptions")
    date_inscription = models.DateField(auto_now_add=True)
    statut_inscription = models.CharField(max_length=12, choices=StatutInscription.choices)
    statut = models.CharField(max_length=10, choices=StatutActivite.choices, default=StatutActivite.ACTIVE)
    decision_fin_annee = models.CharField(
        max_length=20,
        blank=True,
        help_text="Ex. Admis(e), Redouble, Exclu(e) — renseigné en fin d'année",
    )

    class Meta:
        unique_together = ("eleve", "annee_scolaire")
        ordering = ["-annee_scolaire", "classe"]

    def __str__(self):
        return f"{self.eleve} - {self.classe} ({self.annee_scolaire})"
