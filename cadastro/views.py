from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.http import FileResponse, HttpResponseBadRequest
from django.conf import settings
from .forms import RegistroForm, LoginForm
from .models import Documento, Solicitacao, Usuario, HistoricoStatus
from reportlab.lib.utils import ImageReader

import io, os
from reportlab.pdfgen import canvas
import qrcode

DOC_MAP = [
    ('rg_frente', 'RG Frente'),
    ('rg_verso', 'RG Verso'),
    ('laudo', 'Laudo Médico (CID)'),
    ('foto', 'Foto 3x4 (Rosto)'),
]

def index(request):
    return render(request, "cadastro/index.html")


# views.py
import re
from django.views import View
from django.db import transaction
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, get_user_model

from .forms import RegistroForm
from .models import Solicitacao, HistoricoStatus, Documento

User = get_user_model()

def _only_digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")

from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth import login, authenticate
from django.db import transaction
from django.contrib import messages
from .forms import RegistroForm
from .models import Solicitacao, HistoricoStatus, Documento

class RegistroView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("cadastro:acompanhamento")
        return render(request, "cadastro/registro.html", {"form": RegistroForm()})

    @transaction.atomic
    def post(self, request):
        form = RegistroForm(request.POST, request.FILES)

        if not form.is_valid():
            # Retorna o form com erros para o template corrigir
            return render(request, "cadastro/registro.html", {"form": form})

        # 1. Salva o Usuário (O form já limpou o CPF e configurou a senha)
        user = form.save()

        # 2. Cria a Solicitação Vinculada
        sol = Solicitacao.objects.create(usuario=user)

        # 3. Registra Histórico Inicial
        HistoricoStatus.objects.create(
            solicitacao=sol,
            status=sol.status,
            observacao="Solicitação criada pelo usuário."
        )

        # 4. Grava Documentos
        files_map = [
            ("rg_frente", Documento.RG_FRENTE),
            ("rg_verso",  Documento.RG_VERSO),
            ("laudo",     Documento.LAUDO),
            ("foto",      Documento.FOTO),
        ]
        for field_name, tipo in files_map:
            f = request.FILES.get(field_name)
            if f:
                Documento.objects.create(solicitacao=sol, tipo=tipo, arquivo=f)

        # 5. Autenticação Automática
        # Tenta logar o usuário recém-criado para não precisar digitar senha de novo
        if hasattr(user, 'backend'):
             login(request, user)
        else:
             # Fallback: autentica usando a senha limpa do form (password1)
             raw_password = form.cleaned_data.get('password1')
             if raw_password:
                 auth_user = authenticate(request, username=user.username, password=raw_password)
                 if auth_user:
                     login(request, auth_user)
                 else:
                     # Último caso: redireciona para login se falhar auto-login
                     messages.success(request, "Cadastro realizado! Faça login para acessar.")
                     return redirect("cadastro:login")

        messages.success(request, "Solicitação enviada com sucesso!")
        return redirect("cadastro:acompanhamento")


from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
# Importe seu LoginForm personalizado se estiver usando um (ex: .forms import LoginForm)
from .forms import LoginForm

class LoginView(View):
    def get(self, request):
        # CORREÇÃO 1: Se já estiver logado, redireciona para a área correta imediatamente
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect("cadastro:admin_dashboard") # Ou use redirect('/gestao/')
            return redirect("cadastro:acompanhamento")

        return render(request, "cadastro/login.html", {"form": LoginForm()})

    def post(self, request):
        # CORREÇÃO 2: Prevenção de erro CSRF se o usuário já estiver autenticado na sessão
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect("cadastro:admin_dashboard")
            return redirect("cadastro:acompanhamento")

        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # LÓGICA DE REDIRECIONAMENTO DE ADMIN
            if user.is_staff:
                # Se a url '/gestao/' estiver nomeada como 'admin_dashboard' no urls.py:
                return redirect("cadastro:admin_dashboard")
                # Caso contrário, use o caminho direto:
                # return redirect("/gestao/")

            # Usuário comum
            return redirect("cadastro:acompanhamento")

        return render(request, "cadastro/login.html", {"form": form})

