from django.contrib import admin
from .models import SeanceCours, DevoirMaison


class DevoirMaisonInline(admin.StackedInline):
    model = DevoirMaison
    extra = 0


@admin.register(SeanceCours)
class SeanceCoursAdmin(admin.ModelAdmin):
    list_display = ("affectation", "date", "creneau", "titre_chapitre")
    list_filter = ("date", "affectation__classe", "affectation__matiere")
    search_fields = ("titre_chapitre", "contenu_dispense", "affectation__enseignant__nom")
    inlines = [DevoirMaisonInline]
    date_hierarchy = "date"


@admin.register(DevoirMaison)
class DevoirMaisonAdmin(admin.ModelAdmin):
    list_display = ("titre", "affectation", "date_prescription", "date_limite", "est_note")
    list_filter = ("est_note", "date_limite", "affectation__classe")
    search_fields = ("titre", "consignes")
