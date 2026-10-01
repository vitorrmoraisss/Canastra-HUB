from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from core.models import UsuarioBase, Hub, Sala, MensagemContato


class GerenciarSalasTest(TestCase):
    def setUp(self):
        self.admin = UsuarioBase.objects.create_user(
            email='admin_salas@teste', password='123', nome='Admin', tipo='usuario'
        )
        self.admin.is_admin = True
        self.admin.save()
        self.client.force_login(self.admin)

        self.hub = Hub.objects.create(nome_hub='Milho', descricao_hub='Hub do milho')
        self.hub2 = Hub.objects.create(nome_hub='Grãos', descricao_hub='Hub de grãos')

    def test_nao_admin_e_barrado(self):
        usuario_comum = UsuarioBase.objects.create_user(
            email='comum@teste', password='123', nome='Comum', tipo='usuario'
        )
        self.client.force_login(usuario_comum)
        response = self.client.get(reverse('administrador:gerenciarSalas'))
        self.assertRedirects(response, reverse('core:home'))

    def test_gerenciar_salas_lista(self):
        Sala.objects.create(nome_sala='Auditório', descricao_recursos='Projetor')
        response = self.client.get(reverse('administrador:gerenciarSalas'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Auditório')

    def test_cadastrar_sala_sem_hub(self):
        response = self.client.post(reverse('administrador:cadastrarSala'), {
            'txtNomeSala': 'Sala Nova',
            'txtDescricaoRecursos': 'Mesa e cadeiras',
        })
        self.assertRedirects(response, reverse('administrador:cadastrarSala'))
        sala = Sala.objects.get(nome_sala='Sala Nova')
        self.assertEqual(sala.hubs.count(), 0)

    def test_cadastrar_sala_vinculada_a_varios_hubs(self):
        self.client.post(reverse('administrador:cadastrarSala'), {
            'txtNomeSala': 'Sala Compartilhada',
            'txtDescricaoRecursos': 'Bancadas',
            'selHub': [self.hub.id, self.hub2.id],
        })
        sala = Sala.objects.get(nome_sala='Sala Compartilhada')
        self.assertEqual(set(sala.hubs.all()), {self.hub, self.hub2})

    def test_alterar_sala(self):
        sala = Sala.objects.create(nome_sala='Antiga', descricao_recursos='Antigo recurso')
        self.client.post(reverse('administrador:alterarSala'), {
            'idsala': sala.id,
            'txtNomeSala': 'Nova',
            'txtDescricaoRecursos': 'Novo recurso',
            'selHub': [self.hub.id, self.hub2.id],
        })
        sala.refresh_from_db()
        self.assertEqual(sala.nome_sala, 'Nova')
        self.assertEqual(sala.descricao_recursos, 'Novo recurso')
        self.assertEqual(set(sala.hubs.all()), {self.hub, self.hub2})

    def test_desativar_e_ativar_sala(self):
        sala = Sala.objects.create(nome_sala='Alterna', descricao_recursos='Recurso')
        self.client.get(reverse('administrador:deletaSala', args=[sala.id]))
        sala.refresh_from_db()
        self.assertFalse(sala.isActive)

        self.client.get(reverse('administrador:deletaSala', args=[sala.id]))
        sala.refresh_from_db()
        self.assertTrue(sala.isActive)


class MensagensContatoAdminTest(TestCase):
    def setUp(self):
        self.admin = UsuarioBase.objects.create_user(
            email='admin_contato@teste', password='123', nome='Admin', tipo='usuario'
        )
        self.admin.is_admin = True
        self.admin.save()
        self.client.force_login(self.admin)

        self.mensagem = MensagemContato.objects.create(
            nome='João Souza',
            email='joao@example.com',
            tipo='duvida',
            mensagem='Gostaria de tirar uma dúvida.',
        )

    def test_nao_admin_e_barrado(self):
        usuario_comum = UsuarioBase.objects.create_user(
            email='comum_contato@teste', password='123', nome='Comum', tipo='usuario'
        )
        self.client.force_login(usuario_comum)
        response = self.client.get(reverse('administrador:listar_mensagens_contato'))
        self.assertRedirects(response, reverse('core:home'))

    def test_lista_mensagens(self):
        response = self.client.get(reverse('administrador:listar_mensagens_contato'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'João Souza')

    def test_filtro_pendente_e_respondida(self):
        respondida = MensagemContato.objects.create(
            nome='Ana',
            email='ana@example.com',
            tipo='elogio',
            mensagem='Parabéns pelo sistema!',
            resposta='Obrigado!',
        )
        from django.utils import timezone
        respondida.respondido_em = timezone.now()
        respondida.save()

        response = self.client.get(reverse('administrador:listar_mensagens_contato'), {'status': 'pendente'})
        self.assertContains(response, 'João Souza')
        self.assertNotContains(response, 'Ana')

        response = self.client.get(reverse('administrador:listar_mensagens_contato'), {'status': 'respondida'})
        self.assertContains(response, 'Ana')
        self.assertNotContains(response, 'João Souza')

    @patch('administrador.views.GoogleEmailService.enviar_email', return_value=True)
    def test_responder_mensagem_salva_resposta_e_redireciona(self, mock_enviar):
        response = self.client.post(
            reverse('administrador:responder_mensagem_contato', args=[self.mensagem.id]),
            {'txtResposta': 'Obrigado pelo contato, já esclarecemos sua dúvida.'}
        )

        self.assertRedirects(response, reverse('administrador:listar_mensagens_contato'))

        self.mensagem.refresh_from_db()
        self.assertEqual(
            self.mensagem.resposta,
            'Obrigado pelo contato, já esclarecemos sua dúvida.'
        )
        self.assertIsNotNone(self.mensagem.respondido_em)
        self.assertEqual(self.mensagem.respondido_por, self.admin)
        mock_enviar.assert_called_once()
        self.assertEqual(mock_enviar.call_args.kwargs['destinatarios'], self.mensagem.email)

    @patch('administrador.views.GoogleEmailService.enviar_email', return_value=True)
    def test_responder_duas_vezes_envia_email_uma_vez(self, mock_enviar):
        url = reverse('administrador:responder_mensagem_contato', args=[self.mensagem.id])
        self.client.post(url, {'txtResposta': 'Primeira resposta'})
        self.client.post(url, {'txtResposta': 'Segunda resposta'})

        mock_enviar.assert_called_once()
        self.mensagem.refresh_from_db()
        self.assertEqual(self.mensagem.resposta, 'Primeira resposta')

    def test_responder_sem_texto_nao_salva(self):
        response = self.client.post(
            reverse('administrador:responder_mensagem_contato', args=[self.mensagem.id]),
            {'txtResposta': ''}
        )

        self.assertRedirects(
            response,
            reverse('administrador:responder_mensagem_contato', args=[self.mensagem.id])
        )

        self.mensagem.refresh_from_db()
        self.assertIsNone(self.mensagem.respondido_em)
