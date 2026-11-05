import time
from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core import dois_fatores
from core.models import UsuarioBase, CodigoVerificacao, DispositivoConfiavel

CONFIG_EMAIL = {
    'RECUPERACAO_URL': 'https://email.teste/enviar',
    'RECUPERACAO_API_KEY': 'chave-teste',
}
SENHA = 'SenhaForte123'


def criar_usuario(email='empresa@example.com', **extra):
    usuario = UsuarioBase.objects.create_user(
        email=email, nome='Empresa Teste', tipo='empresa', password=SENHA
    )
    for campo, valor in extra.items():
        setattr(usuario, campo, valor)
    usuario.save()
    return usuario


def criar_codigo(usuario, codigo='123456', criado_ha=None, **campos):
    """Cria um código ativo direto no banco. criado_ha: timedelta para recuar criado_em."""
    registro = CodigoVerificacao.objects.create(
        usuario=usuario,
        codigo_hash=make_password(codigo),
        expira_em=timezone.now() + dois_fatores.VALIDADE_CODIGO,
        **campos,
    )
    if criado_ha is not None:
        CodigoVerificacao.objects.filter(pk=registro.pk).update(criado_em=timezone.now() - criado_ha)
        registro.refresh_from_db()
    return registro


@override_settings(**CONFIG_EMAIL)
class GeracaoEnvioCodigoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()

    def test_codigo_tem_seis_digitos_com_zeros_a_esquerda(self):
        with patch('core.dois_fatores.secrets.randbelow', return_value=42):
            self.assertEqual(dois_fatores._gerar_codigo(), '000042')

    @patch('core.dois_fatores._gerar_codigo', return_value='123456')
    @patch('core.dois_fatores.requests.post')
    def test_gera_salva_hash_e_envia_email(self, post, _gerar):
        self.assertTrue(dois_fatores.gerar_e_enviar_codigo(self.usuario))

        registro = CodigoVerificacao.objects.get(usuario=self.usuario)
        self.assertNotEqual(registro.codigo_hash, '123456')
        self.assertIsNone(registro.usado_em)
        payload = post.call_args.kwargs['json']
        self.assertEqual(post.call_args.args[0], CONFIG_EMAIL['RECUPERACAO_URL'])
        self.assertEqual(payload['secret'], CONFIG_EMAIL['RECUPERACAO_API_KEY'])
        self.assertEqual(payload['para'], 'empresa@example.com')
        self.assertTrue(payload['html'])
        self.assertIn('123456', payload['mensagem'])
        self.assertEqual(post.call_args.kwargs['timeout'], 10)

    @patch('core.dois_fatores.requests.post', side_effect=requests.ConnectionError)
    def test_falha_no_envio_retorna_false_e_descarta_codigo(self, _post):
        self.assertFalse(dois_fatores.gerar_e_enviar_codigo(self.usuario))
        self.assertFalse(CodigoVerificacao.objects.filter(usuario=self.usuario).exists())

    @patch('core.dois_fatores.requests.post')
    def test_novo_codigo_invalida_anterior(self, _post):
        with patch('core.dois_fatores._gerar_codigo', return_value='111111'):
            dois_fatores.gerar_e_enviar_codigo(self.usuario)
        with patch('core.dois_fatores._gerar_codigo', return_value='222222'):
            dois_fatores.gerar_e_enviar_codigo(self.usuario)

        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '111111'), 'invalido')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '222222'), 'ok')

    @patch('core.dois_fatores.requests.post')
    def test_apaga_codigos_com_mais_de_uma_hora(self, _post):
        antigo = criar_codigo(self.usuario, criado_ha=timedelta(hours=2))
        recente = criar_codigo(self.usuario, criado_ha=timedelta(minutes=30))

        dois_fatores.gerar_e_enviar_codigo(self.usuario)

        self.assertFalse(CodigoVerificacao.objects.filter(pk=antigo.pk).exists())
        self.assertTrue(CodigoVerificacao.objects.filter(pk=recente.pk).exists())


class LimiteEnvioTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()

    def test_permite_primeiro_envio(self):
        self.assertEqual(dois_fatores.pode_enviar_codigo(self.usuario), (True, None))

    def test_bloqueia_reenvio_antes_de_60_segundos(self):
        criar_codigo(self.usuario, criado_ha=timedelta(seconds=30))
        permitido, motivo = dois_fatores.pode_enviar_codigo(self.usuario)
        self.assertFalse(permitido)
        self.assertEqual(motivo, 'Aguarde alguns segundos para pedir outro código.')

    def test_permite_reenvio_depois_de_60_segundos(self):
        criar_codigo(self.usuario, criado_ha=timedelta(seconds=61))
        self.assertEqual(dois_fatores.pode_enviar_codigo(self.usuario), (True, None))

    def test_bloqueia_sexto_codigo_na_mesma_hora(self):
        for minutos in (5, 15, 25, 35, 45):
            criar_codigo(self.usuario, criado_ha=timedelta(minutes=minutos))
        permitido, motivo = dois_fatores.pode_enviar_codigo(self.usuario)
        self.assertFalse(permitido)
        self.assertEqual(motivo, 'Limite de códigos atingido. Tente novamente mais tarde.')

    def test_codigos_de_mais_de_uma_hora_nao_contam(self):
        for minutos in (61, 70, 80, 90, 100):
            criar_codigo(self.usuario, criado_ha=timedelta(minutes=minutos))
        self.assertEqual(dois_fatores.pode_enviar_codigo(self.usuario), (True, None))


class ValidacaoCodigoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()

    def test_codigo_correto_retorna_ok_e_marca_usado(self):
        registro = criar_codigo(self.usuario, '123456')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '123456'), 'ok')
        registro.refresh_from_db()
        self.assertIsNotNone(registro.usado_em)

    def test_codigo_nao_pode_ser_reutilizado(self):
        criar_codigo(self.usuario, '123456')
        dois_fatores.validar_codigo(self.usuario, '123456')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '123456'), 'invalido')

    def test_aceita_espacos_nas_pontas(self):
        criar_codigo(self.usuario, '123456')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, ' 123456 '), 'ok')

    def test_codigo_ausente_conta_como_tentativa(self):
        registro = criar_codigo(self.usuario, '123456')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, None), 'invalido')
        registro.refresh_from_db()
        self.assertEqual(registro.tentativas, 1)

    def test_codigo_errado_incrementa_tentativas(self):
        registro = criar_codigo(self.usuario, '123456')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '000000'), 'invalido')
        registro.refresh_from_db()
        self.assertEqual(registro.tentativas, 1)

    def test_quinta_tentativa_errada_bloqueia(self):
        criar_codigo(self.usuario, '123456')
        for _ in range(4):
            self.assertEqual(dois_fatores.validar_codigo(self.usuario, '000000'), 'invalido')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '000000'), 'bloqueado')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '123456'), 'invalido')

    def test_codigo_expirado_e_invalido(self):
        criar_codigo(self.usuario, '123456')
        CodigoVerificacao.objects.update(expira_em=timezone.now() - timedelta(seconds=1))
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '123456'), 'invalido')

    def test_sem_codigo_e_invalido(self):
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '123456'), 'invalido')

    def test_codigo_de_outro_usuario_nao_vale(self):
        outro = criar_usuario('outra@example.com')
        criar_codigo(outro, '123456')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '123456'), 'invalido')

    def test_tem_codigo_ativo(self):
        self.assertFalse(dois_fatores.tem_codigo_ativo(self.usuario))
        criar_codigo(self.usuario)
        self.assertTrue(dois_fatores.tem_codigo_ativo(self.usuario))


class MascararEmailTest(TestCase):
    def test_mascara_parte_local(self):
        self.assertEqual(dois_fatores.mascarar_email('marco@gmail.com'), 'ma***@gmail.com')

    def test_parte_local_curta(self):
        self.assertEqual(dois_fatores.mascarar_email('a@b.com'), 'a***@b.com')


class DispositivoConfiavelTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()
        self.factory = RequestFactory()

    def _criar(self, usuario=None):
        """Cria um dispositivo e devolve o token gravado no cookie."""
        request = self.factory.get('/', HTTP_USER_AGENT='Navegador Teste')
        response = HttpResponse()
        dois_fatores.criar_dispositivo_confiavel(request, response, usuario or self.usuario)
        return response.cookies[dois_fatores.COOKIE_DISPOSITIVO]

    def _request_com_cookie(self, token):
        request = self.factory.get('/')
        request.COOKIES[dois_fatores.COOKIE_DISPOSITIVO] = token
        return request

    def test_cria_cookie_seguro_e_guarda_so_hash(self):
        cookie = self._criar()
        dispositivo = DispositivoConfiavel.objects.get(usuario=self.usuario)

        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['max-age'], 30 * 24 * 60 * 60)
        self.assertNotEqual(dispositivo.token_hash, cookie.value)
        self.assertEqual(len(dispositivo.token_hash), 64)
        self.assertEqual(dispositivo.user_agent, 'Navegador Teste')

    def test_reconhece_dispositivo_do_mesmo_usuario(self):
        cookie = self._criar()
        self.assertTrue(dois_fatores.dispositivo_confiavel(self._request_com_cookie(cookie.value), self.usuario))
        self.assertIsNotNone(DispositivoConfiavel.objects.get(usuario=self.usuario).ultimo_uso)

    def test_rejeita_dispositivo_de_outro_usuario(self):
        outro = criar_usuario('outra@example.com')
        cookie = self._criar(outro)
        self.assertFalse(dois_fatores.dispositivo_confiavel(self._request_com_cookie(cookie.value), self.usuario))

    def test_rejeita_dispositivo_expirado(self):
        cookie = self._criar()
        DispositivoConfiavel.objects.update(expira_em=timezone.now() - timedelta(seconds=1))
        self.assertFalse(dois_fatores.dispositivo_confiavel(self._request_com_cookie(cookie.value), self.usuario))

    def test_rejeita_sem_cookie_ou_token_desconhecido(self):
        self.assertFalse(dois_fatores.dispositivo_confiavel(self.factory.get('/'), self.usuario))
        self.assertFalse(dois_fatores.dispositivo_confiavel(self._request_com_cookie('inventado'), self.usuario))

    def test_revogar_apaga_dispositivos_do_usuario(self):
        self._criar()
        outro = criar_usuario('outra@example.com')
        self._criar(outro)

        dois_fatores.revogar_dispositivos(self.usuario)

        self.assertFalse(DispositivoConfiavel.objects.filter(usuario=self.usuario).exists())
        self.assertTrue(DispositivoConfiavel.objects.filter(usuario=outro).exists())


class LoginDuasEtapasTestMixin:
    """Login com e-mail mockado e código fixo 123456. As classes de teste aplicam @override_settings(**CONFIG_EMAIL):
    override_settings só decora subclasses de SimpleTestCase."""

    def setUp(self):
        self.usuario = criar_usuario()
        patcher_post = patch('core.dois_fatores.requests.post')
        self.post = patcher_post.start()
        self.addCleanup(patcher_post.stop)
        patcher_codigo = patch('core.dois_fatores._gerar_codigo', return_value='123456')
        patcher_codigo.start()
        self.addCleanup(patcher_codigo.stop)

    def entrar(self, email='empresa@example.com', senha=SENHA, **extra):
        return self.client.post(reverse('core:login'), {'txtEmail': email, 'txtSenha': senha, **extra})

    def verificar(self, codigo='123456', **extra):
        return self.client.post(reverse('core:verificar_codigo'), {'txtCodigo': codigo, **extra})

    def autenticado(self):
        return '_auth_user_id' in self.client.session


