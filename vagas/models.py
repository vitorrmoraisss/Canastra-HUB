from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, User
from django.db.models.deletion import ProtectedError
from core.models import *
from empresa.models import *

# Create your models here.

ESCOLARIDADE = (
    (0, 'Ensino Fundamental Incompleto'),
    (1, 'Ensino Fundamental Completo'),
    (2, 'Ensino Médio Incompleto'),
    (3, 'Ensino Médio Completo'),
    (4, 'Ensino Técnico'),
    (5, 'Ensino Superior Incompleto'),
    (6, 'Ensino Superior Completo'),
    (7, 'Pós-Graduação (Especialização)'),
    (8, 'Mestrado'),
    (9, 'Doutorado'),
    (10, 'Pós-Doutorado'),
)

class Vagas(models.Model):
    cargo_vaga = models.CharField(max_length=100,  blank=True, null=True)
    descricao_vaga = models.TextField(blank=True, null=True)
    requisito_vaga = models.TextField(blank=True, null=True)
    
    local = models.CharField(max_length=255, blank=True, null=True)
    data_publicacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=255, blank=True, null=True, default='ativa')

    anos_experiencia_req = models.FloatField(default=0.0,blank=True, null=True)
    nivel_formacao_req = models.PositiveSmallIntegerField(default=0, choices=ESCOLARIDADE,blank=True, null=True)

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='vagas')
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE, related_name='vagas', null=True, blank=True)

    def __str__(self):
        return f"Vaga: {self.cargo_vaga}, {self.descricao_vaga}"
    
class UsuarioVaga(models.Model):
    STATUS_CANDIDATADO = 'candidatado'
    STATUS_CONTRATADO = 'contratado'
    STATUS_REJEITADO = 'rejeitado'
    STATUS_CHOICES = [
        (STATUS_CANDIDATADO, 'Candidatado'),
        (STATUS_CONTRATADO, 'Contratado'),
        (STATUS_REJEITADO, 'Rejeitado'),
    ]

    vaga = models.ForeignKey(Vagas, on_delete=models.CASCADE)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    data_candidatura = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_CANDIDATADO)
    data_status = models.DateTimeField(null=True, blank=True)
    ifmg_no_momento_contratacao = models.BooleanField(default=False)


    def __str__(self):
        return f"{self.usuario.nome_social} -> {self.vaga.cargo_vaga}"

class CursoVaga(models.Model):
    vaga = models.ForeignKey(Vagas, on_delete=models.CASCADE)
    curso = models.CharField(max_length=100, blank=True, null=True)
    