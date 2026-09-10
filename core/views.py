import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import FloatField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from core.models import *
from empresa.models import *
from django.contrib.auth.decorators import login_required
from decimal import Decimal, InvalidOperation
from datetime import datetime
import re
import requests
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.template.loader import render_to_string

from treinamento.models import Treinamento, InscricaoTreinamento
from vagas.models import Vagas
from eventos.models import Evento, InscricaoEvento


def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None


def _usuario_logado(request):
    if not request.user.is_authenticated:
        return None
    try:
        return Usuario.objects.get(user=request.user)
    except Usuario.DoesNotExist:
        return None

def home(request):
    # Buscar notícias ativas que devem aparecer na home
    noticias_home = NoticiaHub.objects.filter(
        noticia__isActive=True,
        noticia__isHome=True
    ).select_related('noticia', 'hub').order_by('-noticia__id')[:5]  # Limitando a 10 notícias
    
    return render(request, 'home.html', {
        'noticias_home': noticias_home
    })

def parceiros(request):

    return render(request, 'parceiros.html')

def eventos_treinamentos(request):
    termo = request.GET.get('q', '').strip()

    eventos = Evento.objects.select_related('hub').order_by('-data_evento_inicio')
    treinamentos = Treinamento.objects.select_related('hub').prefetch_related('sessoes').order_by('-id')

    if termo:
        eventos = eventos.filter(
            Q(nome_evento__icontains=termo)
            | Q(descricao_evento__icontains=termo)
            | Q(local_evento__icontains=termo)
        ).distinct()
        treinamentos = treinamentos.filter(
            Q(nome__icontains=termo)
            | Q(descricao__icontains=termo)
            | Q(local__icontains=termo)
        ).distinct()

    inscritos_eventos = set()
    inscritos_treinamentos = set()
    if request.user.is_authenticated:
        inscritos_eventos = set(
            InscricaoEvento.objects.filter(usuario=request.user).values_list('evento_id', flat=True)
        )
        inscritos_treinamentos = set(
            InscricaoTreinamento.objects.filter(usuario=request.user).values_list('treinamento_id', flat=True)
        )

    itens = []
    for e in eventos:
        e.tipo = 'evento'
        e.data_ordenacao = e.data_evento_inicio
        e.inscrito = e.id in inscritos_eventos
        itens.append(e)
    for t in treinamentos:
        t.tipo = 'treinamento'
        t.data_ordenacao = t.data_inicio
        t.inscrito = t.id in inscritos_treinamentos
        itens.append(t)

    itens.sort(key=lambda i: i.data_ordenacao or datetime.min.date(), reverse=True)

    return render(request, 'eventos_treinamentos.html', {
        'itens': itens,
        'termo': termo,
    })

def hubs(request):
    """View para a central de hubs"""
    from matching.models import HubMatchScore

    hubs = Hub.objects.filter(isActive=True)

    # Usuário logado para cálculo de compatibilidade
    usuario_perfil = _usuario_logado(request)

    # Ordena os hubs pela compatibilidade quando houver usuário logado
    ordenado_por_score = usuario_perfil is not None

    if usuario_perfil:
        score_subquery = HubMatchScore.objects.filter(
            usuario=usuario_perfil,
            hub=OuterRef('pk'),
        ).values('score')[:1]

        hubs = hubs.annotate(
            match_score=Coalesce(
                Subquery(
                    score_subquery,
                    output_field=FloatField()
                ),
                Value(0.0),
            )
        ).order_by('-match_score', 'nome_hub')

    # Hubs que o usuário já marcou como interesse
    hubs_vinculados = []

    if (
        request.user.is_authenticated
        and request.session.get('perfil') == 'usuario'
    ):
        usuario = Usuario.objects.filter(
            user=request.user
        ).first()

        if usuario:
            hubs_vinculados = list(
                UsuarioHub.objects.filter(
                    usuario=usuario
                ).values_list(
                    'hub_id',
                    flat=True
                )
            )

    return render(request, 'hubs.html', {
        'hubs': hubs,
        'ordenado_por_score': ordenado_por_score,
        'hubs_vinculados': hubs_vinculados,
        'pode_selecionar_hub': (
            request.user.is_authenticated
            and request.session.get('perfil') == 'usuario'
        ),
    })


