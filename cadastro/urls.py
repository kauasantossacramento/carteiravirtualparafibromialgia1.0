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
    path("atualizar_foto/<int:sol_id>/", views.atualizar_foto, name="atualizar_foto"), # NOVA ROTA
    # página para digitar o código (opcional)
    path("validar/", views.validar_index, name="validar_index"),

    path("validar/<str:codigo>/", views.validar_carteirinha, name="validar"),
    path('gestao/', views.admin_dashboard, name='admin_dashboard'),
    path('gestao/listar/<str:filtro>/', views.admin_lista, name='admin_lista'),

    # Ações do Modal (API interna)
    path('gestao/detalhes/<int:sol_id>/', views.admin_get_detalhes, name='admin_get_detalhes'),
    path('gestao/atualizar/<int:sol_id>/', views.admin_atualizar, name='admin_atualizar'),
    path('gestao/ficha/<int:sol_id>/', views.gerar_ficha_cadastral, name='admin_ficha'),
    path('re-upload/<int:sol_id>/', views.re_upload, name='re_upload'),
]
