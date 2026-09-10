# matching/urls.py
from django.urls import path
from . import views

app_name = "matching"

urlpatterns = [
    path("candidatos/<int:vaga_id>/", views.candidatos_para_vaga, name="candidatos_para_vaga"),
    path("vagas-para/<int:usuario_pk>/", views.vagas_para_usuario, name="vagas_para_usuario"),
    path("produtos-para/<int:interesse_id>/", views.produtos_para_interesse, name="produtos_para_interesse"),
    path("matches/<int:usuario_pk>/", views.matches_para_usuario, name="matches_para_usuario"),
]
