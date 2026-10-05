from django.contrib import admin
from .models import (
    Bulletin,
    Evaluation,
    Note,
    CompetenceAPC,
    EvaluationCompetence,
    ConseilDeClasse,
    MentionConseil,
    DelegueClasse,
    InscriptionGarderie,
)


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


@admin.register(CompetenceAPC)
class CompetenceAPCAdmin(admin.ModelAdmin):
    list_display = ("code", "libelle", "matiere", "niveau")
    list_filter = ("niveau", "matiere")
    search_fields = ("code", "libelle")


@admin.register(EvaluationCompetence)
class EvaluationCompetenceAdmin(admin.ModelAdmin):
    list_display = ("inscription", "competence", "periode", "niveau_maitrise")
    list_filter = ("niveau_maitrise", "periode")
    search_fields = ("inscription__eleve__nom", "competence__libelle")


class MentionConseilInline(admin.TabularInline):
    model = MentionConseil
    extra = 0


@admin.register(ConseilDeClasse)
class ConseilDeClasseAdmin(admin.ModelAdmin):
    list_display = ("classe", "periode", "date_conseil", "president")
    list_filter = ("periode", "classe")
    inlines = [MentionConseilInline]


@admin.register(MentionConseil)
class MentionConseilAdmin(admin.ModelAdmin):
    list_display = ("conseil", "inscription", "type_mention")
    list_filter = ("type_mention", "conseil__periode")
    search_fields = ("inscription__eleve__nom",)


@admin.register(DelegueClasse)
class DelegueClasseAdmin(admin.ModelAdmin):
    list_display = ("eleve", "classe", "annee_scolaire", "type_delegue")
    list_filter = ("annee_scolaire", "classe", "type_delegue")
    search_fields = ("eleve__nom", "eleve__prenoms")


@admin.register(InscriptionGarderie)
class InscriptionGarderieAdmin(admin.ModelAdmin):
    list_display = ("eleve", "annee_scolaire", "formule", "tarif_mensuel", "actif")
    list_filter = ("annee_scolaire", "formule", "actif")
    search_fields = ("eleve__nom", "eleve__prenoms")
