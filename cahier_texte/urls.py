from django.urls import path
from . import views

app_name = "cahier_texte"

urlpatterns = [
    path("", views.index, name="index"),
]
