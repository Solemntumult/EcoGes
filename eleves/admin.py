from django.contrib import admin

from .models import Eleve, Inscription, Tuteur


class TuteurInline(admin.TabularInline):
    model = Tuteur
    extra = 1


@admin.register(Eleve)
class EleveAdmin(admin.ModelAdmin):
    list_display = ("matricule", "nom", "prenoms", "sexe", "statut")
    list_filter = ("statut", "sexe", "regime")
    search_fields = ("matricule", "nom", "prenoms")
    readonly_fields = ("matricule",)
    inlines = [TuteurInline]


@admin.register(Inscription)
class InscriptionAdmin(admin.ModelAdmin):
    list_display = ("eleve", "classe", "annee_scolaire", "statut_inscription", "statut")
    list_filter = ("annee_scolaire", "classe", "statut", "statut_inscription")
    search_fields = ("eleve__nom", "eleve__prenoms", "eleve__matricule")