@login_required
@require_http_methods(["POST"])
def toggle_hub_interesse(request, hub_id):
    """Marca/desmarca um hub como de interesse do usuário logado."""

    if request.session.get('perfil') != 'usuario':
        messages.error(
            request,
            'Apenas usuários podem selecionar hubs de interesse.'
        )
        return redirect('core:hubs')

    usuario = get_object_or_404(
        Usuario,
        user=request.user
    )

    hub = get_object_or_404(
        Hub,
        id=hub_id,
        isActive=True
    )

    vinculo = UsuarioHub.objects.filter(
        usuario=usuario,
        hub=hub
    )

    if vinculo.exists():
        vinculo.delete()
    else:
        UsuarioHub.objects.create(
            usuario=usuario,
            hub=hub
        )

    return redirect('core:hubs')

def hub_detalhe(request, nome_hub):
    """View dinâmica para cada hub"""
    from matching.models import ProdutoMatch

    hub = get_object_or_404(Hub, nome_hub=nome_hub, isActive=True)
    
    # Buscar notícias relacionadas ao hub
    noticias = NoticiaHub.objects.filter(
        hub=hub, 
        noticia__isActive=True
    ).select_related('noticia')

    eventos = Evento.objects.filter(
        hub=hub
    ).order_by('-id')

    vagas = Vagas.objects.filter(
        hub=hub
    ).order_by('-data_publicacao')

    #Treinamento  vinculado ao hub (novo app)
    treinamentos  = Treinamento.objects.filter(hub=hub).prefetch_related('sessoes').order_by('-id')

    #Empresas parceiras vinculadas ao hub
    empresas_hub = EmpresaHub.objects.filter(hub=hub).select_related('empresa__user')

    #Produtos ofertados pelas empresas do hub, com compatibilidade com os interesses do usuário logado
    empresa_ids = empresas_hub.values_list('empresa_id', flat=True)
    produtos = Produto.objects.filter(
        empresa_id__in=empresa_ids,
        isActive=True,
        empresa__user__is_active=True,
    ).select_related('empresa')

    usuario_perfil = _usuario_logado(request)
    if usuario_perfil:
        melhor_score_subquery = ProdutoMatch.objects.filter(
            produto=OuterRef('pk'),
            interesse__usuario=usuario_perfil,
            interesse__isActive=True,
        ).order_by('-score').values('score')[:1]

        produtos = produtos.annotate(
            match_score=Coalesce(
                Subquery(melhor_score_subquery, output_field=FloatField()),
                Value(0.0),
            )
        ).order_by('-match_score', 'nome_produto')

    context = {
        'hub': hub,
        'noticias': noticias,
        'treinamentos': treinamentos,
        'vagas': vagas,
        'eventos': eventos,
        'empresas_hub': empresas_hub,
        'produtos': produtos,
        'ordenado_por_score_produto': usuario_perfil is not None,
    }
    return render(request, 'hub.html', context)

def sobre(request):

    return render(request, 'sobre.html')

def espacos_hub(request):

    return render(request, 'espacos_hub.html')

def cadastro(request):

    return render(request, 'cadastro.html')

    # 4. Prepara o contexto
    contexto = {
        'eventos': eventos,
        'termo_busca': termo_busca,  # Passa o termo de volta para o input na tela
    }

    # 5. Renderiza o template de busca
    return render(request, 'tela_busca_eventos.html', contexto)

def render_cadastro_usuario(request):
    estados = Estado.objects.all().order_by('nome_estado')
    return render(request, 'cadastro_usuario.html', {'estados': estados})


