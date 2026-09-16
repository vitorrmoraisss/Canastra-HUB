from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError


class ConfiguracaoAgendamento(models.Model):
    email_hub = models.EmailField(
        "E-mail do HUB (Aprovações)", default="hub@canastra.com")
    email_professor_1 = models.EmailField(
        "E-mail Professor 1 (FAST)", default="prof1@canastra.com")
    email_professor_2 = models.EmailField(
        "E-mail Professor 2 (FAST)", default="prof2@canastra.com")
    horario_noturno_inicio = models.IntegerField(
        "Início Horário Noturno (0-23h)", default=18)
    horario_noturno_fim = models.IntegerField(
        "Fim Horário Noturno (0-23h)", default=6)

    class Meta:
        verbose_name = "Configuração de Agendamento"
        verbose_name_plural = "Configurações de Agendamento"

    @classmethod
    def get_config(cls):
        config, _ = cls.objects.get_or_create(id=1)
        return config


class ReservaManager(models.Manager):
    def get_queryset(self):
        agora = timezone.now()
        super().get_queryset().filter(
            fim__lte=agora,
            status='confirmada',
            status_checkin='Pendente'
        ).update(status='nao_compareceu')

        return super().get_queryset()


class Reserva(models.Model):
    SALA_CHOICES = [
        ('treinamentos', 'Espaço de Treinamentos'),
        ('reunioes', 'Sala de Reuniões'),
        ('laboratorio', 'Laboratório de Práticas Gerais'),
        ('fast', 'FAST - Fábrica de Soluções Tecnológicas'),
    ]

    STATUS_CHOICES = [
        ('pendente_aprovacao', 'Aguardando Aprovação'),
        ('confirmada', 'Confirmada'),
        ('cancelada', 'Cancelada'),
        ('nao_compareceu', 'Não Compareceu'),
    ]

    APROVACAO_CHOICES = [
        ('Pendente', 'Pendente'),
        ('Aprovado', 'Aprovado'),
        ('Rejeitado', 'Rejeitado'),
        ('N/A', 'N/A'),
    ]

    aprovado_hub = models.CharField(
        "Aprovado pelo HUB", max_length=20, choices=APROVACAO_CHOICES, default='N/A')
    aprovado_professor = models.CharField(
        "Aprovado por Professor", max_length=20, choices=APROVACAO_CHOICES, default='N/A')

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Usuário")
    sala = models.CharField(
        max_length=50, choices=SALA_CHOICES, verbose_name="Sala")
    inicio = models.DateTimeField(verbose_name="Data/Hora de Início")
    fim = models.DateTimeField(verbose_name="Data/Hora de Término")

    empresa_projeto = models.CharField(
        max_length=150, blank=True, null=True, default="Não informado", verbose_name="Empresa/Projeto")
    quantidade_pessoas = models.PositiveIntegerField(
        default=0, verbose_name="Quantidade de Pessoas")
    finalidade = models.CharField(
        max_length=255, blank=True, null=True, default="Não informado", verbose_name="Finalidade")
    equipamentos = models.TextField(
        blank=True, null=True, default="Não informado", verbose_name="Equipamentos")
    observacoes = models.TextField(
        blank=True, null=True, default="Não informado", verbose_name="Observações")

    status_checkin = models.CharField(
        max_length=50, default="Pendente", verbose_name="Status Check-in")
    hora_checkin = models.DateTimeField(
        blank=True, null=True, verbose_name="Hora Check-in")

    google_event_id = models.CharField(
        max_length=255, blank=True, null=True, verbose_name="ID do Evento no Google")
    linha_planilha = models.IntegerField(
        blank=True, null=True, verbose_name="Linha na Planilha Google")

    status = models.CharField(
        max_length=50, choices=STATUS_CHOICES, default='confirmada')
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = ReservaManager()

    class Meta:
        verbose_name = "Reserva"
        verbose_name_plural = "Reservas"
        ordering = ['-inicio']

    def clean(self):
        if self.inicio and self.fim and self.inicio >= self.fim:
            raise ValidationError(
                "A data/hora de término deve ser posterior à data/hora de início.")

    def __str__(self):
        return f"{self.usuario.get_full_name() or self.usuario.email} - {self.get_sala_display()} ({self.inicio.strftime('%d/%m/%Y %H:%M')})"
