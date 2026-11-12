"""Autenticação de dois fatores: código de 6 dígitos enviado por e-mail no login."""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db.models import F
from django.utils import timezone

from core.models import CodigoVerificacao, DispositivoConfiavel
from core.emails import enviar_email

VALIDADE_CODIGO = timedelta(minutes=10)
MAX_TENTATIVAS = 5
INTERVALO_REENVIO = timedelta(seconds=60)
MAX_CODIGOS_POR_HORA = 5
VALIDADE_DISPOSITIVO = timedelta(days=30)
VALIDADE_PENDENCIA = timedelta(minutes=10)
COOKIE_DISPOSITIVO = 'canastra_dispositivo'


def _gerar_codigo():
    return f'{secrets.randbelow(10 ** 6):06d}'


def _codigos_ativos(usuario):
    return CodigoVerificacao.objects.filter(
        usuario=usuario,
        usado_em__isnull=True,
        expira_em__gt=timezone.now(),
        tentativas__lt=MAX_TENTATIVAS,
    )


def tem_codigo_ativo(usuario):
    return _codigos_ativos(usuario).exists()


def pode_enviar_codigo(usuario):
    """Retorna (permitido, motivo do bloqueio)."""
    agora = timezone.now()
    codigos = CodigoVerificacao.objects.filter(usuario=usuario)
    if codigos.filter(criado_em__gt=agora - INTERVALO_REENVIO).exists():
        return False, 'Aguarde alguns segundos para pedir outro código.'
    if codigos.filter(criado_em__gt=agora - timedelta(hours=1)).count() >= MAX_CODIGOS_POR_HORA:
        return False, 'Limite de códigos atingido. Tente novamente mais tarde.'
    return True, None


def gerar_e_enviar_codigo(usuario):
    """Invalida códigos anteriores, cria um novo e envia por e-mail. False se o envio falhar."""
    agora = timezone.now()
    # Códigos da última hora ficam no banco porque contam para o limite de envio
    CodigoVerificacao.objects.filter(usuario=usuario, criado_em__lt=agora - timedelta(hours=1)).delete()
    DispositivoConfiavel.objects.filter(usuario=usuario, expira_em__lt=agora).delete()
    _codigos_ativos(usuario).update(usado_em=agora)

    codigo = _gerar_codigo()
    registro = CodigoVerificacao.objects.create(
        usuario=usuario,
        codigo_hash=make_password(codigo),
        expira_em=agora + VALIDADE_CODIGO,
    )

    enviado = enviar_email(usuario.email, 'codigo_verificacao', {
        'nome': usuario.nome,
        'codigo': codigo,
        'expiracao_minutos': int(VALIDADE_CODIGO.total_seconds() // 60),
    })
    if not enviado:
        # Código que não chegou ao usuário não fica ativo nem conta no limite
        registro.delete()
        return False
    return True


def validar_codigo(usuario, codigo):
    """Retorna 'ok', 'invalido' ou 'bloqueado' (estourou as tentativas)."""
    registro = _codigos_ativos(usuario).order_by('-criado_em').first()
    if registro is None:
        return 'invalido'

    if check_password((codigo or '').strip(), registro.codigo_hash):
        registro.usado_em = timezone.now()
        registro.save(update_fields=['usado_em'])
        return 'ok'

    # F() evita que requisições simultâneas percam incrementos
    CodigoVerificacao.objects.filter(pk=registro.pk).update(tentativas=F('tentativas') + 1)
    registro.refresh_from_db(fields=['tentativas'])
    if registro.tentativas >= MAX_TENTATIVAS:
        registro.usado_em = timezone.now()
        registro.save(update_fields=['usado_em'])
        return 'bloqueado'
    return 'invalido'


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def criar_dispositivo_confiavel(request, response, usuario):
    """Registra o navegador como confiável e grava o token no cookie da resposta."""
    token = secrets.token_urlsafe(32)
    DispositivoConfiavel.objects.create(
        usuario=usuario,
        token_hash=_hash_token(token),
        expira_em=timezone.now() + VALIDADE_DISPOSITIVO,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
    )
    response.set_cookie(
        COOKIE_DISPOSITIVO,
        token,
        max_age=int(VALIDADE_DISPOSITIVO.total_seconds()),
        httponly=True,
        samesite='Lax',
        secure=request.is_secure(),
    )


def dispositivo_confiavel(request, usuario):
    token = request.COOKIES.get(COOKIE_DISPOSITIVO)
    if not token:
        return False
    agora = timezone.now()
    atualizados = DispositivoConfiavel.objects.filter(
        usuario=usuario, token_hash=_hash_token(token), expira_em__gt=agora
    ).update(ultimo_uso=agora)
    return atualizados > 0


def revogar_dispositivos(usuario):
    DispositivoConfiavel.objects.filter(usuario=usuario).delete()


def mascarar_email(email):
    nome, _, dominio = email.partition('@')
    return f'{nome[:2]}***@{dominio}'
