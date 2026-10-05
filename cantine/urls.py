from django.urls import path
from . import views

app_name = "cantine"

urlpatterns = [
    path("", views.menu_actuel, name="menu"),
]
