from django.core.management.base import BaseCommand
from agendamento.utils import processar_noshow_banco


class Command(BaseCommand):
    help = 'Atualiza o status de reservas expiradas sem check-in para "nao_compareceu"'

    def handle(self, *args, **options):
        total = processar_noshow_banco()
        if total > 0:
            self.stdout.write(self.style.SUCCESS(
                f'Sucesso: {total} reserva(s) atualizada(s) para "nao_compareceu".'))
        else:
            self.stdout.write(self.style.NOTICE(
                'Nenhuma reserva pendente para atualização.'))
