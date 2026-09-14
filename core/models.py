import os

from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError

LANGUAGE_FLUENCY = [
    ('Básico', 'Básico'),
    ('Intermediário', 'Intermediário'),
    ('Avançado', 'Avançado'),
    ('Fluente', 'Fluente'),
    ('Nativo', 'Nativo')
]

LANGUAGE_CHOICES = [
    ('Inglês', 'Inglês'),
    ('Espanhol', 'Espanhol'),
    ('Francês', 'Francês'),
    ('Alemão', 'Alemão'),
    ('Mandarim', 'Mandarim'),
    ('Japonês', 'Japonês'),
    ('Italiano', 'Italiano'),
    ('Russo', 'Russo'),
    ('Árabe', 'Árabe'),
    ('Português', 'Português'),
    ('Outro', 'Outro')
]

class UsuarioManager(BaseUserManager):
    def create_user(self, email, nome, tipo, password=None):
        if not email:
            raise ValueError('O usuário deve ter um endereço de e-mail')
        user = self.model(email=self.normalize_email(
            email), nome=nome, tipo=tipo)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nome, tipo, password=None):
        user = self.create_user(email, nome, tipo, password)
        user.is_admin = True
        user.save(using=self._db)
        return user


class UsuarioBase(AbstractBaseUser):
    nome = models.CharField(max_length=300)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)

    tipo = models.CharField(max_length=10, null=False)

    foto = models.ImageField(upload_to="fotos_perfil/",
                             validators=[FileExtensionValidator(
                                 allowed_extensions=["jpg", "png", "jpeg"])],
                             null=True,
                             blank=True,
                             default=None)
    objects = UsuarioManager()
    USERNAME_FIELD = 'email'

    REQUIRED_FIELDS = ['nome']

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    @property
    def is_staff(self):
        return self.is_admin


class Estado(models.Model):
    nome_estado = models.CharField(max_length=100)
    sigla_estado = models.CharField(max_length=2)

    def __str__(self):
        return f"{self.nome_estado} ({self.sigla_estado})"


class Cidade(models.Model):
    nome_cidade = models.CharField(max_length=100)
    estado_cidade = models.ForeignKey(Estado, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.nome_cidade} - {self.estado_cidade.sigla_estado}"


# Endereço
class Endereco(models.Model):
    cep = models.CharField(max_length=10)
    rua = models.CharField(max_length=255)
    bairro = models.CharField(max_length=255)
    numero = models.CharField(max_length=10)
    complemento = models.CharField(max_length=255, blank=True, null=True)
    cidade = models.ForeignKey(Cidade, on_delete=models.PROTECT)
    estado = models.ForeignKey(Estado, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.rua}, {self.numero} - {self.bairro}, {self.cidade.nome_cidade} - {self.estado.sigla_estado}"

#Usuário do Sistema
class Usuario(models.Model):
    user = models.OneToOneField(
        UsuarioBase, on_delete=models.CASCADE, primary_key=True)
    
    # informação pessoal
    nome_social = models.CharField(max_length=255, blank=True, null=True)
    data_nascimento = models.DateField()
    genero = models.CharField(max_length=255)
    estado_civil = models.CharField(max_length=255)
    nacionalidade = models.CharField(max_length=255)
    telefone = models.CharField(max_length=20)
    
     # vínculo com IFMG
    ifmg = models.BooleanField(default=False)

    # endereco
    endereco = models.OneToOneField(
        Endereco, on_delete=models.CASCADE, blank=True, null=True)

    # obejtivo_profissional
    objetivo_profissional = models.OneToOneField(
        ProfessionalTarget, on_delete=models.CASCADE, blank=True, null=True)


class ProfessionalTarget(models.Model):
    cargo_pretendido = models.CharField(max_length=255, blank=True, null=True)
    area_interesse = models.CharField(max_length=255, blank=True, null=True)
    pretensao_salarial = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    disponibilidade =  models.CharField(max_length=255, blank=True, null=True)
    remoto = models.BooleanField(default=False)

class AcademyGraduation(models.Model):
    instituicao_nome = models.CharField(max_length=255, blank=True, null=True)
    grau_escolaridade = models.CharField(max_length=255, blank=True, null=True)
    curso_graduacao = models.CharField(max_length=255, blank=True, null=True)
    situacao_academica = models.CharField(max_length=255, blank=True, null=True)
    data_acad_inicio = models.DateField(blank=True, null=True)
    data_acad_fim = models.DateField(blank=True, null=True)

class SocialMedia(models.Model):
    linkedin = models.URLField(blank=True, null=True)
    github = models.URLField(blank=True, null=True)
    instagram = models.CharField(max_length=100, blank=True, null=True)  # apenas username
    facebook = models.URLField(blank=True, null=True)
    site_pessoal = models.URLField(blank=True, null=True)

