"""Contexto de exemplo para cada tipo de e-mail.

Usado pelos testes (core/tests_emails.py) e pelo comando enviar_emails_exemplo.
Todo tipo em core.emails.TIPOS precisa de uma entrada aqui.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

_TZ = ZoneInfo('America/Sao_Paulo')
_SITE = 'https://canastra.example'

_RESERVA = {
    'solicitante': 'Ana Souza',
    'inicio': datetime(2026, 11, 12, 19, 0, tzinfo=_TZ),
    'fim': datetime(2026, 11, 12, 21, 0, tzinfo=_TZ),
    'empresa_projeto': 'Queijaria Canastra',
    'finalidade': 'Treinamento da equipe de produção',
    'cta_texto': 'Aprovar reserva',
    'cta_link': f'{_SITE}/agendamento/aprovacao/email/token-aprovar/',
    'link_rejeitar': f'{_SITE}/agendamento/aprovacao/email/token-rejeitar/',
    'validade_horas': 48,
}

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
    'contato_resposta': {
        'nome': 'João Souza',
        'mensagem_original': 'Não consegui reservar a sala de reuniões.\nO sistema mostrou erro.',
        'resposta': 'Corrigimos o problema da reserva.\nPode tentar de novo.',
    },
    'aprovacao_reserva_hub': {**_RESERVA, 'sala': 'Espaço de Treinamentos'},
    'aprovacao_reserva_fast': {**_RESERVA, 'sala': 'FAST - Fábrica de Soluções Tecnológicas'},
}
