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

