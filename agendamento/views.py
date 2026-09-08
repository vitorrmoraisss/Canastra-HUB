from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired

from .models import Reserva, ConfiguracaoAgendamento
from .services import GoogleAgendaService, GoogleEmailService
from .utils import (
    obter_slots_por_sala,
    calcular_horario_fim_uso_direto,
    eh_horario_noturno,
    notificar_aprovacoes_pendentes,
    obter_nome_usuario,
    processar_noshow_banco
)


@login_required
def obter_horarios_sala(request):
    sala = request.GET.get('sala', '')
    slots = obter_slots_por_sala(sala)

    opcoes = [
        {'value': f"{s[0]}-{s[1]}", 'label': s[2]}
        for s in slots
    ]
    return JsonResponse({'horarios': opcoes})


@login_required
def realizar_reserva(request):
    if request.method == "POST":
        sala = request.POST.get('sala')
        data_str = request.POST.get('data_reserva')
        bloco_str = request.POST.get('bloco_horario')

        empresa_projeto = request.POST.get('empresa_projeto', 'Não informado')
        quantidade_pessoas = request.POST.get('quantidade_pessoas', 0)
        finalidade = request.POST.get('finalidade', 'Não informado')
        equipamentos = request.POST.get('equipamentos', 'Não informado')
        observacoes = request.POST.get('observacoes', 'Não informado')

        if not data_str or not bloco_str:
            messages.error(
                request, "Por favor, preencha todos os campos do formulário.")
            return redirect('agendamento:realizar_reserva')

        try:
            hora_inicio_str, hora_fim_str = bloco_str.split('-')

            slots_permitidos = obter_slots_por_sala(sala)
            slot_valido = any(s[0] == hora_inicio_str and s[1]
                              == hora_fim_str for s in slots_permitidos)

            if not slot_valido:
                messages.error(
                    request, "Horário inválido para a sala selecionada.")
                return redirect('agendamento:realizar_reserva')

            inicio = parse_datetime(f"{data_str} {hora_inicio_str}:00")
            fim = parse_datetime(f"{data_str} {hora_fim_str}:00")
            inicio = timezone.make_aware(
                inicio) if timezone.is_naive(inicio) else inicio
            fim = timezone.make_aware(fim) if timezone.is_naive(fim) else fim
        except Exception:
            messages.error(
                request, "Erro ao processar o bloco de horário selecionado.")
            return redirect('agendamento:realizar_reserva')

        conflito = Reserva.objects.filter(
            sala=sala, status='confirmada', inicio__lt=fim, fim__gt=inicio
        ).exists()

        if conflito:
            messages.error(
                request, "Esta sala já se encontra reservada para o período selecionado.")
            return redirect('agendamento:realizar_reserva')

        config = ConfiguracaoAgendamento.get_config()

        # Determina as aprovações necessárias
        aprov_hub = 'Pendente' if eh_horario_noturno(inicio, config) else 'N/A'
        aprov_prof = 'Pendente' if (sala.lower() == 'fast') else 'N/A'

        # Se houver qualquer aprovação pendente, o status inicial deve ser 'pendente_aprovacao'
        status_inicial = 'pendente_aprovacao' if (
            aprov_hub == 'Pendente' or aprov_prof == 'Pendente') else 'confirmada'

        nova_reserva = Reserva(
            usuario=request.user,
            sala=sala,
            inicio=inicio,
            fim=fim,
            empresa_projeto=empresa_projeto,
            quantidade_pessoas=int(
                quantidade_pessoas) if quantidade_pessoas else 0,
            finalidade=finalidade,
            equipamentos=equipamentos,
            observacoes=observacoes,
            status=status_inicial,
            aprovado_hub=aprov_hub,
            aprovado_professor=aprov_prof
        )

        nome_amigavel_sala = nova_reserva.get_sala_display()
        nome_usuario = obter_nome_usuario(request.user)
        titulo_evento = f"{nome_amigavel_sala} - {nome_usuario}"

        dados_extras = {
            "empresa_projeto": empresa_projeto,
            "quantidade_pessoas": quantidade_pessoas,
            "finalidade": finalidade,
            "equipamentos": equipamentos,
            "observacoes": observacoes,
            "status_checkin": "Pendente",
            "aprovado_hub": nova_reserva.aprovado_hub,
            "aprovado_professor": nova_reserva.aprovado_professor
        }

        google_id, linha_planilha = None, None
        try:
            google_id, linha_planilha = GoogleAgendaService.enviar_para_google(
                nome_sala=sala,
                titulo=titulo_evento,
                data_inicio=inicio,
                data_fim=fim,
                email_cliente=request.user.email,
                dados_extras=dados_extras
            )
        except Exception as e:
            print(f"Erro de comunicação capturado na View: {e}")

        if not google_id:
            messages.error(
                request, "Não foi possível concluir o agendamento devido a uma falha na integração com o Google Calendar.")
            return redirect('agendamento:realizar_reserva')

        nova_reserva.google_event_id = google_id
        nova_reserva.linha_planilha = linha_planilha
        nova_reserva.save()

        notificar_aprovacoes_pendentes(nova_reserva, request, config)

        messages.success(
            request, "Agendamento realizado e sincronizado com sucesso!")
        return redirect('agendamento:minhas_reservas')

    return render(request, 'agendamento/agendar.html')


