import logging
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from matching.recomendacoes_email import (
    disparo_da_semana_pendente,
    enviar_recomendacoes_semanais,
    proximo_disparo,
)

logger = logging.getLogger(__name__)

# Acorda periodicamente para não depender de um único sleep longo
# (relógio ajustado, suspensão da máquina etc.).
INTERVALO_MAXIMO_ESPERA = 300


class Command(BaseCommand):
    help = (
        'Processo contínuo que dispara o e-mail semanal de vagas compatíveis no dia/hora '
        'configurados (VAGAS_EMAIL_DIA_SEMANA, VAGAS_EMAIL_HORARIO). Ao iniciar, recupera o '
        'disparo da semana se o horário já passou.'
    )

    def handle(self, *args, **options):
        if disparo_da_semana_pendente():
            self._disparar()

        while True:
            alvo = proximo_disparo()
            self.stdout.write(f'Próximo disparo de vagas: {alvo:%d/%m/%Y %H:%M}')
            while (restante := (alvo - timezone.now()).total_seconds()) > 0:
                time.sleep(min(restante, INTERVALO_MAXIMO_ESPERA))
            self._disparar()

    def _disparar(self):
        close_old_connections()
        try:
            resultado = enviar_recomendacoes_semanais()
            self.stdout.write(
                f'Disparo da semana {resultado.semana}: {resultado.enviados} enviado(s), '
                f'{resultado.falhas} falha(s), {resultado.sem_vagas} sem vagas.'
            )
        except Exception:
            logger.exception('Erro no disparo semanal de vagas')
        finally:
            close_old_connections()
