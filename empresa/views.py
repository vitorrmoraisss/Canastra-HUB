from django.shortcuts import render, redirect
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from empresa.models import *
from core.models import *
from django.contrib import messages
from django.http import JsonResponse

import re

def validar_email(email: str) -> bool:
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(padrao, email) is not None


def limpar_numeros(valor):
    # Remove tudo que não for dígito
    return re.sub(r'\D', '', valor)

def _get_contexto_cadastro():
    """Retorna o contexto padrão para renderizar o formulário de cadastro."""
    return {
        'estados': Estado.objects.all().order_by('nome_estado'),
        'hubs': Hub.objects.all().order_by('nome_hub'),
        'complemento_max_length': Empresa._meta.get_field('complemento').max_length,
    }

def _erro_cadastro(request, mensagens:list | str):
    """Atalho para adicionar erro e retornar o formulário com contexto."""
    
    if isinstance(mensagens,str):
        mensagens = [mensagens]

    for mensagem in mensagens:
        messages.error(request, mensagem)
    
    return render(request, 'cadastro_empresa.html', _get_contexto_cadastro())


def cadastro_empresa(request):
    return render(request, 'cadastro_empresa.html', _get_contexto_cadastro())


def criar_empresa(request):
    
    if request.user.is_authenticated:
        messages.warning(
            request, f'Você ja está logado, não é possivel realizar outro cadastro.')
        return redirect('core:home')
    
    if request.method != 'POST':
       return cadastro_empresa(request)
    
    senha = request.POST.get('txtSenha', '').strip()
    confirmacaoSenha = request.POST.get('txtConfirmarSenha', '').strip()
    if senha != confirmacaoSenha:
       return _erro_cadastro(request, 'As senhas devem ser iguais.')    

    nomefantasia = request.POST.get('txtNome', '').strip()
    email = request.POST.get('txtEmail', '').strip()
    segmento = request.POST.get('txtSegmento', '').strip()
    tipo_empresa = request.POST.get('txtTipo', '').strip()
    telefone = limpar_numeros(request.POST.get('txtTelefone'))
    rua = request.POST.get('txtRua', '').strip()
    cep = limpar_numeros(request.POST.get('txtCep'))
    numero_raw = request.POST.get('txtNumero', '').strip()
    complemento = request.POST.get('txtComplemento', '').strip()
    cidade_id = request.POST.get('cidade', '').strip()
    estado_id = request.POST.get('estado', '').strip()
    hubs_selecionados = request.POST.getlist('hubs[]')
    foto_empresa = request.FILES.get('fileFoto')
    cnpj = limpar_numeros(request.POST.get('txtCnpj'))
    razao_social = request.POST.get('txtRazaoSocial', '').strip()

    campos_obrigatorios = {
        'Nome fantasia': nomefantasia,
        'E-mail': email,
        'Senha': senha,
        'Segmento': segmento,
        'Tipo de empresa': tipo_empresa,
        'Telefone': telefone,
        'Rua': rua,
        'CEP': cep,
        'Número': numero_raw,
        'Estado': estado_id,
        'Cidade': cidade_id,
        'CNPJ': cnpj,
        'Razão social': razao_social,
    }

    for nome_campo, valor in campos_obrigatorios.items():
        if not valor:
            return _erro_cadastro(request, f'O campo "{nome_campo}" é obrigatório.')

    if not validar_email(email):
        return _erro_cadastro(request, 'Endereço de e-mail inválido.')

    if len(senha) < 8:
        return _erro_cadastro(request, 'A senha deve ter pelo menos 8 caracteres.')

    if len(cnpj) != 14:
        return _erro_cadastro(request, 'CNPJ inválido — informe os 14 dígitos.')

    if len(telefone) < 10 or len(telefone) > 11:
        return _erro_cadastro(request, 'Telefone inválido — informe DDD + número.')

    if len(cep) != 8:
        return _erro_cadastro(request, 'CEP inválido — informe os 8 dígitos.')

    if not numero_raw.isdigit():
        return _erro_cadastro(request, 'O número do endereço deve ser numérico.')

    numero = int(numero_raw)

    complemento_max = Empresa._meta.get_field('complemento').max_length
    if len(complemento) > complemento_max:
        return _erro_cadastro(
            request,
            f'O complemento pode ter no máximo {complemento_max} caracteres.'
        )

    if not estado_id.isdigit() or not cidade_id.isdigit():
        return _erro_cadastro(request, 'Seleção de estado ou cidade inválida.')

    try:
        estado = Estado.objects.get(id=estado_id)
    except Estado.DoesNotExist:
        return _erro_cadastro(request, 'Estado selecionado não encontrado.')

    try:
        # Garante que a cidade pertence ao estado enviado (evita combinação forjada)
        cidade = Cidade.objects.get(id=cidade_id, estado_cidade=estado)
    except Cidade.DoesNotExist:
        return _erro_cadastro(request, 'Cidade inválida ou não pertence ao estado selecionado.')

    # Valida hubs enviados (ignora IDs inválidos em vez de lançar exceção)
    hubs_validos = []
    if hubs_selecionados:
        ids_numericos = [h for h in hubs_selecionados if str(h).isdigit()]
        hubs_validos = list(Hub.objects.filter(id__in=ids_numericos))
        if len(hubs_validos) != len(ids_numericos):
            return _erro_cadastro(request, 'Um ou mais hubs selecionados são inválidos.')

    if UsuarioBase.objects.filter(email=email).exists():
        return _erro_cadastro(request, 'Já existe uma conta cadastrada com este e-mail.')

    if Empresa.objects.filter(cnpj=cnpj).exists():
        return _erro_cadastro(request, 'Já existe uma empresa cadastrada com este CNPJ.')

    user = UsuarioBase.objects.create_user(
        email=email,
        password=senha,
        nome=nomefantasia,
        tipo='empresa'
    )
    if foto_empresa:
        user.foto = foto_empresa
        user.save()

    empresa = Empresa.objects.create(
        user=user,
        nomefantasia=nomefantasia,
        tipo_empresa=tipo_empresa,
        razao_social=razao_social,
        cnpj=cnpj,
        telefone=telefone,
        rua=rua,
        cep=cep,
        numero=numero,
        complemento=complemento,
        cidade=cidade,
        estado=estado,
        segmento=segmento,
    )

    # Associa hubs apenas quando há seleção válida
    if hubs_validos:
        empresa.hubs.set(hubs_validos)

    messages.success(request, 'Empresa cadastrada com sucesso!')
    return redirect('core:login')