@login_required
def minhas_reservas(request):
    tipo_perfil = request.session.get('perfil')

    if tipo_perfil == 'admin':
        reservas = Reserva.objects.filter(
            status='confirmada').order_by('inicio')
    else:
        reservas = Reserva.objects.filter(
            status='confirmada', usuario=request.user).order_by('inicio')

    return render(request, 'agendamento/minhas_reservas.html', {'reservas': reservas})


@login_required
def api_reservas_calendario(request):
    reservas = Reserva.objects.filter(status='confirmada')
    eventos_json = []

    for r in reservas:
        nome_usuario = obter_nome_usuario(r.usuario)
        eventos_json.append({
            'id': r.id,
            'title': f"{r.get_sala_display()}",
            'start': r.inicio.isoformat(),
            'end': r.fim.isoformat(),
            'backgroundColor': '#22c55e',
            'borderColor': '#22c55e',
            'extendedProps': {
                'sala': r.get_sala_display(),
                'usuario_nome': nome_usuario,
                'usuario_email': r.usuario.email,
                'horario_str': f"{r.inicio.strftime('%H:%M')} às {r.fim.strftime('%H:%M')}"
            }
        })

    return JsonResponse(eventos_json, safe=False)


@login_required
def editar_reserva(request, reserva_id):
    tipo_perfil = request.session.get('perfil')
    if tipo_perfil != 'admin':
        messages.error(
            request, "Acesso negado. Apenas administradores podem editar agendamentos.")
        return redirect('agendamento:minhas_reservas')

    reserva = get_object_or_404(Reserva, id=reserva_id)

    if request.method == "POST":
        sala = request.POST.get('sala')
        data_str = request.POST.get('data_reserva')
        bloco_str = request.POST.get('bloco_horario')

        if not data_str or not bloco_str:
            messages.error(
                request, "Por favor, preencha todos os campos obrigatórios.")
            return redirect('agendamento:editar_reserva', reserva_id=reserva.id)

        try:
            hora_inicio_str, hora_fim_str = bloco_str.split('-')
            inicio = parse_datetime(f"{data_str} {hora_inicio_str}:00")
            fim = parse_datetime(f"{data_str} {hora_fim_str}:00")
            inicio = timezone.make_aware(inicio) if timezone.is_naive(
                inicio) else inicio
            fim = timezone.make_aware(fim) if timezone.is_naive(
                fim) else fim
        except Exception:
            messages.error(
                request, "Erro na leitura dos horários selecionados.")
            return redirect('agendamento:editar_reserva', reserva_id=reserva.id)

        conflito = Reserva.objects.filter(
            sala=sala,
            status='confirmada',
            inicio__lt=fim,
            fim__gt=inicio
        ).exclude(id=reserva.id).exists()

        if conflito:
            messages.error(
                request, "Esta sala já está preenchida para este horário por outro utilizador.")
            return redirect('agendamento:editar_reserva', reserva_id=reserva.id)

        nome_usuario = obter_nome_usuario(reserva.usuario)
        titulo_evento = f"Sala {sala} - {nome_usuario} (Atualizado)"

        dados_extras = {
            "empresa_projeto": reserva.empresa_projeto,
            "quantidade_pessoas": reserva.quantidade_pessoas,
            "finalidade": reserva.finalidade,
            "equipamentos": reserva.equipamentos,
            "observacoes": reserva.observacoes,
            "status_checkin": reserva.status_checkin
        }

        try:
            novo_google_id, nova_linha = GoogleAgendaService.enviar_para_google(
                nome_sala=sala,
                titulo=titulo_evento,
                data_inicio=inicio,
                data_fim=fim,
                email_cliente=reserva.usuario.email,
                dados_extras=dados_extras
            )
            if novo_google_id:
                reserva.google_event_id = novo_google_id
                reserva.linha_planilha = nova_linha
        except Exception:
            messages.warning(
                request, "Alterações salvas localmente, mas falhou a atualização no Google Calendar.")

        reserva.sala = sala
        reserva.inicio = inicio
        reserva.fim = fim
        reserva.save()

        messages.success(
            request, "Agendamento modificado com sucesso!")
        return redirect('agendamento:minhas_reservas')

    context = {
        'reserva': reserva,
        'data_atual': reserva.inicio.strftime('%Y-%m-%d'),
        'bloco_atual': f"{reserva.inicio.strftime('%H:%M')}-{reserva.fim.strftime('%H:%M')}"
    }
    return render(request, 'agendamento/editar_reserva.html', context)


