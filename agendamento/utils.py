from datetime import datetime, timedelta
from django.conf import settings
from django.core.signing import TimestampSigner
from django.urls import reverse
from django.utils import timezone

from .models import Reserva, ConfiguracaoAgendamento
from .services import GoogleEmailService

# ==============================================================================
# CONSTANTES E CONFIGURAÇÕES DE SLOTS
# ==============================================================================

# Slots de 1h20min (Sala de Reuniões e Sala Fast)
SLOTS_80_MINUTOS = [
    ("07:00", "08:20", "07:00 às 08:20"),
    ("08:30", "09:50", "08:30 às 09:50"),
    ("10:00", "11:20", "10:00 às 11:20"),
    ("11:30", "12:50", "11:30 às 12:50"),
    ("13:00", "14:20", "13:00 às 14:20"),
    ("14:30", "15:50", "14:30 às 15:50"),
    ("16:00", "17:20", "16:00 às 17:20"),
    ("17:30", "18:50", "17:30 às 18:50"),
    ("19:00", "20:20", "19:00 às 20:20"),
]

# Slots de 50min (Demais salas / Treinamento)
SLOTS_50_MINUTOS = [
    ("07:00", "07:50", "07:00 às 07:50"),
    ("08:00", "08:50", "08:00 às 08:50"),
    ("09:00", "09:50", "09:00 às 09:50"),
    ("10:00", "10:50", "10:00 às 10:50"),
    ("11:00", "11:50", "11:00 às 11:50"),
    ("12:00", "12:50", "12:00 às 12:50"),
    ("13:00", "13:50", "13:00 às 13:50"),
    ("14:00", "14:50", "14:00 às 14:50"),
    ("15:00", "15:50", "15:00 às 15:50"),
    ("16:00", "16:50", "16:00 às 16:50"),
    ("17:00", "17:50", "17:00 às 17:50"),
    ("18:00", "18:50", "18:00 às 18:50"),
    ("19:00", "19:50", "19:00 às 19:50"),
    ("20:00", "20:50", "20:00 às 20:50"),
]


# ==============================================================================
# FUNÇÕES AUXILIARES DE SLOTS E HORÁRIOS
# ==============================================================================

def obter_slots_por_sala(nome_sala):
    nome_normalizado = nome_sala.lower()
    if 'reunioes' in nome_normalizado or 'fast' in nome_normalizado:
        return SLOTS_80_MINUTOS
    return SLOTS_50_MINUTOS


def obter_duracao_padrao_sala(nome_sala):
    nome_normalizado = nome_sala.lower()
    if any(termo in nome_normalizado for termo in ['reuniao', 'reunioes', 'fast']):
        return 80
    return 50


