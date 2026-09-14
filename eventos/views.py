import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models as db_models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from core.models import Hub

from .models import Evento, InscricaoEvento


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _is_gestor(request):
    """Retorna True se o usuário logado é empresa ou admin."""
    return request.session.get('perfil') in ('empresa', 'admin')


def _redirect_next(request, default_view_name, **kwargs):
    """Redireciona para request.POST['next'] se for uma URL local segura, senão usa o destino padrão."""
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(default_view_name, **kwargs)


# ──────────────────────────────────────────
# LISTAGEM — todos os usuários
# ──────────────────────────────────────────

def listar_eventos(request):
    termo = request.GET.get('q', '').strip()
    eventos = Evento.objects.select_related('hub').order_by('-data_evento_inicio')

    if termo:
        eventos = eventos.filter(
            db_models.Q(nome_evento__icontains=termo)
            | db_models.Q(descricao_evento__icontains=termo)
            | db_models.Q(local_evento__icontains=termo)
        ).distinct()

    inscritos = set()
    if request.user.is_authenticated:
        inscritos = set(
            InscricaoEvento.objects.filter(
                usuario=request.user
            ).values_list('evento_id', flat=True)
        )

    return render(request, 'listar.html', {
        'eventos': eventos,
        'termo': termo,
        'inscritos': inscritos,
    })


# ──────────────────────────────────────────
# DETALHE — view pública com botão de inscrição
# ──────────────────────────────────────────

def detalhe_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)

    ja_inscrito = False
    perfil = request.session.get('perfil')
    pode_inscrever = perfil == 'usuario'

    if request.user.is_authenticated:
        ja_inscrito = InscricaoEvento.objects.filter(
            evento=evento, usuario=request.user
        ).exists()

    return render(request, 'detalhe.html', {
        'evento': evento,
        'ja_inscrito': ja_inscrito,
        'pode_inscrever': pode_inscrever,
    })


# ──────────────────────────────────────────
# CADASTRO — empresa e admin
# ──────────────────────────────────────────

@login_required
def criar_evento(request):
    if not _is_gestor(request):
        messages.error(request, 'Acesso negado.')
        return redirect('eventos:listar_eventos')

    hubs = Hub.objects.filter(isActive=True).order_by('nome_hub')

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if not nome:
            messages.error(request, 'O nome do evento é obrigatório.')
            return render(request, 'eventos/form.html', {'hubs': hubs})

        hub_id = request.POST.get('hub') or None
        hub = Hub.objects.get(id=hub_id) if hub_id else None

        Evento.objects.create(
            nome_evento=nome,
            data_evento_inicio=request.POST.get('data_evento_inicio') or None,
            data_evento_fim=request.POST.get('data_evento_fim') or None,
            horario_evento=request.POST.get('horario_evento') or None,
            local_evento=request.POST.get('local_evento') or None,
            publico_evento=request.POST.get('publico_evento') or None,
            descricao_evento=request.POST.get('descricao_evento') or None,
            vagas_disponiveis=int(request.POST.get('vagas_disponiveis') or 0),
            hub=hub,
        )
        messages.success(request, 'Evento cadastrado com sucesso!')
        return redirect('eventos:listar_eventos')

    return render(request, 'form.html', {'hubs': hubs})


# ──────────────────────────────────────────
# EDITAR — empresa e admin
# ──────────────────────────────────────────

@login_required
def editar_evento(request, evento_id):
    if not _is_gestor(request):
        messages.error(request, 'Acesso negado.')
        return redirect('eventos:listar_eventos')

    evento = get_object_or_404(Evento, id=evento_id)
    hubs = Hub.objects.filter(isActive=True).order_by('nome_hub')

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        if not nome:
            messages.error(request, 'O nome do evento é obrigatório.')
            return render(request, 'eventos/form.html', {'evento': evento, 'hubs': hubs})

        hub_id = request.POST.get('hub') or None
        evento.hub = Hub.objects.get(id=hub_id) if hub_id else None

        evento.nome_evento = nome
        evento.data_evento_inicio = request.POST.get('data_evento_inicio') or None
        evento.data_evento_fim = request.POST.get('data_evento_fim') or None
        evento.horario_evento = request.POST.get('horario_evento') or None
        evento.local_evento = request.POST.get('local_evento') or None
        evento.publico_evento = request.POST.get('publico_evento') or None
        evento.descricao_evento = request.POST.get('descricao_evento') or None
        evento.vagas_disponiveis = int(request.POST.get('vagas_disponiveis') or 0)
        evento.save()

        messages.success(request, 'Evento atualizado com sucesso!')
        return redirect('eventos:detalhe_evento', evento_id=evento.id)

    return render(request, 'form.html', {'evento': evento, 'hubs': hubs})


# ──────────────────────────────────────────
# REMOVER — admin
# ──────────────────────────────────────────