class Competencia(models.Model):
    nome_competencia = models.CharField(max_length=255)
    tipo_competencia = models.CharField(max_length=50, choices=[('tecnica', 'Técnica'), ('comportamental', 'Comportamental')])

    def __str__(self):
        return f"{self.nome_competencia} ({self.tipo_competencia})"

class Hobby(models.Model):
    nome_hobby = models.CharField(max_length=255)

    def __str__(self):
        return self.nome_hobby


class Acessibilidade(models.Model):
    usuario = models.OneToOneField(
        'Usuario',
        on_delete=models.CASCADE,
        related_name='acessibilidade'
    )

    pessoa_com_deficiencia = models.BooleanField(default=False)
    tipo_deficiencia = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    necessidade_adaptacao = models.TextField(
        blank=True,
        null=True
    )

    def __str__(self):
        nome = getattr(self.usuario, 'nome_social', None)
        if not nome:
            nome = getattr(
                getattr(self.usuario, 'user', None),
                'email',
                None
            ) or 'usuário'
        return f"Acessibilidade de {nome}"


class Attachment(models.Model):
    usuario = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(upload_to='attachments/')
    description = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    def __str__(self):
        nome = getattr(self.usuario, 'nome_social', None)
        if not nome:
            nome = getattr(
                getattr(self.usuario, 'user', None),
                'email',
                None
            ) or 'usuário'
        return f"Attachment for {nome}: {self.description or 'No description'}"


    # formação academica 1 
    formacao_academica = models.OneToOneField(
        AcademyGraduation, on_delete=models.CASCADE, blank=True, null=True, related_name='formacao_academica')

    # rede sociais e links
    social_media = models.OneToOneField(
        SocialMedia, on_delete=models.CASCADE, blank=True, null=True)

    # competencias 
    competencias = models.ManyToManyField(Competencia, blank=True)

    # informações adicionais
    interesses_hobbies = models.ManyToManyField(Hobby, blank=True)

    # METADADOS
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    @property
    def cep(self):
        return self.endereco.cep if self.endereco else None

    @property
    def rua(self):
        return self.endereco.rua if self.endereco else None

    @property
    def bairro(self):
        return self.endereco.bairro if self.endereco else None

    @property
    def numero(self):
        return self.endereco.numero if self.endereco else None

    @property
    def complemento(self):
        return self.endereco.complemento if self.endereco else None

    @property
    def cidade(self):
        return self.endereco.cidade if self.endereco and self.endereco.cidade else None

    @property
    def estado(self):
        return self.endereco.estado if self.endereco and self.endereco.estado else None

    @property
    def cargo_pretendido(self):
        return self.objetivo_profissional.cargo_pretendido if self.objetivo_profissional else None

    @property
    def area_interesse(self):
        return self.objetivo_profissional.area_interesse if self.objetivo_profissional else None

    @property
    def pretensao_salarial(self):
        return self.objetivo_profissional.pretensao_salarial if self.objetivo_profissional else None

    @property
    def disponibilidade(self):
        return self.objetivo_profissional.disponibilidade if self.objetivo_profissional else None

    @property
    def remoto(self):
        return self.objetivo_profissional.remoto if self.objetivo_profissional else None

    @property
    def linkedin(self):
        return self.social_media.linkedin if self.social_media else None

    @property
    def github(self):
        return self.social_media.github if self.social_media else None

    @property
    def instagram(self):
        return self.social_media.instagram if self.social_media else None

    @property
    def facebook(self):
        return self.social_media.facebook if self.social_media else None

    @property
    def site_pessoal(self):
        return self.social_media.site_pessoal if self.social_media else None

    @property
    def pessoa_com_deficiencia(self):
        return self.acessibilidade.pessoa_com_deficiencia if self.acessibilidade else False

    @property
    def tipo_deficiencia(self):
        return self.acessibilidade.tipo_deficiencia if self.acessibilidade else None

    @property
    def necessidade_adaptacao(self):
        return self.acessibilidade.necessidade_adaptacao if self.acessibilidade else None

    def __str__(self):
        return self.nome_social or self.user.email

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

class LimitedModel(models.Model):

    def __init__(self, *args, max_instances=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_instances = max_instances if max_instances is not None else int(os.getenv("DEFAULT_INSTANCES", 3))

    class Meta:
        abstract = True

    def clean(self):
        if self.usuario_id:
            model_class = self.__class__
            qtd = model_class.objects.filter(usuario=self.usuario).exclude(pk=self.pk).count()
            if qtd >= self.max_instances:
                raise ValidationError(f'Usuário pode ter no máximo {self.max_instances} {model_class.__name__.lower()}s.')

class ExperienciaProfissional(LimitedModel):

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='experiencias')
    nome_empresa = models.CharField(max_length=255, blank=True, null=True)
    cargo = models.CharField(max_length=255, blank=True, null=True)
    data_inicio = models.DateField(blank=True, null=True)
    data_fim = models.DateField(blank=True, null=True)  
    
    def __init__(self, *args, **kwargs):
        super().__init__(max_instances=int(os.getenv("EXPERIENCIA_PROFISSIONAL_INSTANCES",3)), *args, **kwargs)

    def __str__(self):
        return f"{self.cargo} - {self.nome_empresa}"


