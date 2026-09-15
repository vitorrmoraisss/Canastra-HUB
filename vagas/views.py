from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import FloatField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce


from core.models import Usuario, Estado, Cidade, UsuarioBase
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from vagas.models import Vagas, UsuarioVaga, CursoVaga

import re

_PAGE_SIZE = 12


def limpar_numeros(valor):
    # Remove tudo que não for dígito
    return re.sub(r'\D', '', valor)


def cadastro_vagas(request):
    estados = Estado.objects.all().order_by('nome_estado')
    return render(request, 'cadastro_vagas.html', {'estados': estados})

@login_required
def criar_vagas(request):
    usuario_email = request.session.get('email_atual')

    if request.method == 'POST':
        titulo = request.POST.get('txtTitulo')

        if not titulo or not titulo.strip():
            messages.error(request, 'O título da vaga é obrigatório.')
            estados = Estado.objects.all().order_by('nome_estado')
            return render(request, 'cadastro_vagas.html', {
                'estados': estados,
            })

        descricao_vaga = request.POST.get('txtDescricao')
        local = request.POST.get('txtLocal')
        requisito_vaga = request.POST.get('txtRequisito')
        cursos = request.POST.getlist('txtCursos[]')

        usuario = UsuarioBase.objects.get(email=usuario_email)
        empresa = usuario.empresa

        vaga = Vagas.objects.create(
            cargo_vaga=titulo.strip(),
            local=local,
            descricao_vaga=descricao_vaga,
            requisito_vaga=requisito_vaga,
            empresa=empresa,
        )

        for curso in cursos:
            CursoVaga.objects.create(
                vaga=vaga,
                curso=curso
            )

        messages.success(request, 'Vaga cadastrada com sucesso!')
        return redirect('core:home')

    estados = Estado.objects.all().order_by('nome_estado')
    return render(request, 'cadastro_vagas.html', {
        'estados': estados,
    })


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

    cidades = Cidade.objects.filter(
        estado_cidade_id=estado_id).order_by('nome_cidade')

    cidades_data = [
        {'id': cidade.id, 'nome': cidade.nome_cidade} for cidade in cidades
    ]

    return JsonResponse({
        'cidades': cidades_data,
        'total': len(cidades_data)
    })


# bucar vagas


def buscar_vagas(request):
    """
    Lista todas as vagas ativas, ordenadas por score do candidato (quando logado),
    com filtro por termo de busca e paginação.
    """
    from matching.models import MatchScore

    termo_busca = request.GET.get('q', '').strip()
    page_num = request.GET.get('page', 1)
    

    vagas = Vagas.objects.filter(status='ativa').select_related('empresa')


    # checagem de vagas ativas feita -> adiciona vagas candidatadas pelo usuario
    # pegamos os dados do usuário
    is_empresa = False
    usuario_perfil = None

    if request.user.is_authenticated:
        try:
            usuario_perfil = Usuario.objects.get(user=request.user)
        except Usuario.DoesNotExist:
            pass


    if usuario_perfil:
        score_subquery = MatchScore.objects.filter(
            usuario=usuario_perfil,
            vaga=OuterRef('pk'),
        ).values('score')[:1]

        vagas = vagas.annotate(
            match_score=Coalesce(
                Subquery(score_subquery, output_field=FloatField()),
                Value(0.0),
            )
        ).order_by('-match_score', '-data_publicacao')
    else:
        vagas = vagas.order_by('-data_publicacao')

    # Identifica se o usuário logado é uma empresa
    is_empresa = False

    if request.user.is_authenticated:
        usuario_email = request.session.get('email_atual')

        if usuario_email:
            usuario_base = UsuarioBase.objects.filter(
                email=usuario_email
            ).first()

            if usuario_base and hasattr(usuario_base, 'empresa'):
                is_empresa = True

    if termo_busca:
        vagas = vagas.filter(
            models.Q(cargo_vaga__icontains=termo_busca)
            | models.Q(descricao_vaga__icontains=termo_busca)
            | models.Q(requisito_vaga__icontains=termo_busca)
        ).distinct()

    paginator = Paginator(vagas, _PAGE_SIZE)
    page_obj = paginator.get_page(page_num)

    # 4. Prepara o contexto
    contexto = {
        'page_obj': page_obj,
        'paginator': paginator,
        'termo_busca': termo_busca,
        'is_empresa': is_empresa,
        'ordenado_por_score': usuario_perfil is not None,
    }
    return render(request, 'tela_busca_vagas.html', {
        'page_obj': page_obj,
        'paginator': paginator,
        'termo_busca': termo_busca,
        'ordenado_por_score': usuario_perfil is not None,
    })

