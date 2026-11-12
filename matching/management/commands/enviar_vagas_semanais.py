from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from matching.recomendacoes_email import (
    enviar_recomendacoes_semanais,
    semana_de_referencia,
    simular_para_usuario,
    usuarios_elegiveis,
    vagas_recomendadas,
)


class Command(BaseCommand):
    help = (
        'Executa agora o envio do e-mail semanal de vagas compatíveis (matching) aos candidatos '
        'elegíveis. Pode ser repetido na mesma semana: só envia para quem ainda não recebeu '
        'ou teve falha.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--usuario', action='append', metavar='EMAIL_OU_ID',
            help='Envia só para este candidato (e-mail ou id). Pode repetir a opção.',
        )
        parser.add_argument(
            '--simular', action='store_true',
            help='Mostra quem receberia e quais vagas, sem enviar e-mail nem gravar registros.',
        )

    def handle(self, *args, **options):
        usuarios = None
        if options['usuario']:
            usuarios = list(self._filtrar_usuarios(options['usuario']))

        if options['simular']:
            self._listar_simulacao(usuarios)

        resultado = enviar_recomendacoes_semanais(usuarios=usuarios, simular=options['simular'])

        prefixo = '[SIMULAÇÃO] ' if options['simular'] else ''
        verbo = 'receberia(m)' if options['simular'] else 'enviado(s)'
        self.stdout.write(self.style.SUCCESS(
            f'{prefixo}Semana {resultado.semana}: {resultado.enviados} {verbo}, '
            f'{resultado.falhas} falha(s), {resultado.sem_vagas} sem vagas compatíveis, '
            f'{resultado.ja_enviados} já enviado(s) antes.'
        ))
        if resultado.falhas:
            raise CommandError(
                f'Falha no envio para os candidatos {resultado.falhas_usuarios}. '
                'Detalhes em EnvioVagasEmail (admin) e no log da aplicação.'
            )

    def _filtrar_usuarios(self, identificadores):
        filtro = Q()
        for ident in identificadores:
            filtro |= Q(user__email__iexact=ident)
            if ident.isdigit():
                filtro |= Q(pk=int(ident))
        usuarios = usuarios_elegiveis().filter(filtro)
        if not usuarios.exists():
            raise CommandError(
                f'Nenhum candidato elegível encontrado para {identificadores} '
                '(conta inativa, sem e-mail ou descadastrado também ficam de fora).'
            )
        return usuarios

    def _listar_simulacao(self, usuarios):
        semana = semana_de_referencia()
        for usuario in usuarios if usuarios is not None else usuarios_elegiveis():
            if simular_para_usuario(usuario, semana) != 'enviado':
                continue
            matches = vagas_recomendadas(usuario)
            self.stdout.write(f'{usuario.user.email}:')
            for m in matches:
                self.stdout.write(f'  - [{round(m.score * 100)}%] {m.vaga.cargo_vaga} (vaga {m.vaga_id})')
