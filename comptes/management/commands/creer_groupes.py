"""Commande : créer les groupes de permissions Django par rôle (UC-04).

Usage :
    python manage.py creer_groupes

À lancer après la migration initiale. Les groupes sont idempotents
(ré-exécutables sans risque).
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


# (nom du groupe, liste d'apps dont le groupe obtient toutes les permissions)
GROUPES = {
    "Administration": ["comptes", "parametrage", "eleves", "personnel", "evaluations", "finances", "documents"],
    "Super administration": ["comptes", "parametrage", "eleves", "personnel", "evaluations", "finances", "documents"],
    "Censeurs": ["parametrage", "eleves", "personnel", "evaluations", "documents"],
    "Secrétariat": ["eleves", "documents"],
    "Comptabilité": ["finances", "eleves"],
    "Enseignants": ["evaluations"],
    "Parents": [],
}


class Command(BaseCommand):
    help = "Crée les groupes de permissions par rôle (UC-04)."

    def handle(self, *args, **options):
        for nom, apps in GROUPES.items():
            groupe, cree = Group.objects.get_or_create(name=nom)
            permissions = Permission.objects.none()
            for app in apps:
                cts = ContentType.objects.filter(app_label=app)
                permissions = permissions | Permission.objects.filter(content_type__in=cts)
            groupe.permissions.set(permissions)
            self.stdout.write(self.style.SUCCESS(f"Groupe « {nom} » : {permissions.count()} permissions"))
        self.stdout.write(self.style.SUCCESS("Groupes créés/mis à jour avec succès."))
