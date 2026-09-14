from django.db import models

# Create your models here.
from django.db import models

from empresa.models import Empresa
from core.models import Usuario


class OfertaProduto(models.Model):
    """Produto que uma empresa deseja vender/oferecer no marketplace."""

    empresa = models.ForeignKey(
        Empresa, on_delete=models.CASCADE, related_name='ofertas_produto'
    )
    produto = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, null=True)
    categoria = models.CharField(max_length=100, blank=True, null=True)
    quantidade = models.PositiveIntegerField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Oferta de Produto'
        verbose_name_plural = 'Ofertas de Produto'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.empresa.nomefantasia} oferece: {self.produto}"


class DemandaProduto(models.Model):
    """Produto que um usuário deseja comprar no marketplace."""

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='demandas_produto'
    )
    produto = models.CharField(max_length=255)
    descricao = models.TextField(blank=True, null=True)
    categoria = models.CharField(max_length=100, blank=True, null=True)
    quantidade = models.PositiveIntegerField(blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demanda de Produto'
        verbose_name_plural = 'Demandas de Produto'
        ordering = ['-criado_em']

    def __str__(self):
        return f"{self.usuario.user.nome} procura: {self.produto}"


# O model Match (que liga OfertaProduto <-> DemandaProduto) ainda não foi
# criado — depende da definição de regras de compatibilidade com o time
# de produto (nome exato, categoria, quantidade, localização etc.).