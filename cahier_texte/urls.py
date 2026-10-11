from django.urls import path
from . import views

app_name = "cahier_texte"

urlpatterns = [
    path("", views.index, name="index"),
    path("seances/creer/", views.seance_creer, name="seance_creer"),
    path("seances/<int:pk>/modifier/", views.seance_modifier, name="seance_modifier"),
    path("seances/<int:pk>/supprimer/", views.seance_supprimer, name="seance_supprimer"),
    path("devoirs/creer/", views.devoir_creer, name="devoir_creer"),
    path("devoirs/<int:pk>/supprimer/", views.devoir_supprimer, name="devoir_supprimer"),
]
