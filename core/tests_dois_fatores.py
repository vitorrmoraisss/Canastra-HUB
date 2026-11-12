import time
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


from core import dois_fatores
from core.models import UsuarioBase, CodigoVerificacao, DispositivoConfiavel

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


class GeracaoEnvioCodigoTest(TestCase):
    def setUp(self):
        self.usuario = criar_usuario()

    def test_codigo_tem_seis_digitos_com_zeros_a_esquerda(self):
        with patch('core.dois_fatores.secrets.randbelow', return_value=42):
            self.assertEqual(dois_fatores._gerar_codigo(), '000042')

    @patch('core.dois_fatores._gerar_codigo', return_value='123456')
    @patch('core.dois_fatores.ServicoEmail.enviar', return_value=True)
    def test_gera_salva_hash_e_envia_email(self, enviar, _gerar):
        self.assertTrue(dois_fatores.gerar_e_enviar_codigo(self.usuario))

        registro = CodigoVerificacao.objects.get(usuario=self.usuario)
        self.assertNotEqual(registro.codigo_hash, '123456')
        self.assertIsNone(registro.usado_em)
        para, _assunto, mensagem = enviar.call_args.args
        self.assertEqual(para, 'empresa@example.com')
        self.assertIn('123456', mensagem)

    @patch('core.dois_fatores.ServicoEmail.enviar', return_value=False)
    def test_falha_no_envio_retorna_false_e_descarta_codigo(self, _enviar):
        self.assertFalse(dois_fatores.gerar_e_enviar_codigo(self.usuario))
        self.assertFalse(CodigoVerificacao.objects.filter(usuario=self.usuario).exists())

    @patch('core.dois_fatores.ServicoEmail.enviar', return_value=True)
    def test_novo_codigo_invalida_anterior(self, _enviar):
        with patch('core.dois_fatores._gerar_codigo', return_value='111111'):
            dois_fatores.gerar_e_enviar_codigo(self.usuario)
        with patch('core.dois_fatores._gerar_codigo', return_value='222222'):
            dois_fatores.gerar_e_enviar_codigo(self.usuario)

        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '111111'), 'invalido')
        self.assertEqual(dois_fatores.validar_codigo(self.usuario, '222222'), 'ok')

    @patch('core.dois_fatores.ServicoEmail.enviar', return_value=True)
    def test_apaga_codigos_com_mais_de_uma_hora(self, _enviar):
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
    
    def test_cookie_de_atividade_e_criado_para_usuario_autenticado(self):
        user = UsuarioBase.objects.create_user(
        email="hc290_cookie@example.com",
        nome="Teste Cookie",
        tipo="usuario",
        password="SenhaSegura123!"
    )

        self.client.force_login(user)
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertIn('canastra_last_auth_activity', response.cookies)
        self.assertTrue(
            response.cookies['canastra_last_auth_activity']['httponly']
        )

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
    """Login com e-mail mockado e código fixo 123456."""

    def setUp(self):
        self.usuario = criar_usuario()
        patcher_enviar = patch('core.dois_fatores.ServicoEmail.enviar', return_value=True)
        self.enviar = patcher_enviar.start()
        self.addCleanup(patcher_enviar.stop)
        patcher_codigo = patch('core.dois_fatores._gerar_codigo', return_value='123456')
        patcher_codigo.start()
        self.addCleanup(patcher_codigo.stop)

    def entrar(self, email='empresa@example.com', senha=SENHA, **extra):
        return self.client.post(reverse('core:login'), {'txtEmail': email, 'txtSenha': senha, **extra})

    def verificar(self, codigo='123456', **extra):
        return self.client.post(reverse('core:verificar_codigo'), {'txtCodigo': codigo, **extra})

    def autenticado(self):
        return '_auth_user_id' in self.client.session


class LoginDuasEtapasTest(LoginDuasEtapasTestMixin, TestCase):
    def test_senha_valida_pede_codigo_sem_autenticar(self):
        response = self.entrar()

        self.assertRedirects(response, reverse('core:verificar_codigo'), fetch_redirect_response=False)
        self.assertFalse(self.autenticado())
        self.assertEqual(self.client.session['2fa_usuario_id'], self.usuario.id)
        self.assertEqual(self.enviar.call_count, 1)

    def test_senha_invalida_nao_envia_codigo(self):
        response = self.entrar(senha='errada')

        self.assertContains(response, 'Usuário ou senha inválidos.')
        self.assertNotIn('2fa_usuario_id', self.client.session)
        self.enviar.assert_not_called()

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
        self.enviar.return_value = False
        response = self.entrar()

        self.assertRedirects(
            response,
            reverse('core:login'),
            fetch_redirect_response=False
        )
        self.assertFalse(self.autenticado())
        self.assertNotIn('2fa_usuario_id', self.client.session)
        self.assertNotIn('perfil', self.client.session)
        self.assertNotIn('email_atual', self.client.session)
        self.assertNotIn('id_atual', self.client.session)
        self.assertFalse(CodigoVerificacao.objects.exists())

    def test_segundo_login_em_60s_reaproveita_codigo(self):
        self.entrar()
        response = self.entrar()

        self.assertRedirects(response, reverse('core:verificar_codigo'), fetch_redirect_response=False)
        self.assertEqual(self.enviar.call_count, 1)
        self.assertEqual(self.verificar().status_code, 302)
        self.assertTrue(self.autenticado())

    def test_limite_por_hora_sem_codigo_ativo_bloqueia_login(self):
        for minutos in (5, 15, 25, 35, 45):
            criar_codigo(
                self.usuario,
                criado_ha=timedelta(minutes=minutos),
                usado_em=timezone.now()
            )

        response = self.entrar()

        self.assertRedirects(
            response,
            reverse('core:login'),
            fetch_redirect_response=False
        )
        self.assertFalse(self.autenticado())
        self.assertNotIn('2fa_usuario_id', self.client.session)
        self.assertNotIn('perfil', self.client.session)
        self.assertNotIn('email_atual', self.client.session)
        self.assertNotIn('id_atual', self.client.session)
        self.enviar.assert_not_called()


