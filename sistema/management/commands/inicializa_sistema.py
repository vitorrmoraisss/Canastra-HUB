from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files import File
from django.utils import timezone
import json
from pathlib import Path

from empresa.models import *
from vagas.models import *
from core.models import *
from eventos.models import Evento, InscricaoEvento
from treinamento.models import Treinamento, SessaoTreinamento, InscricaoTreinamento


class Command(BaseCommand):
    help = "Inicializa o sistema com dados padrão"

    def _cria_sala_geral(self, nome_sala, descricao_recursos, caminhos_imagens):
        sala, created = Sala.objects.get_or_create(
            nome_sala=nome_sala,
            defaults={'descricao_recursos': descricao_recursos}
        )
        if created:
            for ordem, caminho_relativo in enumerate(caminhos_imagens):
                caminho = settings.BASE_DIR / caminho_relativo
                if caminho.exists():
                    with open(caminho, 'rb') as f:
                        SalaImagem.objects.create(
                            sala=sala,
                            imagem=File(f, name=Path(caminho_relativo).name),
                            ordem=ordem,
                        )
        return sala

    def handle(self, *args, **options):
        self.stdout.write("1. Populando Estados e Cidades...")
        json_path = settings.BASE_DIR / 'resources' / \
            'static' / 'json' / 'estados-cidades.json'

        if json_path.exists():
            with open(json_path, 'r', encoding='utf-8') as f:
                dados = json.load(f)

            for estado_data in dados['estados']:
                try:
                    estado, _ = Estado.objects.get_or_create(
                        nome_estado=estado_data['nome'],
                        sigla_estado=estado_data['sigla']
                    )
                    cidades_objs = []
                    for nome_cidade in estado_data['cidades']:
                        cidade, cidade_created = Cidade.objects.get_or_create(
                            nome_cidade=nome_cidade,
                            estado_cidade=estado
                        )
                        if cidade_created:
                            cidades_objs.append(cidade)
                    if cidades_objs:
                        print(
                            f"  - Inserido estado {estado.nome_estado} com {len(cidades_objs)} cidades novas.")
                except Exception as e:
                    print(f"Erro ao inserir {estado_data['nome']}: {e}")

        cidade = Cidade.objects.filter(nome_cidade="Arcos").first()
        if not cidade:
            cidade = Cidade.objects.first()

        estado = cidade.estado_cidade if cidade else None

        # 2. Hubs
        self.stdout.write("2. Criando Hubs...")
        caminho_hub1 = settings.BASE_DIR / 'media' / 'fotos_hub' / 'agro_hub.jpg'
        hub1, created1 = Hub.objects.get_or_create(
            nome_hub='Agro',
            defaults={
                'descricao_hub': 'Agro é melhor com o pessoal da canastra',
                'area_foco_hub': 'Agronegócio, cafeicultura, produção rural e comercialização de alimentos',
                'tecnologias_hub': 'Agricultura de precisão, sensores IoT, gestão agrícola digital'
            }
        )
        if created1 and caminho_hub1.exists():
            with open(caminho_hub1, 'rb') as f:
                hub1.foto_hub.save(caminho_hub1.name, File(f), save=True)

        caminho_hub4 = settings.BASE_DIR / 'media' / 'fotos_hub' / 'milho_hub.jpg'
        hub4, created4 = Hub.objects.get_or_create(
            nome_hub='Milho',
            defaults={
                'descricao_hub': 'Milho é melhor com o pessoal da canastra',
                'area_foco_hub': 'Produção de milho, grãos e insumos agrícolas',
                'tecnologias_hub': 'Sementes geneticamente melhoradas, maquinário agrícola'
            }
        )
        if created4 and caminho_hub4.exists():
            with open(caminho_hub4, 'rb') as f:
                hub4.foto_hub.save(caminho_hub4.name, File(f), save=True)

        caminho_hub6 = settings.BASE_DIR / 'media' / 'fotos_hub' / 'graos_hub.jpg'
        hub6, created6 = Hub.objects.get_or_create(
            nome_hub='Grãos',
            defaults={
                'descricao_hub': 'Grãos é melhor com o pessoal da canastra',
                'area_foco_hub': 'Comercialização de grãos, logística agrícola e exportação',
                'tecnologias_hub': 'Armazenagem, transporte, rastreabilidade da produção'
            }
        )
        if created6 and caminho_hub6.exists():
            with open(caminho_hub6, 'rb') as f:
                hub6.foto_hub.save(caminho_hub6.name, File(f), save=True)

        # 3. Salas Gerais
        self.stdout.write("3. Criando Salas e Espaços...")
        self._cria_sala_geral(
            'Incubadora de Empresas e Startups',
            'A Incubadora de Empresas e Startups é o núcleo que dá origem ao próprio Canastra HUB. '
            'Ela oferece suporte técnico, orientação gerencial e infraestrutura física a empreendedores '
            'e estudantes que buscam desenvolver negócios inovadores.',
            [
                'resources/static/img/espacos_hub/incubadora/incubadora3.jpeg',
                'resources/static/img/espacos_hub/incubadora/Incubadora4.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Aceleradora de Empresas',
            'O Aceleradora de Empresas é o programa do Canastra HUB que impulsiona o crescimento de negócios em fase inicial.',
            [
                'resources/static/img/espacos_hub/incubadora/incubadora1.jpeg',
                'resources/static/img/espacos_hub/incubadora/incubadora2.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Espaço de Empresas Simuladas',
            'O Espaço de Empresas Simuladas é um ambiente de aprendizagem prática voltado à formação empreendedora.',
            [
                'resources/static/img/espacos_hub/incubadora/incubadora5.jpeg',
                'resources/static/img/espacos_hub/incubadora/incubadora6.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Fábrica de Soluções Tecnológicas',
            'A Fábrica de Soluções Tecnológicas é o coração digital do Canastra HUB.',
            [
                'resources/static/img/espacos_hub/fast/fabrica (1).jpeg',
                'resources/static/img/espacos_hub/fast/fabrica (2).jpeg',
                'resources/static/img/espacos_hub/fast/fabrica (3).jpeg',
                'resources/static/img/espacos_hub/fast/fabrica (4).jpeg',
            ],
        )

        self._cria_sala_geral(
            'Espaço de Treinamento e Desenvolvimento',
            'O Espaço de Treinamento e Desenvolvimento é dedicado à capacitação de estudantes, empreendedores e comunidade.',
            [
                'resources/static/img/espacos_hub/desenvolvimento/sala_pc1.jpeg',
                'resources/static/img/espacos_hub/desenvolvimento/sala_pc2.jpeg',
                'resources/static/img/espacos_hub/desenvolvimento/sala_pc3.jpeg',
                'resources/static/img/espacos_hub/desenvolvimento/sala_pc4.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Auditórios',
            'Ambientes estruturados para a realização de atividades formativas, apresentações institucionais e eventos acadêmicos.',
            [
                'resources/static/img/espacos_hub/auditorio/auditorio1.jpeg',
                'resources/static/img/espacos_hub/auditorio/auditorio2.jpeg',
                'resources/static/img/espacos_hub/auditorio/auditorio3.jpeg',
                'resources/static/img/espacos_hub/auditorio/auditorio4.jpeg',
            ],
        )

        self._cria_sala_geral(
            'IF Maker',
            'O IF Maker é o espaço do Canastra HUB voltado à prototipagem, modelagem 3D e experimentação tecnológica.',
            [
                'resources/static/img/espacos_hub/maker/maker1.jpeg',
                'resources/static/img/espacos_hub/maker/maker2.jpeg',
                'resources/static/img/espacos_hub/maker/maker3.jpeg',
                'resources/static/img/espacos_hub/maker/maker4.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Espaço SEBRAE',
            'O Espaço Sebrae é uma área estratégica do Canastra HUB destinada à parceria entre o IFMG e o Sebrae Minas.',
            [
                'resources/static/img/sebrae.png',
                'resources/static/img/espacos_hub/incubadora/sebrae.jpeg',
            ],
        )

        # 4. Usuários e Empresa
        self.stdout.write("4. Criando Usuários e Empresas...")

        # Empresa
        user_empresa = UsuarioBase.objects.filter(
            email='empresa@teste').first()
        if not user_empresa:
            user_empresa = UsuarioBase.objects.create_user(
                email='empresa@teste',
                password='123',
                nome='Roberta Cafes',
                tipo='empresa'
            )

        empresa, _ = Empresa.objects.get_or_create(
            user=user_empresa,
            defaults={
                'nomefantasia': 'Roberta Cafés',
                'tipo_empresa': 'Cafecultura',
                'razao_social': 'Roberta Cafés Ltda',
                'cnpj': '11111111111111',
                'telefone': '(37) 3322-4433',
                'rua': 'Rua José da Silva',
                'cep': '39800000',
                'numero': '443',
                'complemento': 'Sala 11',
                'cidade': cidade,
                'estado': estado,
                'segmento': 'cafe',
            }
        )

        # Admin
        user_admin = UsuarioBase.objects.filter(email='admin@teste').first()
        if not user_admin:
            user_admin = UsuarioBase.objects.create_superuser(
                email='admin@teste',
                password='123',
                nome='admin',
                tipo='admin'
            )

        # Usuário 1 (Perfil Agrícola)
        user1 = UsuarioBase.objects.filter(email='usuario@teste').first()
        if not user1:
            user1 = UsuarioBase.objects.create_user(
                email='usuario@teste',
                password='123',
                nome='Cleiton Romario Santos',
                tipo='usuario'
            )

        usuario1, _ = Usuario.objects.get_or_create(
            user=user1,
            defaults={
                'nome_social': 'Cleiton',
                'data_nascimento': '2002-07-11',
                'genero': 'masculino',
                'estado_civil': 'solteiro',
                'nacionalidade': 'brasileiro',
                'telefone': '(37) 99838-1976',
            }
        )

        endereco1, _ = Endereco.objects.get_or_create(
            cep='39800000',
            rua='Rua das Palmeiras',
            numero='981',
            bairro='Centro',
            cidade=cidade,
            estado=estado,
            defaults={'complemento': 'Apto 12'}
        )
        usuario1.endereco = endereco1

        objetivo1, _ = ProfessionalTarget.objects.get_or_create(
            cargo_pretendido='Operador de Máquinas Agrícolas',
            defaults={
                'area_interesse': 'Agronegócio',
                'disponibilidade': 'Imediata',
                'remoto': False,
                'pretensao_salarial': 2500.00,
            }
        )
        usuario1.objetivo_profissional = objetivo1

        formacao1, _ = AcademyGraduation.objects.get_or_create(
            instituicao_nome='Escola Estadual de Arcos',
            defaults={
                'grau_escolaridade': 'Ensino Médio Completo',
                'situacao_academica': 'Concluído',
                'data_acad_inicio': '2018-02-01',
                'data_acad_fim': '2020-12-15',
            }
        )
        usuario1.formacao_academica = formacao1
        usuario1.save()

        # Competências
        # Competências (Ajustado conforme a estrutura do model Competencia)
        try:
            # Exemplo usando o campo 'nome' ou 'descricao' da model Competencia
            competencia1, _ = Competencia.objects.get_or_create(
                nome='Operação de tratores e colheitadeiras',
                defaults={
                    'tipo': 'técnica'  # Remova ou altere se seu model não tiver este campo
                }
            )
            if hasattr(usuario1, 'competencias'):
                usuario1.competencias.add(competencia1)
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f"Aviso ao criar competência: {e}"))

        social1, _ = SocialMedia.objects.get_or_create(
            linkedin='https://www.linkedin.com/in/cleiton-romario',
            defaults={'instagram': 'cleiton.agro'}
        )
        usuario1.social_media = social1
        usuario1.save()

        Acessibilidade.objects.get_or_create(
            usuario=usuario1,
            defaults={
                'pessoa_com_deficiencia': False,
                'necessidade_adaptacao': None,
            }
        )

        ExperienciaProfissional.objects.get_or_create(
            usuario=usuario1,
            cargo='Auxiliar de Campo',
            nome_empresa='Fazenda São João',
            defaults={
                'data_inicio': '2021-03-01',
                'data_fim': '2023-12-31',
            }
        )

        ExperienciaProfissional.objects.get_or_create(
            usuario=usuario1,
            cargo='Operador de Trator',
            nome_empresa='Cooperativa Agrícola do Oeste',
            defaults={'data_inicio': '2024-01-15'}
        )

        CursoExtraCurricular.objects.get_or_create(
            usuario=usuario1,
            nome_curso='Operação e manutenção de tratores',
            defaults={
                'instituicao': 'SENAR Minas',
                'carga_horaria': 40,
                'data_conclusao': '2022-02-18',
            }
        )

        CursoExtraCurricular.objects.get_or_create(
            usuario=usuario1,
            nome_curso='Segurança do trabalho rural',
            defaults={
                'instituicao': 'SENAR Minas',
                'carga_horaria': 20,
                'data_conclusao': '2022-06-24',
            }
        )

        Idioma.objects.filter(usuario=usuario1).delete()
        Idioma.objects.bulk_create([
            Idioma(usuario=usuario1, language='Português', fluency='Avançado'),
            Idioma(usuario=usuario1, language='Inglês', fluency='Básico'),
        ])

        InteresseCompra.objects.get_or_create(
            usuario=usuario1,
            categoria_interesse='Café',
            defaults={
                'descricao_interesse': 'Procuro café arábica de produtor local para revenda',
                'preco_maximo': 60.00,
            }
        )

        # Usuário 2 (Perfil Desenvolvedor)
        user2 = UsuarioBase.objects.filter(email='usuario1@teste').first()
        if not user2:
            user2 = UsuarioBase.objects.create_user(
                email='usuario1@teste',
                password='123',
                nome='Romario Santos',
                tipo='usuario'
            )

        usuario2, _ = Usuario.objects.get_or_create(
            user=user2,
            defaults={
                'nome_social': 'Romario',
                'data_nascimento': '2003-04-22',
                'genero': 'masculino',
                'estado_civil': 'solteiro',
                'nacionalidade': 'brasileiro',
                'telefone': '(37) 98765-4321',
            }
        )

        endereco2, _ = Endereco.objects.get_or_create(
            cep='39800000',
            rua='Av. Brasil',
            numero='200',
            bairro='Jardim América',
            cidade=cidade,
            estado=estado,
        )
        usuario2.endereco = endereco2

        objetivo2, _ = ProfessionalTarget.objects.get_or_create(
            cargo_pretendido='Desenvolvedor de Software',
            defaults={
                'area_interesse': 'Tecnologia da Informação',
                'disponibilidade': 'Imediata',
                'remoto': True,
                'pretensao_salarial': 3000.00,
            }
        )
        usuario2.objetivo_profissional = objetivo2
        usuario2.save()

        Idioma.objects.filter(usuario=usuario2).delete()
        Idioma.objects.bulk_create([
            Idioma(usuario=usuario2, language='Inglês',
                   fluency='Intermediário'),
        ])

        InteresseCompra.objects.get_or_create(
            usuario=usuario2,
            categoria_interesse='Tecnologia',
            defaults={
                'descricao_interesse': 'Interessado em soluções de automação e sensores para agricultura',
            }
        )

        # Usuário Marco
        user_marco = UsuarioBase.objects.filter(
            email='m.tulio.m.carvalho@gmail.com').first()
        if not user_marco:
            user_marco = UsuarioBase.objects.create_user(
                email='m.tulio.m.carvalho@gmail.com',
                password='123',
                nome='Marco Tulio Carvalho',
                tipo='usuario'
            )

        # 5. Vínculos e Produtos
        self.stdout.write("5. Criando Vínculos Empresa x Hub e Produtos...")
        EmpresaHub.objects.get_or_create(empresa=empresa, hub=hub1)
        EmpresaHub.objects.get_or_create(empresa=empresa, hub=hub6)

        produto1, _ = Produto.objects.get_or_create(
            empresa=empresa,
            nome_produto='Café Arábica Especial',
            defaults={
                'categoria_produto': 'Café',
                'descricao_produto': 'Café arábica torrado artesanalmente, produzido na região da Canastra',
                'preco_produto': 45.90,
                'quantidade_disponivel': 200,
            }
        )

        produto2, _ = Produto.objects.get_or_create(
            empresa=empresa,
            nome_produto='Mel Silvestre da Canastra',
            defaults={
                'categoria_produto': 'Apicultura',
                'descricao_produto': 'Mel puro produzido por apicultores parceiros da região da Canastra',
                'preco_produto': 25.00,
                'quantidade_disponivel': 150,
            }
        )

        # 6. Notícias
        self.stdout.write("6. Criando Notícias...")
        caminho_agro1 = settings.BASE_DIR / 'resources' / \
            'static' / 'img' / 'hubs' / 'noticia_agro_1.png'
        if caminho_agro1.exists():
            with open(caminho_agro1, 'rb') as f:
                noticia_agro_1, _ = Noticia.objects.get_or_create(
                    titulo_noticia='Minas Gerais lidera ranking dos melhores cafés do Brasil em 2025',
                    defaults={
                        'descricao_noticia': 'Produtores mineiros conquistaram as três categorias do Cup of Excellence.',
                        'fonte': 'Paloma Santos',
                        'url': 'https://agro.estadao.com.br/agricultura/minas-gerais-lidera-ranking-dos-melhores-cafes-do-brasil-em-2025',
                        'isActive': True,
                        'isHome': False,
                        'imagem_noticia': File(f, name=caminho_agro1.name)
                    }
                )
                NoticiaHub.objects.get_or_create(
                    noticia=noticia_agro_1, hub=hub1)

        caminho_agro2 = settings.BASE_DIR / 'resources' / \
            'static' / 'img' / 'hubs' / 'noticia_agro_2.jpeg'
        if caminho_agro2.exists():
            with open(caminho_agro2, 'rb') as f:
                noticia_agro_2, _ = Noticia.objects.get_or_create(
                    titulo_noticia='O futuro sustentável do agronegócio passa pela boa gestão',
                    defaults={
                        'descricao_noticia': 'No Brasil, anualmente, os dados econômicos demonstram que o agro permanece no centro da economia.',
                        'fonte': 'André Paranhos',
                        'url': 'https://globorural.globo.com/google/amp/opiniao/vozes-do-agro/noticia/2025/11/o-futuro-sustentavel-do-agronegocio-passa-pela-boa-gestao.ghtml',
                        'isActive': True,
                        'isHome': True,
                        'imagem_noticia': File(f, name=caminho_agro2.name)
                    }
                )
                NoticiaHub.objects.get_or_create(
                    noticia=noticia_agro_2, hub=hub1)

        caminho_grao1 = settings.BASE_DIR / 'resources' / 'static' / \
            'img' / 'hubs' / 'graos' / 'noticia_graos1.png'
        if caminho_grao1.exists():
            with open(caminho_grao1, 'rb') as f:
                noticia_grao_1, _ = Noticia.objects.get_or_create(
                    titulo_noticia='A jornada dos grãos pelo Tapajós rumo ao mercado externo',
                    defaults={
                        'descricao_noticia': 'Reportagem viajou em empurrador e acompanhou transporte de grãos pela hidrovia',
                        'fonte': 'Raphael Salomão',
                        'url': 'https://globorural.globo.com/google/amp/especiais/caminhos-da-safra/noticia/2025/11/a-jornada-dos-graos-pelo-tapajos-rumo-ao-mercado-externo.ghtml',
                        'isActive': True,
                        'isHome': True,
                        'imagem_noticia': File(f, name=caminho_grao1.name)
                    }
                )
                NoticiaHub.objects.get_or_create(
                    noticia=noticia_grao_1, hub=hub6)

        caminho_milho1 = settings.BASE_DIR / 'resources' / \
            'static' / 'img' / 'hubs' / 'noticia_milho_1.png'
        if caminho_milho1.exists():
            with open(caminho_milho1, 'rb') as f:
                noticia_milho_1, _ = Noticia.objects.get_or_create(
                    titulo_noticia='Plantio do milho segunda safra avança com chegada de chuvas',
                    defaults={
                        'descricao_noticia': 'Condições climáticas favoráveis impulsionam o avanço do plantio da segunda safra de milho no Centro-Oeste.',
                        'fonte': 'G1 Sorocaba',
                        'url': 'https://g1.globo.com/sp/sorocaba-jundiai/nosso-campo/noticia/2025/11/09/plantio-do-milho-segunda-safra-avanca-com-chegada-de-chuvas.ghtml',
                        'isActive': True,
                        'isHome': False,
                        'imagem_noticia': File(f, name=caminho_milho1.name)
                    }
                )
                NoticiaHub.objects.get_or_create(
                    noticia=noticia_milho_1, hub=hub4)

        # 7. Vagas
        self.stdout.write("7. Criando Vagas...")
        vaga1, _ = Vagas.objects.get_or_create(
            cargo_vaga='Operador de Máquinas Agrícolas',
            empresa=empresa,
            defaults={
                'descricao_vaga': 'Responsável por operar tratores, colheitadeiras e outros equipamentos agrícolas durante o plantio e a colheita.',
                'requisito_vaga': 'Experiência comprovada na operação de máquinas agrícolas e conhecimento básico em manutenção preventiva.',
                'local': 'Fazenda Primavera',
                'status': 'ativa',
                'anos_experiencia_req': 2.0,
                'nivel_formacao_req': 3,
            }
        )

        vaga2, _ = Vagas.objects.get_or_create(
            cargo_vaga='Desenvolvedor Júnior',
            empresa=empresa,
            defaults={
                'descricao_vaga': 'Estamos em busca de um Desenvolvedor Júnior motivado e comprometido para integrar nossa equipe de tecnologia.',
                'requisito_vaga': 'Conhecimento básico em linguagens de programação como Python, JavaScript ou Java.',
                'local': 'Home Office',
                'status': 'ativa',
                'anos_experiencia_req': 0.0,
                'nivel_formacao_req': 5,
            }
        )
        CursoVaga.objects.get_or_create(
            vaga=vaga2, curso='Ciência da Computação')
        CursoVaga.objects.get_or_create(
            vaga=vaga2, curso='Sistemas de Informação')

        vaga3, _ = Vagas.objects.get_or_create(
            cargo_vaga='Apicultor',
            empresa=empresa,
            defaults={
                'descricao_vaga': 'Estamos em busca de um profissional dedicado para atuar no manejo de colmeias.',
                'requisito_vaga': 'Experiência com manejo de abelhas ou interesse em aprender sobre apicultura.',
                'local': 'Fazenda Mel da Canastra',
                'status': 'ativa',
                'anos_experiencia_req': 1.0,
                'nivel_formacao_req': 3,
            }
        )

        # Candidaturas
        UsuarioVaga.objects.get_or_create(vaga=vaga1, usuario=usuario1)

        UsuarioVaga.objects.get_or_create(
            vaga=vaga2,
            usuario=usuario1,
            defaults={
                'status': UsuarioVaga.STATUS_CONTRATADO,
                'data_status': timezone.now(),
                'ifmg_no_momento_contratacao': getattr(usuario1, 'ifmg', False),
            }
        )

        UsuarioVaga.objects.get_or_create(
            vaga=vaga3,
            usuario=usuario1,
            defaults={
                'status': UsuarioVaga.STATUS_REJEITADO,
                'data_status': timezone.now(),
                'ifmg_no_momento_contratacao': getattr(usuario1, 'ifmg', False),
            }
        )

        # 8. Eventos e Treinamentos
        self.stdout.write("8. Criando Eventos e Treinamentos...")
        evento1, _ = Evento.objects.get_or_create(
            nome_evento='Feira do Café da Canastra',
            defaults={
                'data_evento_inicio': '2026-09-10',
                'data_evento_fim': '2026-09-10',
                'horario_evento': '09:00',
                'local_evento': 'Fazenda Primavera',
                'publico_evento': 'Produtores e público geral',
                'descricao_evento': 'Exposição e degustação dos melhores cafés da região da Canastra.',
                'vagas_disponiveis': 100,
                'hub': hub1
            }
        )

        evento2, _ = Evento.objects.get_or_create(
            nome_evento='Encontro do Milho',
            defaults={
                'data_evento_inicio': '2026-10-05',
                'data_evento_fim': '2026-10-05',
                'horario_evento': '14:00',
                'local_evento': 'Hub Milho',
                'publico_evento': 'Produtores de milho',
                'descricao_evento': 'Encontro anual sobre novas técnicas de cultivo de milho.',
                'vagas_disponiveis': 50,
                'hub': hub4
            }
        )

        InscricaoEvento.objects.get_or_create(evento=evento1, usuario=user1)

        treinamento1, _ = Treinamento.objects.get_or_create(
            nome='Boas Práticas em Apicultura',
            defaults={
                'data_inicio': '2026-09-20',
                'data_fim': '2026-09-20',
                'local': 'Fazenda Mel da Canastra',
                'publico_alvo': 'Apicultores',
                'descricao': 'Treinamento sobre manejo de colmeias e extração de mel.',
                'vagas_disponiveis': 30,
                'hub': hub6
            }
        )

        SessaoTreinamento.objects.get_or_create(
            treinamento=treinamento1,
            defaults={'data': '2026-09-20', 'horario': '08:00'}
        )

        treinamento2, _ = Treinamento.objects.get_or_create(
            nome='Manutenção de Máquinas Agrícolas',
            defaults={
                'data_inicio': '2026-11-02',
                'data_fim': '2026-11-03',
                'local': 'Fazenda Primavera',
                'publico_alvo': 'Operadores de máquinas',
                'descricao': 'Curso prático de manutenção preventiva de tratores e colheitadeiras.',
                'vagas_disponiveis': 20,
                'hub': hub1
            }
        )

        SessaoTreinamento.objects.get_or_create(
            treinamento=treinamento2,
            defaults={'data': '2026-11-02', 'horario': '13:00'}
        )

        InscricaoTreinamento.objects.get_or_create(
            treinamento=treinamento1, usuario=user1)

        self.stdout.write(self.style.SUCCESS(
            "✅ Sistema inicializado com sucesso!"))
