from django.test import TestCase, Client
from django.urls import reverse
from core.models import UsuarioBase, Estado, Cidade
from empresa.models import Empresa
from vagas.models import Vagas, UsuarioVaga
from core.models import Usuario


def _make_empresa(email='empresa@test.com', nomefantasia='EmpresaTeste'):
    estado = Estado.objects.create(nome_estado='MG', sigla_estado='MG')
    cidade = Cidade.objects.create(nome_cidade='Patos', estado_cidade=estado)
    user = UsuarioBase.objects.create_user(
        email=email, nome=nomefantasia, tipo='empresa', password='senha123'
    )
    empresa = Empresa.objects.create(
        user=user, nomefantasia=nomefantasia, tipo_empresa='MEI',
        razao_social='Teste Ltda', cnpj='12345678000190',
        telefone='3400000000', rua='Rua A', cep='38700000',
        numero=1, cidade=cidade, estado=estado, segmento='TI',
    )
    return user, empresa


def _make_outra_empresa():
    estado = Estado.objects.first()
    cidade = Cidade.objects.first()
    user = UsuarioBase.objects.create_user(
        email='outra@test.com', nome='Outra', tipo='empresa', password='senha123'
    )
    return Empresa.objects.create(
        user=user, nomefantasia='Outra', tipo_empresa='MEI',
        razao_social='Outra Ltda', cnpj='99999999000199',
        telefone='3400000001', rua='Rua B', cep='38700001',
        numero=2, cidade=cidade, estado=estado, segmento='TI',
    )


def _login_empresa(client, user):
    client.force_login(user)
    session = client.session
    session['perfil'] = 'empresa'
    session['email_atual'] = user.email
    session.save()


class MinhasVagasViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.empresa = _make_empresa()
        _login_empresa(self.client, self.user)
        self.vaga = Vagas.objects.create(
            cargo_vaga='Dev Python', descricao_vaga='Backend',
            requisito_vaga='Python', local='Remoto', empresa=self.empresa,
        )

    def test_lista_vagas_proprias(self):
        resp = self.client.get(reverse('empresa:minhas_vagas'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.vaga, resp.context['vagas'])

    def test_nao_lista_vagas_de_outra_empresa(self):
        outra = _make_outra_empresa()
        vaga_outra = Vagas.objects.create(
            cargo_vaga='Outro cargo', empresa=outra,
        )
        resp = self.client.get(reverse('empresa:minhas_vagas'))
        self.assertNotIn(vaga_outra, resp.context['vagas'])

    def test_redireciona_sem_login(self):
        self.client.logout()
        resp = self.client.get(reverse('empresa:minhas_vagas'))
        self.assertEqual(resp.status_code, 302)

    def test_redireciona_perfil_usuario(self):
        user2 = UsuarioBase.objects.create_user(
            email='u@test.com', nome='User', tipo='usuario', password='s'
        )
        self.client.force_login(user2)
        session = self.client.session
        session['perfil'] = 'usuario'
        session['email_atual'] = user2.email
        session.save()
        resp = self.client.get(reverse('empresa:minhas_vagas'))
        self.assertEqual(resp.status_code, 302)


class DetalheMinhVagaViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.empresa = _make_empresa()
        _login_empresa(self.client, self.user)
        self.vaga = Vagas.objects.create(
            cargo_vaga='Dev', empresa=self.empresa,
        )

    def test_detalhe_vaga_propria(self):
        resp = self.client.get(reverse('empresa:detalhe_minha_vaga', args=[self.vaga.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['vaga'], self.vaga)

    def test_detalhe_vaga_outra_empresa_retorna_404(self):
        outra = _make_outra_empresa()
        vaga_outra = Vagas.objects.create(cargo_vaga='X', empresa=outra)
        resp = self.client.get(reverse('empresa:detalhe_minha_vaga', args=[vaga_outra.id]))
        self.assertEqual(resp.status_code, 404)


class CandidatosVagaViewTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user, self.empresa = _make_empresa()
        _login_empresa(self.client, self.user)
        self.vaga = Vagas.objects.create(
            cargo_vaga='Dev', empresa=self.empresa,
        )
        estado = Estado.objects.first()
        cidade = Cidade.objects.first()
        user_cand = UsuarioBase.objects.create_user(
            email='cand@test.com', nome='Cand', tipo='usuario', password='s'
        )
        self.candidato = Usuario.objects.create(
            user=user_cand, nome_social='Cand Silva',
            estado=estado, cidade=cidade,
            data_nascimento='2000-01-01',
        )
        UsuarioVaga.objects.create(vaga=self.vaga, usuario=self.candidato)

    def test_lista_candidatos_da_vaga(self):
        resp = self.client.get(reverse('empresa:candidatos_vaga', args=[self.vaga.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['candidaturas']), 1)

    def test_candidatos_vaga_outra_empresa_retorna_404(self):
        outra = _make_outra_empresa()
        vaga_outra = Vagas.objects.create(cargo_vaga='X', empresa=outra)
        resp = self.client.get(reverse('empresa:candidatos_vaga', args=[vaga_outra.id]))
        self.assertEqual(resp.status_code, 404)