# detalhe da vaga


@login_required
def detalhe_vaga(request, vaga_id):
    # Tenta buscar a vaga
    vaga = get_object_or_404(Vagas, id=vaga_id)

    # Busca os cursos/requisitos relacionados a esta vaga (CursoVaga)
    cursos = CursoVaga.objects.filter(vaga=vaga)

    ja_candidatado = False
    candidatura = None
    is_owner = False

    if request.user.is_authenticated:
        # Assumindo que o perfil do usuário se chama 'Usuario'
        try:
            usuario = Usuario.objects.get(user=request.user)
            # Verifica se já existe um registro em UsuarioVaga
            candidatura = UsuarioVaga.objects.filter(
                vaga=vaga, usuario=usuario).first()
            ja_candidatado = candidatura is not None
        except Usuario.DoesNotExist:
            pass

        usuario_email = request.session.get('email_atual')
        if usuario_email:
            usuario_base = UsuarioBase.objects.filter(email=usuario_email).first()
            # Empresa.user é OneToOne(primary_key=True) -> Empresa.pk == UsuarioBase.pk
            if usuario_base and vaga.empresa_id == usuario_base.pk:
                is_owner = True

    contexto = {
        'vaga': vaga,
        'cursos': cursos,  # Passando os cursos para o template
        'ja_candidatado': ja_candidatado,
        'candidatura': candidatura,
        'is_owner': is_owner,
    }

    return render(request, 'detalhe_vaga.html', contexto)


@login_required
def mensagembonita(request):

    messages.success(request, f'Inscrição feita com sucesso!')
    return redirect('core:home')

# No seu vagas/views.py
# Assumindo que seu modelo de usuário está em 'usuario.models'
# Função para registrar a candidatura


@login_required
@require_http_methods(["POST"])
def candidatar_vaga(request, vaga_id):
    vaga = get_object_or_404(Vagas, id=vaga_id)

    # CRÍTICO: Obter a instância do seu modelo de perfil Usuario, não o User padrão
    try:
        # Tenta obter o objeto de perfil Usuario associado ao usuário logado
        # Ajuste esta linha se o seu perfil Usuario estiver ligado de forma diferente
        usuario_perfil = Usuario.objects.get(user=request.user)
    except Usuario.DoesNotExist:
        messages.error(request, "Seu perfil de usuário não foi encontrado.")
        return redirect('vagas:detalhe_vaga', vaga_id=vaga.id)

    # Cria o registro apenas se ele não existir
    if UsuarioVaga.objects.filter(vaga=vaga, usuario=usuario_perfil).exists():
        messages.warning(request, "Você já está candidatado a esta vaga.")
    else:
        UsuarioVaga.objects.create(vaga=vaga, usuario=usuario_perfil)
        messages.success(
            request, f"Candidatura à vaga '{vaga.cargo_vaga}' registrada com sucesso!")

    # Redireciona para a página de detalhes da vaga
    return redirect('vagas:detalhe_vaga', vaga_id=vaga.id)

