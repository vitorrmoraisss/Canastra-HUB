from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from core.models import Usuario, ExperienciaProfissional, Estado, Cidade
from datetime import datetime

UsuarioBase = get_user_model()


class CadastroCompletoExperienciaTest(TestCase):
    def setUp(self):
        # Create Estado and Cidade for the Usuario
        estado = Estado.objects.create(nome_estado="Minas Gerais", sigla_estado="MG")
        cidade = Cidade.objects.create(nome_cidade="Belo Horizonte", estado_cidade=estado)

        # Create UsuarioBase
        user = UsuarioBase.objects.create_user(
            email='teste@test.com',
            password='testpass123',
            nome='Teste User',
            tipo='usuario'
        )

        # Create Usuario
        self.usuario = Usuario.objects.create(
            user=user,
            data_nascimento='1990-01-01',
            genero='Masculino',
            estado_civil='Solteiro',
            nacionalidade='Brasileiro',
            estado=estado,
            cidade=cidade
        )

        self.client = Client()
        session = self.client.session
        session['email_atual'] = self.usuario.user.email
        session.save()

    def test_experiencia_profissional_1_e_persistida(self):
        url = reverse('core:cadastro_completo')
        response = self.client.post(url, {
            'txtCargoPretendido': 'Analista',
            'txtAreaInteresse': 'Tecnologia',
            'txtNomeEmpresa1': 'Empresa Teste',
            'txtCargo1': 'Desenvolvedor',
            'txtDataProf1': '2020-01-01',
            'txtDataFimProf1': '2021-01-01',
        }, follow=True)

        # Verify the response is successful
        self.assertEqual(response.status_code, 200)

        exp = ExperienciaProfissional.objects.get(usuario=self.usuario)
        self.assertEqual(exp.nome_empresa1, 'Empresa Teste')
        self.assertEqual(exp.cargo1, 'Desenvolvedor')
        self.assertEqual(str(exp.data_inicio1), '2020-01-01')
        self.assertEqual(str(exp.data_fim1), '2021-01-01')
