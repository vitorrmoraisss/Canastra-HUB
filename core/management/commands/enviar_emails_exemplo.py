"""Envia os e-mails do sistema com dados de exemplo, para conferir o visual nos clientes de e-mail."""
from django.core.management.base import BaseCommand, CommandError

from core.emails import TIPOS, enviar_email
from core.emails_exemplos import EXEMPLOS


class Command(BaseCommand):
    help = 'Envia cada tipo de e-mail com dados de exemplo para o endereço informado.'

    def add_arguments(self, parser):
        parser.add_argument('para', help='Endereço que recebe os e-mails de exemplo.')
        parser.add_argument('--tipo', choices=sorted(TIPOS), help='Envia só este tipo.')

    def handle(self, *args, para, tipo=None, **options):
        tipos = [tipo] if tipo else list(TIPOS)
        falhas = []
        for nome in tipos:
            enviado = enviar_email(para, nome, EXEMPLOS[nome])
            self.stdout.write(f"{'OK   ' if enviado else 'FALHA'} {nome}")
            if not enviado:
                falhas.append(nome)
        if falhas:
            raise CommandError(f"Falha ao enviar: {', '.join(falhas)}")