@login_required
def excluir_reserva(request, reserva_id):
    tipo_perfil = request.session.get('perfil')
    if tipo_perfil != 'admin':
        messages.error(
            request, "Acesso negado. Apenas administradores podem cancelar agendamentos.")
        return redirect('agendamento:minhas_reservas')

    reserva = get_object_or_404(Reserva, id=reserva_id)

    reserva.status = 'cancelada'
    reserva.save()

    if reserva.linha_planilha:
        GoogleAgendaService.atualizar_checkin_google(
            linha_planilha=reserva.linha_planilha,
            status_checkin="CANCELADA",
            hora_checkin=""
        )

    messages.success(request, "Agendamento cancelado com sucesso!")
    return redirect('agendamento:minhas_reservas')


@login_required
def gerador_qrcodes(request):
    if not getattr(request.user, 'is_admin', False):
        messages.error(
            request, "Acesso não permitido. Esta página é restrita a administradores.")
        return redirect('agendamento:minhas_reservas')

    host_atual = request.get_host()
    protocolo = 'https' if request.is_secure() else 'http'

    salas = [
        {'chave': 'treinamentos', 'nome': 'Espaço de Treinamentos'},
        {'chave': 'reunioes', 'nome': 'Sala de Reuniões'},
        {'chave': 'laboratorio', 'nome': 'Laboratório de Práticas Gerais'},
        {'chave': 'fast', 'nome': 'FAST - Fábrica de Soluções Tecnológicas'},
    ]

    for sala in salas:
        url_checkin = f"{protocolo}://{host_atual}/agendamento/checkin/{sala['chave']}/"
        sala['qrcode_url'] = f"https://quickchart.io/qr?text={url_checkin}&size=300"
        sala['full_url'] = url_checkin

    return render(request, 'agendamento/qrcodes.html', {'salas': salas})