def logout_view(request):
    logout(request)
    return redirect("cadastro:index")

# views.py

@login_required
def acompanhamento(request):
    """Painel do usuário para acompanhar e baixar a carteira"""
    # Adicionamos prefetch_related('historico') para trazer a linha do tempo junto
    solicitacoes = (
        request.user.solicitacoes
        .prefetch_related('historico')
        .order_by("-criado_em")
    )
    return render(request, "cadastro/acompanhamento.html", {"solicitacoes": solicitacoes})


def validar_carteirinha(request, codigo):
    sol = Solicitacao.objects.filter(codigo=codigo).first()
    valido = bool(sol and sol.status == Solicitacao.EMITIDA)
    return render(request, "cadastro/validacao.html", {"valido": valido, "solicitacao": sol})


from django.shortcuts import render, redirect


def validar_index(request):
    codigo = request.GET.get("codigo", "").strip()
    if codigo:
        return redirect("cadastro:validar", codigo=codigo)
    return render(request, "cadastro/validar_busca.html")


import io
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
import qrcode

from .models import Solicitacao, Documento


# --- helpers de formatação ---
def _fmt_cpf(cpf: str) -> str:
    if not cpf:
        return ""
    digits = "".join(ch for ch in str(cpf) if ch.isdigit())
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    return cpf  # fallback (deixa como veio)

def _fmt_data(d) -> str:
    try:
        return d.strftime("%d/%m/%Y") if d else ""
    except Exception:
        return str(d) if d else ""

# No seu arquivo views.py

# No topo do arquivo views.py, garanta que tem este import:
from django.utils import timezone

@login_required
def previa_carteirinha(request, sol_id):
    s = get_object_or_404(Solicitacao, id=sol_id, usuario=request.user)

    usuario = s.usuario
    nome = usuario.get_full_name() or usuario.username
    cpf_fmt = _fmt_cpf(usuario.cpf)
    nasc_fmt = _fmt_data(usuario.data_nascimento)

    emergencia_nome = usuario.contato_urgencia_nome or "Não informado"
    emergencia_tel = usuario.contato_urgencia_numero or "-"

    doc_foto = (
        Documento.objects.filter(solicitacao=s, tipo=Documento.FOTO)
        .order_by("-enviado_em")
        .first()
    )
    foto_url = doc_foto.arquivo.url if doc_foto else None

    url_validacao = request.build_absolute_uri(f"/validar/{s.codigo}/")

    # --- LÓGICA DE DATA DE EMISSÃO CORRETA ---
    # Busca no histórico o registro mais recente onde o status é 'emitida'
    # Se não achar (casos antigos), usa a data de criação ou data atual como fallback
    evento_emissao = s.historico.filter(status='emitida').order_by('-alterado_em').first()

    if evento_emissao:
        data_emissao = evento_emissao.alterado_em
    else:
        # Se foi emitida mas não tem histórico (legado), usa a última atualização da solicitação
        data_emissao = s.criado_em

    return render(
        request,
        "cadastro/previa.html",
        {
            "s": s,
            "nome": nome,
            "cpf_fmt": cpf_fmt,
            "nasc_fmt": nasc_fmt,
            "emergencia_nome": emergencia_nome,
            "emergencia_tel": emergencia_tel,
            "foto_url": foto_url,
            "url_validacao": url_validacao,
            "data_emissao": data_emissao, # <--- Enviando a data correta
        },
    )

@login_required

