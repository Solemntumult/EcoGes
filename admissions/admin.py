from django.contrib import admin
from .models import DemandeAdmission, PieceJointeAdmission, TestAdmission


class PieceJointeInline(admin.TabularInline):
    model = PieceJointeAdmission
    extra = 1


class TestAdmissionInline(admin.TabularInline):
    model = TestAdmission
    extra = 1


@admin.register(DemandeAdmission)
class DemandeAdmissionAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenoms", "niveau_souhaite", "nom_parent", "telephone_parent", "statut", "date_soumission")
    list_filter = ("statut", "niveau_souhaite", "annee_scolaire")
    search_fields = ("nom", "prenoms", "nom_parent", "telephone_parent")
    inlines = [PieceJointeInline, TestAdmissionInline]
    date_hierarchy = "date_soumission"


@admin.register(TestAdmission)
class TestAdmissionAdmin(admin.ModelAdmin):
    list_display = ("demande", "matiere", "date_test", "note", "note_sur", "admis")
    list_filter = ("matiere", "admis", "date_test")
