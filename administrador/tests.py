from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

import os

from core.models import UsuarioBase, Hub, Sala, MensagemContato, SalaImagem, Noticia

from django.core.files.uploadedfile import SimpleUploadedFile


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
        sala = Sala.objects.create(
            nome_sala='Alterna',
            descricao_recursos='Recurso'
        )
        url = reverse('administrador:deletaSala', args=[sala.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

        sala.refresh_from_db()
        self.assertTrue(sala.isActive)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

        sala.refresh_from_db()
        self.assertFalse(sala.isActive)

        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)

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


class GerenciarHubsSegurancaTest(TestCase):
    def setUp(self):
        self.admin = UsuarioBase.objects.create_user(
            email='admin_hubs@teste.com',
            password='123',
            nome='Admin',
            tipo='usuario'
        )
        self.admin.is_admin = True
        self.admin.save()

        self.hub = Hub.objects.create(
            nome_hub='Hub Teste',
            descricao_hub='Descrição do hub'
        )

        self.url = reverse(
            'administrador:deletaHub',
            args=[self.hub.id]
        )

    def test_get_nao_altera_status_do_hub(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

        self.hub.refresh_from_db()
        self.assertTrue(self.hub.isActive)

    def test_post_admin_desativa_hub(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse('administrador:gerenciarHubs')
        )

        self.hub.refresh_from_db()
        self.assertFalse(self.hub.isActive)

    def test_post_admin_ativa_hub(self):
        self.client.force_login(self.admin)
        self.hub.isActive = False
        self.hub.save()

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse('administrador:gerenciarHubs')
        )

        self.hub.refresh_from_db()
        self.assertTrue(self.hub.isActive)

    def test_usuario_comum_nao_pode_alterar_hub(self):
        usuario = UsuarioBase.objects.create_user(
            email='comum_hubs@teste.com',
            password='123',
            nome='Usuário comum',
            tipo='usuario'
        )
        self.client.force_login(usuario)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('core:home'))

        self.hub.refresh_from_db()
        self.assertTrue(self.hub.isActive)

    def test_usuario_nao_autenticado_nao_pode_alterar_hub(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

        self.hub.refresh_from_db()
        self.assertTrue(self.hub.isActive)

class DeletarSalaImagemSegurancaTest(TestCase):
    def setUp(self):
        self.admin = UsuarioBase.objects.create_user(
            email='admin_imagem@teste.com',
            password='123',
            nome='Admin',
            tipo='usuario'
        )
        self.admin.is_admin = True
        self.admin.save()

        self.usuario = UsuarioBase.objects.create_user(
            email='comum_imagem@teste.com',
            password='123',
            nome='Usuário comum',
            tipo='usuario'
        )

        self.sala = Sala.objects.create(
            nome_sala='Sala Imagem',
            descricao_recursos='Teste de exclusão'
        )

        arquivo = SimpleUploadedFile(
            'teste.jpg',
            b'conteudo-de-teste',
            content_type='image/jpeg'
        )

        self.imagem = SalaImagem.objects.create(
            sala=self.sala,
            imagem=arquivo
        )

        self.caminho_imagem = self.imagem.imagem.path
        self.url = reverse(
            'administrador:deletaSalaImagem',
            args=[self.imagem.id]
        )

    def tearDown(self):
        import os
        if os.path.exists(self.caminho_imagem):
            os.remove(self.caminho_imagem)

    def test_get_nao_exclui_imagem(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)
        self.assertTrue(SalaImagem.objects.filter(id=self.imagem.id).exists())

    def test_post_admin_exclui_imagem(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse('administrador:gerenciarSalas')
        )
        self.assertFalse(SalaImagem.objects.filter(id=self.imagem.id).exists())
        self.assertFalse(os.path.exists(self.caminho_imagem))

    def test_usuario_comum_nao_exclui_imagem(self):
        self.client.force_login(self.usuario)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('core:home'))
        self.assertTrue(SalaImagem.objects.filter(id=self.imagem.id).exists())

    def test_usuario_nao_autenticado_nao_exclui_imagem(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(SalaImagem.objects.filter(id=self.imagem.id).exists())
        
class DeletaNoticiasSegurancaTest(TestCase):
    def setUp(self):
        self.admin = UsuarioBase.objects.create_user(
            email='admin_noticia@teste.com',
            password='123',
            nome='Admin Notícias',
            tipo='usuario'
        )
        self.admin.is_admin = True
        self.admin.save()

        self.usuario = UsuarioBase.objects.create_user(
            email='comum_noticia@teste.com',
            password='123',
            nome='Usuário comum',
            tipo='usuario'
        )

        self.noticia = Noticia.objects.create(
            titulo_noticia='Notícia de teste',
            descricao_noticia='Descrição de teste',
            fonte='Fonte teste'
        )

        self.url = reverse(
            'administrador:deletaNoticias',
            args=[self.noticia.id]
        )

    def test_get_nao_altera_status_noticia(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

        self.noticia.refresh_from_db()
        self.assertTrue(self.noticia.isActive)

    def test_post_admin_desativa_noticia(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

        self.noticia.refresh_from_db()
        self.assertFalse(self.noticia.isActive)

    def test_post_admin_ativa_noticia(self):
        self.noticia.isActive = False
        self.noticia.save()

        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

        self.noticia.refresh_from_db()
        self.assertTrue(self.noticia.isActive)

    def test_usuario_comum_nao_altera_noticia(self):
        self.client.force_login(self.usuario)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('core:home'))

        self.noticia.refresh_from_db()
        self.assertTrue(self.noticia.isActive)

    def test_usuario_nao_autenticado_nao_altera_noticia(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

        self.noticia.refresh_from_db()
        self.assertTrue(self.noticia.isActive)

class DesativarUsuarioSegurancaTest(TestCase):
    def setUp(self):
        self.admin = UsuarioBase.objects.create_user(
            email='admin_usuario@teste.com',
            password='123',
            nome='Administrador',
            tipo='usuario'
        )
        self.admin.is_admin = True
        self.admin.save()

        self.usuario = UsuarioBase.objects.create_user(
            email='comum_usuario@teste.com',
            password='123',
            nome='Usuário comum',
            tipo='usuario'
        )

        self.url = reverse(
            'administrador:desativar_usuario',
            args=[self.usuario.id]
        )

    def test_get_nao_altera_status_usuario(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_post_admin_desativa_usuario(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse('administrador:listar_usuarios')
        )

        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)

    def test_post_admin_reativa_usuario(self):
        self.usuario.is_active = False
        self.usuario.save()

        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertRedirects(
            response,
            reverse('administrador:listar_usuarios')
        )

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_admin_nao_pode_desativar_outro_admin(self):
        outro_admin = UsuarioBase.objects.create_user(
            email='outro_admin@teste.com',
            password='123',
            nome='Outro administrador',
            tipo='usuario'
        )
        outro_admin.is_admin = True
        outro_admin.save()

        url = reverse(
            'administrador:desativar_usuario',
            args=[outro_admin.id]
        )

        self.client.force_login(self.admin)

        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse('administrador:listar_usuarios')
        )

        outro_admin.refresh_from_db()
        self.assertTrue(outro_admin.is_active)

    def test_usuario_comum_nao_pode_desativar_usuario(self):
        self.client.force_login(self.usuario)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('core:home'))

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)

    def test_usuario_nao_autenticado_nao_pode_desativar(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)

        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.is_active)