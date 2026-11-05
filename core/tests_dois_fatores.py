from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth.hashers import make_password
from django.test import TestCase, override_settings
from django.utils import timezone

from core import dois_fatores
from core.models import UsuarioBase, CodigoVerificacao

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