@login_required
def checkin_qrcode(request, sala_chave):
    agora = timezone.localtime()

    nomes_salas = {
        'reunioes': 'Sala de Reuniões',
        'treinamentos': 'Sala de Treinamentos',
        'fast': 'Espaço Fast',
        'laboratorio': 'Laboratório de Práticas Gerais'
    }
    nome_amigavel = nomes_salas.get(
        sala_chave.lower(), sala_chave.capitalize())

    reserva_atual = Reserva.objects.filter(
        sala=sala_chave,
        status='confirmada',
        inicio__lte=agora,
        fim__gte=agora
    ).first()

    if reserva_atual:
        if reserva_atual.usuario == request.user:
            if reserva_atual.status_checkin in ['CONFIRMADO', 'USO DIRETO']:
                contexto = {
                    'status': 'sucesso',
                    'titulo': 'Sessão Ativa 🟢',
                    'mensagem': f'Você já realizou o check-in nesta sala ({reserva_atual.get_sala_display()}). Seu horário vai até {reserva_atual.fim.strftime("%H:%M")}.',
                    'cor': 'success',
                    'reserva': reserva_atual
                }
                return render(request, 'agendamento/checkin_resultado.html', contexto)

            if request.method == 'POST':
                reserva_atual.status_checkin = 'CONFIRMADO'
                reserva_atual.hora_checkin = agora
                reserva_atual.save()

                if reserva_atual.linha_planilha:
                    GoogleAgendaService.atualizar_checkin_google(
                        linha_planilha=reserva_atual.linha_planilha,
                        status_checkin='CONFIRMADO',
                        hora_checkin=agora.strftime('%H:%M:%S')
                    )

                contexto = {
                    'status': 'sucesso',
                    'titulo': 'Check-in Confirmado! 🟢',
                    'mensagem': f'Seu check-in na sala {reserva_atual.get_sala_display()} foi registrado com sucesso.',
                    'cor': 'success',
                    'reserva': reserva_atual
                }
                return render(request, 'agendamento/checkin_resultado.html', contexto)

            contexto = {
                'status': 'confirmar_checkin',
                'titulo': 'Confirmar Presença 📍',
                'mensagem': f'Você possui uma reserva prévia para a sala {reserva_atual.get_sala_display()}. Clique abaixo para confirmar seu check-in.',
                'cor': 'primary',
                'reserva': reserva_atual
            }
            return render(request, 'agendamento/checkin_resultado.html', contexto)
        else:
            nome_ocupante = obter_nome_usuario(reserva_atual.usuario)
            contexto = {
                'status': 'ocupada',
                'titulo': 'Sala Ocupada 🔴',
                'mensagem': f'Esta sala está atualmente em uso por {nome_ocupante}.',
                'cor': 'danger',
                'reserva': reserva_atual
            }
            return render(request, 'agendamento/checkin_resultado.html', contexto)
    else:
        fim_calculado, minutos_restantes = calcular_horario_fim_uso_direto(
            sala_chave, agora)
        inicio_str = agora.strftime('%H:%M')
        fim_str = fim_calculado.strftime('%H:%M')

        if request.method == 'POST':
            nova_reserva = Reserva(
                usuario=request.user,
                sala=sala_chave,
                inicio=agora,
                fim=fim_calculado,
                empresa_projeto="Uso Presencial Espontâneo",
                quantidade_pessoas=1,
                finalidade="Uso Direto via QR Code",
                equipamentos="Uso geral do espaço",
                observacoes="Iniciado via leitura presencial de QR Code.",
                status='confirmada',
                status_checkin='USO DIRETO',
                hora_checkin=agora
            )

            nome_usuario = obter_nome_usuario(request.user)
            titulo_evento = f"{nome_amigavel} - {nome_usuario} (Uso Direto)"

            dados_extras = {
                "empresa_projeto": nova_reserva.empresa_projeto,
                "quantidade_pessoas": 1,
                "finalidade": nova_reserva.finalidade,
                "equipamentos": nova_reserva.equipamentos,
                "observacoes": nova_reserva.observacoes,
                "status_checkin": "USO DIRETO",
                "hora_checkin": agora.strftime("%d/%m/%Y %H:%M")
            }

            try:
                google_id, linha_planilha = GoogleAgendaService.enviar_para_google(
                    nome_sala=sala_chave,
                    titulo=titulo_evento,
                    data_inicio=nova_reserva.inicio,
                    data_fim=nova_reserva.fim,
                    email_cliente=request.user.email,
                    dados_extras=dados_extras
                )
                nova_reserva.google_event_id = google_id
                nova_reserva.linha_planilha = linha_planilha
            except Exception as e:
                print(f"Erro ao registrar uso direto no Google: {e}")

            nova_reserva.save()

            contexto = {
                'status': 'sucesso',
                'titulo': 'Uso Direto Iniciado 🟡',
                'mensagem': f'Espaço {nome_amigavel} reservado com sucesso! Período das {inicio_str} às {fim_str} ({minutos_restantes} min).',
                'cor': 'success',
                'reserva': nova_reserva
            }

            return render(request, 'agendamento/checkin_resultado.html', contexto)

        contexto = {
            'status': 'confirmar_uso_direto',
            'titulo': 'Espaço Disponível 🟢',
            'nome_amigavel': nome_amigavel,
            'horario_inicio': inicio_str,
            'horario_fim': fim_str,
            'minutos_restantes': minutos_restantes,
            'sala_chave': sala_chave,
            'cor': 'success'
        }
        return render(request, 'agendamento/checkin_resultado.html', contexto)


