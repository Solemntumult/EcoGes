from django.db import models

from eleves.models import Eleve


class ModeleDocument(models.Model):
    """Gabarit personnalisable (en-tête, logo, mentions légales) par type de document."""

    class TypeDocument(models.TextChoices):
        CERTIFICAT_SCOLARITE = "CERTIFICAT_SCOLARITE", "Certificat de scolarité"
        ATTESTATION_REUSSITE = "ATTESTATION_REUSSITE", "Attestation de réussite"
        RELEVE_NOTES = "RELEVE_NOTES", "Relevé de notes"
        LISTE_CLASSE = "LISTE_CLASSE", "Liste de classe"
        CONVOCATION = "CONVOCATION", "Convocation"
        AVIS_RELANCE = "AVIS_RELANCE", "Avis de relance"
        CARTE_SCOLAIRE = "CARTE_SCOLAIRE", "Carte scolaire"

    type_document = models.CharField(max_length=25, choices=TypeDocument.choices, unique=True)
    en_tete_html = models.TextField(blank=True)
    pied_page_html = models.TextField(blank=True)
    logo = models.ImageField(upload_to="modeles/logos/", blank=True, null=True)
    mentions_legales = models.TextField(blank=True)

    def __str__(self):
        return self.get_type_document_display()


# Préfixes de numérotation par type de document (traçabilité anti-fraude)
PREFIXES_NUMEROS = {
    "CERTIFICAT_SCOLARITE": "CER",
    "ATTESTATION_REUSSITE": "ATT",
    "RELEVE_NOTES": "REL",
    "LISTE_CLASSE": "LIS",
    "CONVOCATION": "COU",
    "AVIS_RELANCE": "AVR",
    "CARTE_SCOLAIRE": "CAR",
}


class DocumentAdministratif(models.Model):
    type_document = models.CharField(max_length=25, choices=ModeleDocument.TypeDocument.choices)
    numero = models.CharField(max_length=30, unique=True, editable=False, blank=True, null=True,
                              help_text="N° d'enregistrement (ex. CER-2026-000001)")
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name="documents", null=True, blank=True
    )
    genere_par = models.ForeignKey(
        "comptes.Utilisateur", on_delete=models.SET_NULL, null=True, related_name="documents_generes"
    )
    date_generation = models.DateTimeField(auto_now_add=True)
    fichier_pdf = models.FileField(upload_to="documents_administratifs/", blank=True, null=True)

    class Meta:
        ordering = ["-date_generation"]

    def __str__(self):
        cible = self.eleve if self.eleve else "N/A"
        numero = f"[{self.numero}] " if self.numero else ""
        return f"{numero}{self.get_type_document_display()} - {cible} ({self.date_generation:%d/%m/%Y})"

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generer_numero()
        super().save(*args, **kwargs)

    def _generer_numero(self):
        from django.utils import timezone

        prefixe = PREFIXES_NUMEROS.get(self.type_document, "DOC")
        annee = timezone.now().year
        dernier = DocumentAdministratif.objects.filter(
            numero__startswith=f"{prefixe}-{annee}-"
        ).order_by("-numero").first()
        prochain = int(dernier.numero.split("-")[-1]) + 1 if dernier else 1
        return f"{prefixe}-{annee}-{prochain:06d}"
