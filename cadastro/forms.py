from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Usuario, Documento, Solicitacao

class RegistroForm(UserCreationForm):
    cpf = forms.CharField(max_length=11, label="CPF")
    data_nascimento = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    sexo = forms.CharField(max_length=20)
    endereco = forms.CharField(widget=forms.Textarea)
    telefone = forms.CharField(max_length=20)
    contato_urgencia_nome = forms.CharField(max_length=100)
    contato_urgencia_numero = forms.CharField(max_length=20)

    rg_frente = forms.FileField(required=True, label="RG (frente)")
    rg_verso = forms.FileField(required=True, label="RG (verso)")
    laudo = forms.FileField(required=True, label="Laudo Médico (CID-10)")
    foto = forms.FileField(required=True, label="Foto 3x4")

    class Meta:
        model = Usuario
        fields = [
            "username", "cpf", "first_name", "last_name",
            "data_nascimento", "sexo", "endereco", "telefone",
            "contato_urgencia_nome", "contato_urgencia_numero",
            "password1", "password2",
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.cpf = self.cleaned_data["cpf"]
        user.data_nascimento = self.cleaned_data["data_nascimento"]
        user.sexo = self.cleaned_data["sexo"]
        user.endereco = self.cleaned_data["endereco"]
        user.telefone = self.cleaned_data["telefone"]
        user.contato_urgencia_nome = self.cleaned_data["contato_urgencia_nome"]
        user.contato_urgencia_numero = self.cleaned_data["contato_urgencia_numero"]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Usuário/CPF")
