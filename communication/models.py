from django.db import models
from django.conf import settings
from eleves.models import Eleve


class ConfigurationSMS(models.Model):
    """Configuration de la passerelle SMS (ex. Lighty, Africa's Talking, Twilio)."""
    class Fournisseur(models.TextChoices):
        LIGHTY = "LIGHTY", "Lighty SMS (Bénin)"
        AFRICASTALKING = "AFRICASTALKING", "Africa's Talking"
        TWILIO = "TWILIO", "Twilio"
        GENERIQUE = "GENERIQUE", "Passerelle HTTP Générique"

    fournisseur = models.CharField(max_length=20, choices=Fournisseur.choices, default=Fournisseur.LIGHTY)
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255, blank=True)
    sender_id = models.CharField(max_length=11, help_text="Nom d'expéditeur affiché (max 11 caractères)")
    solde_sms = models.PositiveIntegerField(default=0)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Configuration SMS"
        verbose_name_plural = "Configurations SMS"

    def __str__(self):
        return f"{self.get_fournisseur_display()} ({self.sender_id}) - Solde : {self.solde_sms}"


class MessageSMS(models.Model):
    """Historique des SMS individuels envoyés."""
    class Statut(models.TextChoices):
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        ENVOYE = "ENVOYE", "Envoyé avec succès"
        ECHOUE = "ECHOUE", "Échec d'envoi"

    destinataire_telephone = models.CharField(max_length=30)
    eleve = models.ForeignKey(Eleve, on_delete=models.SET_NULL, null=True, blank=True, related_name="sms_envoyes")
    contenu = models.TextField()
    statut = models.CharField(max_length=15, choices=Statut.choices, default=Statut.EN_ATTENTE)
    date_envoi = models.DateTimeField(auto_now_add=True)
    reponse_passerelle = models.CharField(max_length=255, blank=True)
    cout = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = "Message SMS"
        verbose_name_plural = "Messages SMS"
        ordering = ["-date_envoi"]
        indexes = [
            models.Index(fields=["statut", "date_envoi"]),
            models.Index(fields=["destinataire_telephone"]),
        ]

    def __str__(self):
        return f"SMS vers {self.destinataire_telephone} ({self.get_statut_display()})"


class CampagneSMS(models.Model):
    """Envoi groupé de SMS (ex. relances, alertes générales, réunions de parents)."""
    class Cible(models.TextChoices):
        TOUS = "TOUS", "Tous les parents"
        CLASSE = "CLASSE", "Par classe"
        NIVEAU = "NIVEAU", "Par niveau"
        IMPAYES = "IMPAYES", "Parents ayant des impayés"

    titre = models.CharField(max_length=150)
    cible = models.CharField(max_length=15, choices=Cible.choices)
    contenu = models.TextField(help_text="Texte du SMS (limité à 160 caractères recommandé)")
    nb_destinataires = models.PositiveIntegerField(default=0)
    date_envoi = models.DateTimeField(auto_now_add=True)
    envoyee_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    class Meta:
        verbose_name = "Campagne SMS"
        verbose_name_plural = "Campagnes SMS"
        ordering = ["-date_envoi"]

    def __str__(self):
        return f"{self.titre} ({self.get_cible_display()})"


class Conversation(models.Model):
    """Fil de discussion sécurisé (ex. Parent ↔ Professeur principal ↔ Direction)."""
    sujet = models.CharField(max_length=200)
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name="conversations")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_dernier_message = models.DateTimeField(auto_now=True)
    cloturee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Conversation"
        verbose_name_plural = "Conversations"
        ordering = ["-date_dernier_message"]

    def __str__(self):
        return f"{self.sujet} (Élève : {self.eleve})"


class MessageInterne(models.Model):
    """Message au sein d'une conversation."""
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contenu = models.TextField()
    date_envoi = models.DateTimeField(auto_now_add=True)
    piece_jointe = models.FileField(upload_to="communication/pieces/", blank=True, null=True)
    lu = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Message interne"
        verbose_name_plural = "Messages internes"
        ordering = ["date_envoi"]
        indexes = [
            models.Index(fields=["conversation", "date_envoi"]),
        ]

    def __str__(self):
        return f"De {self.auteur} le {self.date_envoi.strftime('%d/%m %H:%M')}"
