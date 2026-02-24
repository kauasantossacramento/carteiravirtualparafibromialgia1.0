from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Usuario, Documento, Solicitacao

from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Usuario, Documento, Solicitacao

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario
import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import FileExtensionValidator # Importante para validar extensão
from .models import Usuario
import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import FileExtensionValidator # Importante para validar extensão
from .models import Usuario
import re

class RegistroForm(UserCreationForm):
    # Alterado para max_length=14 para aceitar a máscara
    cpf = forms.CharField(
        max_length=14,
        label="CPF",
        widget=forms.TextInput(attrs={'placeholder': '000.000.000-00'})
    )

    data_nascimento = forms.DateField(
        label="Data de Nascimento",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    SEXO_CHOICES = [
        ('MASCULINO', 'MASCULINO'),
        ('FEMININO', 'FEMININO'),
        ('NAO_INFORMAR', 'NÃO INFORMAR'),
    ]
    sexo = forms.ChoiceField(
        choices=SEXO_CHOICES,
        label="Gênero",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    endereco = forms.CharField(label="Endereço Completo", widget=forms.Textarea(attrs={'rows': 3}))
    telefone = forms.CharField(max_length=20, label="Celular / WhatsApp")
    contato_urgencia_nome = forms.CharField(max_length=100, label="Nome do Contato de Urgência")
    contato_urgencia_numero = forms.CharField(max_length=20, label="Telefone de Urgência")

    rg_frente = forms.FileField(required=True, label="RG (frente)")
    rg_verso = forms.FileField(required=True, label="RG (verso)")
    laudo = forms.FileField(required=True, label="Laudo Médico (CID-10)")

    # --- CORREÇÃO: SOMENTE IMAGENS ---
    foto = forms.FileField(
        required=True,
        label="Foto 3x4 (Rosto)",
        help_text="Somente arquivos de imagem (JPG, PNG, JPEG).",
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png'])], # Validação no Servidor
        widget=forms.FileInput(attrs={'accept': 'image/*'}) # Filtro visual na janela de seleção
    )

    class Meta:
        model = Usuario
        # REMOVI "username" DAQUI PARA EVITAR O ERRO SILENCIOSO
        fields = [
            "cpf", "first_name", "last_name",
            "data_nascimento", "sexo", "endereco", "telefone",
            "contato_urgencia_nome", "contato_urgencia_numero",
        ]

    def clean_cpf(self):
        cpf = self.cleaned_data["cpf"]
        # Remove tudo que não for dígito
        cpf_limpo = re.sub(r"\D", "", cpf)

        if len(cpf_limpo) != 11:
             raise forms.ValidationError("O CPF deve conter exatamente 11 dígitos.")

        # --- VERIFICAÇÃO SE JÁ EXISTE NO BANCO ---
        # Isso evita que o sistema "caia" (erro 500) ao tentar salvar duplicado
        if Usuario.objects.filter(cpf=cpf_limpo).exists():
            raise forms.ValidationError("Este CPF já possui cadastro no sistema.")

        return cpf_limpo

    def save(self, commit=True):
        user = super().save(commit=False)
        # Campos extras
        user.cpf = self.cleaned_data["cpf"]
        user.data_nascimento = self.cleaned_data["data_nascimento"]
        user.sexo = self.cleaned_data["sexo"]
        user.endereco = self.cleaned_data["endereco"]
        user.telefone = self.cleaned_data["telefone"]
        user.contato_urgencia_nome = self.cleaned_data["contato_urgencia_nome"]
        user.contato_urgencia_numero = self.cleaned_data["contato_urgencia_numero"]

        # Define o username igual ao CPF automaticamente
        if not user.username:
            user.username = user.cpf

        if commit:
            user.save()
        return user

class LoginForm(AuthenticationForm):
    username = forms.CharField(label="CPF")
    error_messages = {
        'invalid_login': "CPF ou senha incorretos. Por favor, tente novamente. Caso tenha esquecido a senha, será necessário entrar em contato com a Secretaria de Saúde para recuperação. ",
        'inactive': "Esta conta está inativa.",
    }
