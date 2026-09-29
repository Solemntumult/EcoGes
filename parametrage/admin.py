from django.contrib import admin

from .models import (
    AnneeScolaire, BaremeEvaluation, Classe, ClasseMatiereCoefficient,
    Etablissement, GrilleTarifaire, HoraireJournalier, LogoEtablissement,
    Matiere, Niveau, PauseHoraire, Periode, Serie, TypeFrais,
)

admin.site.register(AnneeScolaire)
admin.site.register(Periode)
admin.site.register(Serie)
admin.site.register(ClasseMatiereCoefficient)
admin.site.register(TypeFrais)
admin.site.register(GrilleTarifaire)
admin.site.register(BaremeEvaluation)
admin.site.register(HoraireJournalier)
admin.site.register(PauseHoraire)


class ClasseMatiereCoefficientInline(admin.TabularInline):
    model = ClasseMatiereCoefficient
    extra = 1


@admin.register(Niveau)
class NiveauAdmin(admin.ModelAdmin):
    list_display = ("libelle", "cycle", "serie", "ordre")
    list_filter = ("cycle", "serie")


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ("libelle", "niveau", "annee_scolaire", "effectif_actuel")
    list_filter = ("annee_scolaire", "niveau__cycle")
    inlines = [ClasseMatiereCoefficientInline]


@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ("libelle", "niveau", "tronc_commun")
    list_filter = ("niveau__cycle", "niveau__serie", "tronc_commun")
    inlines = [ClasseMatiereCoefficientInline]


class LogoEtablissementInline(admin.TabularInline):
    model = LogoEtablissement
    extra = 1


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    inlines = [LogoEtablissementInline]
    fieldsets = (
        ("Identité", {"fields": ("nom_officiel", "sigle", "devise", "logo",)}),
        ("Coordonnées", {"fields": (
            "adresse", "ville", "commune", "pays", "boite_postale",
            "telephone", "email", "site_web",
        )}),
        ("Statut légal", {"fields": (
            "statut_juridique", "categorie", "ministere_tutelle",
            "numero_arrete", "date_arrete", "code_etablissement",
            "annee_creation", "fondateur", "ifu", "rccm",
        )}),
        ("Signataires (signature manuscrite après impression)", {"fields": (
            "nom_directeur", "nom_censeur", "nom_comptable",
        )}),
        ("Mentions légales & fiscalité", {"fields": (
            "mentions_legales", "regime_fiscal", "formule_certification",
        )}),
    )
