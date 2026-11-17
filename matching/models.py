from django.db import models
from core.models import Usuario, InteresseCompra, Hub
from vagas.models import Vagas
from empresa.models import Produto


class MatchScore(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='match_scores')
    vaga = models.ForeignKey(Vagas, on_delete=models.CASCADE, related_name='match_scores')
    score = models.FloatField(default=0.0)
    breakdown = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('usuario', 'vaga')

    def __str__(self):
        return f"{self.usuario_id}<->{self.vaga_id}: {self.score}"


class HubMatchScore(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='hub_match_scores')
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE, related_name='match_scores')
    score = models.FloatField(default=0.0)
    breakdown = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('usuario', 'hub')

    def __str__(self):
        return f"{self.usuario_id}<->{self.hub_id}: {self.score}"


class ProdutoMatch(models.Model):
    """Match entre um interesse de compra (demanda) e um produto ofertado (oferta).

    Só é gerado quando a compatibilidade atinge o limiar configurado em
    settings.PRODUCT_MATCH_THRESHOLD, evitando duplicidade por
    (interesse, produto) via unique_together.
    """
    interesse = models.ForeignKey(InteresseCompra, on_delete=models.CASCADE, related_name='produto_matches')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='interesse_matches')
    score = models.FloatField(default=0.0)
    breakdown = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('interesse', 'produto')

    def __str__(self):
        return f"{self.interesse_id}<->{self.produto_id}: {self.score}"



class PreferenciaEmailVagas(models.Model):
    """Preferência do candidato sobre o e-mail semanal de vagas compatíveis.

    A ausência de registro equivale a receber os e-mails (opt-out).
    """
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='preferencia_email_vagas')
    receber_vagas = models.BooleanField(default=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.usuario_id}: {'recebe' if self.receber_vagas else 'descadastrado'}"


class EnvioVagasEmail(models.Model):
    """Registro de cada e-mail semanal de vagas: um por candidato e semana.

    A unicidade (usuario, semana) impede que reexecuções na mesma semana
    reenviem o e-mail a quem já recebeu; falhas ficam registradas e são
    tentadas de novo na próxima execução da mesma semana.
    """
    STATUS_ENVIANDO = 'enviando'
    STATUS_ENVIADO = 'enviado'
    STATUS_FALHA = 'falha'
    STATUS_CHOICES = [
        (STATUS_ENVIANDO, 'Enviando'),
        (STATUS_ENVIADO, 'Enviado'),
        (STATUS_FALHA, 'Falha'),
    ]

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='envios_vagas_email')
    semana = models.DateField(help_text='Segunda-feira da semana de referência do disparo.')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ENVIANDO)
    vagas = models.ManyToManyField(Vagas, related_name='envios_email', blank=True)
    email = models.EmailField()
    tentativas = models.PositiveSmallIntegerField(default=0)
    erro = models.TextField(blank=True, default='')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    enviado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('usuario', 'semana')
        ordering = ['-semana', '-atualizado_em']

    def __str__(self):
        return f"{self.usuario_id} semana {self.semana}: {self.status}"
