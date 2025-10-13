from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

class Usuario(AbstractUser):
    # use o "username" como login; você pode guardar o CPF aqui:
    cpf = models.CharField(max_length=11, unique=True)
    data_nascimento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=20, blank=True)
    endereco = models.TextField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    contato_urgencia_nome = models.CharField(max_length=100, blank=True)
    contato_urgencia_numero = models.CharField(max_length=20, blank=True)

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
        (EMITIDA, "Carteirinha emitida"),
        (REJEITADA, "Rejeitada"),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="solicitacoes")
    criado_em = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=AGUARDANDO)
    codigo = models.CharField(max_length=32, unique=True, blank=True)

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
