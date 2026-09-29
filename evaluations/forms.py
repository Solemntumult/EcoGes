"""Formulaires du module Évaluations (saisie des notes, bulletins, décisions)."""

from decimal import Decimal

from django import forms

from parametrage.models import AnneeScolaire, Classe, Periode

from .models import Evaluation, Note


class EvaluationForm(forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ["matiere", "classe", "periode", "type_evaluation", "coefficient", "date"]
        widgets = {
            "matiere": forms.Select(attrs={"class": "form-select"}),
            "classe": forms.Select(attrs={"class": "form-select"}),
            "periode": forms.Select(attrs={"class": "form-select"}),
            "type_evaluation": forms.Select(attrs={"class": "form-select"}),
            "coefficient": forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        if annee:
            classes_qs = Classe.objects.filter(annee_scolaire=annee).select_related("niveau")
            from parametrage.models import Matiere
            matieres_qs = Matiere.objects.all()
            
            if user and getattr(user, "role", "") == "ENSEIGNANT" and hasattr(user, "fiche_personnel"):
                affectations = user.fiche_personnel.affectations.filter(annee_scolaire=annee)
                classe_ids = affectations.values_list("classe_id", flat=True)
                matiere_ids = affectations.values_list("matiere_id", flat=True)
                classes_qs = classes_qs.filter(id__in=classe_ids)
                matieres_qs = matieres_qs.filter(id__in=matiere_ids)
                
            self.fields["classe"].queryset = classes_qs
            self.fields["matiere"].queryset = matieres_qs
            self.fields["periode"].queryset = Periode.objects.filter(annee_scolaire=annee)


class FormSaisieNotes(forms.Form):
    """Formulaire dynamique : un champ note (0-20) par élève de la classe (UC-20)."""

    def __init__(self, evaluation, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.evaluation = evaluation
        from eleves.models import Inscription

        inscriptions = Inscription.objects.filter(classe=evaluation.classe, statut="ACTIVE")
        notes_existantes = {
            n.inscription_id: n for n in Note.objects.filter(evaluation=evaluation)
        }
        for inscription in inscriptions:
            note = notes_existantes.get(inscription.pk)
            self.fields[f"note_{inscription.pk}"] = forms.DecimalField(
                min_value=Decimal("0"),
                max_value=Decimal("20"),
                decimal_places=2,
                required=False,
                initial=note.valeur if note else None,
                label=f"{inscription.eleve.nom} {inscription.eleve.prenoms}",
                widget=forms.NumberInput(
                    attrs={"class": "form-control", "step": "0.25", "placeholder": "0–20"}
                ),
            )

    def enregistrer(self, saisi_par=None, utilisateur=None):
        """Met à jour les notes saisies. Retourne le nombre de notes enregistrées."""
        from comptes.context_user import get_current_user, set_current_user
        from eleves.models import Inscription

        precedent = get_current_user()
        if utilisateur is not None:
            set_current_user(utilisateur)
        try:
            compteur = 0
            for nom, valeur in self.cleaned_data.items():
                if not nom.startswith("note_") or valeur is None:
                    continue
                inscription = Inscription.objects.filter(pk=nom.split("_", 1)[1]).first()
                if inscription is None:
                    continue
                Note.objects.update_or_create(
                    evaluation=self.evaluation,
                    inscription=inscription,
                    defaults={"valeur": valeur, "saisi_par": saisi_par},
                )
                compteur += 1
            return compteur
        finally:
            if utilisateur is not None:
                set_current_user(precedent)


class BulletinsMasseForm(forms.Form):
    """Sélection classe + période pour la génération en masse (UC-23)."""

    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(), label="Classe",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    periode = forms.ModelChoiceField(
        queryset=Periode.objects.none(), label="Période",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        if annee:
            self.fields["classe"].queryset = Classe.objects.filter(annee_scolaire=annee).select_related("niveau")
            self.fields["periode"].queryset = Periode.objects.filter(annee_scolaire=annee)


class DecisionsForm(forms.Form):
    """Sélection classe + période pour saisir les décisions du conseil (UC-25)."""

    classe = forms.ModelChoiceField(
        queryset=Classe.objects.none(), label="Classe",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        if annee:
            self.fields["classe"].queryset = Classe.objects.filter(annee_scolaire=annee).select_related("niveau")
