from django.db import models
from core.models import UsuarioBase, Hub
from empresa.models import Empresa


class Evento(models.Model):
    nome_evento = models.CharField(max_length=100)
    data_evento_inicio = models.DateField(blank=True, null=True)
    data_evento_fim = models.DateField(blank=True, null=True)
    horario_evento = models.TimeField(blank=True, null=True)
    local_evento = models.CharField(max_length=255, blank=True, null=True)
    publico_evento = models.CharField(max_length=255, blank=True, null=True)
    descricao_evento = models.TextField(max_length=500, blank=True, null=True)
    vagas_disponiveis = models.PositiveIntegerField(default=0)
    isActivate = models.BooleanField(default=True)
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos_criados',
    )
    hub = models.ForeignKey(
        Hub,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eventos',
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evento'
        verbose_name_plural = 'Eventos'
        ordering = ['-data_evento_inicio']

    def __str__(self):
        return f"{self.nome_evento}"

    @property
    def inscritos_count(self):
        return self.inscricoes.count()

    @property
    def vagas_restantes(self):
        if self.vagas_disponiveis == 0:
            return None  # Sem limite
        return max(0, self.vagas_disponiveis - self.inscritos_count)

    @property
    def lotado(self):
        if self.vagas_disponiveis == 0:
            return False
        return self.inscritos_count >= self.vagas_disponiveis


class InscricaoEvento(models.Model):
    STATUS_PRESENCA = [
        ('pendente', 'Pendente'),
        ('presente', 'Presente'),
        ('ausente', 'Ausente'),
    ]

    evento = models.ForeignKey(
        Evento,
        on_delete=models.CASCADE,
        related_name='inscricoes',
    )
    usuario = models.ForeignKey(
        UsuarioBase,
        on_delete=models.CASCADE,
        related_name='inscricoes_eventos',
    )
    data_inscricao = models.DateTimeField(auto_now_add=True)
    presenca = models.CharField(
        max_length=10, choices=STATUS_PRESENCA, default='pendente'
    )

    class Meta:
        unique_together = ('evento', 'usuario')
        verbose_name = 'Inscrição em Evento'
        verbose_name_plural = 'Inscrições em Eventos'
        ordering = ['data_inscricao']

    def __str__(self):
        return f"{self.usuario.email} → {self.evento.nome_evento}"