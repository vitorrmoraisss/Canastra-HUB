from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, User
from django.db.models.deletion import ProtectedError
from core.models import *
# Create your models here.


class Empresa(models.Model):
    user = models.OneToOneField(
        UsuarioBase, on_delete=models.CASCADE, primary_key=True)
    nomefantasia = models.CharField(max_length=100, default="")
    tipo_empresa = models.CharField(max_length=100, default="")
    razao_social = models.CharField(max_length=255, default="")
    cnpj = models.CharField(max_length=20, default="")
    telefone = models.CharField(max_length=20, default="")
    rua = models.CharField(max_length=255, default="")
    cep = models.CharField(max_length=10, default="")
    numero = models.IntegerField(null=True, blank=True)
    complemento = models.CharField(max_length=25, default="")
    cidade = models.ForeignKey(Cidade, on_delete=models.PROTECT)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)
    segmento = models.CharField(max_length=100, default="")

    hubs = models.ManyToManyField(Hub, through='EmpresaHub', blank=True)

    def __str__(self):
        return f"Empresa: {self.user.nome}, {self.nomefantasia}, {self.tipo_empresa}"


class EmpresaHub(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE, blank=True, null= True)

    def __str__(self):
        return f"{self.empresa.user.nome} - {self.hub.nome_hub}"


class Produto(models.Model):
    """Produto/oferta disponibilizado por uma empresa para venda.

    Critérios de compatibilidade (categoria/descrição) e demais atributos
    (preço, quantidade, localização) estão sujeitos à definição final do
    cliente para o processo de Match — ver dependência do card "Match nos Hubs".
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='produtos')
    nome_produto = models.CharField(max_length=150)
    categoria_produto = models.CharField(max_length=150, blank=True, default="")
    descricao_produto = models.TextField(blank=True, default="")
    preco_produto = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    quantidade_disponivel = models.PositiveIntegerField(blank=True, null=True)
    isActive = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome_produto} ({self.empresa.nomefantasia})"
