from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = 'empresa'

urlpatterns = [
    path("cadastro_empresa/", views.cadastro_empresa, name="cadastro_empresa"),
    path("criar_empresa/", views.criar_empresa, name="criar_empresa"),
    path('get_cidades/', views.get_cidades, name='get_cidades'),
    path('minhas_vagas/', views.minhas_vagas, name='minhas_vagas'),
    path('vaga/<int:vaga_id>/', views.detalhe_minha_vaga, name='detalhe_minha_vaga'),
    path('vaga/<int:vaga_id>/candidatos/', views.candidatos_vaga, name='candidatos_vaga'),
    path('candidato/<int:usuario_id>/', views.perfil_candidato, name='perfil_candidato'),
]
