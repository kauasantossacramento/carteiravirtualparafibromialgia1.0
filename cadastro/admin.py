# cadastro/admin.py

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm
from .models import Usuario, Solicitacao, Documento, HistoricoStatus


# --- FORMULÁRIO CORRIGIDO PARA CRIAÇÃO DE USUÁRIO ---
class UsuarioCriacaoAdminForm(UserCreationForm):
    """
    Formulário customizado para criar usuários no admin.
    Herda de UserCreationForm que já trata password e password confirmation.
    """
    class Meta:
        model = Usuario
        # APENAS campos que existem no modelo
        fields = ("username", "email", "cpf")

    def clean_cpf(self):
        """Valida CPF para não permitir duplicatas"""
        cpf = self.cleaned_data.get("cpf")
        
        if not cpf:
            raise forms.ValidationError("O CPF é obrigatório.")
        
        # Verifica se CPF já existe
        if Usuario.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Este CPF já está cadastrado no sistema.")
        
        return cpf

    def clean_username(self):
        """Valida se o username é válido"""
        username = self.cleaned_data.get("username")
        
        if not username:
            raise forms.ValidationError("O nome de usuário é obrigatório.")
        
        if len(username) < 3:
            raise forms.ValidationError("O nome de usuário deve ter pelo menos 3 caracteres.")
        
        return username

    def clean_email(self):
        """Valida se o email é único"""
        email = self.cleaned_data.get("email")
        
        if not email:
            raise forms.ValidationError("O email é obrigatório.")
        
        if Usuario.objects.filter(email=email).exists():
            raise forms.ValidationError("Este email já está cadastrado.")
        
        return email


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    """
    Admin customizado para o modelo Usuario.
    """
    add_form = UsuarioCriacaoAdminForm
    model = Usuario
    
    # Listagem de usuários
    list_display = ("username", "cpf", "email", "first_name", "is_staff", "is_superuser")
    list_filter = ("is_staff", "is_superuser", "groups")
    search_fields = ("username", "cpf", "first_name", "email")
    
    # Tela de CRIAÇÃO (Adicionar Usuário)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "cpf", "password1", "password2"),
            "description": "Preencha os campos obrigatórios para criar um novo usuário."
        }),
    )
    
    # Tela de EDIÇÃO (Usuário já existe)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Informações Pessoais", {
            "fields": ("cpf", "data_nascimento", "sexo", "telefone", "endereco")
        }),
        ("Contato de Emergência", {
            "fields": ("contato_urgencia_nome", "contato_urgencia_numero")
        }),
    )


# --- INLINE PARA VER O HISTÓRICO DENTRO DA SOLICITAÇÃO ---
class HistoricoInline(admin.TabularInline):
    """Mostra o histórico de alterações inline na tela de edição"""
    model = HistoricoStatus
    extra = 0
    readonly_fields = ('alterado_por', 'alterado_em', 'status', 'observacao')
    can_delete = False

    def has_add_permission(self, request, obj):
        return False


