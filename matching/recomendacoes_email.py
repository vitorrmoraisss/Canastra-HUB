"""E-mail semanal com vagas compatíveis, a partir dos MatchScore do matching.

Fluxo de um disparo (enviar_recomendacoes_semanais):
1. Seleciona os candidatos elegíveis: conta ativa, com e-mail e sem
   descadastro (PreferenciaEmailVagas.receber_vagas=False).
2. Para cada um, busca os MatchScore acima do score mínimo, só de vagas
   abertas no momento do disparo, descartando vagas em que já se candidatou
   e vagas já recomendadas em semanas anteriores.
3. Envia um único e-mail com até VAGAS_EMAIL_LIMITE vagas e registra o
   resultado em EnvioVagasEmail (um registro por candidato e semana).

Reexecutar na mesma semana não reenvia para quem já recebeu; quem falhou
é tentado de novo.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from core.models import Usuario
from core.emails import enviar_email
from vagas.models import UsuarioVaga, Vagas

from .models import EnvioVagasEmail, MatchScore

logger = logging.getLogger(__name__)

STATUS_VAGA_ABERTA = 'ativa'
SALT_DESCADASTRO = 'matching.descadastro_vagas_email'
# Um registro "enviando" mais antigo que isso é tratado como execução interrompida.
TEMPO_MAXIMO_ENVIANDO = timedelta(hours=1)
ESPERA_ENTRE_TENTATIVAS = 2  # segundos, multiplicado pelo número da tentativa


@dataclass
class ResultadoDisparo:
    semana: date
    enviados: int = 0
    falhas: int = 0
    sem_vagas: int = 0
    ja_enviados: int = 0
    falhas_usuarios: list[int] = field(default_factory=list)


def semana_de_referencia(momento: datetime | None = None) -> date:
    """Segunda-feira da semana (no fuso local) que contém o momento informado."""
    hoje = timezone.localdate(momento or timezone.now())
    return hoje - timedelta(days=hoje.weekday())


def gerar_token_descadastro(usuario_pk) -> str:
    return signing.dumps({'u': usuario_pk}, salt=SALT_DESCADASTRO)


def ler_token_descadastro(token: str):
    """Retorna o pk do candidato ou None se o token for inválido."""
    try:
        return signing.loads(token, salt=SALT_DESCADASTRO)['u']
    except (signing.BadSignature, KeyError, TypeError):
        return None


def _url_absoluta(caminho: str) -> str:
    return f"{settings.SITE_URL}{caminho}"


def usuarios_elegiveis():
    return (
        Usuario.objects
        .filter(user__is_active=True)
        .exclude(user__email='')
        .exclude(preferencia_email_vagas__receber_vagas=False)
        .select_related('user')
        .order_by('pk')
    )


def vagas_recomendadas(usuario, limite=None, score_minimo=None) -> list[MatchScore]:
    """MatchScore das vagas a recomendar ao candidato, do mais compatível ao menos.

    Só entram vagas abertas agora, de empresas ativas, em que o candidato
    ainda não se candidatou e que ainda não foram recomendadas a ele.
    """
    limite = settings.VAGAS_EMAIL_LIMITE if limite is None else limite
    score_minimo = settings.VAGAS_EMAIL_SCORE_MINIMO if score_minimo is None else score_minimo

    candidatadas = UsuarioVaga.objects.filter(usuario=usuario).values('vaga_id')
    ja_recomendadas = Vagas.objects.filter(
        envios_email__usuario=usuario,
        envios_email__status=EnvioVagasEmail.STATUS_ENVIADO,
    ).values('pk')

    qs = (
        MatchScore.objects
        .filter(
            usuario=usuario,
            score__gte=score_minimo,
            vaga__status=STATUS_VAGA_ABERTA,
            vaga__empresa__user__is_active=True,
        )
        .exclude(vaga_id__in=candidatadas)
        .exclude(vaga_id__in=ja_recomendadas)
        .select_related('vaga__empresa', 'vaga__hub')
        .order_by('-score', '-vaga__data_publicacao')
    )

    # MatchScore é único por (usuario, vaga); o set protege contra duplicata mesmo assim
    resultado, vistos = [], set()
    for match in qs:
        if match.vaga_id in vistos:
            continue
        vistos.add(match.vaga_id)
        resultado.append(match)
        if len(resultado) >= limite:
            break
    return resultado


def montar_contexto_email(usuario, matches) -> dict:
    vagas = [
        {
            'cargo': m.vaga.cargo_vaga or 'Vaga sem título',
            'empresa': m.vaga.empresa.nomefantasia if m.vaga.empresa else '',
            'local': m.vaga.local or '',
            'hub': m.vaga.hub.nome_hub if m.vaga.hub else '',
            'descricao': m.vaga.descricao_vaga or '',
            'compatibilidade': round(m.score * 100),
            'link': _url_absoluta(reverse('vagas:detalhe_vaga', args=[m.vaga_id])),
        }
        for m in matches
    ]
    return {
        'nome': usuario.nome_social or usuario.user.nome,
        'vagas': vagas,
        'cta_texto': 'Ver todas as vagas',
        'cta_link': _url_absoluta(reverse('vagas:buscar_vagas')),
        'link_descadastro': _url_absoluta(
            reverse('matching:descadastrar_vagas_email', args=[gerar_token_descadastro(usuario.pk)])
        ),
    }


def _reservar_envio(usuario, semana) -> EnvioVagasEmail | None:
    """Reserva o envio da semana para o candidato. None se já enviado ou em andamento."""
    with transaction.atomic():
        try:
            envio, criado = EnvioVagasEmail.objects.select_for_update().get_or_create(
                usuario=usuario, semana=semana,
                defaults={'email': usuario.user.email},
            )
        except IntegrityError:
            return None  # outra execução criou o registro ao mesmo tempo
        if criado:
            return envio
        if envio.status == EnvioVagasEmail.STATUS_ENVIADO:
            return None
        if (envio.status == EnvioVagasEmail.STATUS_ENVIANDO
                and timezone.now() - envio.atualizado_em < TEMPO_MAXIMO_ENVIANDO):
            return None
        envio.status = EnvioVagasEmail.STATUS_ENVIANDO
        envio.email = usuario.user.email
        envio.save(update_fields=['status', 'email', 'atualizado_em'])
        return envio


def _enviar_com_tentativas(destino, contexto) -> tuple[bool, int]:
    tentativas = max(1, settings.VAGAS_EMAIL_TENTATIVAS)
    for tentativa in range(1, tentativas + 1):
        if enviar_email(destino, 'vagas_semanais', contexto):
            return True, tentativa
        if tentativa < tentativas:
            time.sleep(ESPERA_ENTRE_TENTATIVAS * tentativa)
    return False, tentativas


def enviar_para_usuario(usuario, semana) -> str:
    """Envia o e-mail da semana a um candidato. Retorna 'enviado', 'falha', 'sem_vagas' ou 'ja_enviado'."""
    if EnvioVagasEmail.objects.filter(
        usuario=usuario, semana=semana, status=EnvioVagasEmail.STATUS_ENVIADO,
    ).exists():
        return 'ja_enviado'

    matches = vagas_recomendadas(usuario)
    if not matches:
        return 'sem_vagas'

    envio = _reservar_envio(usuario, semana)
    if envio is None:
        return 'ja_enviado'

    try:
        contexto = montar_contexto_email(usuario, matches)
        sucesso, tentativas = _enviar_com_tentativas(usuario.user.email, contexto)
        erro = '' if sucesso else 'Provedor de e-mail não confirmou o envio (ver log da aplicação).'
    except Exception as exc:  # falha inesperada não deve derrubar o disparo dos demais
        logger.exception('Erro ao montar/enviar e-mail de vagas para usuario %s', usuario.pk)
        sucesso, tentativas, erro = False, 0, f'{type(exc).__name__}: {exc}'[:1000]

    envio.tentativas += tentativas
    envio.erro = erro
    if sucesso:
        envio.status = EnvioVagasEmail.STATUS_ENVIADO
        envio.enviado_em = timezone.now()
        envio.save()
        envio.vagas.set([m.vaga_id for m in matches])
        logger.info('E-mail de vagas enviado: usuario=%s vagas=%s', usuario.pk, [m.vaga_id for m in matches])
        return 'enviado'

    envio.status = EnvioVagasEmail.STATUS_FALHA
    envio.save()
    envio.vagas.set([m.vaga_id for m in matches])
    logger.error('Falha no e-mail de vagas: usuario=%s email=%s erro=%s', usuario.pk, usuario.user.email, erro)
    return 'falha'


def simular_para_usuario(usuario, semana) -> str:
    """Mesma decisão de enviar_para_usuario, sem enviar nem gravar nada."""
    if EnvioVagasEmail.objects.filter(
        usuario=usuario, semana=semana, status=EnvioVagasEmail.STATUS_ENVIADO,
    ).exists():
        return 'ja_enviado'
    return 'enviado' if vagas_recomendadas(usuario) else 'sem_vagas'


def enviar_recomendacoes_semanais(
    momento: datetime | None = None,
    usuarios=None,
    simular: bool = False,
) -> ResultadoDisparo:
    """Executa o disparo da semana.

    usuarios: queryset/lista para restringir o disparo (default: todos os elegíveis).
    simular: só calcula quem receberia, sem enviar e-mail nem gravar registros.
    """
    semana = semana_de_referencia(momento)
    resultado = ResultadoDisparo(semana=semana)
    logger.info('Iniciando disparo semanal de vagas compatíveis (semana %s, simular=%s)', semana, simular)

    if usuarios is None:
        usuarios = usuarios_elegiveis().iterator()
    acao = simular_para_usuario if simular else enviar_para_usuario

    for usuario in usuarios:
        try:
            situacao = acao(usuario, semana)
        except Exception:
            logger.exception('Erro inesperado no disparo de vagas para usuario %s', usuario.pk)
            situacao = 'falha'

        if situacao == 'enviado':
            resultado.enviados += 1
        elif situacao == 'sem_vagas':
            resultado.sem_vagas += 1
        elif situacao == 'ja_enviado':
            resultado.ja_enviados += 1
        else:
            resultado.falhas += 1
            resultado.falhas_usuarios.append(usuario.pk)

    logger.info(
        'Disparo semanal de vagas concluído (semana %s): enviados=%s falhas=%s sem_vagas=%s ja_enviados=%s',
        semana, resultado.enviados, resultado.falhas, resultado.sem_vagas, resultado.ja_enviados,
    )
    return resultado


def proximo_disparo(agora: datetime | None = None) -> datetime:
    """Próximo horário de disparo configurado (VAGAS_EMAIL_DIA_SEMANA/HORARIO), no fuso local."""
    agora = timezone.localtime(agora or timezone.now())
    dias = (settings.VAGAS_EMAIL_DIA_SEMANA - agora.weekday()) % 7
    alvo = (agora + timedelta(days=dias)).replace(
        hour=settings.VAGAS_EMAIL_HORA, minute=settings.VAGAS_EMAIL_MINUTO, second=0, microsecond=0,
    )
    if alvo <= agora:
        alvo += timedelta(days=7)
    return alvo


def disparo_da_semana_pendente(agora: datetime | None = None) -> bool:
    """True se o horário de disparo desta semana já passou (usado para recuperar disparo perdido)."""
    ultimo = proximo_disparo(agora) - timedelta(days=7)
    return ultimo.date() >= semana_de_referencia(agora)
