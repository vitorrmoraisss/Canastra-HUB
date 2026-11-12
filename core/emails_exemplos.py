"""Contexto de exemplo para cada tipo de e-mail.

Usado pelos testes (core/tests_emails.py) e pelo comando enviar_emails_exemplo.
Todo tipo em core.emails.TIPOS precisa de uma entrada aqui.
"""
from datetime import datetime  # noqa: F401  (usado pelos exemplos de reserva)
from zoneinfo import ZoneInfo

_TZ = ZoneInfo('America/Sao_Paulo')
_SITE = 'https://canastra.example'

EXEMPLOS = {
    'codigo_verificacao': {
        'nome': 'Ana Souza',
        'codigo': '048213',
        'expiracao_minutos': 10,
    },
    'recuperar_senha': {
        'nome': 'Ana Souza',
        'cta_texto': 'Redefinir minha senha',
        'cta_link': f'{_SITE}/redefinir-senha/MQ/token-exemplo/',
        'expiracao_minutos': 30,
    },
    'contato_recebido': {
        'nome_remetente': 'João Souza',
        'email_remetente': 'joao@example.com',
        'tipo': 'Reclamação',
        'mensagem': 'Não consegui reservar a sala de reuniões.\nO sistema mostrou erro.',
        'cta_texto': 'Ver mensagens de contato',
        'cta_link': f'{_SITE}/administrador/mensagens_contato/',
    },
}
