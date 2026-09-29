from django.contrib import admin

from .models import DocumentAdministratif, ModeleDocument

admin.site.register(ModeleDocument)


@admin.register(DocumentAdministratif)
class DocumentAdministratifAdmin(admin.ModelAdmin):
    list_display = ("type_document", "eleve", "genere_par", "date_generation")
    list_filter = ("type_document", "date_generation")
    search_fields = ("eleve__nom", "eleve__matricule")
