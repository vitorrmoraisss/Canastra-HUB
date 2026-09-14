from django.db import models
from django.conf import settings


class Reserva(models.Model):
    # Cadastrando as 4 salas oficiais do Canastra HUB
    SALA_CHOICES = [
        ('treinamentos', 'Espaço de Treinamentos'),
        ('reunioes', 'Sala de Reuniões'),
        ('laboratorio', 'Laboratório de Práticas Gerais'),
        ('fast', 'FAST - Fábrica de Soluções Tecnológicas'),
    ]

    STATUS_CHOICES = [
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuário")
    # Aumentamos o max_length para 30 para caber as novas chaves identificadoras
    sala = models.CharField(
        max_length=30, choices=SALA_CHOICES, verbose_name="Sala")
    inicio = models.DateTimeField(verbose_name="Data/Hora de Início")
    fim = models.DateTimeField(verbose_name="Data/Hora de Término")

    google_event_id = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="ID do Evento no Google")
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='confirmada')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"
        ordering = ['-inicio']

    def __str__(self):
        return f"{self.usuario.email} - {self.get_sala_display()} ({self.inicio.strftime('%d/%m/%Y %H:%M')})"
