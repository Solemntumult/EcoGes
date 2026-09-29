"""Signaux du module Évaluations : traçabilité des notes après verrouillage."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from comptes.context_user import get_current_user

from .models import Note, NoteModification


@receiver(pre_save, sender=Note)
def memoriser_ancienne_valeur(sender, instance, **kwargs):
    """Stocke l'ancienne valeur de la note avant enregistrement."""
    if instance.pk:
        try:
            instance._ancienne_valeur = Note.objects.get(pk=instance.pk).valeur
        except Note.DoesNotExist:
            instance._ancienne_valeur = None
    else:
        instance._ancienne_valeur = None


@receiver(post_save, sender=Note)
def tracer_modification_note(sender, instance, created, **kwargs):
    """Journalise toute modification d'une note appartenant à une évaluation verrouillée."""
    ancienne = getattr(instance, "_ancienne_valeur", None)
    if created or not instance.evaluation.saisie_verrouillee:
        return
    if ancienne is not None and ancienne != instance.valeur:
        utilisateur = get_current_user()
        NoteModification.objects.create(
            note=instance,
            modifie_par=utilisateur,
            ancienne_valeur=ancienne,
            nouvelle_valeur=instance.valeur,
        )
        if utilisateur is not None:
            from comptes.services import journaliser
            journaliser(
                utilisateur, "Modification de note verrouillée", "Note",
                f"{instance.inscription.eleve} — {instance.evaluation} : "
                f"{ancienne} → {instance.valeur}",
            )