@login_required
def gerenciar_configuracoes_hub(request):
    if not getattr(request.user, 'is_admin', False):
        messages.error(
            request, "Acesso negado. Apenas administradores podem acessar esta página.")
        return redirect('agendamento:minhas_reservas')

    config = ConfiguracaoAgendamento.get_config()

    if request.method == 'POST':
        email_hub = request.POST.get('email_hub', '').strip()
        email_prof1 = request.POST.get('email_professor_1', '').strip()
        email_prof2 = request.POST.get('email_professor_2', '').strip()
        horario_inicio = request.POST.get('horario_noturno_inicio')
        horario_fim = request.POST.get('horario_noturno_fim')

        if email_hub and email_prof1 and email_prof2:
            try:
                config.email_hub = email_hub
                config.email_professor_1 = email_prof1
                config.email_professor_2 = email_prof2
                config.horario_noturno_inicio = int(horario_inicio)
                config.horario_noturno_fim = int(horario_fim)
                config.save()

                messages.success(
                    request, "Parâmetros do HUB e e-mails de aprovação atualizados!")
                return redirect('agendamento:configuracoes_hub')
            except (ValueError, TypeError):
                messages.error(
                    request, "Forneça números inteiros válidos entre 0 e 23 para os horários.")
        else:
            messages.error(
                request, "Preencha todos os campos de e-mail obrigatoriamente.")

    return render(request, 'agendamento/configuracoes_hub.html', {'config': config})


@login_required
def listar_agendamentos(request):
    processar_noshow_banco()
    reservas = Reserva.objects.all().order_by('-inicio')
    return render(request, 'agendamento/listar.html', {'reservas': reservas})


def processar_aprovacao_email(request, token):
    signer = TimestampSigner()
    try:
        # Token expira após 48 horas (172800 segundos)
        conteudo = signer.unsign(token, max_age=172800)
        reserva_id, tipo_aprovador, acao = conteudo.split(':')
        reserva = get_object_or_404(Reserva, id=reserva_id)

        if tipo_aprovador == 'hub':
            reserva.aprovado_hub = acao
        elif tipo_aprovador == 'professor':
            reserva.aprovado_professor = acao

        if acao == 'Rejeitado':
            reserva.status = 'cancelada'
            mensagem_texto = "A solicitação foi REJEITADA com sucesso. O agendamento foi cancelado."
        else:
            if reserva.aprovado_hub in ['Aprovado', 'N/A'] and reserva.aprovado_professor in ['Aprovado', 'N/A']:
                reserva.status = 'confirmada'
                mensagem_texto = "Solicitação APROVADA com sucesso! A reserva está confirmada."
            else:
                mensagem_texto = "Sua aprovação foi registrada! Aguardando a validação da outra pendência."

        reserva.save()

        return render(request, 'agendamento/mensagem_agendamento.html', {
            'sucesso': True,
            'mensagem': mensagem_texto
        })

    except (SignatureExpired, BadSignature, Exception):
        return render(request, 'agendamento/mensagem_agendamento.html', {
            'sucesso': False,
            'mensagem': "O link de aprovação é inválido ou já expirou (validade de 48 horas)."
        })
