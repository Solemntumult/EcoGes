from django.urls import path
from . import views

app_name = "viescolaire"

urlpatterns = [
    path("", views.tableau_bord, name="tableau_bord"),
    path("appel/classe/<int:classe_id>/", views.feuille_appel, name="feuille_appel"),
    path("appel/pointer/<int:inscription_id>/", views.pointer_presence, name="pointer_presence"),
]
