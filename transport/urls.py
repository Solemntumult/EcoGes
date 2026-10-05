from django.urls import path
from . import views

app_name = "transport"

urlpatterns = [
    path("", views.liste_lignes, name="lignes"),
]
