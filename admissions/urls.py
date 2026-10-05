from django.urls import path
from . import views

app_name = "admissions"

urlpatterns = [
    path("", views.liste_demandes, name="liste"),
]