# Exemplo de correção para a view de atualizar foto avulsa (se existir)
@login_required
def atualizar_foto(request, sol_id):
    sol = get_object_or_404(Solicitacao, id=sol_id, usuario=request.user)

    if request.method == "POST" and request.FILES.get('nova_foto'):
        nova_foto = request.FILES['nova_foto']

        # Busca o documento do tipo FOTO
        doc_foto = Documento.objects.filter(solicitacao=sol, tipo=Documento.FOTO).first()

        if doc_foto:
            # Apaga arquivo velho e salva o novo
            doc_foto.arquivo.delete(save=False)
            doc_foto.arquivo = nova_foto
            doc_foto.enviado_em = timezone.now()
            doc_foto.save()
        else:
            # Cria se não existir
            Documento.objects.create(solicitacao=sol, tipo=Documento.FOTO, arquivo=nova_foto)

        messages.success(request, "Foto atualizada com sucesso!")

    return redirect('cadastro:previa', sol_id=sol.id)

@login_required
def gerar_carteirinha_pdf(request, sol_id):
    s = get_object_or_404(Solicitacao, id=sol_id, usuario=request.user)

    usuario = s.usuario
    nome = usuario.get_full_name() or usuario.username
    cpf_fmt = _fmt_cpf(usuario.cpf)
    nasc_fmt = _fmt_data(usuario.data_nascimento)

    # arquivo físico da foto (se existir)
    doc_foto = (
        Documento.objects.filter(solicitacao=s, tipo=Documento.FOTO)
        .order_by("-enviado_em")
        .first()
    )
    foto_path = doc_foto.arquivo.path if doc_foto else None

    # --- PDF base ---
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4  # ~595 x 842

    # Fundo roxo
    c.setFillColorRGB(0.16, 0.04, 0.22)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Cartão branco central
    CARD_W, CARD_H = 470, 620
    CARD_X = (W - CARD_W) / 2
    CARD_Y = H - CARD_H - 120
    c.setFillColorRGB(0, 0, 0, alpha=0.15)
    c.roundRect(CARD_X + 4, CARD_Y - 4, CARD_W, CARD_H, 18, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.roundRect(CARD_X, CARD_Y, CARD_W, CARD_H, 18, fill=1, stroke=0)

    # Faixa rosa
    c.setFillColorRGB(0.98, 0.72, 0.90)
    c.roundRect(CARD_X, CARD_Y + CARD_H - 36, CARD_W, 36, 18, fill=1, stroke=0)
    c.rect(CARD_X, CARD_Y + CARD_H - 36, CARD_W, 18, fill=1, stroke=0)

    # Título
    c.setFillColor(colors.HexColor("#3a173f"))
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(CARD_X + CARD_W / 2, CARD_Y + CARD_H - 70, "CARTEIRA DE IDENTIFICAÇÃO DA")
    c.drawCentredString(CARD_X + CARD_W / 2, CARD_Y + CARD_H - 92, "PESSOA COM FIBROMIALGIA")

    # Foto 3x4
    foto_w = foto_h = 170
    foto_x = CARD_X + (CARD_W - foto_w) / 2
    foto_y = CARD_Y + CARD_H - 270
    if foto_path:
        try:
            c.drawImage(ImageReader(foto_path), foto_x, foto_y, foto_w, foto_h,
                        preserveAspectRatio=True, anchor="c")
            c.setStrokeColor(colors.HexColor("#6b3a7a"))
            c.setLineWidth(1.2)
            c.rect(foto_x, foto_y, foto_w, foto_h, stroke=1, fill=0)
        except Exception:
            pass

    # Nome (com "margin-bottom" maior)
    name_label_y = foto_y - 22
    name_value_y = name_label_y - 26  # dá ~15–16pt de folga para o bloco seguinte
    c.setFillColor(colors.HexColor("#8a8397"))
    c.setFont("Helvetica", 14)
    c.drawCentredString(CARD_X + CARD_W / 2, name_label_y, "Nome")
    c.setFillColor(colors.HexColor("#3a173f"))
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(CARD_X + CARD_W / 2, name_value_y, (nome or "")[:40])

    # --- Data de Nascimento / CPF (miolo um pouco mais baixo) ---
    label_y = CARD_Y + 285      # antes 300
    value_y = label_y - 22

    left_x  = CARD_X + 36
    right_x = CARD_X + CARD_W/2 + 16

    c.setFillColor(colors.HexColor("#8a8397"))
    c.setFont("Helvetica", 12)
    c.drawString(left_x,  label_y, "Data de Nascimento")
    c.drawString(right_x, label_y, "CPF")

    c.setFillColor(colors.HexColor("#3a173f"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(left_x,  value_y, nasc_fmt)   # dd/mm/aaaa
    c.drawString(right_x, value_y, cpf_fmt)    # 000.000.000-00

    # QR + instrução (também mais abaixo para recentralizar)
    url_validacao = request.build_absolute_uri(f"/validar/{s.codigo}/")
    qr_img = qrcode.make(url_validacao)
    qr_buf = io.BytesIO()
    qr_img.save(qr_buf, format="PNG")
    qr_buf.seek(0)
    qr_y = CARD_Y + 125         # antes 150
    c.drawImage(ImageReader(qr_buf), CARD_X + 36, qr_y, 110, 110)

    c.setFillColor(colors.HexColor("#6b6276"))
    c.setFont("Helvetica", 11.5)
    txt = (
        "Verifique a autenticidade\n"
        "deste documento escaneando\n"
        "o código ou acessando:\n"
        "valenca.carteiravirtual.com.br/validar/\n"
        f"COD: {s.codigo}"
    )
    textobj = c.beginText(CARD_X + 160, qr_y + 70)
    for line in txt.splitlines():
        textobj.textLine(line)
    c.drawText(textobj)

    # Legal + logos (aproveita mais o rodapé)
    c.setFillColor(colors.HexColor("#6b6276"))
    c.setFont("Helvetica", 11.5)
    c.drawCentredString(CARD_X + CARD_W / 2, CARD_Y + 95,
                        "Atendimento Prioritário | Lei Federal Nº Lei nº 15.176/2025")

    def static_path(rel):
        p = finders.find(rel)
        if not p:
            raise Http404(f"static '{rel}' não encontrado")
        return p

    try:
        logo_pref = ImageReader(static_path("img/logo-prefeitura.png"))
        logo_sec  = ImageReader(static_path("img/logo-secretaria-saude.png"))
        c.drawImage(logo_pref, CARD_X + CARD_W/2 - 140, CARD_Y + 60, 140, 40,
                    preserveAspectRatio=True, mask="auto")
        c.drawImage(logo_sec,  CARD_X + CARD_W/2 + 10,  CARD_Y + 60, 140, 40,
                    preserveAspectRatio=True, mask="auto")
    except Exception:
        pass

    c.showPage()
    c.save()
    buf.seek(0)
    return FileResponse(buf, as_attachment=True, filename=f"carteirinha_{s.id}.pdf")




#administrativo

# Adicione/Verifique estes imports no topo do views.py
import re
import json
from datetime import timedelta, date
from django.utils import timezone  # <--- O que estava faltando
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.core.paginator import Paginator
from django.utils.dateformat import format as date_format
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse


@staff_member_required
def admin_dashboard(request):
    # 1. KPIs (Mantido igual)
    total_emitidas = Solicitacao.objects.filter(status=Solicitacao.EMITIDA).count()
    total_analise = Solicitacao.objects.filter(status__in=[Solicitacao.AGUARDANDO, Solicitacao.ANALISE_INICIADA]).count()
    total_pendente_emissao = Solicitacao.objects.filter(status__in=[Solicitacao.ANALISE_CONCLUIDA, Solicitacao.REJEITADA]).count()

    # 2. Lógica do Filtro de Dias (Novo)
    # Pega o parâmetro 'dias' da URL, padrão é 30 se não existir
    dias_filtro = request.GET.get('dias', '30')
    if dias_filtro not in ['30', '90', '120']:
        dias_filtro = '30'

    dias_int = int(dias_filtro)

    # 3. Gráfico com Filtro Dinâmico
    data_limite = timezone.now() - timedelta(days=dias_int)

    evolucao = (
        Solicitacao.objects.filter(criado_em__gte=data_limite)
        .annotate(dia=TruncDate('criado_em'))
        .values('dia')
        .annotate(qtd=Count('id'))
        .order_by('dia')
    )

    labels_grafico = [date_format(item['dia'], 'd/m') for item in evolucao]
    dados_grafico = [item['qtd'] for item in evolucao]

    context = {
        'total_emitidas': total_emitidas,
        'total_analise': total_analise,
        'total_pendente_emissao': total_pendente_emissao,
        'labels_grafico': json.dumps(labels_grafico),
        'dados_grafico': json.dumps(dados_grafico),
        'dias_filtro': dias_filtro, # Envia para o template saber qual botão marcar
    }
    return render(request, 'cadastro/admin_dashboard.html', context)


@staff_member_required
def admin_lista(request, filtro):
    # Base Query
    qs = Solicitacao.objects.select_related('usuario').all().order_by('-criado_em')

    # Filtros de Status
    titulo_pagina = "Todas as Solicitações"
    cor_topo = "primary" # padrão

    if filtro == 'emitidas':
        qs = qs.filter(status=Solicitacao.EMITIDA)
        titulo_pagina = "Carteiras Emitidas"
        cor_topo = "success" # verde
    elif filtro == 'analise':
        qs = qs.filter(status__in=[Solicitacao.AGUARDANDO, Solicitacao.ANALISE_INICIADA])
        titulo_pagina = "Pendentes de Análise"
        cor_topo = "warning" # laranja
    elif filtro == 'pendencias':
        qs = qs.filter(status__in=[Solicitacao.ANALISE_CONCLUIDA, Solicitacao.REJEITADA])
        titulo_pagina = "Pendentes de Emissão / Outros"
        cor_topo = "info" # azul/neutro

    # Busca (Search Bar)
    q = request.GET.get('q')
    if q:
        qs = qs.filter(
            Q(usuario__first_name__icontains=q) |
            Q(usuario__cpf__icontains=q) |
            Q(codigo__icontains=q)
        )

    # Paginação (15 por página)
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'cadastro/admin_lista.html', {
        'page_obj': page_obj,
        'filtro': filtro,
        'titulo_pagina': titulo_pagina,
        'cor_topo': cor_topo,
        'q': q or '',
        'doc_map': DOC_MAP  # <--- CRUCIAL para o modal funcionar
    })

 # Certifique-se de importar datetime

# Topo do views.py

# --- IMPORTS OBRIGATÓRIOS NO TOPO DO ARQUIVO ---
import re  # <--- ESSENCIAL PARA O WHATSAPP FUNCIONAR
from django.utils.timezone import localtime
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from .models import Solicitacao, Documento  # Certifique-se que seus models estão aqui
from datetime import datetime
# ... (outras views) ...

@staff_member_required
def admin_get_detalhes(request, sol_id):
    # Otimização de banco de dados
    sol = get_object_or_404(Solicitacao.objects.select_related('usuario'), id=sol_id)
    usuario = sol.usuario

    # 1. Documentos
    docs_data = []
    for d in sol.documentos.all():
        docs_data.append({'tipo': d.get_tipo_display(), 'url': d.arquivo.url})

    # 2. Lógica do WhatsApp (CORRIGIDA)
    whatsapp_link = ""
    if usuario.telefone:
        # Remove tudo que não for dígito (ex: (75) 9.8888-7777 vira 75988887777)
        phone_clean = re.sub(r"\D", "", usuario.telefone)

        # Monta a mensagem automática
        nome_tratamento = usuario.first_name or usuario.username
        msg = f"Olá {nome_tratamento}, falo da Secretaria de Saúde sobre sua Carteira de Fibromialgia."

        # Cria o link universal do WhatsApp (API)
        # Adicionamos o '55' (Brasil) antes do número limpo
        whatsapp_link = f"https://wa.me/55{phone_clean}?text={msg}"

    # 3. Formatação da Data
    nasc_formatado = ""
    if usuario.data_nascimento:
        nasc_formatado = usuario.data_nascimento.strftime('%d/%m/%Y')

    # 4. Histórico
    historico_objs = sol.historico.select_related('alterado_por').all()
    historico_data = []
    for h in historico_objs:
        nome_autor = "Sistema"
        if h.alterado_por:
            nome_autor = h.alterado_por.get_full_name() or h.alterado_por.username

        historico_data.append({
            'data': localtime(h.alterado_em).strftime('%d/%m/%Y %H:%M'),
            'autor': nome_autor,
            'status': h.get_status_display(),
            'obs': h.observacao
        })

    # 5. Retorno JSON Completo
    data = {
        'id': sol.id,
        'nome': usuario.get_full_name(),
        'cpf': usuario.cpf,
        'data_nascimento': nasc_formatado,
        'status': sol.status,
        'whatsapp_link': whatsapp_link,  # <--- O frontend vai ler isso aqui
        'documentos': docs_data,
        'historico': historico_data,
        'pendencias': {
            'rg_frente': getattr(sol, 'pendencia_rg_frente', False),
            'rg_verso': getattr(sol, 'pendencia_rg_verso', False),
            'laudo': getattr(sol, 'pendencia_laudo', False),
            'foto': getattr(sol, 'pendencia_foto', False),
        },
        'motivos': {
            'rg_frente': getattr(sol, 'motivo_rg_frente', ""),
            'rg_verso': getattr(sol, 'motivo_rg_verso', ""),
            'laudo': getattr(sol, 'motivo_laudo', ""),
            'foto': getattr(sol, 'motivo_foto', ""),
        }
    }
    return JsonResponse(data)


@staff_member_required
def admin_atualizar(request, sol_id):
    if request.method == "POST":
        sol = get_object_or_404(Solicitacao, id=sol_id)

        # Processar Pendências
        docs = ['rg_frente', 'rg_verso', 'laudo', 'foto']
        houve_pendencia = False

        for doc in docs:
            is_pendente = request.POST.get(f'pendencia_{doc}') == 'on'
            setattr(sol, f'pendencia_{doc}', is_pendente)
            if is_pendente:
                setattr(sol, f'motivo_{doc}', request.POST.get(f'motivo_{doc}'))
                houve_pendencia = True
            else:
                setattr(sol, f'motivo_{doc}', None)

        sol.save()

        # 1. Captura dados
        novo_status = request.POST.get('status')
        observacao = request.POST.get('observacao')
        nova_senha = request.POST.get('nova_senha')
        nova_data_nasc = request.POST.get('data_nascimento') # Campo do form

        alteracoes = []

        # 2. Atualiza Data de Nascimento (Se mudou)
        if nova_data_nasc:
            try:
                # Converte de DD/MM/AAAA para objeto Date do Python
                data_obj = datetime.strptime(nova_data_nasc, '%d/%m/%Y').date()
                if sol.usuario.data_nascimento != data_obj:
                    sol.usuario.data_nascimento = data_obj
                    sol.usuario.save()
                    alteracoes.append(f"Data de nascimento corrigida para {nova_data_nasc}")
            except ValueError:
                pass # Ignora se a data for inválida

        # 3. Atualiza Senha
        if nova_senha and nova_senha.strip():
            sol.usuario.set_password(nova_senha)
            sol.usuario.save()
            alteracoes.append("Senha alterada.")

        # 4. Atualiza Status
        if novo_status and novo_status != sol.status:
            sol.status = novo_status
            sol.save()
            alteracoes.append(f"Status: {sol.get_status_display()}")

        # 5. Histórico
        if alteracoes or observacao:
            HistoricoStatus.objects.create(
                solicitacao=sol,
                status=sol.status,
                alterado_por=request.user,
                observacao=observacao or " | ".join(alteracoes)
            )

        messages.success(request, "Atualização realizada com sucesso!")
        referer = request.META.get('HTTP_REFERER', 'cadastro:admin_dashboard')
        return redirect(referer)


# Em views.py

@staff_member_required
def gerar_ficha_cadastral(request, sol_id):
    sol = get_object_or_404(Solicitacao, id=sol_id)
    u = sol.usuario

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Cabeçalho
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, 800, "FICHA CADASTRAL - FIBROMIALGIA")
    c.setFont("Helvetica", 10)
    c.drawString(50, 785, f"Gerado em: {timezone.now().strftime('%d/%m/%Y %H:%M')} | Sistema CarteiraVirtual.com.br")
    c.line(50, 775, 545, 775)

    # Dados Pessoais
    y = 750
    line_height = 20

    def draw_line(label, value):
        nonlocal y
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"{label}:")
        c.setFont("Helvetica", 12)
        c.drawString(200, y, str(value or "---"))
        y -= line_height

    draw_line("Nome Completo", u.get_full_name())
    draw_line("CPF", u.cpf)
    draw_line("Data de Nascimento", u.data_nascimento.strftime('%d/%m/%Y') if u.data_nascimento else "-")
    draw_line("Sexo", u.sexo)
    draw_line("Telefone", u.telefone)

    y -= 10 # Espaço extra
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Endereço")
    y -= 25

    # Endereço (quebra de linha simples se for longo)
    c.setFont("Helvetica", 12)
    endereco = u.endereco or "Não informado"
    # Lógica simples para quebrar texto longo
    import textwrap
    lines = textwrap.wrap(endereco, width=60)
    for line in lines:
        c.drawString(50, y, line)
        y -= line_height

    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Contato de Urgência")
    y -= 25

    draw_line("Nome do Contato", u.contato_urgencia_nome)
    draw_line("Telefone do Contato", u.contato_urgencia_numero)

    y -= 20
    c.line(50, y, 545, y)
    y -= 30
    draw_line("Status da Solicitação", sol.get_status_display())
    draw_line("Código da Carteira:", sol.codigo)

    c.showPage()
    c.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"ficha_{u.cpf}.pdf")



