
from django.db import models


class ConfiguracaoSite(models.Model):
    nome_site = models.CharField(
        "Nome do site",
        max_length=150,
        default="Canastra HUB"
    )

    descricao = models.TextField(
        "Descrição institucional",
        blank=True
    )

    email_contato = models.EmailField(
        "E-mail de contato",
        blank=True
    )

    telefone = models.CharField(
        "Telefone de contato",
        max_length=30,
        blank=True
    )

    endereco = models.CharField(
        "Endereço",
        max_length=255,
        blank=True
    )

    cidade = models.CharField(
        "Cidade",
        max_length=100,
        blank=True
    )

    estado = models.CharField(
        "Estado",
        max_length=100,
        blank=True
    )

    link_mapa = models.URLField(
        "Link do Google Maps",
        blank=True,
        max_length=500
    )
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome_site

    class Meta:
        verbose_name = "Configuração do site"
        verbose_name_plural = "Configurações do site"
