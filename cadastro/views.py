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

class RegistroView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("cadastro:acompanhamento")
        return render(request, "cadastro/registro.html", {"form": RegistroForm()})

    @transaction.atomic
    def post(self, request):
        form = RegistroForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, "cadastro/registro.html", {"form": form})

        # --- cria/atualiza usuário a partir do form, garantindo CPF limpo e senha setada ---
        # se seu RegistroForm é ModelForm de Usuario, usamos commit=False para ajustar campos
        user = form.save(commit=False)

        # normaliza CPF (sem máscara)
        if hasattr(user, "cpf"):
            user.cpf = _only_digits(user.cpf)

        # pega a senha do form e garante set_password (caso o form não faça isso)
        raw_password = (
            form.cleaned_data.get("password1")
            or form.cleaned_data.get("password")
            or None
        )
        if raw_password:
            user.set_password(raw_password)

        # garante username (se estiver vazio, usa o CPF como username)
        if not getattr(user, "username", ""):
            user.username = user.cpf or user.username

        user.save()
        # se o form tinha M2M, salve agora
        if hasattr(form, "save_m2m"):
            form.save_m2m()

        # --- cria solicitação vinculada (igual ao seu código) ---
        sol = Solicitacao.objects.create(usuario=user)
        HistoricoStatus.objects.create(
            solicitacao=sol,
            status=sol.status,
            alterado_por=None,
            observacao="Solicitação criada pelo usuário.",
        )

        # --- grava documentos (igual ao seu código; só checa existência) ---
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

        # --- autentica e faz login com backend definido (evita ValueError com múltiplos backends) ---
        auth_user = None
        if raw_password:
            # tenta autenticar por username e, se falhar, por CPF
            auth_user = authenticate(request, username=user.username, password=raw_password)
            if not auth_user and user.cpf:
                auth_user = authenticate(request, username=user.cpf, password=raw_password)

        if auth_user is not None:
            login(request, auth_user)  # já vem com atributo backend
        else:
            # fallback: se por algum motivo não autenticou (ex.: sem senha no form),
            # loga explicitando o backend custom de CPF/username
            try:
                login(request, user, backend="cadastro.backends.CPFOrUsernameBackend")
            except Exception:
                messages.info(request, "Cadastro criado. Faça login para continuar.")
                return redirect("cadastro:login")

        messages.success(request, "Cadastro realizado com sucesso!")
        return redirect("cadastro:acompanhamento")


class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("cadastro:acompanhamento")
        return render(request, "cadastro/login.html", {"form": LoginForm()})

    def post(self, request):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect("cadastro:acompanhamento")
        return render(request, "cadastro/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("cadastro:index")


@login_required
def acompanhamento(request):
    """Painel do usuário para acompanhar e baixar a carteirinha quando EMITIDA"""
    solicitacoes = request.user.solicitacoes.order_by("-criado_em")
    return render(request, "cadastro/acompanhamento.html", {"solicitacoes": solicitacoes})


@login_required
def gerar_carteirinha_pdf(request, sol_id):
    """Gera PDF só quando a solicitação estiver EMITIDA"""
    sol = get_object_or_404(Solicitacao, id=sol_id, usuario=request.user)
    if sol.status != Solicitacao.EMITIDA:
        return HttpResponseBadRequest("Carteirinha ainda não liberada.")

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)

    # fundo (opcional): coloque um 'layout_carteirinha.png' em static/
    fundo = os.path.join(settings.STATICFILES_DIRS[0], "layout_carteirinha.png")
    if os.path.exists(fundo):
        c.drawImage(fundo, 0, 0, width=595, height=842)  # A4 portrait; ajuste conforme o layout

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 780, "CARTEIRINHA DE IDENTIFICAÇÃO – FIBROMIALGIA")

    c.setFont("Helvetica", 12)
    nome = sol.usuario.get_full_name() or sol.usuario.username
    c.drawString(50, 740, f"Nome: {nome}")
    c.drawString(50, 720, f"CPF: {sol.usuario.cpf}")
    c.drawString(50, 700, f"Código: {sol.codigo}")

    # QRCode para validar
    url_validacao = request.build_absolute_uri(f"/validar/{sol.codigo}/")
    img_qr = qrcode.make(url_validacao)

    qr_buf = io.BytesIO()
    img_qr.save(qr_buf, format="PNG")
    qr_buf.seek(0)

    # antes: c.drawImage(qr_buf, 450, 690, 100, 100)  # dá TypeError
    c.drawImage(ImageReader(qr_buf), 450, 690, 100, 100)


    c.showPage()
    c.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"carteirinha_{sol.codigo}.pdf")


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


@login_required
def previa_carteirinha(request, sol_id):
    s = get_object_or_404(Solicitacao, id=sol_id, usuario=request.user)

    # dados vindos do usuário
    usuario = s.usuario
    nome = usuario.get_full_name() or usuario.username
    cpf_fmt = _fmt_cpf(usuario.cpf)
    nasc_fmt = _fmt_data(usuario.data_nascimento)

    # foto 3x4: último Documento do tipo FOTO (se existir)
    doc_foto = (
        Documento.objects.filter(solicitacao=s, tipo=Documento.FOTO)
        .order_by("-enviado_em")
        .first()
    )
    foto_url = doc_foto.arquivo.url if doc_foto else None

    url_validacao = request.build_absolute_uri(f"/validar/{s.codigo}/")

    return render(
        request,
        "cadastro/previa.html",
        {
            "s": s,
            "nome": nome,
            "cpf_fmt": cpf_fmt,
            "nasc_fmt": nasc_fmt,
            "foto_url": foto_url,
            "url_validacao": url_validacao,
        },
    )


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
    c.drawCentredString(CARD_X + CARD_W / 2, CARD_Y + CARD_H - 70, "CARTEIRINHA DE IDENTIFICAÇÃO DA")
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
        "validar.carteirinha.com.br\n"
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

