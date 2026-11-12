"""E-mails de aprovação de reserva (agendamento.utils.notificar_aprovacoes_pendentes)."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from agendamento.models import ConfiguracaoAgendamento, Reserva
from agendamento.utils import notificar_aprovacoes_pendentes
from core.models import UsuarioBase

INICIO_UTC = datetime(2026, 11, 12, 23, 0, tzinfo=dt_timezone.utc)  # 20:00 em São Paulo


@override_settings(SITE_URL='https://canastra.example')
class NotificarAprovacoesTest(TestCase):
    def setUp(self):
        self.usuario = UsuarioBase.objects.create_user(
            email='ana@example.com', nome='Ana <b>Souza</b>', tipo='empresa', password='SenhaForte123'
        )
        self.config = ConfiguracaoAgendamento.get_config()
        self.request = RequestFactory().get('/')

    def _reserva(self, **extra):
        dados = {
            'usuario': self.usuario,
            'sala': 'treinamentos',
            'inicio': INICIO_UTC,
            'fim': INICIO_UTC + timedelta(hours=2),
            'finalidade': '<script>alert(1)</script>',
            'empresa_projeto': 'Projeto X',
            'aprovado_hub': 'N/A',
            'aprovado_professor': 'N/A',
        }
        dados.update(extra)
        return Reserva.objects.create(**dados)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_hub_recebe_email_escapado_com_horario_local(self, enviar):
        reserva = self._reserva(aprovado_hub='Pendente')

        notificar_aprovacoes_pendentes(reserva, self.request, self.config)

        enviar.assert_called_once()
        para, assunto, html = enviar.call_args.args
        texto = enviar.call_args.kwargs['texto']
        self.assertEqual(para, self.config.email_hub)
        self.assertEqual(assunto, '[Canastra HUB] Reserva noturna aguarda aprovação')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('Ana &lt;b&gt;Souza&lt;/b&gt;', html)
        self.assertIn('12/11/2026 20:00', html)
        self.assertIn('12/11/2026 20:00', texto)
        self.assertIn('Aprovar reserva', html)
        self.assertIn('Rejeitar reserva', html)
        self.assertIn('/agendamento/aprovacao/email/', texto)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_fast_envia_para_os_dois_professores(self, enviar):
        reserva = self._reserva(sala='fast', aprovado_professor='Pendente')

        notificar_aprovacoes_pendentes(reserva, self.request, self.config)

        self.assertEqual(
            [c.args[0] for c in enviar.call_args_list],
            [self.config.email_professor_1, self.config.email_professor_2],
        )
        self.assertEqual(enviar.call_args.args[1], '[Canastra HUB] Reserva no FAST aguarda aprovação')

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_sem_pendencia_nao_envia(self, enviar):
        notificar_aprovacoes_pendentes(self._reserva(), self.request, self.config)
        enviar.assert_not_called()

    def test_links_de_aprovar_e_rejeitar_sao_diferentes(self):
        reserva = self._reserva(aprovado_hub='Pendente')
        with patch('agendamento.utils.enviar_email', return_value=True) as enviar_email:
            notificar_aprovacoes_pendentes(reserva, self.request, self.config)
        contexto = enviar_email.call_args.args[2]
        self.assertNotEqual(contexto['cta_link'], contexto['link_rejeitar'])
        self.assertTrue(contexto['cta_link'].startswith('http://testserver/agendamento/aprovacao/email/'))
