from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.models import (
    Usuario,
    ExperienciaProfissional,
    Estado,
    Cidade,
    Endereco,
    Hub,
    UsuarioHub,
)

UsuarioBase = get_user_model()


class ToggleHubInteresseTest(TestCase):
    def setUp(self):
        self.estado = Estado.objects.create(
            nome_estado='Minas Gerais',
            sigla_estado='MG'
        )

        self.cidade = Cidade.objects.create(
            nome_cidade='Arcos',
            estado_cidade=self.estado
        )

        self.endereco = Endereco.objects.create(
            cep='123',
            rua='rua',
            numero='1',
            bairro='bairro',
            cidade=self.cidade,
            estado=self.estado,
        )

        self.user = UsuarioBase.objects.create_user(
            email='usuario@teste.com',
            password='123',
            nome='Teste',
            tipo='usuario'
        )

        self.usuario = Usuario.objects.create(
            user=self.user,
            data_nascimento='2000-01-01',
            genero='masculino',
            estado_civil='solteiro',
            nacionalidade='brasileiro',
            telefone='123',
            endereco=self.endereco,
        )

        self.hub = Hub.objects.create(
            nome_hub='Agro',
            descricao_hub='desc',
            isActive=True
        )

        self.hub_inativo = Hub.objects.create(
            nome_hub='Inativo',
            descricao_hub='desc',
            isActive=False
        )

        self.client = Client()
        self.client.force_login(self.user)

        session = self.client.session
        session['perfil'] = 'usuario'
        session.save()

    def test_marcar_interesse(self):
        self.client.post(
            reverse('core:toggle_hub_interesse', args=[self.hub.id])
        )

        self.assertTrue(
            UsuarioHub.objects.filter(
                usuario=self.usuario,
                hub=self.hub
            ).exists()
        )

    def test_desmarcar_interesse(self):
        UsuarioHub.objects.create(
            usuario=self.usuario,
            hub=self.hub
        )

        self.client.post(
            reverse('core:toggle_hub_interesse', args=[self.hub.id])
        )

        self.assertFalse(
            UsuarioHub.objects.filter(
                usuario=self.usuario,
                hub=self.hub
            ).exists()
        )

    def test_requer_login(self):
        self.client.logout()

        response = self.client.post(
            reverse('core:toggle_hub_interesse', args=[self.hub.id])
        )

        self.assertNotEqual(response.status_code, 200)

        self.assertFalse(
            UsuarioHub.objects.filter(hub=self.hub).exists()
        )

    def test_hub_inativo_nao_pode_ser_selecionado(self):
        response = self.client.post(
            reverse(
                'core:toggle_hub_interesse',
                args=[self.hub_inativo.id]
            )
        )

        self.assertEqual(response.status_code, 404)

        self.assertFalse(
            UsuarioHub.objects.filter(
                hub=self.hub_inativo
            ).exists()
        )

    def test_empresa_nao_pode_selecionar(self):
        session = self.client.session
        session['perfil'] = 'empresa'
        session.save()

        self.client.post(
            reverse('core:toggle_hub_interesse', args=[self.hub.id])
        )

        self.assertFalse(
            UsuarioHub.objects.filter(hub=self.hub).exists()
        )


class CadastroCompletoExperienciaTest(TestCase):
    def setUp(self):
        estado = Estado.objects.create(
            nome_estado="Minas Gerais",
            sigla_estado="MG"
        )

        cidade = Cidade.objects.create(
            nome_cidade="Belo Horizonte",
            estado_cidade=estado
        )

        endereco = Endereco.objects.create(
            cep="12345678",
            rua="Rua Teste",
            numero="123",
            bairro="Centro",
            cidade=cidade,
            estado=estado,
        )

        user = UsuarioBase.objects.create_user(
            email='teste@test.com',
            password='testpass123',
            nome='Teste User',
            tipo='usuario'
        )

        self.usuario = Usuario.objects.create(
            user=user,
            data_nascimento='1990-01-01',
            genero='Masculino',
            estado_civil='Solteiro',
            nacionalidade='Brasileiro',
            telefone='123456789',
            endereco=endereco,
        )

        self.client = Client()

        session = self.client.session
        session['email_atual'] = self.usuario.user.email
        session.save()

    def test_experiencia_profissional_1_e_persistida(self):
        url = reverse('core:cadastro_completo')

        response = self.client.post(
            url,
            {
                'txtCargoPretendido': 'Analista',
                'txtAreaInteresse': 'Tecnologia',
                'txtNomeEmpresa1': 'Empresa Teste',
                'txtCargo1': 'Desenvolvedor',
                'txtDataProf1': '2020-01-01',
                'txtDataFimProf1': '2021-01-01',
            },
            follow=True
        )

        self.assertEqual(response.status_code, 200)

        exp = ExperienciaProfissional.objects.get(
            usuario=self.usuario
        )

        self.assertEqual(
            exp.nome_empresa,
            'Empresa Teste'
        )

        self.assertEqual(
            exp.cargo,
            'Desenvolvedor'
        )

        self.assertEqual(
            str(exp.data_inicio),
            '2020-01-01'
        )

        self.assertEqual(
            str(exp.data_fim),
            '2021-01-01'
        )