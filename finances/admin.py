from django.contrib import admin

from .models import (
    Echeance, Facture, FicheDePaie, ImputationPaiement, LigneFacture,
    Paiement, Recu, Remise,
)


@admin.register(Echeance)
class EcheanceAdmin(admin.ModelAdmin):
    list_display = ("inscription", "libelle", "montant_du", "date_echeance", "statut")
    list_filter = ("statut", "date_echeance", "type_frais")
    search_fields = ("inscription__eleve__nom", "inscription__eleve__matricule")


class ImputationInline(admin.TabularInline):
    model = ImputationPaiement
    extra = 1


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("inscription", "montant", "mode_paiement", "statut", "date_paiement", "encaisse_par")
    list_filter = ("mode_paiement", "statut", "date_paiement")
    search_fields = ("inscription__eleve__nom", "inscription__eleve__matricule", "reference")
    inlines = [ImputationInline]


class LigneFactureInline(admin.TabularInline):
    model = LigneFacture
    extra = 1


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ("numero", "inscription", "montant_total", "statut", "date_emission")
    list_filter = ("statut", "date_emission")
    readonly_fields = ("numero",)
    search_fields = ("numero", "inscription__eleve__nom", "inscription__eleve__matricule")
    inlines = [LigneFactureInline]


admin.site.register(Recu)
admin.site.register(Remise)


@admin.register(FicheDePaie)
class FicheDePaieAdmin(admin.ModelAdmin):
    list_display = ("numero", "personnel", "mois", "annee", "heures_total", "montant_brut", "statut", "date_paiement")
    list_filter = ("statut", "annee", "mois")
    readonly_fields = ("numero", "heures_total", "montant_brut")
    search_fields = ("numero", "personnel__nom", "personnel__prenoms")
