from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse, NoReverseMatch
from django.db import IntegrityError

from core.models import (
    UsuarioBase,
    Usuario,
    Estado,
    Cidade,
    Endereco,
    Hub,
    UsuarioHub,
    ExperienciaProfissional,
    Sala,
    SalaImagem,
)



class EstruturaEstrategicaTest(TestCase):
    def setUp(self):
        self.sala_ativa = Sala.objects.create(
            nome_sala='Auditórios',
            descricao_recursos='Capacidade para 100 pessoas'
        )
        self.sala_inativa = Sala.objects.create(
            nome_sala='Sala Desativada',
            descricao_recursos='Recurso qualquer', isActive=False
        )

    def test_pagina_carrega(self):
        response = self.client.get(reverse('core:espacos_hub'))
        self.assertEqual(response.status_code, 200)

    def test_sala_ativa_aparece_com_descricao(self):
        response = self.client.get(reverse('core:espacos_hub'))
        content = response.content.decode()
        self.assertIn(self.sala_ativa.nome_sala, content)
        self.assertIn(self.sala_ativa.descricao_recursos, content)

    def test_sala_inativa_nao_aparece(self):
        response = self.client.get(reverse('core:espacos_hub'))
        content = response.content.decode()
        self.assertNotIn('Sala Desativada', content)

    def test_rota_sobre_removida(self):
        with self.assertRaises(NoReverseMatch):
            reverse('core:sobre')

    def test_imagens_da_sala_renderizadas_no_carousel(self):
        img1 = SalaImagem.objects.create(sala=self.sala_ativa, imagem='fotos_sala/a.jpg', ordem=0)
        img2 = SalaImagem.objects.create(sala=self.sala_ativa, imagem='fotos_sala/b.jpg', ordem=1)
        response = self.client.get(reverse('core:espacos_hub'))
        content = response.content.decode()
        self.assertIn('data-carousel', content)
        self.assertIn(img1.imagem.url, content)
        self.assertIn(img2.imagem.url, content)


class CoreTestSetupMixin:
    """Cria Estado/Cidade base, usados tanto no cadastro quanto no login."""

    def setUp(self):
        self.estado = Estado.objects.create(
            nome_estado='Minas Gerais',
            sigla_estado='MG'
        )

        self.cidade = Cidade.objects.create(
            nome_cidade='Bambuí',
            estado_cidade=self.estado
        )


