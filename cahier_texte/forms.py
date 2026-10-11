"""Formulaires du module Cahier de textes."""

from django import forms
from .models import SeanceCours, DevoirMaison
from personnel.models import Affectation


class SeanceCoursForm(forms.ModelForm):
    """Formulaire de saisie d'une séance de cours."""

    class Meta:
        model = SeanceCours
        fields = [
            "affectation",
            "date",
            "creneau",
            "heures",
            "titre_chapitre",
            "contenu_dispense",
            "objectifs_vises",
            "statut",
            "motif_statut",
            "date_report",
            "fichier_support",
        ]
        widgets = {
            "affectation": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "creneau": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: 08:00 - 10:00"}),
            "heures": forms.NumberInput(attrs={"class": "form-control", "step": "0.5", "min": "0.5"}),
            "titre_chapitre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Titre du chapitre / leçon"}),
            "contenu_dispense": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Notions, cours, exercices traités..."}),
            "objectifs_vises": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Objectifs pédagogiques..."}),
            "statut": forms.Select(attrs={"class": "form-select"}),
            "motif_statut": forms.TextInput(attrs={"class": "form-control", "placeholder": "Raison si annulé ou reporté"}),
            "date_report": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "fichier_support": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user and getattr(user, "role", None) == "ENSEIGNANT":
            self.fields["affectation"].queryset = Affectation.objects.filter(
                personnel__utilisateur=user
            ).select_related("classe", "matiere")
        else:
            self.fields["affectation"].queryset = Affectation.objects.select_related(
                "classe", "matiere", "personnel"
            ).all()


class DevoirMaisonForm(forms.ModelForm):
    """Formulaire de prescription d'un devoir à domicile."""

    class Meta:
        model = DevoirMaison
        fields = [
            "affectation",
            "titre",
            "date_prescription",
            "date_limite",
            "consignes",
            "est_note",
            "bareme",
            "fichier_sujet",
        ]
        widgets = {
            "affectation": forms.Select(attrs={"class": "form-select"}),
            "titre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Intitulé du devoir..."}),
            "date_prescription": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "date_limite": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "consignes": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Consignes de travail..."}),
            "est_note": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "bareme": forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "fichier_sujet": forms.FileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if user and getattr(user, "role", None) == "ENSEIGNANT":
            self.fields["affectation"].queryset = Affectation.objects.filter(
                personnel__utilisateur=user
            ).select_related("classe", "matiere")
        else:
            self.fields["affectation"].queryset = Affectation.objects.select_related(
                "classe", "matiere", "personnel"
            ).all()
