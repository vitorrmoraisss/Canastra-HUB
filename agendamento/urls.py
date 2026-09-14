from django.urls import path
from . import views

urlpatterns = [
    # Agora a rota principal (/agendamento/) abre diretamente o painel com calendário + lista
    path('', views.minhas_reservas, name='minhas_reservas'),

    # O formulário de criação passa a ter o subcaminho /agendamento/novo/
    path('novo/', views.realizar_reserva, name='realizar_reserva'),

    # Rota que alimenta os blocos do FullCalendar
    path('api/reservas/', views.api_reservas_calendario,
         name='api_reservas_calendario'),

    # Rotas de gerenciamento administrativo
    path('editar/<int:reserva_id>/', views.editar_reserva, name='editar_reserva'),
    path('excluir/<int:reserva_id>/',
         views.excluir_reserva, name='excluir_reserva'),
]
