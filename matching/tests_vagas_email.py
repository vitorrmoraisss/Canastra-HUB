"""Testes do e-mail semanal de vagas compatíveis (matching/recomendacoes_email.py)."""
from datetime import date, datetime, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import Cidade, Estado, Usuario, UsuarioBase
from empresa.models import Empresa
from matching import recomendacoes_email as rec
from matching.models import EnvioVagasEmail, MatchScore, PreferenciaEmailVagas
from vagas.models import UsuarioVaga, Vagas

TZ = ZoneInfo('America/Sao_Paulo')


def _sem_signals_de_matching():
    """Desliga o recálculo de scores dos signals: os testes criam MatchScore à mão."""
    return [
        patch('matching.signals.get_matcher', return_value=MagicMock()),
        patch('matching.signals._agendar_scores_for_usuario'),
        patch('matching.signals._upsert_hub_scores_for_usuario'),
        patch('matching.signals._upsert_scores_for_vaga'),
    ]


@override_settings(
    SITE_URL='https://canastra.example',
    VAGAS_EMAIL_SCORE_MINIMO=0.5,
    VAGAS_EMAIL_LIMITE=3,
    VAGAS_EMAIL_TENTATIVAS=2,
)
class BaseVagasEmailTest(TestCase):
    def setUp(self):
        for p in _sem_signals_de_matching():
            p.start()
            self.addCleanup(p.stop)
        sleep = patch('matching.recomendacoes_email.time.sleep')
        sleep.start()
        self.addCleanup(sleep.stop)

        estado = Estado.objects.create(nome_estado='Minas Gerais', sigla_estado='MG')
        cidade = Cidade.objects.create(nome_cidade='Piumhi', estado_cidade=estado)
        user_empresa = UsuarioBase.objects.create_user(
            email='empresa@example.com', nome='Empresa', tipo='empresa', password='x')
        self.empresa = Empresa.objects.create(
            user=user_empresa, nomefantasia='Queijaria Canastra', cidade=cidade, estado=estado)
        self.usuario = self._candidato('ana@example.com', 'Ana')

    def _candidato(self, email, nome, ativo=True):
        base = UsuarioBase.objects.create_user(email=email, nome=nome, tipo='usuario', password='x')
        base.is_active = ativo
        base.save()
        return Usuario.objects.create(user=base, data_nascimento=date(2000, 1, 1))

    def _vaga(self, cargo, status='ativa', empresa=None):
        return Vagas.objects.create(
            cargo_vaga=cargo, descricao_vaga=f'Descrição de {cargo}', local='Piumhi',
            status=status, empresa=empresa or self.empresa)

    def _score(self, vaga, score, usuario=None):
        return MatchScore.objects.create(usuario=usuario or self.usuario, vaga=vaga, score=score)


class VagasRecomendadasTest(BaseVagasEmailTest):
    def test_ordena_por_score_e_aplica_minimo_e_limite(self):
        v1, v2, v3, v4, v5 = (self._vaga(f'Vaga {i}') for i in range(1, 6))
        self._score(v1, 0.6)
        self._score(v2, 0.9)
        self._score(v3, 0.7)
        self._score(v4, 0.55)
        self._score(v5, 0.4)  # abaixo do mínimo

        ids = [m.vaga_id for m in rec.vagas_recomendadas(self.usuario)]

        self.assertEqual(ids, [v2.pk, v3.pk, v1.pk])

    def test_ignora_vagas_fechadas_e_de_empresa_inativa(self):
        aberta = self._vaga('Aberta')
        fechada = self._vaga('Fechada', status='inativa')
        self._score(aberta, 0.8)
        self._score(fechada, 0.95)
        self.empresa.user.is_active = False
        self.empresa.user.save()

        self.assertEqual(rec.vagas_recomendadas(self.usuario), [])

        self.empresa.user.is_active = True
        self.empresa.user.save()
        self.assertEqual([m.vaga_id for m in rec.vagas_recomendadas(self.usuario)], [aberta.pk])

    def test_ignora_vagas_ja_candidatadas_e_ja_recomendadas(self):
        candidatada, recomendada, nova = self._vaga('A'), self._vaga('B'), self._vaga('C')
        for v in (candidatada, recomendada, nova):
            self._score(v, 0.8)
        UsuarioVaga.objects.create(vaga=candidatada, usuario=self.usuario)
        envio = EnvioVagasEmail.objects.create(
            usuario=self.usuario, semana=date(2026, 1, 5), email='ana@example.com',
            status=EnvioVagasEmail.STATUS_ENVIADO)
        envio.vagas.set([recomendada])

        self.assertEqual([m.vaga_id for m in rec.vagas_recomendadas(self.usuario)], [nova.pk])

    def test_vaga_de_envio_que_falhou_pode_ser_recomendada_de_novo(self):
        vaga = self._vaga('A')
        self._score(vaga, 0.8)
        envio = EnvioVagasEmail.objects.create(
            usuario=self.usuario, semana=date(2026, 1, 5), email='ana@example.com',
            status=EnvioVagasEmail.STATUS_FALHA)
        envio.vagas.set([vaga])

        self.assertEqual([m.vaga_id for m in rec.vagas_recomendadas(self.usuario)], [vaga.pk])


