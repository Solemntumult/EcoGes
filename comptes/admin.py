from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import JournalActivite, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "get_full_name", "role", "email", "actif", "is_active")
    list_filter = ("role", "actif", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Informations métier", {"fields": ("role", "telephone", "actif")}),
    )


@admin.register(JournalActivite)
class JournalActiviteAdmin(admin.ModelAdmin):
    list_display = ("date_heure", "utilisateur", "action", "objet_concerne")
    list_filter = ("date_heure",)
    search_fields = ("action", "objet_concerne", "utilisateur__username")
    readonly_fields = [f.name for f in JournalActivite._meta.fields]