@login_required
def remover_evento(request, evento_id):
    if request.session.get('perfil') != 'admin':
        messages.error(request, 'Apenas administradores podem remover eventos.')
        return redirect('eventos:listar_eventos')

    evento = get_object_or_404(Evento, id=evento_id)

    if request.method == 'POST':
        evento.delete()
        messages.success(request, 'Evento removido com sucesso.')
        return redirect('eventos:listar_eventos')

    return render(request, 'eventos/confirmar_remocao.html', {'evento': evento})


# ──────────────────────────────────────────
# INSCRIÇÃO — usuário
# ──────────────────────────────────────────

@login_required
def inscrever(request, evento_id):
    if request.session.get('perfil') != 'usuario':
        messages.error(request, 'Apenas usuários podem se inscrever em eventos.')
        return _redirect_next(request, 'eventos:detalhe_evento', evento_id=evento_id)

    evento = get_object_or_404(Evento, id=evento_id)

    if InscricaoEvento.objects.filter(evento=evento, usuario=request.user).exists():
        messages.warning(request, 'Você já está inscrito neste evento.')
        return _redirect_next(request, 'eventos:detalhe_evento', evento_id=evento_id)

    if evento.lotado:
        messages.error(request, 'Não há vagas disponíveis para este evento.')
        return _redirect_next(request, 'eventos:detalhe_evento', evento_id=evento_id)

    InscricaoEvento.objects.create(evento=evento, usuario=request.user)
    messages.success(request, f'Inscrição realizada com sucesso em "{evento.nome_evento}"!')
    return _redirect_next(request, 'eventos:detalhe_evento', evento_id=evento_id)


@login_required
def cancelar_inscricao(request, evento_id):
    if request.session.get('perfil') != 'usuario':
        return _redirect_next(request, 'eventos:detalhe_evento', evento_id=evento_id)

    evento = get_object_or_404(Evento, id=evento_id)
    InscricaoEvento.objects.filter(evento=evento, usuario=request.user).delete()
    messages.success(request, 'Inscrição cancelada com sucesso.')
    return _redirect_next(request, 'eventos:detalhe_evento', evento_id=evento_id)


# ──────────────────────────────────────────
# GESTÃO DE INSCRITOS — empresa e admin
# ──────────────────────────────────────────

@login_required
def gerenciar_inscricoes(request, evento_id):
    if not _is_gestor(request):
        messages.error(request, 'Acesso negado.')
        return redirect('eventos:listar_eventos')

    evento = get_object_or_404(Evento, id=evento_id)
    inscricoes = evento.inscricoes.select_related('usuario').order_by('data_inscricao')

    return render(request, 'inscritos.html', {
        'evento': evento,
        'inscricoes': inscricoes,
    })


@login_required
def atualizar_presenca(request, inscricao_id):
    if not _is_gestor(request):
        messages.error(request, 'Acesso negado.')
        return redirect('eventos:listar_eventos')

    inscricao = get_object_or_404(InscricaoEvento, id=inscricao_id)
    novo_status = request.POST.get('presenca')
    opcoes_validas = [s[0] for s in InscricaoEvento.STATUS_PRESENCA]

    if novo_status in opcoes_validas:
        inscricao.presenca = novo_status
        inscricao.save()
        messages.success(request, 'Presença atualizada.')
    else:
        messages.error(request, 'Status de presença inválido.')

    return redirect('eventos:gerenciar_inscricoes', evento_id=inscricao.evento_id)


@login_required
def remover_inscricao(request, inscricao_id):
    if not _is_gestor(request):
        messages.error(request, 'Acesso negado.')
        return redirect('eventos:listar_eventos')

    inscricao = get_object_or_404(InscricaoEvento, id=inscricao_id)
    evento_id = inscricao.evento_id
    inscricao.delete()
    messages.success(request, 'Inscrição removida.')
    return redirect('eventos:gerenciar_inscricoes', evento_id=evento_id)


# ──────────────────────────────────────────
# EXPORTAR CSV — empresa e admin
# ──────────────────────────────────────────

@login_required
def exportar_csv(request, evento_id):
    if not _is_gestor(request):
        messages.error(request, 'Acesso negado.')
        return redirect('eventos:listar_eventos')

    evento = get_object_or_404(Evento, id=evento_id)
    inscricoes = evento.inscricoes.select_related('usuario').order_by('data_inscricao')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="inscritos_{evento.nome_evento}.csv"'
    )
    response.write('\ufeff')  # BOM para Excel

    writer = csv.writer(response)
    writer.writerow(['Nome', 'E-mail', 'Data Inscrição', 'Presença'])
    for i in inscricoes:
        writer.writerow([
            i.usuario.nome,
            i.usuario.email,
            i.data_inscricao.strftime('%d/%m/%Y %H:%M'),
            i.get_presenca_display(),
        ])

    return response