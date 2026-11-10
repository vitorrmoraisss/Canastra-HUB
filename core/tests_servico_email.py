from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from agendamento.services import GoogleEmailService
from core.models import UsuarioBase
from core.servico_email import ServicoEmail

CONFIG_GAS = {'GAS_EMAIL_URL': 'https://email.teste/exec', 'GAS_API_SECRET': 'chave-teste'}


def resposta_gas(status_http=200, corpo=None):
    resposta = Mock(status_code=status_http, text=str(corpo))
    resposta.json.return_value = {'status': 'sucesso'} if corpo is None else corpo
    if status_http >= 400:
        resposta.raise_for_status.side_effect = requests.HTTPError(f'{status_http}')
    return resposta


@override_settings(**CONFIG_GAS)
class ServicoEmailTest(SimpleTestCase):
    @patch('core.servico_email.requests.post')
    def test_envia_payload_do_apps_script(self, post):
        post.return_value = resposta_gas()

        self.assertTrue(ServicoEmail.enviar('a@example.com', 'Assunto', '<p>Oi</p>'))

        post.assert_called_once_with(
            CONFIG_GAS['GAS_EMAIL_URL'],
            json={
                'secret': CONFIG_GAS['GAS_API_SECRET'],
                'para': 'a@example.com',
                'assunto': 'Assunto',
                'mensagem': '<p>Oi</p>',
                'html': True,
            },
            timeout=10,
        )

    @patch('core.servico_email.requests.post')
    def test_permite_texto_puro(self, post):
        post.return_value = resposta_gas()
        ServicoEmail.enviar('a@example.com', 'Assunto', 'Oi', html=False)
        self.assertFalse(post.call_args.kwargs['json']['html'])

    @patch('core.servico_email.requests.post')
    def test_status_de_erro_do_apps_script_retorna_false(self, post):
        post.return_value = resposta_gas(corpo={'status': 'erro', 'mensagem': 'Não autorizado.'})
        self.assertFalse(ServicoEmail.enviar('a@example.com', 'Assunto', 'Oi'))

    @patch('core.servico_email.requests.post')
    def test_erro_http_retorna_false(self, post):
        post.return_value = resposta_gas(status_http=401)
        self.assertFalse(ServicoEmail.enviar('a@example.com', 'Assunto', 'Oi'))

    @patch('core.servico_email.requests.post', side_effect=requests.ConnectionError)
    def test_falha_de_conexao_retorna_false(self, _post):
        self.assertFalse(ServicoEmail.enviar('a@example.com', 'Assunto', 'Oi'))

    @patch('core.servico_email.requests.post')
    def test_resposta_que_nao_e_json_retorna_false(self, post):
        post.return_value = resposta_gas()
        post.return_value.json.side_effect = ValueError
        self.assertFalse(ServicoEmail.enviar('a@example.com', 'Assunto', 'Oi'))

    @override_settings(GAS_EMAIL_URL='')
    @patch('core.servico_email.requests.post')
    def test_sem_configuracao_nao_chama_apps_script(self, post):
        self.assertFalse(ServicoEmail.enviar('a@example.com', 'Assunto', 'Oi'))
        post.assert_not_called()


class RemetentesUsamServicoEmailTest(TestCase):
    """Todos os envios passam pela classe: trocar de provedor muda só ServicoEmail."""

    @patch('core.servico_email.ServicoEmail.enviar', return_value=True)
    def test_recuperar_senha(self, enviar):
        UsuarioBase.objects.create_user(
            email='empresa@example.com', nome='Empresa', tipo='empresa', password='SenhaForte123'
        )
        self.client.post(reverse('core:recuperar_senha'), {'txtEmail': 'empresa@example.com'})

        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.args[0], 'empresa@example.com')

    @override_settings(EMAIL_HUB_APROVACAO='hub@example.com')
    @patch('core.servico_email.ServicoEmail.enviar', return_value=True)
    def test_contato_envia_texto_puro_ao_hub(self, enviar):
        self.client.post(reverse('core:contato'), {
            'txtNome': 'João Souza',
            'txtEmail': 'joao@example.com',
            'txtTipo': 'duvida',
            'txtMensagem': 'Uma dúvida.',
        })

        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.args[0], 'hub@example.com')
        self.assertFalse(enviar.call_args.kwargs['html'])

    @patch('core.servico_email.ServicoEmail.enviar', return_value=True)
    def test_agendamento_envia_para_cada_destinatario(self, enviar):
        self.assertTrue(GoogleEmailService.enviar_email(['a@example.com', '', 'b@example.com '], 'Assunto', '<p>Oi</p>'))

        self.assertEqual(
            [chamada.args[0] for chamada in enviar.call_args_list],
            ['a@example.com', 'b@example.com'],
        )

    @patch('core.servico_email.ServicoEmail.enviar', return_value=False)
    def test_agendamento_informa_falha(self, _enviar):
        self.assertFalse(GoogleEmailService.enviar_email('a@example.com', 'Assunto', '<p>Oi</p>'))
