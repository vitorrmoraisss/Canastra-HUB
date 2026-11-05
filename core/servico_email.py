"""Envio de e-mail da aplicação. Para trocar de provedor, altere só esta classe."""
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class ServicoEmail:
    """Envia e-mails pelo web app do Google Apps Script."""

    TIMEOUT = 10

    @classmethod
    def enviar(cls, para, assunto, mensagem, html=True):
        """Retorna True só quando o provedor confirma o envio."""
        if not settings.GAS_EMAIL_URL or not settings.GAS_API_SECRET:
            logger.error('E-mail não enviado: GAS_EMAIL_URL ou GAS_API_SECRET não configurados')
            return False

        try:
            resposta = requests.post(
                settings.GAS_EMAIL_URL,
                json={
                    'secret': settings.GAS_API_SECRET,
                    'para': para,
                    'assunto': assunto,
                    'mensagem': mensagem,
                    'html': html,
                },
                timeout=cls.TIMEOUT,
            )
            resposta.raise_for_status()
            dados = resposta.json()
        except (requests.RequestException, ValueError):
            logger.exception('Falha ao enviar e-mail')
            return False

        # O Apps Script responde 200 mesmo quando recusa o envio
        if not isinstance(dados, dict) or dados.get('status') != 'sucesso':
            logger.error('Apps Script recusou o e-mail: %s', resposta.text[:200])
            return False
        return True
