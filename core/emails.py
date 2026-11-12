"""Montagem e envio padronizado de todos os e-mails do sistema.

Todo e-mail sai por enviar_email(para, tipo, contexto). Cada tipo tem um
assunto e um par de templates (<template>.html e <template>.txt) que herdam
email/base_email.html e email/base_email.txt.

Guia de estilo: docs/emails/guia-de-estilo.md
"""
import logging
import re
from dataclasses import dataclass

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from core.servico_email import ServicoEmail

logger = logging.getLogger(__name__)

PREFIXO_ASSUNTO = '[Canastra HUB]'
LIMITE_ASSUNTO_ESTILO = 60
LIMITE_ASSUNTO_ENDPOINT = 200
LIMITE_CORPO = 20_000


@dataclass(frozen=True)
class TipoEmail:
    assunto: str   # aceita campos de str.format com chaves do contexto
    template: str  # caminho sem extensão; renderiza .html e .txt


@dataclass(frozen=True)
class EmailRenderizado:
    assunto: str
    html: str
    texto: str


TIPOS = {
    'codigo_verificacao': TipoEmail('Código de verificação', 'email/codigo_verificacao'),
}


def _contexto_global():
    return {
        'site_url': settings.SITE_URL,
        'logo_url': settings.EMAIL_LOGO_URL,
        'link_contato': f"{settings.SITE_URL}{reverse('core:contato')}",
    }


def _limpar_texto(texto):
    linhas = [linha.rstrip() for linha in texto.strip().splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(linhas))


def renderizar_email(tipo, contexto):
    try:
        definicao = TIPOS[tipo]
    except KeyError:
        raise ValueError(f'Tipo de e-mail desconhecido: {tipo!r}') from None

    dados = {**_contexto_global(), **contexto}
    assunto = ' '.join(f'{PREFIXO_ASSUNTO} {definicao.assunto.format(**dados)}'.split())
    dados['assunto'] = assunto
    html = render_to_string(f'{definicao.template}.html', dados)
    texto = _limpar_texto(render_to_string(f'{definicao.template}.txt', dados))
    return EmailRenderizado(assunto=assunto, html=html, texto=texto)


def enviar_email(para, tipo, contexto):
    """Envia o e-mail do tipo para um ou mais destinatários.

    Retorna True só se todos os envios forem confirmados pelo provedor.
    """
    lista = [para] if isinstance(para, str) else list(para)
    destinatarios = [d.strip() for d in lista if d and d.strip()]
    if not destinatarios:
        logger.error('E-mail %s não enviado: nenhum destinatário', tipo)
        return False

    email = renderizar_email(tipo, contexto)

    if len(email.assunto) > LIMITE_ASSUNTO_ESTILO:
        logger.warning('Assunto do e-mail %s passa de %s caracteres: %r', tipo, LIMITE_ASSUNTO_ESTILO, email.assunto)
    if len(email.assunto) > LIMITE_ASSUNTO_ENDPOINT:
        logger.error('E-mail %s não enviado: assunto com %s caracteres', tipo, len(email.assunto))
        return False
    if len(email.html) > LIMITE_CORPO or len(email.texto) > LIMITE_CORPO:
        logger.error('E-mail %s não enviado: corpo com %s/%s caracteres (HTML/texto)', tipo, len(email.html), len(email.texto))
        return False

    sucesso = True
    for destinatario in destinatarios:
        if not ServicoEmail.enviar(destinatario, email.assunto, email.html, html=True, texto=email.texto):
            sucesso = False
    return sucesso