def cadastro_usuario(request):
    if request.user.is_authenticated:
        messages.warning(
            request,
            'Você já está logado, não é possível realizar outro cadastro.'
        )
        return redirect('core:home')

    if request.method != 'POST':
        return render_cadastro_usuario(request)

    nomeUser = request.POST.get('txtNome', '').strip()

    if not nomeUser:
      messages.error(request, 'O nome é obrigatório.')
      return render_cadastro_usuario(request)

    if len(nomeUser) < 3:
      messages.error(request, 'O nome deve possuir no mínimo 3 caracteres.')
      return render_cadastro_usuario(request)
      
    nomeSocial = request.POST.get('txtNomeSocial')
    dataNasc = request.POST.get('txtDataNasc')
    genero = request.POST.get('txtGenero')
    estadoCivil = request.POST.get('txtEstadoCivil')
    nacionalidade = request.POST.get('txtNacionalidade')
    email = request.POST.get('txtEmail', '').strip()
    telefone = request.POST.get('txtTelefone')
    senha = request.POST.get('txtSenha')
    confirmacaoSenha = request.POST.get('txtConfirmarSenha')
    foto_user = request.FILES.get('fileFoto')
    cep = request.POST.get('txtCep')
    rua = request.POST.get('txtRua')
    numero = request.POST.get('txtNumero')
    bairro = request.POST.get('txtBairro')
    complemento = request.POST.get('txtComplemento')
    estado_id = request.POST.get('estado')
    cidade_id = request.POST.get('cidade')
    
    if senha != confirmacaoSenha:
        messages.error(request,"As senhas devem ser iguais.")
        return render_cadastro_usuario(request)


    if request.method == 'POST':
        # =========================
        # DADOS PRINCIPAIS
        # =========================

        nomeUser = request.POST.get('txtNome', '').strip()
        email = request.POST.get('txtEmail', '').strip()
        senha = request.POST.get('txtSenha', '')

        # =========================
        # VALIDAÇÃO DO NOME
        # =========================

        if not nomeUser:
            messages.error(request, 'O nome é obrigatório.')
            return render_cadastro_usuario(request)

        if len(nomeUser) < 3:
            messages.error(
                request,
                'O nome deve possuir no mínimo 3 caracteres.'
            )
            return render_cadastro_usuario(request)

        # =========================
        # VALIDAÇÃO DO E-MAIL
        # =========================

        if not email:
            messages.error(request, 'O e-mail é obrigatório.')
            return render_cadastro_usuario(request)

        # Verifica se o e-mail já está cadastrado
        if UsuarioBase.objects.filter(email=email).exists():
            messages.error(
                request,
                'Já existe uma conta cadastrada com este e-mail.'
            )
            return render_cadastro_usuario(request)

        # =========================
        # VALIDAÇÃO DA SENHA
        # =========================

        if not senha.strip():
            messages.error(request, 'A senha é obrigatória.')
            return render_cadastro_usuario(request)

        if not confirmacaoSenha.strip():
            messages.error(
                request,
                'A confirmação da senha é obrigatória.'
            )
            return render_cadastro_usuario(request)

        if senha != confirmacaoSenha:
            messages.error(request, 'As senhas devem ser iguais.')
            return render_cadastro_usuario(request)

        # =========================
        # DEMAIS DADOS
        # =========================

        nomeSocial = request.POST.get('txtNomeSocial')
        dataNasc = request.POST.get('txtDataNasc')
        genero = request.POST.get('txtGenero')
        estadoCivil = request.POST.get('txtEstadoCivil')
        nacionalidade = request.POST.get('txtNacionalidade')

        telefone = request.POST.get('txtTelefone')
        foto_user = request.FILES.get('fileFoto')
        cep = request.POST.get('txtCep') or ''
        rua = request.POST.get('txtRua') or ''
        numero = request.POST.get('txtNumero') or ''
        bairro = request.POST.get('txtBairro') or ''
        complemento = request.POST.get('txtComplemento') or ''

        cidade_id = request.POST.get('cidade')
        estado_id = request.POST.get('estado')
        
        if not cidade_id:
            messages.error(request, 'Selecione uma cidade.')
            return render(request, 'cadastro_usuario.html', {'estados': estados})

        if not estado_id:
            messages.error(request, 'Selecione um estado.')
            return render(request, 'cadastro_usuario.html', {'estados': estados})

        # =========================
        # VALIDAÇÃO DO ESTADO
        # =========================

        if not estado_id:
            messages.error(request, 'Selecione um estado.')
            return render_cadastro_usuario(request)

        if not str(estado_id).isdigit():
            messages.error(request, 'Estado inválido.')
            return render_cadastro_usuario(request)

        try:
            estado = Estado.objects.get(id=estado_id)
        except Estado.DoesNotExist:
            messages.error(request, 'Estado inválido.')
            return render_cadastro_usuario(request)

        # =========================
        # VALIDAÇÃO DA CIDADE
        # =========================
        if not cidade_id:
          messages.error(request, 'Selecione uma cidade.')
          return render_cadastro_usuario(request)

        if not str(cidade_id).isdigit():
           messages.error(request, 'Cidade inválida.')
           return render_cadastro_usuario(request)

        try:
          cidade = Cidade.objects.get(
          id=cidade_id,
          estado_cidade_id=estado_id
        )
        except Cidade.DoesNotExist:
          messages.error(
          request,
          'A cidade selecionada não pertence ao estado informado.'
        )
        return render_cadastro_usuario(request)

        if not dataNasc:
            messages.error(
                request,
                'Informe a data de nascimento.'
            )
            return render_cadastro_usuario(request)

        # =========================
        # CRIAÇÃO DO USUÁRIO
        # =========================


        user = UsuarioBase.objects.create_user(
            email=email,
            password=senha,
            nome=nome_user,
            tipo='usuario'
        )
       if foto_user:
    user.foto = foto_user
    user.save()

    # =========================
    # CRIAÇÃO DO ENDEREÇO
    # =========================

    endereco = Endereco.objects.create(
      cep=cep,
      rua=rua,
      numero=numero,
      bairro=bairro,
      complemento=complemento,
      estado=estado,
      cidade=cidade
    )

    # =========================
    # CRIAÇÃO DO PERFIL
    # =========================

    usuario = Usuario.objects.create(
      user=user,
      nome_social=nomeSocial or None,
      data_nascimento=dataNasc,
      genero=genero,
      estado_civil=estadoCivil,
      nacionalidade=nacionalidade,
      telefone=telefone,
      endereco=endereco,
    )

        request.session['usuario_email'] = usuario.user.email

        messages.success(
            request,
            'Cadastro inicial realizado! Complete seu perfil profissional!'
        )


        return redirect('core:login')

    # =========================
    # GET
    # =========================

    return render(request, 'cadastro_usuario.html', {'estados': estados})

    def cadastro_completo(request):
      usuario_email = request.session.get('usuario_email') or request.session.get('email_atual')
    
    if not usuario_email:
        messages.error(request, 'Você deve realizar o cadastro inicial primeiro!')
        return redirect('core:cadastro_usuario')

    usuario = Usuario.objects.select_related('user').filter(user__email=usuario_email).first()
    if not usuario:
        messages.error(request, 'Usuário não encontrado.')
        return redirect('core:cadastro_usuario')

    if request.method == 'POST':
        request.session['incompleto'] = False

        nome_social = request.POST.get('nome_social') or request.POST.get('txtNomeSocial') or None
        data_nascimento = _parse_date(request.POST.get('data_nascimento') or request.POST.get('txtDataNasc'))
        genero = request.POST.get('genero') or request.POST.get('txtGenero') or usuario.genero
        estado_civil = request.POST.get('estado_civil') or request.POST.get('txtEstadoCivil') or usuario.estado_civil
        nacionalidade = request.POST.get('nacionalidade') or request.POST.get('txtNacionalidade') or usuario.nacionalidade
        telefone = request.POST.get('telefone') or request.POST.get('txtTelefone') or usuario.telefone

        usuario.nome_social = nome_social
        usuario.data_nascimento = data_nascimento or usuario.data_nascimento
        usuario.genero = genero
        usuario.estado_civil = estado_civil
        usuario.nacionalidade = nacionalidade
        usuario.telefone = telefone
        usuario.save()

        endereco = usuario.endereco or Endereco()
        estado_id = request.POST.get('estado') or request.POST.get('estado_id')
        cidade_id = request.POST.get('cidade') or request.POST.get('cidade_id')
        endereco.cep = request.POST.get('cep') or request.POST.get('txtCep') or (endereco.cep or '')
        endereco.rua = request.POST.get('rua') or request.POST.get('txtRua') or (endereco.rua or '')
        endereco.bairro = request.POST.get('bairro') or request.POST.get('txtBairro') or (endereco.bairro or '')
        endereco.numero = request.POST.get('numero') or request.POST.get('txtNumero') or (endereco.numero or '')
        endereco.complemento = request.POST.get('complemento') or request.POST.get('txtComplemento') or (endereco.complemento or '')

        if estado_id:
            endereco.estado = Estado.objects.get(id=estado_id)
        if cidade_id:
            endereco.cidade = Cidade.objects.get(id=cidade_id)

        if endereco.estado and endereco.cidade:
            endereco.save()
            usuario.endereco = endereco
            usuario.save()

        objetivo = usuario.objetivo_profissional or ProfessionalTarget.objects.create()
        objetivo.cargo_pretendido = request.POST.get('cargo_pretendido') or request.POST.get('txtCargoPretendido') or None
        objetivo.area_interesse = request.POST.get('area_interesse') or request.POST.get('txtAreaInteresse') or None
        objetivo.pretensao_salarial = _parse_decimal(request.POST.get('pretensao_salarial') or request.POST.get('decPretensaoSalarial'))
        objetivo.disponibilidade = request.POST.get('disponibilidade') or request.POST.get('txtDisponibilidade') or None
        objetivo.remoto = request.POST.get('remoto') == 'sim' or request.POST.get('remoto') == 'on'
        objetivo.save()
        usuario.objetivo_profissional = objetivo
        usuario.save()

        formacao = usuario.formacao_academica or AcademyGraduation.objects.create()
        for index in ('1', '2', '3'):
            instituicao = request.POST.get(f'instituicao_nome{index}') or request.POST.get(f'txtNomeInstituicao{index}')
            grau = request.POST.get(f'grau_escolaridade{index}') or request.POST.get(f'escolaridade{index}')
            curso = request.POST.get(f'curso_graduacao{index}') or request.POST.get(f'txtCurso{index}')
            situacao = request.POST.get(f'situacao_academica{index}') or request.POST.get(f'txtSituacao{index}')
            data_inicio = _parse_date(request.POST.get(f'data_acad_inicio{index}') or request.POST.get(f'txtDataAcad{index}'))
            data_fim = _parse_date(request.POST.get(f'data_acad_fim{index}') or request.POST.get(f'txtDataFimAcad{index}'))

            if any([instituicao, grau, curso, situacao, data_inicio, data_fim]):
                formacao.instituicao_nome = instituicao or formacao.instituicao_nome
                formacao.grau_escolaridade = grau or formacao.grau_escolaridade
                formacao.curso_graduacao = curso or formacao.curso_graduacao
                formacao.situacao_academica = situacao or formacao.situacao_academica
                formacao.data_acad_inicio = data_inicio or formacao.data_acad_inicio
                formacao.data_acad_fim = data_fim or formacao.data_acad_fim
                break

        formacao.save()
        usuario.formacao_academica = formacao
        usuario.save()

        social = usuario.social_media or SocialMedia.objects.create()
        social.linkedin = request.POST.get('linkedin') or request.POST.get('txtLinkedin') or None
        social.github = request.POST.get('github') or request.POST.get('txtGithub') or None
        social.instagram = request.POST.get('instagram') or request.POST.get('txtInstagram') or None
        social.facebook = request.POST.get('facebook') or request.POST.get('txtFacebook') or None
        social.site_pessoal = request.POST.get('site_pessoal') or request.POST.get('txtSitePessoal') or None
        social.save()
        usuario.social_media = social
        usuario.save()

        usuario.competencias.clear()
        for raw_value in [request.POST.get('skills'), request.POST.get('competencias')]:
            if raw_value:
                for item in [part.strip() for part in raw_value.split(',') if part.strip()]:
                    competencia, _ = Competencia.objects.get_or_create(
                        nome_competencia=item,
                        defaults={'tipo_competencia': 'tecnica'}
                    )
                    usuario.competencias.add(competencia)

        for index in ('1', '2', '3'):
            tecnica = request.POST.get(f'txtHardSkil{index}') or request.POST.get(f'competencias_tecnicas{index}')
            comportamental = request.POST.get(f'txtSoftSkil{index}') or request.POST.get(f'competencias_comportamentais{index}')
            for raw_value, tipo_competencia in ((tecnica, 'tecnica'), (comportamental, 'comportamental')):
                if raw_value:
                    for item in [part.strip() for part in raw_value.split(',') if part.strip()]:
                        competencia, _ = Competencia.objects.get_or_create(
                            nome_competencia=item,
                            defaults={'tipo_competencia': tipo_competencia}
                        )
                        usuario.competencias.add(competencia)

        usuario.interesses_hobbies.clear()
        for raw_value in [request.POST.get('interesses_hobbies') or request.POST.get('txtHobbie')]:
            if raw_value:
                for item in [part.strip() for part in raw_value.split(',') if part.strip()]:
                    hobby, _ = Hobby.objects.get_or_create(nome_hobby=item)
                    usuario.interesses_hobbies.add(hobby)

        acessibilidade = usuario.acessibilidade or Acessibilidade.objects.create(usuario=usuario)
        acessibilidade.pessoa_com_deficiencia = request.POST.get('pcd') == 'sim' or request.POST.get('pessoa_com_deficiencia') == 'on'
        acessibilidade.tipo_deficiencia = request.POST.get('tipoDeficiencia') or request.POST.get('tipo_deficiencia') or None
        acessibilidade.necessidade_adaptacao = request.POST.get('necessidadeAdaptacao') or request.POST.get('necessidade_adaptacao') or None
        acessibilidade.save()

        if request.FILES.get('curriculoPdf'):
            Attachment.objects.filter(usuario=usuario, description='curriculo').delete()
            Attachment.objects.create(usuario=usuario, file=request.FILES['curriculoPdf'], description='curriculo')
        if request.FILES.get('cartaApresentacao'):
            Attachment.objects.filter(usuario=usuario, description='carta_apresentacao').delete()
            Attachment.objects.create(usuario=usuario, file=request.FILES['cartaApresentacao'], description='carta_apresentacao')

        ExperienciaProfissional.objects.filter(usuario=usuario).delete()
        for index in ('1', '2', '3'):
            nome_empresa = request.POST.get(f'txtNomeEmpresa{index}') or request.POST.get(f'nome_empresa{index}')
            cargo = request.POST.get(f'txtCargo{index}') or request.POST.get(f'cargo{index}')
            data_inicio = _parse_date(request.POST.get(f'txtDataProf{index}') or request.POST.get(f'data_inicio{index}'))
            data_fim = _parse_date(request.POST.get(f'txtDataFimProf{index}') or request.POST.get(f'data_fim{index}'))
            if any([nome_empresa, cargo, data_inicio, data_fim]):
                ExperienciaProfissional.objects.create(
                    usuario=usuario,
                    nome_empresa=nome_empresa or None,
                    cargo=cargo or None,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                )

        CursoExtraCurricular.objects.filter(usuario=usuario).delete()
        for index in ('1', '2', '3'):
            nome_curso = request.POST.get(f'txtNomeCurso{index}') or request.POST.get(f'nome_curso{index}')
            instituicao = request.POST.get(f'txtInstituicao{index}') or request.POST.get(f'instituicao{index}')
            carga_horaria = request.POST.get(f'txtCargaHoras{index}') or request.POST.get(f'carga_horaria{index}')
            data_conclusao = _parse_date(request.POST.get(f'txtDataFimCurso{index}') or request.POST.get(f'data_conclusao{index}'))
            link_certificado = request.POST.get(f'txtLinkCertificado{index}') or request.POST.get(f'link_certificado{index}')
            if any([nome_curso, instituicao, carga_horaria, data_conclusao, link_certificado]):
                CursoExtraCurricular.objects.create(
                    usuario=usuario,
                    nome_curso=nome_curso or None,
                    instituicao=instituicao or None,
                    carga_horaria=int(carga_horaria) if carga_horaria else None,
                    data_conclusao=data_conclusao,
                    link_certificado=link_certificado or None,
                )

        Idioma.objects.filter(usuario=usuario).delete()
        for index in ('1', '2', '3'):
            language = request.POST.get(f'txtIdioma{index}') or request.POST.get(f'idioma{index}')
            fluency = request.POST.get(f'fluencia{index}') or request.POST.get(f'nivel_fluencia{index}')
            if language:
                Idioma.objects.create(usuario=usuario, language=language, fluency=fluency)

        messages.success(request, 'Cadastro realizado com sucesso!')
        return render(request, 'home.html')

    estados = Estado.objects.all().order_by('nome_estado')
    return render(request, 'cadastro_usuario_completo.html', {'estados': estados})



