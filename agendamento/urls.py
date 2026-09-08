from django.urls import path
from . import views

app_name = 'agendamento'

urlpatterns = [
    path('', views.minhas_reservas, name='minhas_reservas'),
    path('api/horarios-sala/', views.obter_horarios_sala,
         name='obter_horarios_sala'),
    path('novo/', views.realizar_reserva, name='realizar_reserva'),
    path('api/reservas/', views.api_reservas_calendario,
         name='api_reservas_calendario'),
    path('editar/<int:reserva_id>/', views.editar_reserva, name='editar_reserva'),
    path('excluir/<int:reserva_id>/',
         views.excluir_reserva, name='excluir_reserva'),
    path('qrcodes/', views.gerador_qrcodes, name='gerador_qrcodes'),
    path('checkin/<str:sala_chave>/', views.checkin_qrcode, name='checkin_qrcode'),
    path('configuracoes/', views.gerenciar_configuracoes_hub,
         name='configuracoes_hub'),
    path('aprovacao/email/<str:token>/', views.processar_aprovacao_email,
         name='processar_aprovacao_email'),
]