@login_required
@require_http_methods(["POST"])
def cancelar_candidatura(request, vaga_id):
    vaga = get_object_or_404(Vagas, id=vaga_id)

    try:
        usuario_perfil = Usuario.objects.get(user=request.user)

        candidatura = UsuarioVaga.objects.get(
            vaga=vaga,
            usuario=usuario_perfil
        )

        candidatura.delete()

        messages.success(
            request,
            f'Candidatura à vaga \'{vaga.cargo_vaga}\' cancelada com sucesso.'
        )

    except UsuarioVaga.DoesNotExist:
        messages.error(
            request,
            "Erro: Candidatura não encontrada."
        )

    except Usuario.DoesNotExist:
        messages.error(
            request,
            "Seu perfil de usuário não foi encontrado."
        )

    return redirect(
        'vagas:detalhe_vaga',
        vaga_id=vaga.id
    )
        

@login_required
@require_http_methods(["POST"])
def alterar_status_vaga(request, vaga_id):
    vaga = get_object_or_404(Vagas, id=vaga_id)

    # Obtém o usuário logado
    usuario_email = request.session.get('email_atual')

    try:
        usuario = UsuarioBase.objects.get(email=usuario_email)
        empresa = usuario.empresa
    except UsuarioBase.DoesNotExist:
        messages.error(request, "Usuário não encontrado.")
        return redirect('core:home')

    # Garante que a vaga pertence à empresa logada
    if vaga.empresa != empresa:
        messages.error(
            request,
            "Você não tem permissão para alterar esta vaga."
        )
        return redirect('core:home')

    # Altera o status
    if vaga.status == 'ativa':
        vaga.status = 'inativa'
        mensagem = f"A vaga '{vaga.cargo_vaga}' foi desativada com sucesso."
    else:
        vaga.status = 'ativa'
        mensagem = f"A vaga '{vaga.cargo_vaga}' foi reativada com sucesso."

    vaga.save()

    messages.success(request, mensagem)

    return redirect('core:home')

@login_required
def minhas_vagas(request):
    usuario_email = request.session.get('email_atual')

    try:
        usuario = UsuarioBase.objects.get(email=usuario_email)
        empresa = usuario.empresa
    except UsuarioBase.DoesNotExist:
        messages.error(request, "Usuário não encontrado.")
        return redirect('core:home')

    vagas = Vagas.objects.filter(
        empresa=empresa
    ).order_by('-data_publicacao')

    return render(request, 'minhas_vagas.html', {
        'vagas': vagas,
        'empresa': empresa,
    })


    # Redireciona para a página de detalhes da vaga
    return redirect('vagas:detalhe_vaga', vaga_id=vaga.id)


@login_required
def listar_candidatos(request, vaga_id):
    usuario_email = request.session.get('email_atual')
    usuario_base = get_object_or_404(UsuarioBase, email=usuario_email)
    vaga = get_object_or_404(Vagas, id=vaga_id, empresa=usuario_base.empresa)

    candidaturas = UsuarioVaga.objects.filter(
        vaga=vaga).select_related('usuario').order_by('-data_candidatura')

    return render(request, 'listar_candidatos.html', {
        'vaga': vaga,
        'candidaturas': candidaturas,
    })


@login_required
@require_http_methods(["POST"])
def atualizar_status_candidatura(request, usuariovaga_id):
    usuario_email = request.session.get('email_atual')
    usuario_base = get_object_or_404(UsuarioBase, email=usuario_email)
    candidatura = get_object_or_404(
        UsuarioVaga, id=usuariovaga_id, vaga__empresa=usuario_base.empresa)

    novo_status = request.POST.get('status')
    if novo_status not in (UsuarioVaga.STATUS_CONTRATADO, UsuarioVaga.STATUS_REJEITADO):
        messages.error(request, "Status inválido.")
        return redirect('vagas:listar_candidatos', vaga_id=candidatura.vaga.id)

    candidatura.status = novo_status
    candidatura.data_status = timezone.now()
    if novo_status == UsuarioVaga.STATUS_CONTRATADO:
        candidatura.ifmg_no_momento_contratacao = candidatura.usuario.ifmg
    candidatura.save()

    messages.success(request, "Status da candidatura atualizado com sucesso!")
    return redirect('vagas:listar_candidatos', vaga_id=candidatura.vaga.id)