def login(request):
    if request.method == 'POST':
        email = request.POST.get('txtEmail')
        senha = request.POST.get('txtSenha')

        usuario = authenticate(request, username=email, password=senha)
        
        if usuario is not None:
            request.session.flush()
            #cria a sessao do usuario
            auth_login(request, usuario)
                
            request.session['is_login'] = False
            if usuario.foto and hasattr(usuario.foto, "url"):
                foto = usuario.foto.url
            else:
                foto = None
            if usuario.is_admin:
                request.session['is_admin'] = usuario.is_admin
            request.session['nome'] = usuario.nome
            request.session['foto'] = foto
            request.session['perfil'] = usuario.tipo
            if usuario.tipo == "usuario":
                tblusuario = Usuario.objects.get(user = usuario)
                if tblusuario.area_interesse == None:
                    request.session['incompleto'] = True 
                    
            request.session['id_atual'] = usuario.id
            request.session['email_atual'] = usuario.email
            
            
            #configura sessao para expirar em 4 horas
            request.session.set_expiry(14400)
            
            messages.success(request, 'Login realizado com sucesso!')
            return redirect('core:home')
        
        else:
            messages.error(request, 'Usuário ou senha inválidos.')

    return render(request, 'login.html')


def logout(request):
    # limpa a sessao ao deslogar
    request.session.flush()
    auth_logout(request)

    messages.success(request, 'Logout realizado com sucesso.')
    return redirect('core:home')


