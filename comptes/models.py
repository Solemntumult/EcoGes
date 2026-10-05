from django.contrib.auth.models import AbstractUser
from django.db import models


class Utilisateur(AbstractUser):
    """Utilisateur du système, étendu par un rôle métier.

    On s'appuie sur le modèle Django natif (mot de passe hashé,
    gestion des sessions, permissions) et on ajoute uniquement
    les champs propres au contexte scolaire.
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur / Direction"
        CENSEUR = "CENSEUR", "Censeur / Direction des études"
        SECRETARIAT = "SECRETARIAT", "Secrétariat"
        COMPTABLE = "COMPTABLE", "Comptable / Caissier(ère)"
        ENSEIGNANT = "ENSEIGNANT", "Enseignant"
        PARENT = "PARENT", "Parent / Élève"
        SURVEILLANT = "SURVEILLANT", "Surveillant général / Vie scolaire"
        INFIRMIER = "INFIRMIER", "Infirmerie / Santé scolaire"
        RESPONSABLE_CANTINE = "RESPONSABLE_CANTINE", "Responsable cantine / Intendance"
        SUPERADMIN = "SUPERADMIN", "Super-administrateur technique"

    role = models.CharField(max_length=25, choices=Role.choices, default=Role.SECRETARIAT)
    telephone = models.CharField(max_length=30, blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    # Verrouillage de compte après tentatives de connexion échouées (UC-02)
    tentatives_connexion = models.PositiveSmallIntegerField(default=0)
    bloque_jusqua = models.DateTimeField(null=True, blank=True)

    @property
    def est_bloque(self):
        from django.utils import timezone
        return bool(self.bloque_jusqua and self.bloque_jusqua > timezone.now())

    @property
    def role_label(self):
        return self.get_role_display()

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"


class JournalActivite(models.Model):
    """Journal des actions sensibles (traçabilité)."""

    utilisateur = models.ForeignKey(
        Utilisateur, on_delete=models.SET_NULL, null=True, related_name="actions"
    )
    action = models.CharField(max_length=255)
    objet_concerne = models.CharField(max_length=255, blank=True)
    detail = models.TextField(blank=True)
    date_heure = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_heure"]
        verbose_name = "Journal d'activité"
        verbose_name_plural = "Journal d'activité"

    def __str__(self):
        return f"[{self.date_heure:%d/%m/%Y %H:%M}] {self.utilisateur} - {self.action}"
