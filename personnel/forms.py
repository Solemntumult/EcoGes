"""Formulaires du module Personnel (fiches, affectations, emploi du temps)."""

from django import forms

from parametrage.models import AnneeScolaire, Classe, Matiere

from .models import Affectation, CreneauEmploiDuTemps, DisponibiliteEnseignant, Personnel


class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = ["nom", "prenoms", "fonction", "qualification", "telephone",
                  "email", "date_embauche", "actif", "utilisateur"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control"}),
            "prenoms": forms.TextInput(attrs={"class": "form-control"}),
            "fonction": forms.Select(attrs={"class": "form-select"}),
            "qualification": forms.TextInput(attrs={"class": "form-control"}),
            "telephone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "date_embauche": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "actif": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "utilisateur": forms.Select(attrs={"class": "form-select"}),
        }


class AffectationForm(forms.ModelForm):
    class Meta:
        model = Affectation
        fields = ["personnel", "classe", "matiere", "annee_scolaire", "tarif_horaire"]
        widgets = {
            name: forms.Select(attrs={"class": "form-select"}) for name in
            ["personnel", "classe", "matiere", "annee_scolaire"]
        }
        widgets["tarif_horaire"] = forms.NumberInput(attrs={
            "class": "form-control", "step": "0.01", "min": "0",
            "placeholder": "Montant / heure",
        })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["tarif_horaire"].label = "Tarif horaire (F par heure de cours)"
        self.fields["tarif_horaire"].help_text = "Rémunération de cet enseignant pour une heure sur cette classe/matière."
        annee = AnneeScolaire.objects.filter(est_courante=True).first()
        if annee:
            self.fields["classe"].queryset = Classe.objects.filter(annee_scolaire=annee).select_related("niveau")
            self.fields["matiere"].queryset = Matiere.objects.select_related("niveau")

    def clean(self):
        donnees = super().clean()
        # Contrainte d'unicité (personnel, classe, matiere, annee) — erreur propre au lieu d'une IntegrityError
        if all(donnees.get(champ) for champ in ("personnel", "classe", "matiere", "annee_scolaire")):
            doublon = Affectation.objects.filter(
                personnel=donnees["personnel"],
                classe=donnees["classe"],
                matiere=donnees["matiere"],
                annee_scolaire=donnees["annee_scolaire"],
            ).exclude(pk=self.instance.pk if self.instance else None)
            if doublon.exists():
                self.add_error(None, "Cette affectation existe déjà pour l'année scolaire choisie.")
        return donnees


class CreneauForm(forms.ModelForm):
    class Meta:
        model = CreneauEmploiDuTemps
        fields = ["affectation", "jour", "heure_debut", "heure_fin", "salle"]
        widgets = {
            "affectation": forms.Select(attrs={"class": "form-select"}),
            "jour": forms.Select(attrs={"class": "form-select"}),
            "heure_debut": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"class": "form-control", "type": "time"}),
            "salle": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. Salle 12"}),
        }

    def clean(self):
        donnees = super().clean()
        debut = donnees.get("heure_debut")
        fin = donnees.get("heure_fin")
        if debut and fin and fin <= debut:
            self.add_error("heure_fin", "L'heure de fin doit être postérieure à l'heure de début.")
        return donnees


class DisponibiliteForm(forms.ModelForm):
    class Meta:
        model = DisponibiliteEnseignant
        fields = ["jour", "heure_debut", "heure_fin"]
        widgets = {
            "jour": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "heure_debut": forms.TimeInput(attrs={"class": "form-control form-control-sm", "type": "time"}),
            "heure_fin": forms.TimeInput(attrs={"class": "form-control form-control-sm", "type": "time"}),
        }