def recuperar_senha(request):
    if request.method == 'POST':
        email = (request.POST.get('txtEmail') or '').strip().lower()
        mensagem_padrao = 'Se o e-mail estiver cadastrado, você receberá as instruções.'

        usuario = UsuarioBase.objects.filter(email=email).first()
        if usuario:
            uidb64 = urlsafe_base64_encode(force_bytes(usuario.pk))
            token = default_token_generator.make_token(usuario)
            link = request.build_absolute_uri(
                reverse('core:redefinir_senha', kwargs={'uidb64': uidb64, 'token': token})
            )

            corpo_email = render_to_string('email/recuperar_senha_email.html', {
                'nome': usuario.nome,
                'link': link,
                'expiracao_minutos': 30,
            })

            try:
                requests.post(
                    settings.RECUPERACAO_URL,
                    json={
                        'secret': settings.RECUPERACAO_API_KEY,
                        'para': usuario.email,
                        'assunto': 'Redefinição de senha — Canastra HUB',
                        'mensagem': corpo_email,
                        'html': True,
                    },
                    timeout=10,
                )
            except requests.RequestException:
                logging.exception('Falha ao enviar e-mail de recuperação de senha')

        messages.success(request, mensagem_padrao)
        return redirect('core:login')

    return render(request, 'recuperar_senha.html')


