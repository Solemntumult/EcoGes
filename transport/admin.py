from django.contrib import admin
from .models import LigneTransport, ArretTransport, InscriptionTransport


class ArretTransportInline(admin.TabularInline):
    model = ArretTransport
    extra = 2


@admin.register(LigneTransport)
class LigneTransportAdmin(admin.ModelAdmin):
    list_display = ("libelle", "chauffeur", "telephone_chauffeur", "immatriculation_vehicule", "capacite_places", "actif")
    list_filter = ("actif",)
    inlines = [ArretTransportInline]


@admin.register(InscriptionTransport)
class InscriptionTransportAdmin(admin.ModelAdmin):
    list_display = ("inscription", "ligne", "arret", "formule", "tarif_mensuel", "actif")
    list_filter = ("ligne", "formule", "actif")
    search_fields = ("inscription__eleve__nom", "inscription__eleve__prenoms")
