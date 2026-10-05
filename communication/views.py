from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from comptes.mixins import roles_requis
from .models import Conversation, MessageInterne, CampagneSMS, MessageSMS

ROLES_COM = ["ADMIN", "SUPERADMIN", "CENSEUR", "SECRETARIAT", "ENSEIGNANT", "PARENT"]


@login_required
@roles_requis(ROLES_COM)
def messagerie(request):
    """Liste des conversations de l'utilisateur."""
    conversations = Conversation.objects.all()[:20]
    return render(request, "communication/messagerie.html", {"conversations": conversations})


@login_required
@roles_requis(ROLES_COM)
def conversation_detail(request, conversation_id):
    """Fil de discussion et envoi de message."""
    conversation = get_object_or_404(Conversation, pk=conversation_id)
    if request.method == "POST":
        contenu = request.POST.get("contenu")
        if contenu:
            MessageInterne.objects.create(
                conversation=conversation,
                auteur=request.user,
                contenu=contenu,
            )
            messages.success(request, "Message envoyé.")
            return redirect("communication:conversation_detail", conversation_id=conversation.id)

    return render(
        request,
        "communication/conversation_detail.html",
        {
            "conversation": conversation,
            "messages_liste": conversation.messages.select_related("auteur").all(),
        },
    )
