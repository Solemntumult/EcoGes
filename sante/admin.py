from django.contrib import admin
from .models import FicheMedicale, Vaccination, PassageInfirmerie


class VaccinationInline(admin.TabularInline):
    model = Vaccination
    extra = 1


@admin.register(FicheMedicale)
class FicheMedicaleAdmin(admin.ModelAdmin):
    list_display = ("eleve", "groupe_sanguin", "medecin_traitant", "telephone_medecin")
    search_fields = ("eleve__nom", "eleve__prenoms", "allergies", "affections_chroniques")
    list_filter = ("groupe_sanguin",)
    inlines = [VaccinationInline]


@admin.register(PassageInfirmerie)
class PassageInfirmerieAdmin(admin.ModelAdmin):
    list_display = ("eleve", "motif", "issue", "parent_prevenu", "date_heure_entree", "enregistre_par")
    list_filter = ("issue", "parent_prevenu", "date_heure_entree")
    search_fields = ("eleve__nom", "eleve__prenoms", "motif")
    date_hierarchy = "date_heure_entree"
