"""Signaux du module Paramétrage : liaison automatique du tronc commun.

Règle métier : une matière marquée « tronc commun » est automatiquement liée
à TOUTES les classes de son niveau (une liaison ``ClasseMatiereCoefficient``
par classe, coefficient par défaut 1, réglable ensuite par classe) :

- à la création d'une classe → toutes les matières tronc commun du niveau ;
- à la création (ou activation) d'une matière tronc commun → toutes les
  classes existantes du niveau.

Les liaisons ne sont jamais supprimées automatiquement : retirer une matière
d'une classe reste une action explicite (interface « Coefficients »).
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Classe, ClasseMatiereCoefficient, Matiere


@receiver(pre_save, sender=Matiere)
def memoriser_etat_tronc_commun(sender, instance, **kwargs):
    """Mémorise l'état précédent de ``tronc_commun`` (pour détecter une activation)."""
    if instance.pk:
        try:
            instance._tronc_commun_avant = Matiere.objects.get(pk=instance.pk).tronc_commun
        except Matiere.DoesNotExist:
            instance._tronc_commun_avant = False
    else:
        instance._tronc_commun_avant = False


@receiver(post_save, sender=Matiere)
def lier_matiere_tronc_commun(sender, instance, created, **kwargs):
    """Une matière tronc commun est liée à toutes les classes de son niveau."""
    if not instance.tronc_commun:
        return
    activee = created or not getattr(instance, "_tronc_commun_avant", False)
    if not activee:
        return
    for classe in Classe.objects.filter(niveau=instance.niveau):
        ClasseMatiereCoefficient.objects.get_or_create(classe=classe, matiere=instance)


@receiver(post_save, sender=Classe)
def lier_tronc_commun_nouvelle_classe(sender, instance, created, **kwargs):
    """À la création d'une classe, lie les matières tronc commun de son niveau."""
    if not created:
        return
    for matiere in Matiere.objects.filter(niveau=instance.niveau, tronc_commun=True):
        ClasseMatiereCoefficient.objects.get_or_create(classe=instance, matiere=matiere)
