from django.urls import path
from . import views

app_name = "bibliotheque"

urlpatterns = [
    path("", views.catalogue, name="catalogue"),
]
