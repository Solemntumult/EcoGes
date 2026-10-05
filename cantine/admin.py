from django.contrib import admin
from .models import InscriptionCantine, PresenceRepas, MenuSemaine


@admin.register(InscriptionCantine)
class InscriptionCantineAdmin(admin.ModelAdmin):
    list_display = ("inscription", "formule", "tarif", "allergies", "actif")
    list_filter = ("formule", "actif")
    search_fields = ("inscription__eleve__nom", "inscription__eleve__prenoms", "allergies")


@admin.register(PresenceRepas)
class PresenceRepasAdmin(admin.ModelAdmin):
    list_display = ("inscription_cantine", "date", "present", "heure_passage")
    list_filter = ("date", "present")


@admin.register(MenuSemaine)
class MenuSemaineAdmin(admin.ModelAdmin):
    list_display = ("date_debut", "date_fin")
