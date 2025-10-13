from django.urls import path
from . import views

app_name = "cadastro"

urlpatterns = [
    path("", views.index, name="index"),
    path("registro/", views.RegistroView.as_view(), name="registro"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("acompanhamento/", views.acompanhamento, name="acompanhamento"),
    path("emitir/<int:sol_id>/", views.gerar_carteirinha_pdf, name="emitir"),
    path("previa/<int:sol_id>/", views.previa_carteirinha, name="previa"),
    # página para digitar o código (opcional)
    path("validar/", views.validar_index, name="validar_index"),

    # 👉 ESTA TEM QUE APONTAR PARA validar_carteirinha
    path("validar/<str:codigo>/", views.validar_carteirinha, name="validar"),
]