class ReenvioCodigoTest(LoginDuasEtapasTestMixin, TestCase):
    def test_reenvio_antes_de_60s_e_bloqueado(self):
        self.entrar()
        response = self.client.post(reverse('core:reenviar_codigo'), follow=True)

        self.assertContains(response, 'Aguarde alguns segundos para pedir outro código.')
        self.assertEqual(self.enviar.call_count, 1)

    def test_reenvio_depois_de_60s_envia_novo_codigo(self):
        self.entrar()
        CodigoVerificacao.objects.update(criado_em=timezone.now() - timedelta(seconds=61))

        response = self.client.post(reverse('core:reenviar_codigo'))

        self.assertRedirects(response, reverse('core:verificar_codigo'), fetch_redirect_response=False)
        self.assertEqual(self.enviar.call_count, 2)

    def test_reenvio_exige_post(self):
        self.entrar()
        self.assertEqual(self.client.get(reverse('core:reenviar_codigo')).status_code, 405)

    def test_reenvio_sem_pendencia_volta_para_o_login(self):
        response = self.client.post(reverse('core:reenviar_codigo'))
        self.assertRedirects(response, reverse('core:login'), fetch_redirect_response=False)
        self.enviar.assert_not_called()


class LembrarDispositivoTest(LoginDuasEtapasTestMixin, TestCase):
    def test_lembrar_cria_cookie_e_dispositivo(self):
        self.entrar()
        response = self.verificar(lembrar_dispositivo='on')

        self.assertIn(dois_fatores.COOKIE_DISPOSITIVO, response.cookies)
        self.assertEqual(DispositivoConfiavel.objects.filter(usuario=self.usuario).count(), 1)

    def test_sem_lembrar_nao_cria_cookie(self):
        self.entrar()
        response = self.verificar()

        self.assertNotIn(dois_fatores.COOKIE_DISPOSITIVO, response.cookies)
        self.assertFalse(DispositivoConfiavel.objects.exists())

    def test_dispositivo_lembrado_pula_codigo(self):
        self.entrar()
        self.verificar(lembrar_dispositivo='on')
        self.client.post(reverse('core:logout'))

        response = self.entrar(next='/hubs/')

        self.assertRedirects(response, '/hubs/', fetch_redirect_response=False)
        self.assertTrue(self.autenticado())
        self.assertEqual(self.enviar.call_count, 1)

    def test_cookie_de_outro_usuario_nao_pula_codigo(self):
        self.entrar()
        self.verificar(lembrar_dispositivo='on')
        self.client.post(reverse('core:logout'))
        criar_usuario('outra@example.com')

        response = self.entrar(email='outra@example.com')

        self.assertRedirects(response, reverse('core:verificar_codigo'), fetch_redirect_response=False)
        self.assertFalse(self.autenticado())

    def test_redefinir_senha_revoga_dispositivos(self):
        self.entrar()
        self.verificar(lembrar_dispositivo='on')
        self.client.post(reverse('core:logout'))

        # O token de redefinição depende de last_login, que o login acabou de atualizar
        self.usuario.refresh_from_db()
        uidb64 = urlsafe_base64_encode(force_bytes(self.usuario.pk))
        token = default_token_generator.make_token(self.usuario)
        self.client.post(
            reverse('core:redefinir_senha', kwargs={'uidb64': uidb64, 'token': token}),
            {'txtSenha': 'NovaSenha123', 'txtConfirmarSenha': 'NovaSenha123'},
        )

        self.assertFalse(DispositivoConfiavel.objects.filter(usuario=self.usuario).exists())
        # Passa o intervalo de reenvio: o código anterior já foi usado e não pode ser reaproveitado
        CodigoVerificacao.objects.update(criado_em=timezone.now() - timedelta(seconds=61))
        response = self.entrar(senha='NovaSenha123')
        self.assertRedirects(response, reverse('core:verificar_codigo'), fetch_redirect_response=False)


class AdminDuasEtapasTest(LoginDuasEtapasTestMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = criar_usuario('admin@example.com', is_admin=True)

    def test_login_do_admin_redireciona_para_login_com_2fa(self):
        response = self.client.get('/admin/login/?next=/admin/')
        self.assertRedirects(response, '/login/?next=%2Fadmin%2F', fetch_redirect_response=False)

    def test_post_direto_no_login_do_admin_nao_autentica(self):
        response = self.client.post('/admin/login/', {'username': 'admin@example.com', 'password': SENHA})

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.autenticado())

    def test_admin_acessa_painel_depois_do_codigo(self):
        self.entrar(email='admin@example.com', next='/admin/')
        response = self.verificar()

        self.assertRedirects(response, '/admin/', fetch_redirect_response=False)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

