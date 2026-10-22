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
from matching.models import HubMatchScore, MatchScore, ProdutoMatch
from matching.signals import _upsert_hub_scores_for_usuario, _upsert_scores_for_usuario


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

    def _cria_empresa(self, email, nome, cidade, hubs, **dados):
        user = UsuarioBase.objects.filter(email=email).first()
        if user:
            empresa_existente = Empresa.objects.filter(user=user).first()
            if empresa_existente:
                return empresa_existente
        else:
            user = UsuarioBase.objects.create_user(
                email=email, password='123', nome=nome, tipo='empresa'
            )
        empresa = Empresa.objects.create(
            user=user,
            cidade=cidade,
            estado=cidade.estado_cidade,
            **dados,
        )
        for hub in hubs:
            EmpresaHub.objects.get_or_create(empresa=empresa, hub=hub)
        return empresa

    def _cria_usuario(self, email, nome, cidade, perfil, objetivo, formacao=None,
                      competencias_tecnicas=(), competencias_comportamentais=(),
                      hobbies=(), experiencias=(), cursos=(), idiomas=(), social=None):
        """Cria um Usuario completo sem duplicar perfis em execuções repetidas."""
        user = UsuarioBase.objects.filter(email=email).first()
        if user:
            usuario_existente = Usuario.objects.filter(user=user).first()
            if usuario_existente:
                return usuario_existente
        else:
            user = UsuarioBase.objects.create_user(
                email=email, password='123', nome=nome, tipo='usuario'
            )
        usuario = Usuario.objects.create(
            user=user,
            endereco=Endereco.objects.create(
                cep='39800000',
                rua=perfil.pop('rua'),
                numero=perfil.pop('numero'),
                bairro='Centro',
                cidade=cidade,
                estado=cidade.estado_cidade,
            ),
            objetivo_profissional=ProfessionalTarget.objects.create(**objetivo),
            formacao_academica=AcademyGraduation.objects.create(**formacao) if formacao else None,
            social_media=SocialMedia.objects.create(**(social or {})),
            **perfil,
        )
        usuario.competencias.add(
            *[Competencia.objects.get_or_create(nome_competencia=nome_c, tipo_competencia='tecnica')[0]
              for nome_c in competencias_tecnicas],
            *[Competencia.objects.get_or_create(nome_competencia=nome_c, tipo_competencia='comportamental')[0]
              for nome_c in competencias_comportamentais],
        )
        usuario.interesses_hobbies.add(
            *[Hobby.objects.get_or_create(nome_hobby=nome_h)[0] for nome_h in hobbies]
        )
        Acessibilidade.objects.create(usuario=usuario, pessoa_com_deficiencia=False)
        for exp in experiencias:
            ExperienciaProfissional.objects.create(usuario=usuario, **exp)
        for curso in cursos:
            CursoExtraCurricular.objects.create(usuario=usuario, **curso)
        for language, fluency in idiomas:
            Idioma.objects.create(usuario=usuario, language=language, fluency=fluency)
        return usuario

    def handle(self, *args, **options):
        
        # 1. Populando Estados e Cidades
        self.stdout.write("1. Populando Estados e Cidades...")
        json_path = (
            settings.BASE_DIR
            / "resources"
            / "static"
            / "json"
            / "estados-cidades.json"
        )

        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                dados = json.load(f)

            for estado_data in dados["estados"]:
                try:
                    estado, _ = Estado.objects.get_or_create(
                        nome_estado=estado_data["nome"],
                        sigla_estado=estado_data["sigla"],
                    )

                    cidades_objs = []
                    for nome_cidade in estado_data["cidades"]:
                        _, cidade_created = Cidade.objects.get_or_create(
                            nome_cidade=nome_cidade,
                            estado_cidade=estado,
                        )
                        if cidade_created:
                            cidades_objs.append(nome_cidade)

                    if cidades_objs:
                        self.stdout.write(
                            f"  - Inserido estado {estado.nome_estado} "
                            f"com {len(cidades_objs)} cidades novas."
                        )
                except Exception as e:
                    self.stdout.write(
                        f"Erro ao inserir {estado_data['nome']}: {e}"
                    )
        else:
            self.stdout.write(
                f"Arquivo de estados e cidades não encontrado: {json_path}"
            )

        cidade = Cidade.objects.filter(nome_cidade="Arcos").first()
        if not cidade:
            cidade = Cidade.objects.first()

        estado = cidade.estado_cidade if cidade else None

        # 2. Hubs
        self.stdout.write("2. Criando Hubs...")

        hubs_config = [
            {
                "nome": "Agro",
                "imagem": "agro_hub.jpg",
                "descricao": "Agro é melhor com o pessoal da canastra",
                "area": (
                    "Agronegócio, cafeicultura, produção rural "
                    "e comercialização de alimentos"
                ),
                "tecnologias": (
                    "Agricultura de precisão, sensores IoT, "
                    "gestão agrícola digital"
                ),
            },
            {
                "nome": "Milho",
                "imagem": "milho_hub.jpg",
                "descricao": "Milho é melhor com o pessoal da canastra",
                "area": "Produção de milho, grãos e insumos agrícolas",
                "tecnologias": (
                    "Sementes geneticamente melhoradas, "
                    "maquinário agrícola"
                ),
            },
            {
                "nome": "Grãos",
                "imagem": "graos_hub.jpg",
                "descricao": "Grãos é melhor com o pessoal da canastra",
                "area": (
                    "Comercialização de grãos, logística agrícola "
                    "e exportação"
                ),
                "tecnologias": (
                    "Armazenagem, transporte, rastreabilidade da produção"
                ),
            },
        ]

        for config in hubs_config:
            hub, created = Hub.objects.get_or_create(
                nome_hub=config["nome"],
                defaults={
                    "descricao_hub": config["descricao"],
                    "area_foco_hub": config["area"],
                    "tecnologias_hub": config["tecnologias"],
                },
            )

            imagem_path = (
                settings.BASE_DIR
                / "media"
                / "fotos_hub"
                / config["imagem"]
            )

            if created and imagem_path.exists():
                with open(imagem_path, "rb") as f:
                    hub.foto_hub.save(
                        imagem_path.name,
                        File(f),
                        save=True,
                    )


        # Referências usadas pelos dados de demonstração do matching.
        hub1 = Hub.objects.get(nome_hub="Agro")
        hub4 = Hub.objects.get(nome_hub="Milho")
        hub6 = Hub.objects.get(nome_hub="Grãos")

        # 3. Salas Gerais
        self.stdout.write("3. Criando Salas e Espaços...")
        self._cria_sala_geral(
            "Incubadora de Empresas e Startups",
            "A Incubadora de Empresas e Startups é o núcleo que dá origem "
            "ao próprio Canastra HUB. Ela oferece suporte técnico, "
            "orientação gerencial e infraestrutura física a empreendedores "
            "e estudantes que buscam desenvolver negócios inovadores.",

            [
                'resources/static/img/espacos_hub/incubadora/incubadora3.jpeg',
                'resources/static/img/espacos_hub/incubadora/Incubadora4.jpeg',
            ],
    )

        self._cria_sala_geral(
            'Aceleradora de Empresas',
            'Programa que ajuda negócios em fase inicial a crescer mais rápido. Com apoio do SEBRAE e de '
            'mentores do setor produtivo, oferece capacitações, mentorias e conexões estratégicas para que '
            'empresas incubadas e startups validem seu modelo de negócio, ampliem a rede de contatos e '
            'alcancem sustentabilidade financeira.',
            [
                'resources/static/img/espacos_hub/incubadora/incubadora1.jpeg',
                'resources/static/img/espacos_hub/incubadora/incubadora2.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Espaço de Empresas Simuladas',
            'Ambiente de aprendizagem prática em que estudantes conduzem empresas simuladas. Eles aplicam '
            'gestão, marketing, contabilidade e produção em situações próximas às do mercado e se preparam '
            'para atuar em empresas juniores, startups e empreendimentos incubados.',
            [
                'resources/static/img/espacos_hub/incubadora/incubadora5.jpeg',
                'resources/static/img/espacos_hub/incubadora/incubadora6.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Fábrica de Soluções Tecnológicas',
            'O núcleo de desenvolvimento de software do Canastra HUB. Uma equipe de estudantes, professores '
            'e técnicos cria sistemas, aplicativos e plataformas para demandas da região, com foco em '
            'agronegócio, alimentos e sustentabilidade. O trabalho segue métodos ágeis, como Scrum e Design '
            'Thinking.',
            [
                'resources/static/img/espacos_hub/fast/fabrica (1).jpeg',
                'resources/static/img/espacos_hub/fast/fabrica (2).jpeg',
                'resources/static/img/espacos_hub/fast/fabrica (3).jpeg',
                'resources/static/img/espacos_hub/fast/fabrica (4).jpeg',
            ],
        )

        self._cria_sala_geral(
            'Espaço de Treinamento e Desenvolvimento',
            'Espaço dedicado à capacitação de estudantes, empreendedores e comunidade. Com salas equipadas, '
            'auditórios e recursos multimídia, recebe cursos, workshops, hackathons e mentorias sobre '
            'inovação, liderança e empreendedorismo.',
            [
                'resources/static/img/espacos_hub/desenvolvimento/sala_pc1.jpeg',
                'resources/static/img/espacos_hub/desenvolvimento/sala_pc2.jpeg',
                'resources/static/img/espacos_hub/desenvolvimento/sala_pc3.jpeg',
                'resources/static/img/espacos_hub/desenvolvimento/sala_pc4.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Auditórios',
            'Auditórios preparados para palestras, defesas, workshops, apresentações institucionais e '
            'eventos acadêmicos. Recebem os encontros promovidos pelo HUB e aproximam pessoas de diferentes '
            'áreas em torno do conhecimento e do empreendedorismo.',
            [
                'resources/static/img/espacos_hub/auditorio/auditorio1.jpeg',
                'resources/static/img/espacos_hub/auditorio/auditorio2.jpeg',
                'resources/static/img/espacos_hub/auditorio/auditorio3.jpeg',
                'resources/static/img/espacos_hub/auditorio/auditorio4.jpeg',
            ],
        )

        self._cria_sala_geral(
            'IF Maker',
            'Laboratório de prototipagem do Canastra HUB. Com impressoras 3D, cortadoras a laser e '
            'fresadoras CNC, permite que estudantes e empreendedores modelem, construam e testem protótipos '
            'antes de chegar ao produto final. Apoia os projetos da Fábrica de Soluções e das empresas '
            'juniores.',
            [
                'resources/static/img/espacos_hub/maker/maker1.jpeg',
                'resources/static/img/espacos_hub/maker/maker2.jpeg',
                'resources/static/img/espacos_hub/maker/maker3.jpeg',
                'resources/static/img/espacos_hub/maker/maker4.jpeg',
            ],
        )

        self._cria_sala_geral(
            'Espaço SEBRAE',
            'Fruto da parceria entre o IFMG e o Sebrae Minas. Oferece atendimento, consultoria e programas '
            'de capacitação para empreendedores, startups e pequenos negócios, além de acesso a mentorias '
            'especializadas, editais de fomento e oportunidades de networking.',
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

        # --- Usuários extras: perfis variados para exercitar o matching ---
        # Cada perfil foi pensado para casar com uma vaga/hub específico (ver
        # MATCH_ESPERADO no fim do comando).
        usuario4 = self._cria_usuario(
            email='agronoma@teste',
            nome='Ana Paula Ribeiro',
            cidade=Cidade.objects.get(nome_cidade='Bambuí', estado_cidade__sigla_estado='MG'),
            perfil=dict(
                nome_social='Ana Paula', data_nascimento='1998-03-15', genero='feminino',
                estado_civil='solteira', nacionalidade='brasileira', telefone='(37) 99911-2233',
                ifmg=True, rua='Rua do Cerrado', numero='120',
            ),
            objetivo=dict(
                cargo_pretendido='Engenheira Agrônoma', area_interesse='Agronomia e produção de grãos',
                disponibilidade='Imediata', remoto=False, pretensao_salarial=6500.00,
            ),
            formacao=dict(
                instituicao_nome='IFMG Campus Bambuí', grau_escolaridade='Bacharelado',
                curso_graduacao='Agronomia', situacao_academica='Concluído',
                data_acad_inicio='2016-02-01', data_acad_fim='2020-12-15',
            ),
            competencias_tecnicas=[
                'Manejo e análise de solo', 'Agricultura de precisão',
                'Planejamento de safra de milho e soja', 'Georreferenciamento (QGIS)',
            ],
            competencias_comportamentais=['Liderança de equipes de campo', 'Comunicação com produtores'],
            hobbies=['Trilhas na Serra da Canastra', 'Fotografia'],
            experiencias=[
                dict(cargo='Estagiária de Extensão Rural', nome_empresa='EMATER-MG',
                     data_inicio='2019-07-01', data_fim='2020-12-15'),
                dict(cargo='Engenheira Agrônoma Júnior', nome_empresa='Cooperativa Agrícola do Oeste',
                     data_inicio='2021-02-01'),
            ],
            cursos=[
                dict(nome_curso='Agricultura de precisão com drones', instituicao='Embrapa',
                     carga_horaria=60, data_conclusao='2022-08-10'),
            ],
            idiomas=[('Português', 'Nativo'), ('Inglês', 'Avançado'), ('Espanhol', 'Intermediário')],
            social=dict(linkedin='https://www.linkedin.com/in/ana-ribeiro-agro'),
        )

        usuario5 = self._cria_usuario(
            email='apicultor@teste',
            nome='Lucas Ferreira Lima',
            cidade=Cidade.objects.get(nome_cidade='São Roque de Minas', estado_cidade__sigla_estado='MG'),
            perfil=dict(
                nome_social='Lucas', data_nascimento='1995-09-02', genero='masculino',
                estado_civil='casado', nacionalidade='brasileiro', telefone='(37) 99822-4455',
                rua='Estrada da Canastra', numero='15',
            ),
            objetivo=dict(
                cargo_pretendido='Apicultor', area_interesse='Apicultura e produção de mel',
                disponibilidade='Imediata', remoto=False, pretensao_salarial=2300.00,
            ),
            formacao=dict(
                instituicao_nome='Escola Estadual São Roque', grau_escolaridade='Ensino Médio Completo',
                situacao_academica='Concluído', data_acad_fim='2013-12-10',
            ),
            competencias_tecnicas=[
                'Manejo de colmeias e captura de enxames', 'Extração, filtragem e envase de mel',
                'Controle sanitário de apiários',
            ],
            competencias_comportamentais=['Paciência e atenção a detalhes'],
            hobbies=['Jardinagem', 'Pesca'],
            experiencias=[
                dict(cargo='Auxiliar de Apiário', nome_empresa='Apiário Serra Alta',
                     data_inicio='2018-03-01', data_fim='2022-06-30'),
                dict(cargo='Apicultor', nome_empresa='Mel da Canastra', data_inicio='2022-07-01'),
            ],
            cursos=[
                dict(nome_curso='Apicultura básica', instituicao='SENAR Minas',
                     carga_horaria=40, data_conclusao='2017-11-20'),
            ],
            idiomas=[('Português', 'Nativo')],
        )

        usuario6 = self._cria_usuario(
            email='logistica@teste',
            nome='Juliana Costa Mendes',
            cidade=Cidade.objects.get(nome_cidade='Formiga', estado_cidade__sigla_estado='MG'),
            perfil=dict(
                nome_social='Juliana', data_nascimento='1997-11-28', genero='feminino',
                estado_civil='solteira', nacionalidade='brasileira', telefone='(37) 99733-6677',
                rua='Av. Getúlio Vargas', numero='870',
            ),
            objetivo=dict(
                cargo_pretendido='Analista de Logística', area_interesse='Logística e armazenagem de grãos',
                disponibilidade='30 dias', remoto=False, pretensao_salarial=4200.00,
            ),
            formacao=dict(
                instituicao_nome='UNIFOR-MG', grau_escolaridade='Tecnólogo',
                curso_graduacao='Logística', situacao_academica='Concluído',
                data_acad_inicio='2016-02-01', data_acad_fim='2018-12-10',
            ),
            competencias_tecnicas=[
                'Gestão de estoques e armazenagem', 'Roteirização de transporte de cargas',
                'Excel avançado', 'SAP MM',
            ],
            competencias_comportamentais=['Organização', 'Negociação com fornecedores'],
            hobbies=['Corrida de rua'],
            experiencias=[
                dict(cargo='Assistente de Logística', nome_empresa='Armazéns Gerais Formiga',
                     data_inicio='2019-01-15', data_fim='2022-03-31'),
                dict(cargo='Analista de Logística Júnior', nome_empresa='Transportadora Oeste Minas',
                     data_inicio='2022-04-01'),
            ],
            idiomas=[('Português', 'Nativo'), ('Inglês', 'Básico')],
        )

        usuario7 = self._cria_usuario(
            email='dev@teste',
            nome='Pedro Henrique Alves',
            cidade=Cidade.objects.get(nome_cidade='Bambuí', estado_cidade__sigla_estado='MG'),
            perfil=dict(
                nome_social='Pedro', data_nascimento='2000-01-20', genero='masculino',
                estado_civil='solteiro', nacionalidade='brasileiro', telefone='(37) 99644-8899',
                ifmg=True, rua='Rua dos Estudantes', numero='45',
            ),
            objetivo=dict(
                cargo_pretendido='Desenvolvedor Python/Django', area_interesse='Desenvolvimento de software',
                disponibilidade='Imediata', remoto=True, pretensao_salarial=5500.00,
            ),
            formacao=dict(
                instituicao_nome='IFMG Campus Bambuí', grau_escolaridade='Bacharelado',
                curso_graduacao='Sistemas de Informação', situacao_academica='Concluído',
                data_acad_inicio='2018-02-01', data_acad_fim='2022-12-15',
            ),
            competencias_tecnicas=[
                'Python e Django', 'APIs REST', 'PostgreSQL', 'Docker', 'JavaScript e React',
            ],
            competencias_comportamentais=['Trabalho em equipe ágil (Scrum)', 'Resolução de problemas'],
            hobbies=['Robótica', 'Programação de jogos'],
            experiencias=[
                dict(cargo='Estagiário de Desenvolvimento', nome_empresa='Fábrica de Soluções Tecnológicas IFMG',
                     data_inicio='2021-03-01', data_fim='2022-12-15'),
                dict(cargo='Desenvolvedor Python Júnior', nome_empresa='AgroSoft Sistemas',
                     data_inicio='2023-02-01'),
            ],
            cursos=[
                dict(nome_curso='Django REST Framework', instituicao='Alura',
                     carga_horaria=30, data_conclusao='2022-05-30'),
                dict(nome_curso='Docker para desenvolvedores', instituicao='Udemy',
                     carga_horaria=20, data_conclusao='2023-08-15'),
            ],
            idiomas=[('Português', 'Nativo'), ('Inglês', 'Avançado')],
            social=dict(github='https://github.com/pedro-alves-dev'),
        )

        usuario8 = self._cria_usuario(
            email='barista@teste',
            nome='Beatriz Moreira Souza',
            cidade=Cidade.objects.get(nome_cidade='Piumhi', estado_cidade__sigla_estado='MG'),
            perfil=dict(
                nome_social='Beatriz', data_nascimento='1999-06-10', genero='feminino',
                estado_civil='solteira', nacionalidade='brasileira', telefone='(37) 99555-1122',
                rua='Rua do Café', numero='300',
            ),
            objetivo=dict(
                cargo_pretendido='Classificadora de Café', area_interesse='Cafeicultura e cafés especiais',
                disponibilidade='Imediata', remoto=False, pretensao_salarial=3200.00,
            ),
            formacao=dict(
                instituicao_nome='IFMG Campus Bambuí', grau_escolaridade='Técnico',
                curso_graduacao='Cafeicultura', situacao_academica='Concluído',
                data_acad_inicio='2017-02-01', data_acad_fim='2018-12-10',
            ),
            competencias_tecnicas=[
                'Classificação física de grãos de café', 'Prova de xícara (cupping) SCA',
                'Torra de café especial',
            ],
            competencias_comportamentais=['Atendimento ao cliente'],
            hobbies=['Culinária', 'Fotografia'],
            experiencias=[
                dict(cargo='Barista', nome_empresa='Cafeteria Grão Mineiro',
                     data_inicio='2019-02-01', data_fim='2021-08-31'),
                dict(cargo='Auxiliar de Classificação de Café', nome_empresa='Cooxupé',
                     data_inicio='2021-09-01'),
            ],
            cursos=[
                dict(nome_curso='Q-Grader Arábica (preparatório)', instituicao='SENAR Minas',
                     carga_horaria=80, data_conclusao='2023-04-28'),
            ],
            idiomas=[('Português', 'Nativo'), ('Inglês', 'Intermediário')],
        )


        empresa_tech = self._cria_empresa(
            email='tech@teste',
            nome='Canastra Tech',
            cidade=Cidade.objects.get(nome_cidade='Bambuí', estado_cidade__sigla_estado='MG'),
            hubs=[hub1],
            nomefantasia='Canastra Tech Soluções',
            tipo_empresa='Tecnologia',
            razao_social='Canastra Tech Soluções em Software Ltda',
            cnpj='22222222222222',
            telefone='(37) 3431-5566',
            rua='Rua Inovação',
            cep='38900000',
            numero=50,
            segmento='tecnologia',
        )
        Produto.objects.get_or_create(
            empresa=empresa_tech,
            nome_produto='Sensor IoT de Umidade do Solo',
            categoria_produto='Tecnologia',
            descricao_produto='Sensor sem fio para monitoramento de umidade e temperatura do solo, com automação de irrigação',
            preco_produto=890.00,
            quantidade_disponivel=40,
        )
        Produto.objects.get_or_create(
            empresa=empresa_tech,
            nome_produto='Plataforma de Gestão Agrícola',
            categoria_produto='Software',
            descricao_produto='Sistema web para gestão de safra, custos de produção e rastreabilidade da fazenda',
            preco_produto=199.00,
            quantidade_disponivel=999,
        )

        empresa_graos = self._cria_empresa(
            email='graos@teste',
            nome='Grãos do Oeste',
            cidade=Cidade.objects.get(nome_cidade='Formiga', estado_cidade__sigla_estado='MG'),
            hubs=[hub4, hub6],
            nomefantasia='Grãos do Oeste Armazéns',
            tipo_empresa='Armazenagem e comércio de grãos',
            razao_social='Grãos do Oeste Armazéns Gerais Ltda',
            cnpj='33333333333333',
            telefone='(37) 3321-7788',
            rua='Rodovia MG-050',
            cep='35570000',
            numero=1200,
            segmento='graos',
        )
        Produto.objects.get_or_create(
            empresa=empresa_graos,
            nome_produto='Milho em Grão a Granel',
            categoria_produto='Grãos',
            descricao_produto='Milho amarelo seco e classificado, vendido a granel para ração e indústria',
            preco_produto=75.00,
            quantidade_disponivel=5000,
        )
        Produto.objects.get_or_create(
            empresa=empresa_graos,
            nome_produto='Sementes de Milho Híbrido',
            categoria_produto='Insumos agrícolas',
            descricao_produto='Sementes de milho híbrido de alta produtividade, tratadas e certificadas',
            preco_produto=520.00,
            quantidade_disponivel=300,
        )


        caminho_agro_noticia_3 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'noticia_agro_3.png'
        if caminho_agro_noticia_3.exists() and not Noticia.objects.filter(titulo_noticia='MG lança certificação para produtores que adotam agricultura regenerativa').exists():
            with open(caminho_agro_noticia_3, 'rb') as f:
                noticia_agro_3 = Noticia.objects.create(
                    titulo_noticia='MG lança certificação para produtores que adotam agricultura regenerativa',
                    descricao_noticia='Reconhecimento integra o programa Certifica Minas e estará disponível a partir de 2026.',
                    fonte='Redação Agro Estadão',
                    url='https://agro.estadao.com.br/sustentabilidade/mg-lanca-certificacao-para-produtores-que-adotam-agricultura-regenerativa',
                    isActive=True,
                    isHome=False,
                    imagem_noticia=File(f, name=caminho_agro_noticia_3.name)
                )
            NoticiaHub.objects.create(noticia=noticia_agro_3, hub=hub1)

        caminho_grao_noticia_2 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'graos' / 'noticia_graos2.png'
        if caminho_grao_noticia_2.exists() and not Noticia.objects.filter(titulo_noticia='Feijão: Exportações seguem registrando desempenho recorde').exists():
            with open(caminho_grao_noticia_2, 'rb') as f:
                noticia_grao_2 = Noticia.objects.create(
                    titulo_noticia='Feijão: Exportações seguem registrando desempenho recorde',
                    descricao_noticia='As exportações brasileiras de feijão seguem registrando um desempenho recorde, tanto no volume mensal quanto no acumulado de 12 meses.',
                    fonte='Sociedade Nacional de Agricultura',
                    url='https://sna.agr.br/feijao-exportacoes-seguem-registrando-desempenho-recorde/',
                    isActive=True,
                    isHome=False,
                    imagem_noticia=File(f, name=caminho_grao_noticia_2.name)
                )
            NoticiaHub.objects.create(noticia=noticia_grao_2, hub=hub6)

        caminho_grao_noticia_3 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'graos' / 'noticia_graos3.png'
        if caminho_grao_noticia_3.exists() and not Noticia.objects.filter(titulo_noticia='SIC 2025 destaca inovação e sustentabilidade na cafeicultura mundial').exists():
            with open(caminho_grao_noticia_3, 'rb') as f:
                noticia_grao_3 = Noticia.objects.create(
                    titulo_noticia='SIC 2025 destaca inovação e sustentabilidade na cafeicultura mundial',
                    descricao_noticia='Aconteceu na última quarta-feira (05/11), no Expominas, em Belo Horizonte, a 13ª SIC (Semana Internacional do Café).',
                    fonte='Hannah Andrade',
                    url='https://amirt.com.br/sic-2025-destaca-inovacao-e-sustentabilidade-reforcando-protagonismo-de-minas-gerais-na-cafeicultura-mundial/',
                    isActive=True,
                    isHome=False,
                    imagem_noticia=File(f, name=caminho_grao_noticia_3.name)
                )
            NoticiaHub.objects.create(noticia=noticia_grao_3, hub=hub6)
    
            # --- Notícias Milho ---
            caminho_milho_noticia_1 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'noticia_milho_1.png'
            with open(caminho_milho_noticia_1, 'rb') as f:
                noticia_milho_1 = Noticia.objects.create(
                    titulo_noticia='Plantio do milho segunda safra avança com chegada de chuvas',
                    descricao_noticia='Condições climáticas favoráveis impulsionam o avanço do plantio da segunda safra de milho no Centro-Oeste.',
                    fonte='G1 Sorocaba',
                    url='https://g1.globo.com/sp/sorocaba-jundiai/nosso-campo/noticia/2025/11/09/plantio-do-milho-segunda-safra-avanca-com-chegada-de-chuvas.ghtml',
                    isActive=True,
                    isHome=False,
                    imagem_noticia=File(f, name=caminho_milho_noticia_1.name)
                )
            NoticiaHub.objects.create(noticia=noticia_milho_1, hub=hub4)

        caminho_milho_noticia_2 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'noticia_milho_2.png'
        if caminho_milho_noticia_2.exists() and not Noticia.objects.filter(titulo_noticia='Levantamento da Emater-MG aponta municípios campeões na produção de milho e soja').exists():
            with open(caminho_milho_noticia_2, 'rb') as f:
                noticia_milho_2 = Noticia.objects.create(
                    titulo_noticia='Levantamento da Emater-MG aponta municípios campeões na produção de milho e soja',
                    descricao_noticia='Triângulo e Noroeste de Minas dominam a lista na safra 2024/2025.',
                    fonte='Roberto Meokare',
                    url='https://www.otempo.com.br/canal-o-tempo/podcasts/agrotempo/2025/9/8/levantamento-da-emater-mg-aponta-municipios-campeoes-na-producao-de-milho-e-soja',
                    isActive=True,
                    isHome=True,
                    imagem_noticia=File(f, name=caminho_milho_noticia_2.name)
                )
            NoticiaHub.objects.create(noticia=noticia_milho_2, hub=hub4)

        caminho_milho_noticia_3 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'noticia_milho_3.png'
        if caminho_milho_noticia_3.exists() and not Noticia.objects.filter(titulo_noticia='Santa Catarina registra recuperação na produção de milho em 2025').exists():
            with open(caminho_milho_noticia_3, 'rb') as f:
                noticia_milho_3 = Noticia.objects.create(
                    titulo_noticia='Santa Catarina registra recuperação na produção de milho em 2025',
                    descricao_noticia='Depois de anos consecutivos de queda na produção, a safra de milho em Santa Catarina começa a dar sinais de recuperação.',
                    fonte='NDTV',
                    url='https://ndmais.com.br/video/santa-catarina-registra-recuperacao-na-producao-de-milho-em-2025/',
                    isActive=True,
                    isHome=False,
                    imagem_noticia=File(f, name=caminho_milho_noticia_3.name)
                )
            NoticiaHub.objects.create(noticia=noticia_milho_3, hub=hub4)

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

        vaga4, _ = Vagas.objects.get_or_create(
            cargo_vaga='Engenheiro(a) Agrônomo(a)',
            empresa=empresa_graos,
            defaults={
                'descricao_vaga': 'Planejamento e acompanhamento técnico das lavouras de milho e soja de produtores parceiros, com recomendações de adubação e manejo.',
                'requisito_vaga': 'Graduação em Agronomia, CREA ativo, experiência com análise de solo e agricultura de precisão.',
                'local': 'Formiga - MG',
                'status': 'ativa',
                'anos_experiencia_req': 2.0,
                'nivel_formacao_req': 6,
            }
        )
        if vaga4.hub_id is None:
            vaga4.hub = hub4
            vaga4.save(update_fields=['hub'])
        CursoVaga.objects.get_or_create(vaga=vaga4, curso='Agronomia')

        vaga5, _ = Vagas.objects.get_or_create(
            cargo_vaga='Analista de Logística de Grãos',
            empresa=empresa_graos,
            defaults={
                'descricao_vaga': 'Coordenar recebimento, armazenagem e expedição de grãos, controlando estoques e roteirizando o transporte até os clientes.',
                'requisito_vaga': 'Formação em Logística ou Administração, domínio de Excel e experiência com gestão de estoques.',
                'local': 'Formiga - MG',
                'status': 'ativa',
                'anos_experiencia_req': 2.0,
                'nivel_formacao_req': 6,
            }
        )
        if vaga5.hub_id is None:
            vaga5.hub = hub6
            vaga5.save(update_fields=['hub'])
        CursoVaga.objects.get_or_create(vaga=vaga5, curso='Logística')
        CursoVaga.objects.get_or_create(vaga=vaga5, curso='Administração')

        vaga6, _ = Vagas.objects.get_or_create(
            cargo_vaga='Desenvolvedor Python/Django Pleno',
            empresa=empresa_tech,
            defaults={
                'descricao_vaga': 'Desenvolver e manter a plataforma web de gestão agrícola, criando APIs REST e integrações com sensores IoT.',
                'requisito_vaga': 'Experiência com Python, Django, APIs REST, PostgreSQL e Docker. Desejável conhecimento em React.',
                'local': 'Remoto',
                'status': 'ativa',
                'anos_experiencia_req': 2.0,
                'nivel_formacao_req': 6,
            }
        )
        if vaga6.hub_id is None:
            vaga6.hub = hub1
            vaga6.save(update_fields=['hub'])
        CursoVaga.objects.get_or_create(vaga=vaga6, curso='Sistemas de Informação')
        CursoVaga.objects.get_or_create(vaga=vaga6, curso='Ciência da Computação')

        vaga7, _ = Vagas.objects.get_or_create(
            cargo_vaga='Técnico em Agricultura de Precisão',
            empresa=empresa_tech,
            defaults={
                'descricao_vaga': 'Instalar e calibrar sensores de solo, operar drones de mapeamento e apoiar produtores no uso da plataforma de gestão.',
                'requisito_vaga': 'Curso técnico em Agropecuária ou áreas afins, conhecimento em georreferenciamento.',
                'local': 'Bambuí - MG',
                'status': 'ativa',
                'anos_experiencia_req': 1.0,
                'nivel_formacao_req': 4,
            }
        )
        if vaga7.hub_id is None:
            vaga7.hub = hub1
            vaga7.save(update_fields=['hub'])

        vaga8, _ = Vagas.objects.get_or_create(
            cargo_vaga='Classificador(a) e Provador(a) de Café',
            empresa=empresa,
            defaults={
                'descricao_vaga': 'Realizar classificação física e sensorial (prova de xícara) dos lotes de café especial e acompanhar a torra.',
                'requisito_vaga': 'Curso técnico em Cafeicultura ou certificação em classificação de café. Experiência com cupping.',
                'local': 'Arcos - MG',
                'status': 'ativa',
                'anos_experiencia_req': 1.0,
                'nivel_formacao_req': 4,
            }
        )
        if vaga8.hub_id is None:
            vaga8.hub = hub1
            vaga8.save(update_fields=['hub'])


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


        # Candidaturas adicionais para validar o matching; get_or_create evita duplicações.
        UsuarioVaga.objects.get_or_create(vaga=vaga2, usuario=usuario2, defaults={
            'status': UsuarioVaga.STATUS_CONTRATADO,
            'data_status': timezone.now(),
            'ifmg_no_momento_contratacao': getattr(usuario2, 'ifmg', False),
        })
        UsuarioVaga.objects.get_or_create(vaga=vaga3, usuario=usuario5, defaults={
            'status': UsuarioVaga.STATUS_REJEITADO,
            'data_status': timezone.now(),
            'ifmg_no_momento_contratacao': getattr(usuario5, 'ifmg', False),
        })
        UsuarioVaga.objects.get_or_create(vaga=vaga4, usuario=usuario4)
        UsuarioVaga.objects.get_or_create(vaga=vaga5, usuario=usuario6)
        UsuarioVaga.objects.get_or_create(vaga=vaga6, usuario=usuario7)
        UsuarioVaga.objects.get_or_create(vaga=vaga6, usuario=usuario2)
        UsuarioVaga.objects.get_or_create(vaga=vaga8, usuario=usuario8)

        # Interesses adicionais de compra para os perfis usados nos testes de matching.
        interesses_extras = [
            (usuario4, 'Insumos agrícolas', 'Sementes de milho híbrido certificadas para lavoura experimental', 600.00),
            (usuario6, 'Grãos', 'Compra de milho a granel para fábrica de ração', 80.00),
            (usuario5, 'Apicultura', 'Mel silvestre puro para revenda em feiras da região', None),
            (usuario8, 'Café', 'Café especial torrado de produtores da Canastra para cafeteria', 70.00),
            (usuario7, 'Artesanato', 'Peças de couro e cerâmica feitas à mão', None),
        ]
        for usuario_interesse, categoria, descricao, preco in interesses_extras:
            defaults_interesse = {'descricao_interesse': descricao}
            if preco is not None:
                defaults_interesse['preco_maximo'] = preco
            InteresseCompra.objects.get_or_create(
                usuario=usuario_interesse,
                categoria_interesse=categoria,
                defaults=defaults_interesse,
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
        # --- Recalcula todos os scores ---
        # Os signals de Usuario disparam antes das competências/hobbies (ManyToMany)
        # serem adicionados, e o HubMatchScore depende dos ProdutoMatch criados
        # pelos interesses acima. Recalcula com o estado final do banco.
        for usuario in Usuario.objects.all():
            _upsert_scores_for_usuario(usuario)
            _upsert_hub_scores_for_usuario(usuario)

        # --- Match Usuário x Vaga: ranking e conferência do candidato esperado ---
        match_esperado = {
            vaga1: usuario1,
            vaga2: usuario2,
            vaga3: usuario5,
            vaga4: usuario4,
            vaga5: usuario6,
            vaga6: usuario7,
            vaga7: usuario4,
            vaga8: usuario8,
        }
        print("\n--- Match Usuário x Vaga ---")
        divergencias = 0
        for vaga, esperado in match_esperado.items():
            ranking = list(
                MatchScore.objects.filter(vaga=vaga)
                .select_related('usuario__user')
                .order_by('-score')
            )
            print(f"\n  {vaga.cargo_vaga} ({vaga.empresa.nomefantasia})")
            for posicao, score in enumerate(ranking[:3], start=1):
                print(f"    {posicao}. {score.usuario.user.email}: {score.score * 100:.2f}%")
            ok = bool(ranking) and ranking[0].usuario_id == esperado.pk
            divergencias += not ok
            print(f"    esperado: {esperado.user.email} -> {'OK' if ok else 'DIVERGENTE'}")
        print(f"\n  {len(match_esperado) - divergencias}/{len(match_esperado)} vagas com o candidato esperado em 1º")

        # --- Visualiza os resultados do Match nos Hubs gerados dinamicamente pelos signals ---
        print("\n--- Match Usuário x Hub ---")
        for score in HubMatchScore.objects.select_related(
            'usuario__user',
            'hub'
        ).order_by('usuario_id', '-score'):
            print(
                f"  {score.usuario.user.email} <-> "
                f"{score.hub.nome_hub}: {score.score}%"
            )

        print("\n--- Match Interesse de Compra x Produto ---")
        for match in ProdutoMatch.objects.select_related(
            'interesse__usuario__user',
            'produto__empresa'
        ).order_by('-score'):
            print(
                f"  {match.interesse.usuario.user.email} "
                f"({match.interesse.categoria_interesse}) <-> "
                f"{match.produto.nome_produto} "
                f"({match.produto.empresa.nomefantasia}): "
                f"{match.score}%"
            )

        print("\nUser-1", user1.email, usuario1)
        print("User-2", user2.email, usuario2)
        print("Empresa", user_empresa.email, empresa.segmento)
        print("Admin", user_admin.email, user_admin.is_admin)
        print("hub1", hub1.nome_hub)
        print("hub4", hub4.nome_hub)
        print("hub6", hub6.nome_hub)
        print("vaga1", vaga1.cargo_vaga)
        print("vaga2", vaga2.cargo_vaga)
        print("vaga3", vaga3.cargo_vaga)
        for usuario in (usuario4, usuario5, usuario6, usuario7, usuario8):
            print("Usuario", usuario.user.email, usuario.objetivo_profissional.cargo_pretendido)
        print("Empresa", empresa_tech.user.email, empresa_tech.segmento)
        print("Empresa", empresa_graos.user.email, empresa_graos.segmento)

