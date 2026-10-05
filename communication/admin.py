from django.contrib import admin
from .models import ConfigurationSMS, MessageSMS, CampagneSMS, Conversation, MessageInterne


@admin.register(ConfigurationSMS)
class ConfigurationSMSAdmin(admin.ModelAdmin):
    list_display = ("fournisseur", "sender_id", "solde_sms", "actif")


@admin.register(MessageSMS)
class MessageSMSAdmin(admin.ModelAdmin):
    list_display = ("destinataire_telephone", "eleve", "statut", "date_envoi", "cout")
    list_filter = ("statut", "date_envoi")
    search_fields = ("destinataire_telephone", "contenu", "eleve__nom")


@admin.register(CampagneSMS)
class CampagneSMSAdmin(admin.ModelAdmin):
    list_display = ("titre", "cible", "nb_destinataires", "date_envoi", "envoyee_par")
    list_filter = ("cible", "date_envoi")


class MessageInterneInline(admin.TabularInline):
    model = MessageInterne
    extra = 1


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("sujet", "eleve", "date_creation", "date_dernier_message", "cloturee")
    list_filter = ("cloturee", "date_creation")
    search_fields = ("sujet", "eleve__nom")
    inlines = [MessageInterneInline]