from django.db.models import Count
from vagas.models import Vagas, UsuarioVaga
from core.models import UsuarioBase


def _get_empresa_logada(request):
    email = request.session.get('email_atual')
    if not email:
        return None
    try:
        return UsuarioBase.objects.get(email=email).empresa
    except Exception:
        return None


@login_required
def minhas_vagas(request):
    if request.session.get('perfil') != 'empresa':
        messages.error(request, 'Acesso negado.')
        return redirect('core:home')

    empresa = _get_empresa_logada(request)
    if not empresa:
        messages.error(request, 'Empresa não encontrada.')
        return redirect('core:home')

    vagas = (
        Vagas.objects
        .filter(empresa=empresa)
        .annotate(num_candidatos=Count('usuariovaga'))
        .order_by('-data_publicacao')
    )
    return render(request, 'empresa/minhas_vagas.html', {'vagas': vagas})


@login_required
def detalhe_minha_vaga(request, vaga_id):
    if request.session.get('perfil') != 'empresa':
        messages.error(request, 'Acesso negado.')
        return redirect('core:home')

    empresa = _get_empresa_logada(request)
    if not empresa:
        messages.error(request, 'Empresa não encontrada.')
        return redirect('core:home')

    vaga = get_object_or_404(Vagas, id=vaga_id, empresa=empresa)
    num_candidatos = UsuarioVaga.objects.filter(vaga=vaga).count()
    from vagas.models import CursoVaga
    cursos = CursoVaga.objects.filter(vaga=vaga)
    return render(request, 'empresa/detalhe_minha_vaga.html', {
        'vaga': vaga,
        'num_candidatos': num_candidatos,
        'cursos': cursos,
    })


@login_required
def candidatos_vaga(request, vaga_id):
    if request.session.get('perfil') != 'empresa':
        messages.error(request, 'Acesso negado.')
        return redirect('core:home')

    empresa = _get_empresa_logada(request)
    if not empresa:
        messages.error(request, 'Empresa não encontrada.')
        return redirect('core:home')

    vaga = get_object_or_404(Vagas, id=vaga_id, empresa=empresa)
    candidaturas = (
        UsuarioVaga.objects
        .filter(vaga=vaga)
        .select_related('usuario__user')
        .order_by('data_candidatura')
    )
    return render(request, 'empresa/candidatos_vaga.html', {
        'vaga': vaga,
        'candidaturas': candidaturas,
    })


@login_required
def perfil_candidato(request, usuario_id):
    if request.session.get('perfil') != 'empresa':
        messages.error(request, 'Acesso negado.')
        return redirect('core:home')

    empresa = _get_empresa_logada(request)
    if not empresa:
        messages.error(request, 'Empresa não encontrada.')
        return redirect('core:home')

    candidato_base = get_object_or_404(UsuarioBase, id=usuario_id, tipo='usuario')
    if not UsuarioVaga.objects.filter(vaga__empresa=empresa, usuario__user=candidato_base).exists():
        messages.error(request, 'Candidato não encontrado para suas vagas.')
        return redirect('empresa:minhas_vagas')

    try:
        perfil = candidato_base.usuario
    except Exception:
        perfil = None

    from core.models import ExperienciaProfissional
    experiencias = []
    if perfil:
        try:
            experiencias = list(ExperienciaProfissional.objects.filter(usuario=perfil))
        except Exception:
            pass

    return render(request, 'empresa/perfil_candidato.html', {
        'candidato': candidato_base,
        'perfil': perfil,
        'experiencias': experiencias,
    })

