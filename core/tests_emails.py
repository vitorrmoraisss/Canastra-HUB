"""Testes do serviço central de e-mails (core/emails.py) e de todos os tipos."""
import re
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core import emails
from core.emails_exemplos import EXEMPLOS

CONFIG = {'SITE_URL': 'https://canastra.example', 'EMAIL_LOGO_URL': 'https://cdn.example/logo.jpg'}


@override_settings(**CONFIG)
class TodosOsTiposTest(SimpleTestCase):
    def test_todo_tipo_tem_exemplo(self):
        self.assertEqual(set(EXEMPLOS), set(emails.TIPOS))

    def test_padrao_de_cada_tipo(self):
        for tipo in emails.TIPOS:
            with self.subTest(tipo=tipo):
                contexto = EXEMPLOS[tipo]
                email = emails.renderizar_email(tipo, contexto)

                self.assertTrue(email.assunto.startswith('[Canastra HUB] '))
                self.assertLessEqual(len(email.assunto), emails.LIMITE_ASSUNTO_ESTILO)
                self.assertIn('https://cdn.example/logo.jpg', email.html)
                self.assertIn('https://canastra.example/contato/', email.html)
                self.assertIn('https://canastra.example/contato/', email.texto)
                for corpo in (email.html, email.texto):
                    self.assertIn('Olá', corpo)
                    self.assertIn('Equipe Canastra HUB', corpo)
                    self.assertIn('Não responda a este e-mail', corpo)
                    self.assertLessEqual(len(corpo), emails.LIMITE_CORPO)
                self.assertIsNone(re.search(r'<[a-zA-Z/!]', email.texto), 'texto puro com tag HTML')
                if contexto.get('cta_link'):
                    self.assertIn(f'href="{contexto["cta_link"]}"', email.html)
                    self.assertIn(contexto['cta_link'], email.texto)


@override_settings(**CONFIG)
class RenderizarEmailTest(SimpleTestCase):
    def test_tipo_desconhecido_gera_erro(self):
        with self.assertRaises(ValueError):
            emails.renderizar_email('inexistente', {})

    def test_saudacao_sem_nome(self):
        for nome in ('', None):
            with self.subTest(nome=nome):
                email = emails.renderizar_email('codigo_verificacao', {**EXEMPLOS['codigo_verificacao'], 'nome': nome})
                self.assertIn('Olá,', email.texto)
                self.assertNotIn('Olá, ,', email.texto)
                self.assertNotIn('None', email.texto)

    def test_texto_puro_nao_escapa_e_html_escapa(self):
        email = emails.renderizar_email('codigo_verificacao', {**EXEMPLOS['codigo_verificacao'], 'nome': 'Ana & Bia'})
        self.assertIn('Olá, Ana & Bia,', email.texto)
        self.assertIn('Ana &amp; Bia', email.html)

    def test_assunto_com_campo_e_sem_quebra_de_linha(self):
        tipo = emails.TipoEmail('Aviso {x}', 'email/codigo_verificacao')
        with patch.dict(emails.TIPOS, {'teste': tipo}):
            email = emails.renderizar_email('teste', {**EXEMPLOS['codigo_verificacao'], 'x': 'linha 1\nlinha 2'})
        self.assertEqual(email.assunto, '[Canastra HUB] Aviso linha 1 linha 2')

    def test_texto_sem_linhas_em_branco_repetidas(self):
        email = emails.renderizar_email('codigo_verificacao', EXEMPLOS['codigo_verificacao'])
        self.assertNotIn('\n\n\n', email.texto)


@override_settings(**CONFIG)
class EnviarEmailTest(SimpleTestCase):
    contexto = EXEMPLOS['codigo_verificacao']

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_envia_html_e_texto(self, enviar):
        self.assertTrue(emails.enviar_email('a@example.com', 'codigo_verificacao', self.contexto))

        enviar.assert_called_once()
        para, assunto, html = enviar.call_args.args
        self.assertEqual(para, 'a@example.com')
        self.assertEqual(assunto, '[Canastra HUB] Código de verificação')
        self.assertIn(self.contexto['codigo'], html)
        self.assertTrue(enviar.call_args.kwargs['html'])
        self.assertIn(self.contexto['codigo'], enviar.call_args.kwargs['texto'])

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_lista_envia_um_por_destinatario_e_ignora_vazios(self, enviar):
        self.assertTrue(emails.enviar_email(['a@example.com', '', ' b@example.com ', None], 'codigo_verificacao', self.contexto))
        self.assertEqual([c.args[0] for c in enviar.call_args_list], ['a@example.com', 'b@example.com'])

    @patch('core.emails.ServicoEmail.enviar')
    def test_falha_de_um_destinatario_nao_interrompe_os_demais(self, enviar):
        enviar.side_effect = lambda para, *a, **k: para != 'a@example.com'
        self.assertFalse(emails.enviar_email(['a@example.com', 'b@example.com'], 'codigo_verificacao', self.contexto))
        self.assertEqual(enviar.call_count, 2)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_sem_destinatario_nao_envia(self, enviar):
        with self.assertLogs('core.emails', level='ERROR'):
            self.assertFalse(emails.enviar_email(['', None], 'codigo_verificacao', self.contexto))
        enviar.assert_not_called()

    @patch('core.emails.LIMITE_CORPO', 10)
    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_corpo_acima_do_limite_nao_envia(self, enviar):
        with self.assertLogs('core.emails', level='ERROR'):
            self.assertFalse(emails.enviar_email('a@example.com', 'codigo_verificacao', self.contexto))
        enviar.assert_not_called()

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_assunto_acima_do_limite_tecnico_nao_envia(self, enviar):
        with patch.dict(emails.TIPOS, {'teste': emails.TipoEmail('x' * 190, 'email/codigo_verificacao')}):
            with self.assertLogs('core.emails', level='ERROR'):
                self.assertFalse(emails.enviar_email('a@example.com', 'teste', self.contexto))
        enviar.assert_not_called()

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_assunto_longo_avisa_mas_envia(self, enviar):
        with patch.dict(emails.TIPOS, {'teste': emails.TipoEmail('x' * 50, 'email/codigo_verificacao')}):
            with self.assertLogs('core.emails', level='WARNING'):
                self.assertTrue(emails.enviar_email('a@example.com', 'teste', self.contexto))
        enviar.assert_called_once()
