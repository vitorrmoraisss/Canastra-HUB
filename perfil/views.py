"""
App perfil — toda a lógica de exibição e atualização de perfil
extraída de core/views.py.

Imports de models são feitos diretamente de seus apps de origem;
este módulo não define nenhum model próprio.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from core.models import (
    Acessibilidade,
    AcademyGraduation,
    Attachment,
    Cidade,
    Competencia,
    CursoExtraCurricular,
    Endereco,
    Estado,
    ExperienciaProfissional,
    Hobby,
    Hub,
    UsuarioHub,
    InteresseCompra,
    Idioma,
    LANGUAGE_CHOICES,
    LANGUAGE_FLUENCY,
    ProfessionalTarget,
    SocialMedia,
    Usuario,
)
from empresa.models import Empresa, EmpresaHub


# ══════════════════════════════════════════
# EXIBIÇÃO DO PERFIL
# ══════════════════════════════════════════

@login_required
def perfil(request):
    """
    Exibe o perfil do usuário logado.
    Detecta o tipo (admin, empresa, usuario) e carrega os dados correspondentes.
    """
    user = request.user
    tipo_perfil = request.session.get('perfil', 'admin')

    estados = Estado.objects.all().order_by('nome_estado')

    contexto = {
        'user': user,
        'estados': estados,
        'cidades': Cidade.objects.none(),
    }

    if tipo_perfil == 'empresa':
        try:
            empresa = Empresa.objects.select_related('cidade', 'estado').get(user=user)
            if empresa.estado:
                contexto['cidades'] = Cidade.objects.filter(
                    estado_cidade=empresa.estado
                ).order_by('nome_cidade')

            hubs = Hub.objects.all().order_by('nome_hub')
            hubs_vinculados = list(
                EmpresaHub.objects.filter(empresa=empresa).values_list('hub_id', flat=True)
            )

            contexto.update({
                'empresa': empresa,
                'hubs': hubs,
                'hubs_vinculados': hubs_vinculados,
            })
        except Empresa.DoesNotExist:
            messages.error(request, 'Perfil de empresa não encontrado.')
            return redirect('core:home')

    elif tipo_perfil == 'usuario':
        try:
            usuario = Usuario.objects.select_related(
                'endereco__cidade',
                'endereco__estado',
                'objetivo_profissional',
                'formacao_academica',
                'social_media',
                'acessibilidade',
            ).get(user=user)
            experiencias = ExperienciaProfissional.objects.filter(usuario=usuario)
            cursos_extras = CursoExtraCurricular.objects.filter(usuario=usuario)
            idiomas = Idioma.objects.filter(usuario=usuario)
            interesses_compra = list(
                InteresseCompra.objects
                .filter(usuario=usuario, isActive=True)
                .order_by('criado_em')[:3]
            )
            interesses_compra.extend([None] * (3 - len(interesses_compra)))
            idiomas = list(Idioma.objects.filter(usuario=usuario))
            idiomas_slots = idiomas + [None] * (3 - len(idiomas))


            if usuario.estado:
                contexto['cidades'] = Cidade.objects.filter(
                    estado_cidade=usuario.estado
                ).order_by('nome_cidade')

            hubs = Hub.objects.filter(isActive=True).order_by('nome_hub')
            hubs_vinculados = list(
                UsuarioHub.objects.filter(usuario=usuario).values_list('hub_id', flat=True)
            )

            contexto.update({
                'usuario': usuario,
                'experiencias': experiencias,
                'cursos_extras': cursos_extras,
                'idiomas': idiomas,
                'hubs': hubs,
                'hubs_vinculados': hubs_vinculados,
                'interesses_compra': interesses_compra,
                'idiomas_slots': idiomas_slots,
                'language_choices': LANGUAGE_CHOICES,
                'fluency_choices': LANGUAGE_FLUENCY,
            })
        except Usuario.DoesNotExist:
            messages.error(request, 'Perfil de usuário não encontrado.')
            return redirect('core:home')

    # Admin usa apenas dados do user — sem dados extras

    return render(request, 'perfil/perfil.html', contexto)


# ══════════════════════════════════════════
# ATUALIZAÇÃO DO PERFIL
# ══════════════════════════════════════════

@login_required
def atualizar_perfil(request):
    """
    Processa o formulário POST de atualização de perfil.
    Despacha para o helper específico por tipo de perfil.
    """
    if request.method != 'POST':
        return redirect('perfil:perfil')

    user = request.user
    tipo_perfil = request.session.get('perfil', 'admin')
    apenas_foto = request.POST.get('apenas_foto') == '1'

    try:
        # Foto — comum a todos
        if 'foto' in request.FILES:
            foto = request.FILES['foto']
            ext = foto.name.split('.')[-1].lower()
            if ext in ('jpg', 'jpeg', 'png'):
                user.foto = foto
                user.save()
                if apenas_foto:
                    messages.success(request, 'Foto atualizada com sucesso!')
                    return redirect('perfil:perfil')

        # Nome — comum a todos
        if request.POST.get('nome'):
            user.nome = request.POST.get('nome')
        user.save()

        if tipo_perfil == 'admin':
            messages.success(request, 'Perfil atualizado com sucesso!')

        elif tipo_perfil == 'empresa':
            _atualizar_empresa(request, user)
            messages.success(request, 'Perfil da empresa atualizado com sucesso!')

        elif tipo_perfil == 'usuario':
            _atualizar_usuario(request, user)
            messages.success(request, 'Perfil atualizado com sucesso!')

    except Exception as e:
        messages.error(request, f'Erro ao atualizar perfil: {str(e)}')

    return redirect('perfil:perfil')


# ══════════════════════════════════════════
# API AJAX — cidades por estado
# ══════════════════════════════════════════

def buscar_cidades(request):
    """
    Retorna JSON com cidades filtradas por estado_id.
    Usada nos selects de perfil via AJAX.
    """
    estado_id = request.GET.get('estado_id')
    if not estado_id:
        return JsonResponse({'cidades': []})
    try:
        cidades = Cidade.objects.filter(
            estado_cidade_id=estado_id
        ).order_by('nome_cidade')
        return JsonResponse({
            'cidades': [{'id': c.id, 'nome': c.nome_cidade} for c in cidades]
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ══════════════════════════════════════════
# HELPERS PRIVADOS — empresa
# ══════════════════════════════════════════

def _atualizar_empresa(request, user):
    empresa = Empresa.objects.get(user=user)

    empresa.nomefantasia = request.POST.get('nomefantasia', empresa.nomefantasia)
    empresa.razao_social = request.POST.get('razao_social', empresa.razao_social)
    empresa.cnpj = request.POST.get('cnpj', empresa.cnpj)
    empresa.tipo_empresa = request.POST.get('tipo_empresa', empresa.tipo_empresa)
    empresa.segmento = request.POST.get('segmento', empresa.segmento)
    empresa.telefone = request.POST.get('telefone', empresa.telefone)
    empresa.cep = request.POST.get('cep', empresa.cep)
    empresa.rua = request.POST.get('rua', empresa.rua)
    empresa.numero = request.POST.get('numero', empresa.numero) or 0
    empresa.complemento = request.POST.get('complemento', empresa.complemento)

    estado_id = request.POST.get('estado')
    cidade_id = request.POST.get('cidade')
    if estado_id:
        empresa.estado = Estado.objects.get(id=estado_id)
    if cidade_id:
        empresa.cidade = Cidade.objects.get(id=cidade_id)

    empresa.save()
    _atualizar_hubs_empresa(request, empresa)


def _atualizar_hubs_empresa(request, empresa):
    hubs_selecionados = request.POST.getlist('hubs')
    hubs_ids = [int(h) for h in hubs_selecionados if h]
    EmpresaHub.objects.filter(empresa=empresa).delete()
    for hub_id in hubs_ids:
        try:
            EmpresaHub.objects.create(empresa=empresa, hub=Hub.objects.get(id=hub_id))
        except Hub.DoesNotExist:
            pass


# ══════════════════════════════════════════
# HELPERS PRIVADOS — usuário
# ══════════════════════════════════════════

def _atualizar_usuario(request, user):
    usuario = Usuario.objects.select_related(
        'endereco',
        'objetivo_profissional',
        'formacao_academica',
        'social_media',
        'acessibilidade',
    ).get(user=user)

    # Dados pessoais
    usuario.nome_social = request.POST.get('nome_social') or None
    usuario.data_nascimento = _parse_date(request.POST.get('data_nascimento')) or usuario.data_nascimento
    usuario.genero = request.POST.get('genero', usuario.genero)
    usuario.estado_civil = request.POST.get('estado_civil', usuario.estado_civil)
    usuario.nacionalidade = request.POST.get('nacionalidade', usuario.nacionalidade)
    usuario.telefone = request.POST.get('telefone', usuario.telefone)

    # Endereço
    endereco = usuario.endereco or Endereco.objects.create()
    endereco.cep = request.POST.get('cep') or (endereco.cep or '')
    endereco.rua = request.POST.get('rua') or (endereco.rua or '')
    endereco.bairro = request.POST.get('bairro') or (endereco.bairro or '')
    endereco.numero = request.POST.get('numero') or (endereco.numero or '')
    endereco.complemento = request.POST.get('complemento') or None

    estado_id = request.POST.get('estado')
    cidade_id = request.POST.get('cidade')
    if estado_id:
        endereco.estado = Estado.objects.get(id=estado_id)
    if cidade_id:
        endereco.cidade = Cidade.objects.get(id=cidade_id)

    endereco.save()
    usuario.endereco = endereco

    # Objetivo profissional
    objetivo = usuario.objetivo_profissional or ProfessionalTarget.objects.create()
    objetivo.cargo_pretendido = request.POST.get('cargo_pretendido') or None
    objetivo.area_interesse = request.POST.get('area_interesse') or None
    objetivo.pretensao_salarial = _parse_decimal(request.POST.get('pretensao_salarial'))
    objetivo.disponibilidade = request.POST.get('disponibilidade') or None
    objetivo.remoto = request.POST.get('remoto') == 'on'
    objetivo.save()
    usuario.objetivo_profissional = objetivo

    # Vínculo com IFMG
    usuario.ifmg = request.POST.get('ifmg') == 'on'

    # Redes sociais
    social = usuario.social_media or SocialMedia.objects.create()
    social.linkedin = request.POST.get('linkedin') or None
    social.github = request.POST.get('github') or None
    social.instagram = request.POST.get('instagram') or None
    social.facebook = request.POST.get('facebook') or None
    social.site_pessoal = request.POST.get('site_pessoal') or None
    social.save()
    usuario.social_media = social

    # Formação acadêmica
    formacao = usuario.formacao_academica or AcademyGraduation.objects.create()
    for n in ('1', '2', '3'):
        instituicao = request.POST.get(f'instituicao_nome{n}')
        grau = request.POST.get(f'grau_escolaridade{n}')
        curso = request.POST.get(f'curso_graduacao{n}')
        situacao = request.POST.get(f'situacao_academica{n}')
        data_inicio = _parse_date(request.POST.get(f'data_acad_inicio{n}'))
        data_fim = _parse_date(request.POST.get(f'data_acad_fim{n}'))

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

    # Competências
    usuario.competencias.clear()
    for n in ('1', '2', '3'):
        for field_name, tipo_competencia in (
            (f'competencias_tecnicas{n}', 'tecnica'),
            (f'competencias_comportamentais{n}', 'comportamental'),
        ):
            raw_value = request.POST.get(field_name)
            if raw_value:
                for item in [part.strip() for part in raw_value.split(',') if part.strip()]:
                    competencia, _ = Competencia.objects.get_or_create(
                        nome_competencia=item,
                        defaults={'tipo_competencia': tipo_competencia}
                    )
                    usuario.competencias.add(competencia)

    # Inclusão e acessibilidade
    acessibilidade, _ = Acessibilidade.objects.get_or_create(usuario=usuario)
    acessibilidade.pessoa_com_deficiencia = request.POST.get('pessoa_com_deficiencia') == 'on'
    acessibilidade.tipo_deficiencia = request.POST.get('tipo_deficiencia') or None
    acessibilidade.necessidade_adaptacao = request.POST.get('necessidade_adaptacao') or None
    acessibilidade.save()

    # Informações adicionais
    usuario.interesses_hobbies.clear()
    interesses_hobbies = request.POST.get('interesses_hobbies')
    if interesses_hobbies:
        for item in [part.strip() for part in interesses_hobbies.split(',') if part.strip()]:
            hobby, _ = Hobby.objects.get_or_create(nome_hobby=item)
            usuario.interesses_hobbies.add(hobby)

    # Interesses de compra usados no matching de produtos e hubs.
    # Cada slot do formulário carrega o id do registro que edita (campo oculto
    # interesse_idN), então desativar um interesse não faz os demais slots
    # passarem a editar o registro errado.
    interesses_por_id = {
        interesse.pk: interesse
        for interesse in InteresseCompra.objects.filter(usuario=usuario)
    }
    for indice in range(1, 4):
        categoria = (request.POST.get(f'categoria_interesse{indice}') or '').strip()
        descricao = (request.POST.get(f'descricao_interesse{indice}') or '').strip()
        preco_maximo = _parse_decimal(request.POST.get(f'preco_maximo{indice}'))

        interesse_id = _parse_int(request.POST.get(f'interesse_id{indice}'))
        # Só aceita ids que pertencem ao próprio usuário
        interesse = interesses_por_id.get(interesse_id) if interesse_id else None

        if categoria or descricao or preco_maximo is not None:
            if interesse is None:
                interesse = InteresseCompra(usuario=usuario)
            interesse.categoria_interesse = categoria
            interesse.descricao_interesse = descricao
            interesse.preco_maximo = preco_maximo
            interesse.isActive = True
            interesse.save()
        elif interesse is not None and interesse.isActive:
            interesse.isActive = False
            interesse.save()

    # Anexos
    if 'curriculo_pdf' in request.FILES:
        Attachment.objects.filter(usuario=usuario, description='curriculo').delete()
        Attachment.objects.create(usuario=usuario, file=request.FILES['curriculo_pdf'], description='curriculo')
    if 'carta_apresentacao' in request.FILES:
        Attachment.objects.filter(usuario=usuario, description='carta_apresentacao').delete()
        Attachment.objects.create(usuario=usuario, file=request.FILES['carta_apresentacao'], description='carta_apresentacao')

    usuario.save()

    _atualizar_experiencias(request, usuario)
    _atualizar_cursos(request, usuario)
    _atualizar_idiomas(request, usuario)
    _atualizar_hubs_usuario(request, usuario)


def _atualizar_hubs_usuario(request, usuario):
    hubs_selecionados = request.POST.getlist('hubs')
    hubs_ids = [int(h) for h in hubs_selecionados if h]
    UsuarioHub.objects.filter(usuario=usuario).delete()
    for hub_id in hubs_ids:
        try:
            hub = Hub.objects.get(id=hub_id, isActive=True)
        except Hub.DoesNotExist:
            continue
        UsuarioHub.objects.create(usuario=usuario, hub=hub)


def _atualizar_experiencias(request, usuario):
    ExperienciaProfissional.objects.filter(usuario=usuario).delete()
    for n in ('1', '2', '3'):
        nome_empresa = request.POST.get(f'nome_empresa{n}')
        cargo = request.POST.get(f'cargo{n}')
        data_inicio = _parse_date(request.POST.get(f'data_inicio{n}'))
        data_fim = _parse_date(request.POST.get(f'data_fim{n}'))
        if any([nome_empresa, cargo, data_inicio, data_fim]):
            ExperienciaProfissional.objects.create(
                usuario=usuario,
                nome_empresa=nome_empresa or None,
                cargo=cargo or None,
                data_inicio=data_inicio,
                data_fim=data_fim,
            )


def _atualizar_cursos(request, usuario):
    CursoExtraCurricular.objects.filter(usuario=usuario).delete()
    for n in ('1', '2', '3'):
        nome_curso = request.POST.get(f'nome_curso{n}')
        instituicao = request.POST.get(f'instituicao{n}')
        carga_horaria = _parse_int(request.POST.get(f'carga_horaria{n}'))
        data_conclusao = _parse_date(request.POST.get(f'data_conclusao{n}'))
        link_certificado = request.POST.get(f'link_certificado{n}')
        if any([nome_curso, instituicao, carga_horaria, data_conclusao, link_certificado]):
            CursoExtraCurricular.objects.create(
                usuario=usuario,
                nome_curso=nome_curso or None,
                instituicao=instituicao or None,
                carga_horaria=carga_horaria,
                data_conclusao=data_conclusao,
                link_certificado=link_certificado or None,
            )


def _atualizar_idiomas(request, usuario):
    idiomas_vistos = set()
    usuario.idiomas.all().delete()
    for n in ('1', '2', '3'):
        language = request.POST.get(f'idioma{n}')
        fluency = request.POST.get(f'nivel_fluencia{n}')
        if not language or language in idiomas_vistos:
            continue
        idiomas_vistos.add(language)
        Idioma.objects.create(usuario=usuario, language=language, fluency=fluency)


# ══════════════════════════════════════════
# HELPERS DE PARSING
# ══════════════════════════════════════════

def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_decimal(value_str):
    if not value_str:
        return None
    try:
        return Decimal(value_str)
    except (InvalidOperation, ValueError):
        return None


def _parse_int(value_str):
    if not value_str:
        return None
    try:
        return int(value_str)
    except ValueError:
        return None