class CadastroUsuarioTestCase(CoreTestSetupMixin, TestCase):
    """Testes da view core:cadastro_usuario (POST)."""

    def setUp(self):
        super().setUp()
        self.url = reverse('core:cadastro_usuario')

    def _dados_validos(self, **overrides):
        dados = {
            'txtNome': 'Maria Silva',
            'txtSenha': 'SenhaForte123',
            'txtConfirmarSenha': 'SenhaForte123',
            'txtNomeSocial': 'Maria',
            'txtDataNasc': '1995-05-20',
            'txtGenero': 'Feminino',
            'txtEstadoCivil': 'Solteira',
            'txtNacionalidade': 'Brasileira',
            'txtEmail': 'maria@example.com',
            'txtTelefone': '35999999999',
            'txtCep': '38900-000',
            'txtRua': 'Rua A',
            'txtNumero': '100',
            'txtBairro': 'Centro',
            'txtComplemento': '',
            'cidade': str(self.cidade.id),
            'estado': str(self.estado.id),
        }

        dados.update(overrides)
        return dados

    def test_cadastro_sucesso_cria_usuariobase_e_usuario(self):
        response = self.client.post(
            self.url,
            self._dados_validos()
        )

        self.assertRedirects(
            response,
            reverse('core:login')
        )

        self.assertTrue(
            UsuarioBase.objects.filter(
                email='maria@example.com'
            ).exists()
        )

        user = UsuarioBase.objects.get(
            email='maria@example.com'
        )

        self.assertTrue(
            user.check_password('SenhaForte123')
        )

        self.assertTrue(
            Usuario.objects.filter(user=user).exists()
        )

    def test_cadastro_sem_nome_nao_cria_usuario(self):
        response = self.client.post(
            self.url,
            self._dados_validos(txtNome='')
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'O nome é obrigatório.'
        )

        self.assertFalse(
            UsuarioBase.objects.filter(
                email='maria@example.com'
            ).exists()
        )

    def test_cadastro_nome_curto_nao_cria_usuario(self):
        response = self.client.post(
            self.url,
            self._dados_validos(txtNome='Ma')
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'O nome deve possuir no mínimo 3 caracteres.'
        )

        self.assertFalse(
            UsuarioBase.objects.filter(
                email='maria@example.com'
            ).exists()
        )

    def test_cadastro_senha_confirmacao_diferente_nao_cria_usuario(self):
        response = self.client.post(
            self.url,
            self._dados_validos(
                txtConfirmarSenha='OutraSenha123'
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'As senhas devem ser iguais.'
        )

        self.assertFalse(
            UsuarioBase.objects.filter(
                email='maria@example.com'
            ).exists()
        )

    def test_cadastro_sem_cidade_redireciona(self):
        response = self.client.post(
            self.url,
            self._dados_validos(cidade='')
        )

        self.assertRedirects(
            response,
            reverse('core:cadastro_usuario')
        )

        self.assertFalse(
            UsuarioBase.objects.filter(
                email='maria@example.com'
            ).exists()
        )

    def test_cadastro_estado_invalido_nao_cria_usuario(self):
        response = self.client.post(
            self.url,
            self._dados_validos(estado='9999')
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'Estado inválido.'
        )

        self.assertFalse(
            UsuarioBase.objects.filter(
                email='maria@example.com'
            ).exists()
        )

    def test_cadastro_cidade_invalida_nao_cria_usuario(self):
        response = self.client.post(
            self.url,
            self._dados_validos(cidade='9999')
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'Cidade inválida.'
        )

        self.assertFalse(
            UsuarioBase.objects.filter(
                email='maria@example.com'
            ).exists()
        )

    def test_cadastro_email_duplicado(self):
        """
        A view atual deve impedir o cadastro duplicado.
        """

        UsuarioBase.objects.create_user(
            email='maria@example.com',
            nome='Já Cadastrada',
            tipo='usuario',
            password='Outra123',
        )

        response = self.client.post(
            self.url,
            self._dados_validos()
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertContains(
            response,
            'Já existe uma conta cadastrada com este e-mail.'
        )

    def test_cadastro_usuario_ja_logado_nao_permite_novo_cadastro(self):
        user = UsuarioBase.objects.create_user(
            email='logado@example.com',
            nome='Logado',
            tipo='usuario',
            password='Senha123',
        )

        self.client.force_login(user)

        response = self.client.post(
            self.url,
            self._dados_validos()
        )

        self.assertRedirects(
            response,
            reverse('core:home')
        )

        self.assertFalse(
            UsuarioBase.objects.filter(
                email='maria@example.com'
            ).exists()
        )


class LoginTestCase(CoreTestSetupMixin, TestCase):
    """Testes da view core:login."""

    def setUp(self):
        super().setUp()

        self.url = reverse('core:login')
        self.senha = 'SenhaForte123'

        self.user = UsuarioBase.objects.create_user(
            email='usuario@example.com',
            nome='Usuário Teste',
            tipo='usuario',
            password=self.senha
        )

        endereco = Endereco.objects.create(
            cep='38900-000',
            rua='Rua A',
            bairro='Centro',
            numero='10',
            cidade=self.cidade,
            estado=self.estado,
        )

        self.usuario = Usuario.objects.create(
            user=self.user,
            data_nascimento='1990-01-01',
            genero='Feminino',
            estado_civil='Solteira',
            nacionalidade='Brasileira',
            telefone='35999999999',
            endereco=endereco,
        )

    def test_login_credenciais_validas_redireciona_para_home(self):
        response = self.client.post(
            self.url,
            {
                'txtEmail': 'usuario@example.com',
                'txtSenha': self.senha,
            }
        )

        self.assertRedirects(
            response,
            reverse('core:home')
        )

        self.assertEqual(
            self.client.session['email_atual'],
            'usuario@example.com'
        )

        self.assertEqual(
            self.client.session['nome'],
            'Usuário Teste'
        )

    def test_login_credenciais_invalidas_nao_autentica(self):
        response = self.client.post(
            self.url,
            {
                'txtEmail': 'usuario@example.com',
                'txtSenha': 'senhaErrada',
            }
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'Usuário ou senha inválidos.'
        )

        self.assertNotIn(
            'email_atual',
            self.client.session
        )

    def test_login_email_inexistente_nao_autentica(self):
        response = self.client.post(
            self.url,
            {
                'txtEmail': 'naoexiste@example.com',
                'txtSenha': 'qualquer',
            }
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'Usuário ou senha inválidos.'
        )

    def test_login_usuario_sem_area_interesse_marca_cadastro_incompleto(self):
        response = self.client.post(
            self.url,
            {
                'txtEmail': 'usuario@example.com',
                'txtSenha': self.senha,
            }
        )

        self.assertRedirects(
            response,
            reverse('core:home')
        )

        self.assertTrue(
            self.client.session.get('incompleto')
        )


class HubsListagemTestCase(TestCase):
    """Testes da listagem dinâmica de Hubs."""

    def setUp(self):
        self.hub_ativo1 = Hub.objects.create(
            nome_hub='Agro',
            descricao_hub='Hub do agronegócio',
            isActive=True
        )

        self.hub_ativo2 = Hub.objects.create(
            nome_hub='Tech',
            descricao_hub='Hub de tecnologia',
            isActive=True
        )

        self.hub_inativo = Hub.objects.create(
            nome_hub='Descontinuado',
            descricao_hub='Hub desativado',
            isActive=False
        )

    def test_lista_apenas_hubs_ativos(self):
        response = self.client.get(
            reverse('core:hubs')
        )

        self.assertEqual(
            response.status_code,
            200
        )

        hubs_exibidos = list(
            response.context['hubs']
        )

        self.assertIn(
            self.hub_ativo1,
            hubs_exibidos
        )

        self.assertIn(
            self.hub_ativo2,
            hubs_exibidos
        )

        self.assertNotIn(
            self.hub_inativo,
            hubs_exibidos
        )

    def test_novo_hub_criado_aparece_automaticamente(self):
        novo_hub = Hub.objects.create(
            nome_hub='Recém-criado',
            descricao_hub='Criado durante o teste',
            isActive=True
        )

        response = self.client.get(
            reverse('core:hubs')
        )

        hubs_exibidos = list(
            response.context['hubs']
        )

        self.assertIn(
            novo_hub,
            hubs_exibidos
        )

    def test_hub_desativado_some_da_lista(self):
        self.hub_ativo1.isActive = False
        self.hub_ativo1.save()

        response = self.client.get(
            reverse('core:hubs')
        )

        hubs_exibidos = list(
            response.context['hubs']
        )

        self.assertNotIn(
            self.hub_ativo1,
            hubs_exibidos
        )

        self.assertIn(
            self.hub_ativo2,
            hubs_exibidos
        )


class HubDetalheTestCase(TestCase):
    """Testes da view core:hub_detalhe."""

    def setUp(self):
        self.hub_ativo = Hub.objects.create(
            nome_hub='Agro',
            descricao_hub='Hub do agronegócio',
            isActive=True
        )

        self.hub_inativo = Hub.objects.create(
            nome_hub='Descontinuado',
            descricao_hub='Hub desativado',
            isActive=False
        )

    def test_hub_ativo_acessivel_com_dados_corretos(self):
        response = self.client.get(
            reverse(
                'core:hub_detalhe',
                args=[self.hub_ativo.nome_hub]
            )
        )

        self.assertEqual(
            response.status_code,
            200
        )

        self.assertEqual(
            response.context['hub'],
            self.hub_ativo
        )

    def test_hub_desativado_retorna_404(self):
        response = self.client.get(
            reverse(
                'core:hub_detalhe',
                args=[self.hub_inativo.nome_hub]
            )
        )

        self.assertEqual(
            response.status_code,
            404
        )


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
            reverse(
                'core:toggle_hub_interesse',
                args=[self.hub.id]
            )
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
            reverse(
                'core:toggle_hub_interesse',
                args=[self.hub.id]
            )
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
            reverse(
                'core:toggle_hub_interesse',
                args=[self.hub.id]
            )
        )

        self.assertNotEqual(
            response.status_code,
            200
        )

        self.assertFalse(
            UsuarioHub.objects.filter(
                hub=self.hub
            ).exists()
        )

    def test_hub_inativo_nao_pode_ser_selecionado(self):
        response = self.client.post(
            reverse(
                'core:toggle_hub_interesse',
                args=[self.hub_inativo.id]
            )
        )

        self.assertEqual(
            response.status_code,
            404
        )

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
            reverse(
                'core:toggle_hub_interesse',
                args=[self.hub.id]
            )
        )

        self.assertFalse(
            UsuarioHub.objects.filter(
                hub=self.hub
            ).exists()
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

        self.assertEqual(
            response.status_code,
            200
        )

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
