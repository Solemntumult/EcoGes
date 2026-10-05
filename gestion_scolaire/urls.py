"""
Configuration des URLs du projet Gestion Scolaire.

Expose l'interface d'administration Django ainsi que les interfaces métier
dédiées à chaque profil (connexion, secrétariat, comptabilité, enseignant,
direction, parents).
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Administration — Gestion Scolaire"
admin.site.site_title = "Gestion Scolaire"
admin.site.index_title = "Tableau de bord administrateur"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("comptes.urls")),
    path("parametrage/", include("parametrage.urls")),
    path("eleves/", include("eleves.urls")),
    path("personnel/", include("personnel.urls")),
    path("evaluations/", include("evaluations.urls")),
    path("finances/", include("finances.urls")),
    path("documents/", include("documents.urls")),
    path("statistiques/", include("statistiques.urls")),
    path("portail/", include("portail.urls")),
    path("vie-scolaire/", include("viescolaire.urls")),
    path("cahier-texte/", include("cahier_texte.urls")),
    path("communication/", include("communication.urls")),
    path("cantine/", include("cantine.urls")),
    path("sante/", include("sante.urls")),
    path("transport/", include("transport.urls")),
    path("bibliotheque/", include("bibliotheque.urls")),
    path("admissions/", include("admissions.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
