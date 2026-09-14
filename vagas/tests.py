from django.test import TestCase, Client
from django.urls import reverse

from core.models import Usuario, UsuarioBase, Estado, Cidade
from empresa.models import Empresa
from vagas.models import Vagas, UsuarioVaga


class SinalizacaoContratacaoTests(TestCase):
    def setUp(self):
        self.estado = Estado.objects.create(nome_estado="Minas Gerais", sigla_estado="MG")
        self.cidade = Cidade.objects.create(nome_cidade="Poços de Caldas", estado_cidade=self.estado)

        self.empresa_base = UsuarioBase.objects.create_user(
            email="empresa@teste.com", nome="Empresa Teste", tipo="empresa", password="123456")
        self.empresa = Empresa.objects.create(
            user=self.empresa_base, nomefantasia="Empresa Teste",
            cidade=self.cidade, estado=self.estado)

        self.candidato_base = UsuarioBase.objects.create_user(
            email="candidato@teste.com", nome="Candidato Teste", tipo="candidato", password="123456")
        self.candidato = Usuario.objects.create(
            user=self.candidato_base, data_nascimento="2000-01-01", genero="M",
            estado_civil="solteiro", nacionalidade="brasileira", telefone="123456",
            cep="37700-000", rua="Rua A", bairro="Centro", numero="1",
            cidade=self.cidade, estado=self.estado, ifmg=True)

        self.vaga = Vagas.objects.create(cargo_vaga="Dev", empresa=self.empresa)
        self.candidatura = UsuarioVaga.objects.create(vaga=self.vaga, usuario=self.candidato)

        self.client = Client()

    def _login_empresa(self):
        session = self.client.session
        session['email_atual'] = self.empresa_base.email
        session.save()
        self.client.force_login(self.empresa_base)

    def test_candidatura_status_default(self):
        self.assertEqual(self.candidatura.status, UsuarioVaga.STATUS_CANDIDATADO)

    def test_empresa_marca_como_contratado_registra_flag_ifmg_e_data(self):
        self._login_empresa()
        url = reverse('vagas:atualizar_status_candidatura', args=[self.candidatura.id])
        response = self.client.post(url, {'status': 'contratado'})

        self.candidatura.refresh_from_db()
        self.assertRedirects(
            response, reverse('vagas:listar_candidatos', args=[self.vaga.id]))
        self.assertEqual(self.candidatura.status, UsuarioVaga.STATUS_CONTRATADO)
        self.assertTrue(self.candidatura.ifmg_no_momento_contratacao)
        self.assertIsNotNone(self.candidatura.data_status)

    def test_empresa_marca_como_rejeitado(self):
        self._login_empresa()
        url = reverse('vagas:atualizar_status_candidatura', args=[self.candidatura.id])
        self.client.post(url, {'status': 'rejeitado'})

        self.candidatura.refresh_from_db()
        self.assertEqual(self.candidatura.status, UsuarioVaga.STATUS_REJEITADO)
        self.assertFalse(self.candidatura.ifmg_no_momento_contratacao)

    def test_empresa_de_outra_vaga_nao_pode_alterar_status(self):
        outra_empresa_base = UsuarioBase.objects.create_user(
            email="outra@teste.com", nome="Outra Empresa", tipo="empresa", password="123456")
        Empresa.objects.create(
            user=outra_empresa_base, nomefantasia="Outra Empresa",
            cidade=self.cidade, estado=self.estado)

        session = self.client.session
        session['email_atual'] = outra_empresa_base.email
        session.save()
        self.client.force_login(outra_empresa_base)

        url = reverse('vagas:atualizar_status_candidatura', args=[self.candidatura.id])
        response = self.client.post(url, {'status': 'contratado'})

        self.assertEqual(response.status_code, 404)
        self.candidatura.refresh_from_db()
        self.assertEqual(self.candidatura.status, UsuarioVaga.STATUS_CANDIDATADO)

    def test_listar_candidatos_mostra_flag_ifmg(self):
        self._login_empresa()
        url = reverse('vagas:listar_candidatos', args=[self.vaga.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sim")
