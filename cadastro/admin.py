from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, Solicitacao, Documento, HistoricoStatus

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ("username", "cpf", "first_name", "last_name", "is_staff")
    fieldsets = UserAdmin.fieldsets + (
        ("Dados adicionais", {
            "fields": (
                "cpf", "data_nascimento", "sexo", "endereco",
                "telefone", "contato_urgencia_nome", "contato_urgencia_numero"
            )
        }),
    )

@admin.register(Solicitacao)
class SolicitacaoAdmin(admin.ModelAdmin):
    list_display = ("id", "usuario", "status", "criado_em", "codigo")
    list_filter = ("status",)
    search_fields = ("usuario__username", "usuario__cpf", "codigo")

    actions = ["aprovar_emitir", "marcar_analise", "marcar_concluida", "rejeitar"]

    def _set_status(self, request, queryset, status, label):
        updated = 0
        for sol in queryset:
            sol.status = status
            sol.save()
            HistoricoStatus.objects.create(
                solicitacao=sol, status=status, alterado_por=request.user,
                observacao=f"Status alterado via admin: {label}."
            )
            updated += 1
        self.message_user(request, f"{updated} solicitações {label}.")

    def aprovar_emitir(self, request, queryset):
        self._set_status(request, queryset, "emitida", "marcadas como EMITIDAS")
    aprovar_emitir.short_description = "Aprovar e marcar como EMITIDA"

    def marcar_analise(self, request, queryset):
        self._set_status(request, queryset, "analise_iniciada", "com ANÁLISE INICIADA")

    def marcar_concluida(self, request, queryset):
        self._set_status(request, queryset, "analise_concluida", "com ANÁLISE CONCLUÍDA")

    def rejeitar(self, request, queryset):
        self._set_status(request, queryset, "rejeitada", "REJEITADAS")

@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ("id", "solicitacao", "tipo", "arquivo", "enviado_em")
    list_filter = ("tipo",)

@admin.register(HistoricoStatus)
class HistoricoStatusAdmin(admin.ModelAdmin):
    list_display = ("solicitacao", "status", "alterado_por", "alterado_em", "observacao")
    list_filter = ("status",)