class UsuariosElegiveisTest(BaseVagasEmailTest):
    def test_exclui_inativos_e_descadastrados(self):
        self._candidato('inativo@example.com', 'Inativo', ativo=False)
        descadastrado = self._candidato('fora@example.com', 'Fora')
        PreferenciaEmailVagas.objects.create(usuario=descadastrado, receber_vagas=False)
        reativado = self._candidato('volta@example.com', 'Volta')
        PreferenciaEmailVagas.objects.create(usuario=reativado, receber_vagas=True)

        self.assertEqual(set(rec.usuarios_elegiveis()), {self.usuario, reativado})


class DisparoSemanalTest(BaseVagasEmailTest):
    MOMENTO = datetime(2026, 11, 9, 9, 0, tzinfo=TZ)  # segunda-feira

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_envia_um_email_com_vagas_e_links(self, enviar):
        vaga = self._vaga('Queijeiro')
        self._score(vaga, 0.82)

        resultado = rec.enviar_recomendacoes_semanais(self.MOMENTO)

        self.assertEqual((resultado.enviados, resultado.falhas), (1, 0))
        enviar.assert_called_once()
        destino, assunto, corpo = enviar.call_args.args
        self.assertEqual(destino, 'ana@example.com')
        self.assertIn('Queijeiro', corpo)
        self.assertIn('Queijaria Canastra', corpo)
        self.assertIn('82%', corpo)
        self.assertIn('https://canastra.example' + reverse('vagas:detalhe_vaga', args=[vaga.pk]), corpo)
        self.assertIn('https://canastra.example/matching/vagas-email/', corpo)
        self.assertEqual(assunto, '[Canastra HUB] Vagas compatíveis com o seu perfil')
        self.assertIn('Ver todas as vagas', corpo)
        texto = enviar.call_args.kwargs['texto']
        self.assertIn('Queijeiro', texto)
        self.assertIn('https://canastra.example/matching/vagas-email/', texto)

        envio = EnvioVagasEmail.objects.get(usuario=self.usuario)
        self.assertEqual(envio.status, EnvioVagasEmail.STATUS_ENVIADO)
        self.assertEqual(envio.semana, date(2026, 11, 9))
        self.assertEqual(list(envio.vagas.all()), [vaga])
        self.assertIsNotNone(envio.enviado_em)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_nao_envia_sem_vagas_compativeis(self, enviar):
        self._score(self._vaga('Fraca'), 0.2)

        resultado = rec.enviar_recomendacoes_semanais(self.MOMENTO)

        self.assertEqual(resultado.sem_vagas, 1)
        enviar.assert_not_called()
        self.assertFalse(EnvioVagasEmail.objects.exists())

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_reexecucao_na_mesma_semana_nao_duplica(self, enviar):
        self._score(self._vaga('A'), 0.8)

        rec.enviar_recomendacoes_semanais(self.MOMENTO)
        self._score(self._vaga('B'), 0.9)  # vaga nova no meio da semana
        resultado = rec.enviar_recomendacoes_semanais(self.MOMENTO + timedelta(days=2))

        self.assertEqual(resultado.ja_enviados, 1)
        self.assertEqual(enviar.call_count, 1)
        self.assertEqual(EnvioVagasEmail.objects.count(), 1)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_semana_seguinte_envia_so_vagas_novas(self, enviar):
        antiga = self._vaga('Antiga')
        self._score(antiga, 0.9)
        rec.enviar_recomendacoes_semanais(self.MOMENTO)

        nova = self._vaga('Nova')
        self._score(nova, 0.7)
        rec.enviar_recomendacoes_semanais(self.MOMENTO + timedelta(days=7))

        self.assertEqual(enviar.call_count, 2)
        corpo = enviar.call_args.args[2]
        self.assertIn('Nova', corpo)
        self.assertNotIn('Antiga', corpo)

    @patch('core.emails.ServicoEmail.enviar', return_value=False)
    def test_falha_e_registrada_e_tentada_de_novo_na_mesma_semana(self, enviar):
        self._score(self._vaga('A'), 0.8)

        with self.assertLogs('matching.recomendacoes_email', level='ERROR'):
            resultado = rec.enviar_recomendacoes_semanais(self.MOMENTO)

        self.assertEqual(resultado.falhas, 1)
        self.assertEqual(resultado.falhas_usuarios, [self.usuario.pk])
        self.assertEqual(enviar.call_count, 2)  # VAGAS_EMAIL_TENTATIVAS
        envio = EnvioVagasEmail.objects.get(usuario=self.usuario)
        self.assertEqual(envio.status, EnvioVagasEmail.STATUS_FALHA)
        self.assertEqual(envio.tentativas, 2)
        self.assertTrue(envio.erro)

        enviar.return_value = True
        resultado = rec.enviar_recomendacoes_semanais(self.MOMENTO + timedelta(hours=3))

        self.assertEqual(resultado.enviados, 1)
        envio.refresh_from_db()
        self.assertEqual(envio.status, EnvioVagasEmail.STATUS_ENVIADO)
        self.assertEqual(envio.tentativas, 3)

    @patch('core.emails.ServicoEmail.enviar')
    def test_falha_de_um_destinatario_nao_interrompe_os_demais(self, enviar):
        bia = self._candidato('bia@example.com', 'Bia')
        vaga = self._vaga('A')
        self._score(vaga, 0.8)
        self._score(vaga, 0.8, usuario=bia)
        enviar.side_effect = lambda para, *a, **k: para == 'bia@example.com'

        with self.assertLogs('matching.recomendacoes_email', level='ERROR'):
            resultado = rec.enviar_recomendacoes_semanais(self.MOMENTO)

        self.assertEqual((resultado.enviados, resultado.falhas), (1, 1))

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_comando_de_gerenciamento(self, enviar):
        self._score(self._vaga('A'), 0.8)
        call_command('enviar_vagas_semanais', stdout=MagicMock())
        enviar.assert_called_once()


