import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime
from django.http import JsonResponse
from .models import Reserva
from .services import GoogleAgendaService


@login_required
def realizar_reserva(request):
    if request.method == "POST":
        sala = request.POST.get('sala')
        data_str = request.POST.get('data_reserva')
        bloco_str = request.POST.get('bloco_horario')

        if not data_str or not bloco_str:
            messages.error(
                request, "Por favor, preencha todos os campos do formulário.")
            return redirect('realizar_reserva')

        try:
            hora_inicio_str, hora_fim_str = bloco_str.split('-')
            inicio_comb = f"{data_str} {hora_inicio_str}:00"
            fim_comb = f"{data_str} {hora_fim_str}:00"

            inicio = parse_datetime(inicio_comb)
            fim = parse_datetime(fim_comb)
        except Exception:
            messages.error(
                request, "Erro ao processar o bloco de horário selecionado.")
            return redirect('realizar_reserva')

        if fim <= inicio:
            messages.error(
                request, "A hora de término deve ser posterior à hora de início.")
            return redirect('realizar_reserva')

        # 1. MOTOR DE SEGURANÇA LOCAL: Evita sobreposição de horários antes de chamar a API externa
        conflito = Reserva.objects.filter(
            sala=sala,
            status='confirmada',
            inicio__lt=fim,
            fim__gt=inicio
        ).exists()

        if conflito:
            messages.error(
                request, "Esta sala já se encontra reservada para o período selecionado.")
            return redirect('realizar_reserva')

        # --- AQUI COMEÇA A MANOBRA DO "TUDO OU NADA" ---

        # 2. Criamos o objeto na memória do Python (Instanciamos, mas AINDA NÃO USAMOS o .save())
        nova_reserva = Reserva(
            usuario=request.user,
            sala=sala,
            inicio=inicio,
            fim=fim,
            status='confirmada'
        )

        nome_amigavel_sala = nova_reserva.get_sala_display()
        titulo_evento = f"{nome_amigavel_sala} - {request.user.nome}"

        # 3. Disparamos PRIMEIRO para o Google Agenda
        google_id = None
        try:
            google_id = GoogleAgendaService.enviar_para_google(
                nome_sala=sala,
                titulo=titulo_evento,
                data_inicio=inicio.isoformat(),
                data_fim=fim.isoformat(),
                email_cliente=request.user.email
            )
        except Exception as e:
            print(f"Erro de comunicação capturado na View: {e}")
            google_id = None

        # 4. VALIDAÇÃO CRUCIAL: Se o Google falhou em retornar o ID, barramos o processo!
        if not google_id:
            # Não chamamos o .save(), portanto nada vai pro banco local.
            messages.error(
                request,
                "Não foi possível concluir o agendamento devido a uma falha temporária na integração com o Google Calendar. "
                "Por favor, verifique sua conexão ou tente novamente em alguns instantes."
            )
            # Retorna para o formulário mantendo o horário livre para novas tentativas
            return redirect('realizar_reserva')

        # 5. SUCESSO TOTAL: O Google criou a agenda, agora consolidamos no banco de dados local
        nova_reserva.google_event_id = google_id
        nova_reserva.save()

        messages.success(
            request, "Agendamento realizado e sincronizado com o Google com sucesso!")
        return redirect('minhas_reservas')

    return render(request, 'agendamento/agendar.html')
# reservas gerais - todas vizualizadas
# @login_required
# def minhas_reservas(request):
#     # Coleta todas as reservas confirmadas para exibir no painel de controle
#     reservas = Reserva.objects.filter(status='confirmada').order_by('inicio')
#     return render(request, 'agendamento/minhas_reservas.html', {'reservas': reservas})


@login_required
def minhas_reservas(request):
    # 1. Verifica se o perfil ativo na sessão é administrador
    tipo_perfil = request.session.get('perfil')

    if tipo_perfil == 'admin':
        # Se for admin, lista todos os agendamentos confirmados do sistema
        reservas = Reserva.objects.filter(
            status='confirmada').order_by('inicio')
    else:
        # Se for usuário comum, filtra trazendo apenas as reservas criadas por ele mesmo
        reservas = Reserva.objects.filter(
            status='confirmada', usuario=request.user).order_by('inicio')

    return render(request, 'agendamento/minhas_reservas.html', {'reservas': reservas})