@admin.register(Solicitacao)
class SolicitacaoAdmin(admin.ModelAdmin):
    """Admin para gerenciar solicitações de carteira"""
    list_display = ("id", "usuario", "status", "criado_em", "codigo")
    list_filter = ("status", "criado_em")
    search_fields = ("usuario__username", "usuario__cpf", "codigo")
    readonly_fields = ("codigo", "criado_em")
    
    # Adiciona o histórico visualmente na tela de edição
    inlines = [HistoricoInline]
    
    actions = ["aprovar_emitir", "marcar_analise", "marcar_concluida", "rejeitar"]

    # --- CAMPO EXTRA PARA ESCREVER O MOTIVO ---
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        
        # Injetamos um campo que não existe no modelo, apenas no formulário
        form.base_fields['observacao_admin'] = forms.CharField(
            label="Motivo / Observação da Alteração",
            required=False,
            widget=forms.Textarea(attrs={'rows': 3, 'style': 'width: 90%;'}),
            help_text="⚠️ Se estiver alterando o status (especialmente para REJEITADA), escreva o motivo aqui."
        )
        return form

    # --- SALVAR COM LÓGICA PERSONALIZADA ---
    def save_model(self, request, obj, form, change):
        # Verifica qual era o status antes de salvar
        status_anterior = None
        if change:
            try:
                old_obj = Solicitacao.objects.get(pk=obj.pk)
                status_anterior = old_obj.status
            except Solicitacao.DoesNotExist:
                pass

        # Salva a alteração normal do Django
        super().save_model(request, obj, form, change)

        # Se o status mudou, cria o histórico
        if not change or (status_anterior != obj.status):
            # Pega o texto que o admin digitou
            obs_texto = form.cleaned_data.get('observacao_admin', '')

            # Se deixou em branco, define um texto padrão inteligente
            if not obs_texto:
                if obj.status == 'rejeitada':
                    obs_texto = "Solicitação rejeitada. Favor verificar pendências na Secretaria."
                elif obj.status == 'emitida':
                    obs_texto = "Documentação validada e carteira emitida."
                else:
                    obs_texto = f"Status atualizado para: {obj.get_status_display()}"

            # Cria o registro no histórico
            HistoricoStatus.objects.create(
                solicitacao=obj,
                status=obj.status,
                alterado_por=request.user,
                observacao=obs_texto
            )

    # --- AÇÕES EM MASSA ---
    def _set_status(self, request, queryset, status, label):
        """Helper para atualizar status em massa"""
        updated = 0
        for sol in queryset:
            if sol.status != status:
                sol.status = status
                sol.save()
                HistoricoStatus.objects.create(
                    solicitacao=sol, 
                    status=status, 
                    alterado_por=request.user,
                    observacao=f"Atualização em lote: {label}."
                )
                updated += 1
        self.message_user(request, f"{updated} solicitação(ões) atualizada(s) para {label}.")

    def aprovar_emitir(self, request, queryset):
        """Ação para aprovar e marcar como emitida"""
        self._set_status(request, queryset, "emitida", "EMITIDA")
    aprovar_emitir.short_description = "✅ Aprovar e marcar como EMITIDA"

    def marcar_analise(self, request, queryset):
        """Ação para marcar como em análise"""
        self._set_status(request, queryset, "analise_iniciada", "ANÁLISE INICIADA")
    marcar_analise.short_description = "🔄 Marcar como ANÁLISE INICIADA"

    def marcar_concluida(self, request, queryset):
        """Ação para marcar análise como concluída"""
        self._set_status(request, queryset, "analise_concluida", "ANÁLISE CONCLUÍDA")
    marcar_concluida.short_description = "✔️ Marcar como ANÁLISE CONCLUÍDA"

    def rejeitar(self, request, queryset):
        """Ação para rejeitar solicitação"""
        self._set_status(request, queryset, "rejeitada", "REJEITADA")
    rejeitar.short_description = "❌ Marcar como REJEITADA"


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    """Admin para gerenciar documentos"""
    list_display = ("id", "solicitacao", "tipo", "arquivo", "enviado_em")
    list_filter = ("tipo", "enviado_em")
    search_fields = ("solicitacao__id", "solicitacao__usuario__username")
    readonly_fields = ("enviado_em",)


@admin.register(HistoricoStatus)
class HistoricoStatusAdmin(admin.ModelAdmin):
    """Admin para visualizar histórico de status"""
    list_display = ("solicitacao", "status", "alterado_por", "alterado_em")
    list_filter = ("status", "alterado_em")
    search_fields = ("solicitacao__id", "solicitacao__usuario__username")
    readonly_fields = ("solicitacao", "status", "alterado_por", "alterado_em", "observacao")
    
    def has_add_permission(self, request):
        """Impede adição manual de histórico"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Impede deleção de histórico"""
        return False