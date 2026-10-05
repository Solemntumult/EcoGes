from django.contrib import admin
from .models import Ouvrage, Exemplaire, Emprunt, PretManuel


class ExemplaireInline(admin.TabularInline):
    model = Exemplaire
    extra = 1


@admin.register(Ouvrage)
class OuvrageAdmin(admin.ModelAdmin):
    list_display = ("titre", "auteur", "categorie", "isbn", "emplacement")
    list_filter = ("categorie",)
    search_fields = ("titre", "auteur", "isbn")
    inlines = [ExemplaireInline]


@admin.register(Exemplaire)
class ExemplaireAdmin(admin.ModelAdmin):
    list_display = ("ouvrage", "code_barre", "etat", "disponible")
    list_filter = ("etat", "disponible")
    search_fields = ("code_barre", "ouvrage__titre")


@admin.register(Emprunt)
class EmpruntAdmin(admin.ModelAdmin):
    list_display = ("exemplaire", "eleve", "date_emprunt", "date_retour_prevue", "date_retour_effective")
    list_filter = ("date_emprunt", "date_retour_prevue")
    search_fields = ("eleve__nom", "eleve__prenoms", "exemplaire__ouvrage__titre")


@admin.register(PretManuel)
class PretManuelAdmin(admin.ModelAdmin):
    list_display = ("exemplaire", "inscription", "annee_scolaire", "caution_versee", "restitue")
    list_filter = ("annee_scolaire", "restitue")
    search_fields = ("inscription__eleve__nom", "inscription__eleve__prenoms")
