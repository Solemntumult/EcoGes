from django.contrib import admin
from .models import Appel, JustificatifAbsence, IncidentDisciplinaire, Sanction, Retenue, ConseilDiscipline


@admin.register(Appel)
class AppelAdmin(admin.ModelAdmin):
    list_display = ("inscription", "date", "creneau", "statut", "justifie", "enregistre_par")
    list_filter = ("statut", "justifie", "date", "inscription__classe")
    search_fields = ("inscription__eleve__nom", "inscription__eleve__prenoms", "inscription__eleve__matricule")
    date_hierarchy = "date"


@admin.register(JustificatifAbsence)
class JustificatifAbsenceAdmin(admin.ModelAdmin):
    list_display = ("appel", "statut", "date_depot", "valide_par", "date_validation")
    list_filter = ("statut", "date_depot")
    search_fields = ("appel__inscription__eleve__nom", "motif")


@admin.register(IncidentDisciplinaire)
class IncidentDisciplinaireAdmin(admin.ModelAdmin):
    list_display = ("eleve", "date_incident", "type_incident", "gravite", "signale_par")
    list_filter = ("gravite", "date_incident")
    search_fields = ("eleve__nom", "eleve__prenoms", "type_incident")


class RetenueInline(admin.StackedInline):
    model = Retenue
    extra = 0


@admin.register(Sanction)
class SanctionAdmin(admin.ModelAdmin):
    list_display = ("eleve", "type_sanction", "date_decision", "date_debut", "date_fin", "decide_par")
    list_filter = ("type_sanction", "date_decision")
    search_fields = ("eleve__nom", "eleve__prenoms", "motif")
    inlines = [RetenueInline]


@admin.register(Retenue)
class RetenueAdmin(admin.ModelAdmin):
    list_display = ("sanction", "date", "heure_debut", "heure_fin", "salle", "surveillant", "effectuee")
    list_filter = ("effectuee", "date")


@admin.register(ConseilDiscipline)
class ConseilDisciplineAdmin(admin.ModelAdmin):
    list_display = ("eleve", "annee_scolaire", "date_conseil", "convocation_envoyee")
    list_filter = ("annee_scolaire", "convocation_envoyee")
    search_fields = ("eleve__nom", "eleve__prenoms", "motif")
