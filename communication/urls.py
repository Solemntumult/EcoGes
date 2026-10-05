from django.urls import path
from . import views

app_name = "communication"

urlpatterns = [
    path("messagerie/", views.messagerie, name="messagerie"),
    path("messagerie/<int:conversation_id>/", views.conversation_detail, name="conversation_detail"),
]
