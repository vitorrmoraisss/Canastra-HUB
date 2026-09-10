from django.test import TestCase, Client
from django.urls import reverse

from core.models import UsuarioBase, Usuario, Estado, Cidade, Hub, UsuarioHub


class SelecaoHubsUsuarioTest(TestCase):
    def setUp(self):
        self.estado = Estado.objects.create(nome_estado='Minas Gerais', sigla_estado='MG')
        self.cidade = Cidade.objects.create(nome_cidade='Arcos', estado_cidade=self.estado)

        self.user = UsuarioBase.objects.create_user(
            email='usuario@teste.com', password='123', nome='Teste', tipo='usuario'
        )
        self.usuario = Usuario.objects.create(
            user=self.user,
            data_nascimento='2000-01-01',
            genero='masculino',
            estado_civil='solteiro',
            nacionalidade='brasileiro',
            telefone='123',
            cep='123',
            rua='rua',
            numero='1',
            bairro='bairro',
            cidade=self.cidade,
            estado=self.estado,
        )

        self.hub1 = Hub.objects.create(nome_hub='Agro', descricao_hub='desc', isActive=True)
        self.hub2 = Hub.objects.create(nome_hub='Tech', descricao_hub='desc', isActive=True)
        self.hub_inativo = Hub.objects.create(nome_hub='Inativo', descricao_hub='desc', isActive=False)

        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session['perfil'] = 'usuario'
        session.save()

    def _atualizar(self, hub_ids):
        return self.client.post(reverse('perfil:atualizar_perfil'), {'hubs': hub_ids})

    def test_selecionar_um_hub(self):
        self._atualizar([str(self.hub1.id)])
        self.assertEqual(
            list(UsuarioHub.objects.filter(usuario=self.usuario).values_list('hub_id', flat=True)),
            [self.hub1.id],
        )

    def test_selecionar_multiplos_hubs(self):
        self._atualizar([str(self.hub1.id), str(self.hub2.id)])
        ids = set(UsuarioHub.objects.filter(usuario=self.usuario).values_list('hub_id', flat=True))
        self.assertEqual(ids, {self.hub1.id, self.hub2.id})

    def test_desmarcar_hub(self):
        self._atualizar([str(self.hub1.id), str(self.hub2.id)])
        self._atualizar([str(self.hub1.id)])
        self.assertEqual(
            list(UsuarioHub.objects.filter(usuario=self.usuario).values_list('hub_id', flat=True)),
            [self.hub1.id],
        )

    def test_hub_inativo_nao_pode_ser_selecionado(self):
        self._atualizar([str(self.hub_inativo.id)])
        self.assertFalse(UsuarioHub.objects.filter(usuario=self.usuario).exists())
