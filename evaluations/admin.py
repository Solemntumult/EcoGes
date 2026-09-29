from django.contrib import admin

from .models import Bulletin, Evaluation, Note


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("matiere", "classe", "periode", "type_evaluation", "date", "saisie_verrouillee")
    list_filter = ("periode", "classe", "type_evaluation", "saisie_verrouillee")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("inscription", "evaluation", "valeur", "saisi_par")
    list_filter = ("evaluation__periode", "evaluation__matiere")
    search_fields = ("inscription__eleve__nom", "inscription__eleve__matricule")


@admin.register(Bulletin)
class BulletinAdmin(admin.ModelAdmin):
    list_display = ("inscription", "periode", "est_annuel", "moyenne_generale", "rang")
    list_filter = ("periode", "est_annuel")