class ComandoEnviarVagasTest(BaseVagasEmailTest):
    def setUp(self):
        super().setUp()
        self.bia = self._candidato('bia@example.com', 'Bia')
        vaga = self._vaga('Queijeiro')
        self._score(vaga, 0.8)
        self._score(vaga, 0.8, usuario=self.bia)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_simular_nao_envia_nem_grava(self, enviar):
        saida = StringIO()
        call_command('enviar_vagas_semanais', '--simular', stdout=saida)

        enviar.assert_not_called()
        self.assertFalse(EnvioVagasEmail.objects.exists())
        self.assertIn('ana@example.com', saida.getvalue())
        self.assertIn('[80%] Queijeiro', saida.getvalue())
        self.assertIn('2 receberia(m)', saida.getvalue())

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_usuario_restringe_envio_por_email_ou_id(self, enviar):
        call_command('enviar_vagas_semanais', '--usuario', 'BIA@example.com', stdout=StringIO())
        self.assertEqual([c.args[0] for c in enviar.call_args_list], ['bia@example.com'])

        call_command('enviar_vagas_semanais', '--usuario', str(self.usuario.pk), stdout=StringIO())
        self.assertEqual(enviar.call_count, 2)
        self.assertEqual(enviar.call_args.args[0], 'ana@example.com')

    def test_usuario_inexistente_gera_erro(self):
        with self.assertRaises(CommandError):
            call_command('enviar_vagas_semanais', '--usuario', 'ninguem@example.com', stdout=StringIO())

    @patch('core.emails.ServicoEmail.enviar', return_value=False)
    def test_falha_gera_erro_no_comando(self, _enviar):
        with self.assertLogs('matching.recomendacoes_email', level='ERROR'), \
                self.assertRaises(CommandError):
            call_command('enviar_vagas_semanais', stdout=StringIO())