@login_required
@transaction.atomic
def re_upload(request, sol_id):
    # Garante que a solicitação pertence ao usuário logado
    sol = get_object_or_404(Solicitacao, id=sol_id, usuario=request.user)

    if request.method == "POST":
        files_map = [
            ("rg_frente", Documento.RG_FRENTE),
            ("rg_verso",  Documento.RG_VERSO),
            ("laudo",     Documento.LAUDO),
            ("foto",      Documento.FOTO),
        ]

        arquivos_enviados = 0

        for field_name, tipo_const in files_map:
            f = request.FILES.get(field_name)

            if f:
                # --- CORREÇÃO: LÓGICA DE SUBSTITUIÇÃO ---

                # Tenta buscar o documento existente
                doc_existente = Documento.objects.filter(
                    solicitacao=sol,
                    tipo=tipo_const
                ).first()

                if doc_existente:
                    # 1. Remove o arquivo físico antigo do disco para não ocupar espaço
                    if doc_existente.arquivo:
                        doc_existente.arquivo.delete(save=False)

                    # 2. Atualiza com o novo arquivo
                    doc_existente.arquivo = f
                    doc_existente.enviado_em = timezone.now() # Atualiza a data de envio
                    doc_existente.save()
                else:
                    # 3. Se não existir, cria um novo
                    Documento.objects.create(solicitacao=sol, tipo=tipo_const, arquivo=f)

                # --- FIM DA CORREÇÃO ---

                # Limpa as pendências (mesma lógica anterior)
                setattr(sol, f'pendencia_{field_name}', False)
                setattr(sol, f'motivo_{field_name}', None)

                arquivos_enviados += 1

        if arquivos_enviados > 0:
            # Volta o status para análise
            sol.status = Solicitacao.ANALISE_INICIADA
            sol.save()

            HistoricoStatus.objects.create(
                solicitacao=sol,
                status=sol.status,
                alterado_por=request.user,
                observacao=f"O cidadão reenviou {arquivos_enviados} documento(s) para correção."
            )

            messages.success(request, "Documentos atualizados com sucesso! Sua solicitação voltou para análise.")
        else:
            messages.error(request, "Nenhum arquivo foi selecionado.")

    return redirect("cadastro:acompanhamento")