def calcular_horario_fim_uso_direto(nome_sala, agora=None):
    if agora is None:
        agora = timezone.localtime()

    slots = obter_slots_por_sala(nome_sala)

    for inicio_str, fim_str, _ in slots:
        h_fim = datetime.strptime(fim_str, "%H:%M").time()
        dt_fim = datetime.combine(agora.date(), h_fim)

        if timezone.is_aware(agora):
            dt_fim = timezone.make_aware(
                dt_fim, timezone.get_current_timezone())

        if agora < dt_fim:
            minutos_restantes = int((dt_fim - agora).total_seconds() // 60)
            return dt_fim, minutos_restantes

    duracao_padrao = obter_duracao_padrao_sala(nome_sala)
    dt_fim = agora + timedelta(minutes=duracao_padrao)
    return dt_fim, duracao_padrao


# ==============================================================================
# FUNÇÕES DE REGRAS DE NEGÓCIO E NOTIFICAÇÃO
# ==============================================================================

def processar_noshow_banco():
    agora = timezone.now()

    qtd_atualizadas = Reserva.objects.filter(
        fim__lte=agora,
        status='confirmada',
        status_checkin='Pendente'
    ).update(status='nao_compareceu')

    return qtd_atualizadas


def gerar_link_aprovacao(request, reserva_id, tipo_aprovador, acao):
    """Gera um link seguro assinado criptograficamente."""
    signer = TimestampSigner()
    conteudo = f"{reserva_id}:{tipo_aprovador}:{acao}"
    token = signer.sign(conteudo)

    url_relativa = reverse(
        'agendamento:processar_aprovacao_email', kwargs={'token': token})
    return request.build_absolute_uri(url_relativa)


def obter_nome_usuario(usuario):
    """Retorna o nome completo ou username do solicitante de forma segura."""
    if not usuario:
        return "Solicitante não identificado"

    if hasattr(usuario, 'get_full_name') and usuario.get_full_name():
        return usuario.get_full_name()

    return getattr(usuario, 'first_name', getattr(usuario, 'username', str(usuario)))


def eh_horario_noturno(horario, config):
    """Verifica se a hora do agendamento cai dentro da janela noturna configurada."""
    hora = horario.hour
    inicio = config.horario_noturno_inicio  # ex: 18
    fim = config.horario_noturno_fim        # ex: 22

    if inicio <= fim:
        return inicio <= hora < fim
    else:
        return hora >= inicio or hora < fim


def notificar_aprovacoes_pendentes(reserva, request, config):
    signer = TimestampSigner()
    protocolo = 'https' if request.is_secure() else 'http'
    host = request.get_host()

    # notificacao para horario noturno - email hub
    if reserva.aprovado_hub == 'Pendente':
        token_aprovar = signer.sign(f"{reserva.id}:hub:Aprovado")
        token_rejeitar = signer.sign(f"{reserva.id}:hub:Rejeitado")

        url_aprovar = f"{protocolo}://{host}{reverse('agendamento:processar_aprovacao_email', kwargs={'token': token_aprovar})}"
        url_rejeitar = f"{protocolo}://{host}{reverse('agendamento:processar_aprovacao_email', kwargs={'token': token_rejeitar})}"

        mensagem_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #0f172a;">Solicitação de Aprovação - HUB</h2>
            <p>Uma nova reserva em horário noturno exige sua validação.</p>
            <ul>
                <li><strong>Espaço:</strong> {reserva.get_sala_display()}</li>
                <li><strong>Solicitante:</strong> {getattr(reserva.usuario, 'nome', reserva.usuario.email)}</li>
                <li><strong>Início:</strong> {reserva.inicio.strftime('%d/%m/%Y %H:%M')}</li>
                <li><strong>Término:</strong> {reserva.fim.strftime('%d/%m/%Y %H:%M')}</li>
                <li><strong>Finalidade:</strong> {reserva.finalidade}</li>
            </ul>
            <p style="margin-top: 20px;">Clique em uma das opções para responder (válido por 48h):</p>
            <div style="margin-top: 15px;">
                <a href="{url_aprovar}" style="background-color: #22c55e; color: #ffffff; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-right: 10px;">Aprovar Reserva</a>
                <a href="{url_rejeitar}" style="background-color: #ef4444; color: #ffffff; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: bold;">Rejeitar Reserva</a>
            </div>
        </div>
        """

        GoogleEmailService.enviar_email(
            destinatarios=config.email_hub,
            assunto=f"[Aprovação Pendente] Reserva HUB - {reserva.get_sala_display()}",
            mensagem_html=mensagem_html
        )

    # 2. Notificação para Professores (Espaço FAST)
    if reserva.aprovado_professor == 'Pendente':
        token_aprovar = signer.sign(f"{reserva.id}:professor:Aprovado")
        token_rejeitar = signer.sign(f"{reserva.id}:professor:Rejeitado")

        url_aprovar = f"{protocolo}://{host}{reverse('agendamento:processar_aprovacao_email', kwargs={'token': token_aprovar})}"
        url_rejeitar = f"{protocolo}://{host}{reverse('agendamento:processar_aprovacao_email', kwargs={'token': token_rejeitar})}"

        mensagem_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #0f172a;">Solicitação de Aprovação - FAST</h2>
            <p>Uma nova reserva na fábrica FAST aguarda sua validação docente.</p>
            <ul>
                <li><strong>Solicitante:</strong> {getattr(reserva.usuario, 'nome', reserva.usuario.email)}</li>
                <li><strong>Início:</strong> {reserva.inicio.strftime('%d/%m/%Y %H:%M')}</li>
                <li><strong>Término:</strong> {reserva.fim.strftime('%d/%m/%Y %H:%M')}</li>
                <li><strong>Empresa/Projeto:</strong> {reserva.empresa_projeto}</li>
                <li><strong>Finalidade:</strong> {reserva.finalidade}</li>
            </ul>
            <p style="margin-top: 20px;">Clique em uma das opções para responder (válido por 48h):</p>
            <div style="margin-top: 15px;">
                <a href="{url_aprovar}" style="background-color: #22c55e; color: #ffffff; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: bold; margin-right: 10px;">Aprovar Reserva</a>
                <a href="{url_rejeitar}" style="background-color: #ef4444; color: #ffffff; padding: 10px 18px; text-decoration: none; border-radius: 6px; font-weight: bold;">Rejeitar Reserva</a>
            </div>
        </div>
        """

        professores = [p for p in [
            config.email_professor_1, config.email_professor_2] if p]
        if professores:
            GoogleEmailService.enviar_email(
                destinatarios=professores,
                assunto=f"[Aprovação Pendente] Reserva FAST - {reserva.get_sala_display()}",
                mensagem_html=mensagem_html
            )
