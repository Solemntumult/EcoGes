from django.contrib import admin

from .models import Affectation, CreneauEmploiDuTemps, Personnel


@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenoms", "fonction", "telephone", "actif")
    list_filter = ("fonction", "actif")
    search_fields = ("nom", "prenoms")


admin.site.register(Affectation)
admin.site.register(CreneauEmploiDuTemps)