@override_settings(**CONFIG_EMAIL)
class LoginDuasEtapasTest(LoginDuasEtapasTestMixin, TestCase):
    def test_senha_valida_pede_codigo_sem_autenticar(self):
        response = self.entrar()

        self.assertRedirects(response, reverse('core:verificar_codigo'), fetch_redirect_response=False)
        self.assertFalse(self.autenticado())
        self.assertEqual(self.client.session['2fa_usuario_id'], self.usuario.id)
        self.assertEqual(self.post.call_count, 1)

    def test_senha_invalida_nao_envia_codigo(self):
        response = self.entrar(senha='errada')

        self.assertContains(response, 'Usuário ou senha inválidos.')
        self.assertNotIn('2fa_usuario_id', self.client.session)
        self.post.assert_not_called()

    def test_tela_de_verificacao_mostra_email_mascarado(self):
        self.entrar()
        response = self.client.get(reverse('core:verificar_codigo'))

        self.assertContains(response, 'em***@example.com')
        self.assertContains(response, 'name="txtCodigo"')

    def test_codigo_correto_conclui_login(self):
        self.entrar()
        response = self.verificar()

        self.assertRedirects(response, reverse('core:home'), fetch_redirect_response=False)
        self.assertTrue(self.autenticado())
        self.assertEqual(self.client.session['nome'], 'Empresa Teste')
        self.assertEqual(self.client.session['perfil'], 'empresa')
        self.assertEqual(self.client.session['id_atual'], self.usuario.id)
        self.assertNotIn('2fa_usuario_id', self.client.session)

    def test_codigo_correto_respeita_next(self):
        self.entrar(next='/hubs/')
        response = self.verificar()

        self.assertRedirects(response, '/hubs/', fetch_redirect_response=False)

    def test_codigo_errado_nao_autentica(self):
        self.entrar()
        response = self.verificar('000000')

        self.assertContains(response, 'Código inválido ou expirado.')
        self.assertFalse(self.autenticado())

    def test_cinco_erros_voltam_para_o_login(self):
        self.entrar()
        for _ in range(4):
            self.verificar('000000')
        response = self.verificar('000000')

        self.assertRedirects(response, reverse('core:login'), fetch_redirect_response=False)
        self.assertNotIn('2fa_usuario_id', self.client.session)
        self.assertFalse(self.autenticado())

    def test_verificacao_sem_pendencia_volta_para_o_login(self):
        response = self.client.get(reverse('core:verificar_codigo'))
        self.assertRedirects(response, reverse('core:login'), fetch_redirect_response=False)

    def test_pendencia_expirada_volta_para_o_login(self):
        self.entrar()
        sessao = self.client.session
        sessao['2fa_iniciado_em'] = time.time() - dois_fatores.VALIDADE_PENDENCIA.total_seconds() - 1
        sessao.save()

        response = self.verificar()

        self.assertRedirects(response, reverse('core:login'), fetch_redirect_response=False)
        self.assertFalse(self.autenticado())

    def test_falha_no_envio_nao_cria_pendencia(self):
        self.post.side_effect = requests.ConnectionError
        response = self.entrar()

        self.assertContains(response, 'Não foi possível enviar o código. Tente novamente.')
        self.assertNotIn('2fa_usuario_id', self.client.session)
        self.assertFalse(CodigoVerificacao.objects.exists())

    def test_segundo_login_em_60s_reaproveita_codigo(self):
        self.entrar()
        response = self.entrar()

        self.assertRedirects(response, reverse('core:verificar_codigo'), fetch_redirect_response=False)
        self.assertEqual(self.post.call_count, 1)
        self.assertEqual(self.verificar().status_code, 302)
        self.assertTrue(self.autenticado())

    def test_limite_por_hora_sem_codigo_ativo_bloqueia_login(self):
        for minutos in (5, 15, 25, 35, 45):
            criar_codigo(self.usuario, criado_ha=timedelta(minutes=minutos), usado_em=timezone.now())

        response = self.entrar()

        self.assertContains(response, 'Limite de códigos atingido. Tente novamente mais tarde.')
        self.assertNotIn('2fa_usuario_id', self.client.session)
        self.post.assert_not_called()


@override_settings(**CONFIG_EMAIL)
class ReenvioCodigoTest(LoginDuasEtapasTestMixin, TestCase):
    def test_reenvio_antes_de_60s_e_bloqueado(self):
        self.entrar()
        response = self.client.post(reverse('core:reenviar_codigo'), follow=True)

        self.assertContains(response, 'Aguarde alguns segundos para pedir outro código.')
        self.assertEqual(self.post.call_count, 1)

    def test_reenvio_depois_de_60s_envia_novo_codigo(self):
        self.entrar()
        CodigoVerificacao.objects.update(criado_em=timezone.now() - timedelta(seconds=61))

        response = self.client.post(reverse('core:reenviar_codigo'))

        self.assertRedirects(response, reverse('core:verificar_codigo'), fetch_redirect_response=False)
        self.assertEqual(self.post.call_count, 2)

    def test_reenvio_exige_post(self):
        self.entrar()
        self.assertEqual(self.client.get(reverse('core:reenviar_codigo')).status_code, 405)

    def test_reenvio_sem_pendencia_volta_para_o_login(self):
        response = self.client.post(reverse('core:reenviar_codigo'))
        self.assertRedirects(response, reverse('core:login'), fetch_redirect_response=False)
        self.post.assert_not_called()