def redefinir_senha(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        usuario = UsuarioBase.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, UsuarioBase.DoesNotExist):
        usuario = None

    token_valido = usuario is not None and default_token_generator.check_token(usuario, token)

    if not token_valido:
        messages.error(request, 'Este link é inválido ou expirou. Solicite a recuperação novamente.')
        return redirect('core:recuperar_senha')

    if request.method == 'POST':
        senha = request.POST.get('txtSenha') or ''
        confirmar_senha = request.POST.get('txtConfirmarSenha') or ''

        if senha != confirmar_senha:
            messages.error(request, 'As senhas não coincidem.')
            return render(request, 'nova_senha.html')

        if len(senha) < 8 or not re.search(r'[A-Z]', senha) or not re.search(r'[a-z]', senha) or not re.search(r'[0-9]', senha):
            messages.error(request, 'A senha deve ter pelo menos 8 caracteres, com letras maiúsculas, minúsculas e números.')
            return render(request, 'nova_senha.html')

        usuario.set_password(senha)
        usuario.save()

        messages.success(request, 'Senha redefinida com sucesso! Faça login com sua nova senha.')
        return redirect('core:login')

    return render(request, 'nova_senha.html')


@require_http_methods(["GET"])
def get_cidades(request):
    """View para retornar cidades via AJAX baseado no estado selecionado"""
    estado_id = request.GET.get('estado_id')

    # Validação básica do parâmetro
    if not estado_id or not estado_id.isdigit():
        return JsonResponse({
            'cidades': [],
            'error': 'ID do estado inválido'
        })

    # Verificar se o estado existe
    if not Estado.objects.filter(id=estado_id).exists():
        return JsonResponse({
            'cidades': [],
            'error': 'Estado não encontrado'
        })

    # Buscar cidades
    cidades = Cidade.objects.filter(
        estado_cidade_id=estado_id
    ).order_by('nome_cidade').values('id', 'nome_cidade')

    cidades_data = [
        {'id': cidade['id'], 'nome': cidade['nome_cidade']}
        for cidade in cidades
    ]

    return JsonResponse({
        'cidades': cidades_data,
        'total': len(cidades_data)
    })


# =============================================
# API AJAX PARA CIDADES
# =============================================

def buscar_cidades(request):
    """
    API para buscar cidades por estado via AJAX.
    Retorna JSON com lista de cidades.
    """
    estado_id = request.GET.get('estado_id')
    
    if not estado_id:
        return JsonResponse({'cidades': []})
    
    try:
        cidades = Cidade.objects.filter(estado_cidade_id=estado_id).order_by('nome_cidade')
        cidades_list = [{'id': c.id, 'nome': c.nome_cidade} for c in cidades]
        return JsonResponse({'cidades': cidades_list})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