class AgendaTest(TestCase):
    @override_settings(VAGAS_EMAIL_DIA_SEMANA=0, VAGAS_EMAIL_HORA=9, VAGAS_EMAIL_MINUTO=30)
    def test_proximo_disparo(self):
        domingo = datetime(2026, 11, 8, 20, 0, tzinfo=TZ)
        segunda_cedo = datetime(2026, 11, 9, 9, 15, tzinfo=TZ)
        segunda_tarde = datetime(2026, 11, 9, 9, 30, tzinfo=TZ)

        self.assertEqual(rec.proximo_disparo(domingo), datetime(2026, 11, 9, 9, 30, tzinfo=TZ))
        self.assertEqual(rec.proximo_disparo(segunda_cedo), datetime(2026, 11, 9, 9, 30, tzinfo=TZ))
        self.assertEqual(rec.proximo_disparo(segunda_tarde), datetime(2026, 11, 16, 9, 30, tzinfo=TZ))

    @override_settings(VAGAS_EMAIL_DIA_SEMANA=2, VAGAS_EMAIL_HORA=9, VAGAS_EMAIL_MINUTO=0)
    def test_disparo_da_semana_pendente(self):
        self.assertFalse(rec.disparo_da_semana_pendente(datetime(2026, 11, 10, 12, 0, tzinfo=TZ)))  # terça
        self.assertTrue(rec.disparo_da_semana_pendente(datetime(2026, 11, 11, 10, 0, tzinfo=TZ)))  # quarta
        self.assertTrue(rec.disparo_da_semana_pendente(datetime(2026, 11, 15, 10, 0, tzinfo=TZ)))  # domingo

    def test_semana_de_referencia_usa_fuso_local(self):
        # 02:00 UTC de segunda = 23:00 de domingo em São Paulo: ainda é a semana anterior
        momento = datetime(2026, 11, 9, 2, 0, tzinfo=ZoneInfo('UTC'))
        self.assertEqual(rec.semana_de_referencia(momento), date(2026, 11, 2))


class DescadastroViewTest(BaseVagasEmailTest):
    def _url(self, token=None):
        token = token or rec.gerar_token_descadastro(self.usuario.pk)
        return reverse('matching:descadastrar_vagas_email', args=[token])

    def test_get_nao_altera_preferencia(self):
        resposta = self.client.get(self._url())
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(PreferenciaEmailVagas.objects.get(usuario=self.usuario).receber_vagas)

    def test_post_descadastra_e_reativa(self):
        self.client.post(self._url(), {'receber': '0'})
        self.assertFalse(PreferenciaEmailVagas.objects.get(usuario=self.usuario).receber_vagas)
        self.assertNotIn(self.usuario, rec.usuarios_elegiveis())

        self.client.post(self._url(), {'receber': '1'})
        self.assertTrue(PreferenciaEmailVagas.objects.get(usuario=self.usuario).receber_vagas)

    def test_token_invalido(self):
        resposta = self.client.post(self._url('token-falso'), {'receber': '0'})
        self.assertEqual(resposta.status_code, 404)
        self.assertFalse(PreferenciaEmailVagas.objects.exists())