@login_required
def api_reservas_calendario(request):
    reservas = Reserva.objects.filter(status='confirmada')
    eventos_json = []

    for r in reservas:
        eventos_json.append({
            'id': r.id,
            'title': f"{r.get_sala_display()}",
            'start': r.inicio.isoformat(),
            'end': r.fim.isoformat(),
            'backgroundColor': '#22c55e',
            'borderColor': '#22c55e',
            # PASSAMOS OS DADOS EXTRA AQUI DENTRO:
            'extendedProps': {
                'sala': r.get_sala_display(),
                'usuario_nome': r.usuario.nome,
                'usuario_email': r.usuario.email,
                'horario_str': f"{r.inicio.strftime('%H:%M')} às {r.fim.strftime('%H:%M')}"
            }
        })

    return JsonResponse(eventos_json, safe=False)


@login_required
def editar_reserva(request, reserva_id):
    # SEGURANÇA POR SESSÃO: Bloqueia perfis que não sejam administradores
    tipo_perfil = request.session.get('perfil')
    if tipo_perfil != 'admin':
        messages.error(
            request, "Acesso negado. Apenas administradores podem editar agendamentos.")
        return redirect('minhas_reservas')

    reserva = get_object_or_404(Reserva, id=reserva_id)

    if request.method == "POST":
        sala = request.POST.get('sala')
        data_str = request.POST.get('data_reserva')
        bloco_str = request.POST.get('bloco_horario')

        if not data_str or not bloco_str:
            messages.error(
                request, "Por favor, preencha todos os campos obrigatórios.")
            return redirect('editar_reserva', reserva_id=reserva.id)

        try:
            hora_inicio_str, hora_fim_str = bloco_str.split('-')
            inicio_comb = f"{data_str} {hora_inicio_str}:00"
            fim_comb = f"{data_str} {hora_fim_str}:00"

            inicio = parse_datetime(inicio_comb)
            fim = parse_datetime(fim_comb)
        except Exception:
            messages.error(
                request, "Erro na leitura dos horários selecionados.")
            return redirect('editar_reserva', reserva_id=reserva.id)

        # MOTOR DE SEGURANÇA: Bloqueia conflitos desconsiderando o id da própria reserva em edição
        conflito = Reserva.objects.filter(
            sala=sala,
            status='confirmada',
            inicio__lt=fim,
            fim__gt=inicio
        ).exclude(id=reserva.id).exists()

        if conflito:
            messages.error(
                request, "Esta sala já está preenchida para este horário por outro utilizador.")
            return redirect('editar_reserva', reserva_id=reserva.id)

        # ATUALIZAÇÃO GOOGLE AGENDA
        titulo_evento = f"Sala {sala} - {reserva.usuario.nome} (Atualizado)"
        try:
            novo_google_id = GoogleAgendaService.enviar_para_google(
                sala=sala,
                titulo=titulo_evento,
                data_inicio=inicio.isoformat(),
                data_fim=fim.isoformat(),
                email_cliente=reserva.usuario.email
            )
            if novo_google_id:
                reserva.google_event_id = novo_google_id
        except Exception:
            messages.warning(
                request, "Alterações salvas localmente, mas falhou a atualização no Google Calendar.")

        # Guarda as alterações definitivas no banco de dados
        reserva.sala = sala
        reserva.inicio = inicio
        reserva.fim = fim
        reserva.save()

        # REDIRECIONAMENTO INTELIGENTE: Devolve o admin à central de gerenciamento
        messages.success(
            request, f"Agendamento de {reserva.usuario.nome} modificado com sucesso!")
        return redirect('minhas_reservas')

    # Método GET
    context = {
        'reserva': reserva,
        'data_atual': reserva.inicio.strftime('%Y-%m-%d'),
        'bloco_atual': f"{reserva.inicio.strftime('%H:%M')}-{reserva.fim.strftime('%H:%M')}"
    }
    return render(request, 'agendamento/editar_reserva.html', context)


@login_required
def excluir_reserva(request, reserva_id):
    # SEGURANÇA POR SESSÃO: Bloqueia perfis que não sejam administradores
    tipo_perfil = request.session.get('perfil')
    if tipo_perfil != 'admin':
        messages.error(
            request, "Acesso negado. Apenas administradores podem cancelar agendamentos.")
        return redirect('minhas_reservas')

    reserva = get_object_or_404(Reserva, id=reserva_id)

    # Executa a exclusão lógica alterando o status para cancelada
    reserva.status = 'cancelada'
    reserva.save()

    # REDIRECIONAMENTO INTELIGENTE: Atualiza a lista removendo o item imediatamente
    messages.success(request, "Agendamento cancelado com sucesso!")
    return redirect('minhas_reservas')
