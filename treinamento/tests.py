from django.test import TestCase
from django.urls import reverse

from core.models import UsuarioBase, Hub
from .models import (
    Treinamento,
    InscricaoTreinamento,
    ListaEspera,
)


class TreinamentoTestBase(TestCase):

    def setUp(self):
        self.usuario = UsuarioBase.objects.create_user(
            email='usuario@teste.com',
            nome='Usuário Teste',
            tipo='usuario',
            password='senha123'
        )

        self.gestor = UsuarioBase.objects.create_user(
            email='gestor@teste.com',
            nome='Gestor Teste',
            tipo='empresa',
            password='senha123'
        )

        self.hub = Hub.objects.create(
            nome_hub='Hub Teste',
            descricao_hub='Hub para testes'
        )

        self.treinamento = Treinamento.objects.create(
            nome='Treinamento Teste',
            vagas_disponiveis=2,
            hub=self.hub
        )

    def autenticar(self, usuario, perfil):
        self.client.force_login(usuario)
        session = self.client.session
        session['perfil'] = perfil
        session['email_atual'] = usuario.email
        session.save()


class InscricaoTreinamentoTests(TreinamentoTestBase):

    def test_usuario_comum_pode_se_inscrever(self):
        self.autenticar(self.usuario, 'usuario')

        response = self.client.post(
            reverse(
                'treinamento:inscrever',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            InscricaoTreinamento.objects.filter(
                treinamento=self.treinamento,
                usuario=self.usuario
            ).exists()
        )

        self.treinamento.refresh_from_db()
        self.assertEqual(self.treinamento.vagas_disponiveis, 1)

    def test_usuario_sem_vaga_entra_na_lista_de_espera(self):
        self.treinamento.vagas_disponiveis = 0
        self.treinamento.save()

        self.autenticar(self.usuario, 'usuario')

        response = self.client.post(
            reverse(
                'treinamento:inscrever',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ListaEspera.objects.filter(
                treinamento=self.treinamento,
                usuario=self.usuario
            ).exists()
        )

        self.assertEqual(
            InscricaoTreinamento.objects.filter(
                treinamento=self.treinamento
            ).count(),
            0
        )

    def test_usuario_nao_pode_se_inscrever_duas_vezes(self):
        InscricaoTreinamento.objects.create(
            treinamento=self.treinamento,
            usuario=self.usuario
        )

        self.autenticar(self.usuario, 'usuario')

        response = self.client.post(
            reverse(
                'treinamento:inscrever',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            InscricaoTreinamento.objects.filter(
                treinamento=self.treinamento,
                usuario=self.usuario
            ).count(),
            1
        )

    def test_empresa_nao_pode_se_inscrever(self):
        self.autenticar(self.gestor, 'empresa')

        response = self.client.post(
            reverse(
                'treinamento:inscrever',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            InscricaoTreinamento.objects.filter(
                treinamento=self.treinamento,
                usuario=self.gestor
            ).exists()
        )

    def test_get_nao_permite_inscricao(self):
        self.autenticar(self.usuario, 'usuario')

        response = self.client.get(
            reverse(
                'treinamento:inscrever',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 405)


class CancelamentoInscricaoTests(TreinamentoTestBase):

    def test_usuario_pode_cancelar_inscricao(self):
        InscricaoTreinamento.objects.create(
            treinamento=self.treinamento,
            usuario=self.usuario
        )

        self.treinamento.vagas_disponiveis = 1
        self.treinamento.save()

        self.autenticar(self.usuario, 'usuario')

        response = self.client.post(
            reverse(
                'treinamento:cancelar',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            InscricaoTreinamento.objects.filter(
                treinamento=self.treinamento,
                usuario=self.usuario
            ).exists()
        )

        self.treinamento.refresh_from_db()
        self.assertEqual(self.treinamento.vagas_disponiveis, 2)

    def test_cancelamento_promove_proximo_da_lista_de_espera(self):
        proximo = UsuarioBase.objects.create_user(
            email='proximo@teste.com',
            nome='Próximo Usuário',
            tipo='usuario',
            password='senha123'
        )

        InscricaoTreinamento.objects.create(
            treinamento=self.treinamento,
            usuario=self.usuario
        )

        ListaEspera.objects.create(
            treinamento=self.treinamento,
            usuario=proximo
        )

        self.treinamento.vagas_disponiveis = 1
        self.treinamento.save()

        self.autenticar(self.usuario, 'usuario')

        response = self.client.post(
            reverse(
                'treinamento:cancelar',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 302)

        self.assertTrue(
            InscricaoTreinamento.objects.filter(
                treinamento=self.treinamento,
                usuario=proximo
            ).exists()
        )

        self.assertFalse(
            ListaEspera.objects.filter(
                treinamento=self.treinamento,
                usuario=proximo
            ).exists()
        )

        self.treinamento.refresh_from_db()
        self.assertEqual(self.treinamento.vagas_disponiveis, 1)

    def test_usuario_pode_sair_da_lista_de_espera(self):
        ListaEspera.objects.create(
            treinamento=self.treinamento,
            usuario=self.usuario
        )

        self.autenticar(self.usuario, 'usuario')

        response = self.client.post(
            reverse(
                'treinamento:cancelar',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ListaEspera.objects.filter(
                treinamento=self.treinamento,
                usuario=self.usuario
            ).exists()
        )

    def test_empresa_nao_pode_cancelar_inscricao(self):
        InscricaoTreinamento.objects.create(
            treinamento=self.treinamento,
            usuario=self.gestor
        )

        self.autenticar(self.gestor, 'empresa')

        response = self.client.post(
            reverse(
                'treinamento:cancelar',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            InscricaoTreinamento.objects.filter(
                treinamento=self.treinamento,
                usuario=self.gestor
            ).exists()
        )

    def test_get_nao_permite_cancelamento(self):
        self.autenticar(self.usuario, 'usuario')

        response = self.client.get(
            reverse(
                'treinamento:cancelar',
                args=[self.treinamento.id, 0]
            )
        )

        self.assertEqual(response.status_code, 405)


class GerenciamentoTreinamentoTests(TreinamentoTestBase):

    def test_usuario_comum_nao_pode_gerenciar_inscricoes(self):
        self.autenticar(self.usuario, 'usuario')

        response = self.client.get(
            reverse(
                'treinamento:gerenciar_inscricoes',
                args=[self.treinamento.id]
            )
        )

        self.assertRedirects(
            response,
            reverse('treinamento:listar_treinamentos')
        )

    def test_gestor_pode_atualizar_presenca(self):
        inscricao = InscricaoTreinamento.objects.create(
            treinamento=self.treinamento,
            usuario=self.usuario
        )

        self.autenticar(self.gestor, 'empresa')

        response = self.client.post(
            reverse(
                'treinamento:atualizar_presenca',
                args=[inscricao.id]
            ),
            {'presenca': 'presente'}
        )

        self.assertEqual(response.status_code, 302)

        inscricao.refresh_from_db()
        self.assertEqual(inscricao.presenca, 'presente')

    def test_gestor_nao_pode_salvar_presenca_invalida(self):
        inscricao = InscricaoTreinamento.objects.create(
            treinamento=self.treinamento,
            usuario=self.usuario
        )

        self.autenticar(self.gestor, 'empresa')

        response = self.client.post(
            reverse(
                'treinamento:atualizar_presenca',
                args=[inscricao.id]
            ),
            {'presenca': 'invalida'}
        )

        self.assertEqual(response.status_code, 302)

        inscricao.refresh_from_db()
        self.assertEqual(inscricao.presenca, 'pendente')

    def test_usuario_comum_nao_pode_atualizar_presenca(self):
        inscricao = InscricaoTreinamento.objects.create(
            treinamento=self.treinamento,
            usuario=self.usuario
        )

        self.autenticar(self.usuario, 'usuario')

        response = self.client.post(
            reverse(
                'treinamento:atualizar_presenca',
                args=[inscricao.id]
            ),
            {'presenca': 'presente'}
        )

        self.assertEqual(response.status_code, 302)

        inscricao.refresh_from_db()
        self.assertEqual(inscricao.presenca, 'pendente')

    def test_get_nao_permite_atualizar_presenca(self):
        inscricao = InscricaoTreinamento.objects.create(
            treinamento=self.treinamento,
            usuario=self.usuario
        )

        self.autenticar(self.gestor, 'empresa')

        response = self.client.get(
            reverse(
                'treinamento:atualizar_presenca',
                args=[inscricao.id]
            )
        )

        self.assertEqual(response.status_code, 405)

    def test_usuario_comum_nao_pode_exportar_csv(self):
        self.autenticar(self.usuario, 'usuario')

        response = self.client.get(
            reverse(
                'treinamento:exportar_csv',
                args=[self.treinamento.id]
            )
        )

        self.assertRedirects(
            response,
            reverse('treinamento:listar_treinamentos')
        )