"""Formulaires du module Comptes (authentification, utilisateurs)."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password

from .models import Utilisateur


class ConnexionForm(AuthenticationForm):
    """Formulaire de connexion (UC-02) — le verrouillage est géré dans la vue."""

    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Identifiant", "autofocus": True}),
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Mot de passe"}),
    )


class CreationUtilisateurForm(forms.ModelForm):
    """Création d'un compte utilisateur hors admin Django (UC-01)."""

    password1 = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    password2 = forms.CharField(
        label="Confirmation du mot de passe",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Utilisateur
        fields = ["username", "first_name", "last_name", "email", "role", "telephone", "actif"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "role": forms.Select(attrs={"class": "form-select"}),
            "telephone": forms.TextInput(attrs={"class": "form-control"}),
            "actif": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Les deux mots de passe ne correspondent pas.")
        validate_password(p1, self.instance)
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user
