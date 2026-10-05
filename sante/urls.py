from django.urls import path
from . import views

app_name = "sante"

urlpatterns = [
    path("", views.registre, name="registre"),
]
