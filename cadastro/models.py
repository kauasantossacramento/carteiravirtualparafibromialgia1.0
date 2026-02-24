from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

class Usuario(AbstractUser):
    cpf = models.CharField(max_length=11, unique=True)
    data_nascimento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=20, blank=True)
    endereco = models.TextField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    contato_urgencia_nome = models.CharField(max_length=100, blank=True)
    contato_urgencia_numero = models.CharField(max_length=20, blank=True)

    # --- ADICIONE ESTA LINHA ---
    # Isso diz ao Django: "Quando criar superuser pelo terminal, peça também estes campos"
    REQUIRED_FIELDS = ['email', 'cpf']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.cpf})"

class Solicitacao(models.Model):
    AGUARDANDO = "aguardando"
    ANALISE_INICIADA = "analise_iniciada"
    ANALISE_CONCLUIDA = "analise_concluida"
    EMITIDA = "emitida"
    REJEITADA = "rejeitada"

    STATUS_CHOICES = [
        (AGUARDANDO, "Aguardando análise"),
        (ANALISE_INICIADA, "Análise iniciada"),
        (ANALISE_CONCLUIDA, "Análise concluída"),
        (EMITIDA, "Carteira emitida"),
        (REJEITADA, "Rejeitada"),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="solicitacoes")
    criado_em = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AGUARDANDO)
    codigo = models.CharField(max_length=32, unique=True, blank=True)

    # Campos de Pendência (Boolean)
    pendencia_rg_frente = models.BooleanField(default=False)
    pendencia_rg_verso = models.BooleanField(default=False)
    pendencia_laudo = models.BooleanField(default=False)
    pendencia_foto = models.BooleanField(default=False)

    # Motivos de Rejeição (Choices)
    MOTIVO_CHOICES = [
        ('qualidade', 'Imagem com baixa qualidade/ilegível'),
        ('invalido', 'Documento não identificado ou inválido'),
        ('desatualizado', 'Documento fora da validade/antigo'),
    ]

    motivo_rg_frente = models.CharField(max_length=20, choices=MOTIVO_CHOICES, blank=True, null=True)
    motivo_rg_verso = models.CharField(max_length=20, choices=MOTIVO_CHOICES, blank=True, null=True)
    motivo_laudo = models.CharField(max_length=20, choices=MOTIVO_CHOICES, blank=True, null=True)
    motivo_foto = models.CharField(max_length=20, choices=MOTIVO_CHOICES, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = uuid.uuid4().hex[:16].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sol#{self.id} - {self.usuario} - {self.status}"


class HistoricoStatus(models.Model):
    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE, related_name="historico")
    status = models.CharField(max_length=20, choices=Solicitacao.STATUS_CHOICES)
    alterado_por = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.SET_NULL)
    alterado_em = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["-alterado_em"]


class Documento(models.Model):
    RG_FRENTE = "rg_frente"
    RG_VERSO = "rg_verso"
    LAUDO = "laudo"
    FOTO = "foto"

    TIPO_CHOICES = [
        (RG_FRENTE, "RG Frente"),
        (RG_VERSO, "RG Verso"),
        (LAUDO, "Laudo Médico (CID)"),
        (FOTO, "Foto 3x4"),
    ]

    solicitacao = models.ForeignKey(Solicitacao, on_delete=models.CASCADE, related_name="documentos")
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    arquivo = models.FileField(upload_to="documentos/%Y/%m/%d/")
    enviado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.tipo} - Sol {self.solicitacao_id}"