class CursoExtraCurricular(LimitedModel):
    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name='cursos_extras')
    nome_curso = models.CharField(max_length=255, blank=True, null=True)
    instituicao = models.CharField(max_length=255, blank=True, null=True)
    carga_horaria = models.PositiveIntegerField(blank=True, null=True)
    data_conclusao = models.DateField(blank=True, null=True)
    link_certificado = models.URLField(blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(max_instances=int(os.getenv("CURSO_EXTRA_CURRICULAR_INSTANCES",3)), *args, **kwargs)

    def __str__(self):
        return "\n".join([
            self.nome_curso
        ])


class Idioma(LimitedModel):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='idiomas')
    language = models.CharField(max_length=100, choices=LANGUAGE_CHOICES)
    fluency = models.CharField(max_length=100, choices=LANGUAGE_FLUENCY, blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(max_instances=int(os.getenv("IDIOMA_INSTANCES",3)), *args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'language'], name='unique_idioma_por_usuario')
        ]

    def __str__(self):
        return f"{self.language} ({self.fluency})"


class Hub(models.Model):
    nome_hub = models.CharField(max_length=100, unique=True)
    descricao_hub = models.CharField(max_length=250)
    foto_hub = models.ImageField(upload_to="fotos_hub/",
                             validators=[FileExtensionValidator(
                                 allowed_extensions=["jpg", "png", "jpeg"])],
                             null=True,
                             blank=True,
                             default=None)
    isActive = models.BooleanField(default=True)
    area_foco_hub = models.TextField(blank=True, default="")
    tecnologias_hub = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.nome_hub}"


class UsuarioHub(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.usuario.nome_social or self.usuario.user.nome} - {self.hub.nome_hub}"


class Sala(models.Model):
    hubs = models.ManyToManyField(Hub, related_name='salas', blank=True)
    nome_sala = models.CharField(max_length=100)
    descricao_recursos = models.TextField()
    foto_sala = models.ImageField(upload_to="fotos_sala/",
                             validators=[FileExtensionValidator(
                                 allowed_extensions=["jpg", "png", "jpeg"])],
                             null=True,
                             blank=True,
                             default=None)
    isActive = models.BooleanField(default=True)

    def __str__(self):
        nomes_hubs = ", ".join(self.hubs.values_list('nome_hub', flat=True))
        if nomes_hubs:
            return f"{self.nome_sala} ({nomes_hubs})"
        return self.nome_sala


class SalaImagem(models.Model):
    sala = models.ForeignKey(Sala, on_delete=models.CASCADE, related_name='imagens')
    imagem = models.ImageField(upload_to="fotos_sala/",
                             validators=[FileExtensionValidator(
                                 allowed_extensions=["jpg", "png", "jpeg"])])
    ordem = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['ordem', 'id']

    def __str__(self):
        return f"Imagem {self.ordem} de {self.sala.nome_sala}"


class Noticia(models.Model):
    titulo_noticia = models.CharField(max_length=250)
    descricao_noticia = models.CharField(max_length=250)
    fonte = models.CharField(max_length=50)
    url = models.URLField(blank=True, null=True)
    isActive = models.BooleanField(default=True)
    isHome = models.BooleanField(default=True)
    imagem_noticia = models.ImageField(upload_to="fotos_noticia/",
                             validators=[FileExtensionValidator(
                                 allowed_extensions=["jpg", "png", "jpeg"])],
                             null=True,
                             blank=True,
                             default=None, db_column='foto_hub')

class NoticiaHub(models.Model):
    noticia = models.ForeignKey(Noticia, on_delete=models.CASCADE)
    hub = models.ForeignKey(Hub, on_delete=models.CASCADE)


class InteresseCompra(models.Model):
    """Interesse de compra declarado por um usuário (demanda).

    Categoria/descrição usadas como critério de compatibilidade com Produto —
    sujeitas à definição final do cliente para o processo de Match.
    """
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='interesses_compra')
    categoria_interesse = models.CharField(max_length=150, blank=True, default="")
    descricao_interesse = models.TextField(blank=True, default="")
    preco_maximo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    isActive = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.usuario_id}: {self.categoria_interesse or self.descricao_interesse}"

