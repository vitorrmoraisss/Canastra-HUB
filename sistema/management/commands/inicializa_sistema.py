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
from matching.models import HubMatchScore, ProdutoMatch


class Command(BaseCommand):
    help = "Inicializa o sistema com dados padrão"

    def _cria_sala_geral(self, nome_sala, descricao_recursos, caminhos_imagens):
        sala = Sala.objects.create(
            nome_sala=nome_sala,
            descricao_recursos=descricao_recursos,
        )
        for ordem, caminho_relativo in enumerate(caminhos_imagens):
            caminho = settings.BASE_DIR / caminho_relativo
            with open(caminho, 'rb') as f:
                SalaImagem.objects.create(
                    sala=sala,
                    imagem=File(f, name=Path(caminho_relativo).name),
                    ordem=ordem,
                )
        return sala

    def handle(self, *args, **options):

        # --- Estados e cidades ---
        with open('resources/static/json/estados-cidades.json', 'r', encoding='utf-8') as f:
            dados = json.load(f)

        for estado_data in dados['estados']:
            try:
                estado, created = Estado.objects.get_or_create(
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
                print(
                    f"Inserido estado {estado.nome_estado} com {len(cidades_objs)} cidades novas.")
            except Exception as e:
                print(f"Erro ao inserir {estado_data['nome']}: {e}")

        # --- Hubs ---
        # area_foco_hub/tecnologias_hub alimentam o Match Usuario x Hub (matching/scoring.py)
        caminho_hub1_imagem = settings.BASE_DIR / 'media' / 'fotos_hub' / 'agro_hub.jpg'
        with open(caminho_hub1_imagem, 'rb') as f:
            hub1 = Hub.objects.create(
                nome_hub='Agro',
                descricao_hub='Agro é melhor com o pessoal da canastra',
                foto_hub=File(f, name=caminho_hub1_imagem.name),
                area_foco_hub='Agronegócio, cafeicultura, produção rural e comercialização de alimentos',
                tecnologias_hub='Agricultura de precisão, sensores IoT, gestão agrícola digital'
            )

        caminho_hub4_imagem = settings.BASE_DIR / 'media' / 'fotos_hub' / 'milho_hub.jpg'
        with open(caminho_hub4_imagem, 'rb') as f:
            hub4 = Hub.objects.create(
                nome_hub='Milho',
                descricao_hub='Milho é melhor com o pessoal da canastra',
                foto_hub=File(f, name=caminho_hub4_imagem.name),
                area_foco_hub='Produção de milho, grãos e insumos agrícolas',
                tecnologias_hub='Sementes geneticamente melhoradas, maquinário agrícola'
            )

        caminho_hub6_imagem = settings.BASE_DIR / 'media' / 'fotos_hub' / 'graos_hub.jpg'
        with open(caminho_hub6_imagem, 'rb') as f:
            hub6 = Hub.objects.create(
                nome_hub='Grãos',
                descricao_hub='Grãos é melhor com o pessoal da canastra',
                foto_hub=File(f, name=caminho_hub6_imagem.name),
                area_foco_hub='Comercialização de grãos, logística agrícola e exportação',
                tecnologias_hub='Armazenagem, transporte, rastreabilidade da produção'
            )

        # Estrutura geral do campus (salas sem hub específico) — texto e imagens
        # reaproveitados da antiga página estática espacos_hub.html
        self._cria_sala_geral(
            'Incubadora de Empresas e Startups',
            'Onde o Canastra HUB nasceu. A Incubadora apoia estudantes e empreendedores que querem criar '
            'negócios inovadores, com suporte técnico, orientação de gestão e espaço físico para trabalhar. '
            'O objetivo é transformar ideias em empresas viáveis, ligando projetos de base tecnológica às '
            'demandas do agronegócio, da indústria e dos serviços da região.',
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


        cidade = Cidade.objects.get(nome_cidade='Arcos')
        estado = cidade.estado_cidade

        # --- Empresa e Admin ---
        user_empresa = UsuarioBase.objects.create_user(
            email='empresa@teste',
            password='123',
            nome='Roberta Cafes',
            tipo='empresa'
        )
        empresa = Empresa.objects.create(
            user=user_empresa,
            nomefantasia='Roberta Cafés',
            tipo_empresa='Cafecultura',
            razao_social='Roberta Cafés Ltda',
            cnpj='11111111111111',
            telefone='(37) 3322-4433',
            rua='Rua José da Silva',
            cep='39800000',
            numero='443',
            complemento='Sala 11',
            cidade=cidade,
            estado=estado,
            segmento='cafe'
        )

        user_admin = UsuarioBase.objects.create_superuser(
            email='admin@teste',
            password='123',
            nome='admin',
            tipo='admin'
        )

        # --- Usuário 1: perfil agrícola ---
        user1 = UsuarioBase.objects.create_user(
            email='usuario@teste',
            password='123',
            nome='Cleiton Romario Santos',
            tipo='usuario'
        )
        usuario1 = Usuario.objects.create(
            user=user1,
            nome_social='Cleiton',
            data_nascimento='2002-07-11',
            genero='masculino',
            estado_civil='solteiro',
            nacionalidade='brasileiro',
            telefone='(37) 99838-1976',
            endereco=Endereco.objects.create(
                cep='39800000',
                rua='Rua das Palmeiras',
                numero='981',
                bairro='Centro',
                cidade=cidade,
                estado=estado,
                complemento='Apto 12',
            ),
            objetivo_profissional=ProfessionalTarget.objects.create(
                cargo_pretendido='Operador de Máquinas Agrícolas',
                area_interesse='Agronegócio',
                disponibilidade='Imediata',
                remoto=False,
                pretensao_salarial=2500.00,
            ),
            formacao_academica=AcademyGraduation.objects.create(
                instituicao_nome='SENAR Minas',
                grau_escolaridade='Curso Técnico',
                curso_graduacao='Mecanização Agrícola',
                situacao_academica='Concluído',
                data_acad_inicio='2021-02-01',
                data_acad_fim='2021-12-10',
            ),
            social_media=SocialMedia.objects.create(
                linkedin='https://www.linkedin.com/in/cleiton-romario',
                instagram='cleiton.agro',
            ),
        )
        usuario1.competencias.add(
            Competencia.objects.create(
                nome_competencia='Operação de tratores, colheitadeiras e implementos agrícolas',
                tipo_competencia='tecnica',
            ),
            Competencia.objects.create(
                nome_competencia='Manutenção preventiva de equipamentos',
                tipo_competencia='tecnica',
            ),
            Competencia.objects.create(
                nome_competencia='Trabalho em equipe',
                tipo_competencia='comportamental',
            ),
            Competencia.objects.create(
                nome_competencia='Organização e comprometimento',
                tipo_competencia='comportamental',
            ),
        )
        Acessibilidade.objects.create(
            usuario=usuario1,
            pessoa_com_deficiencia=False,
        )
        ExperienciaProfissional.objects.create(
            usuario=usuario1,
            cargo='Auxiliar de Campo',
            nome_empresa='Fazenda São João',
            data_inicio='2021-03-01',
            data_fim='2023-12-31',
        )
        ExperienciaProfissional.objects.create(
            usuario=usuario1,
            cargo='Operador de Trator',
            nome_empresa='Cooperativa Agrícola do Oeste',
            data_inicio='2024-01-15',
        )
        CursoExtraCurricular.objects.create(
            usuario=usuario1,
            nome_curso='Operação e manutenção de tratores',
            instituicao='SENAR Minas',
            carga_horaria=40,
            data_conclusao='2022-02-18',
        )
        CursoExtraCurricular.objects.create(
            usuario=usuario1,
            nome_curso='Segurança do trabalho rural',
            instituicao='SENAR Minas',
            carga_horaria=20,
            data_conclusao='2022-06-24',
        )
        Idioma.objects.bulk_create([
            Idioma(usuario=usuario1, language='Português', fluency='Avançado'),
            Idioma(usuario=usuario1, language='Inglês', fluency='Básico'),
        ])

        # --- Usuário 2: perfil desenvolvedor ---
        user2 = UsuarioBase.objects.create_user(
            email='usuario1@teste',
            password='123',
            nome='Romario Santos',
            tipo='usuario'
        )
        usuario2 = Usuario.objects.create(
            user=user2,
            nome_social='Romario',
            data_nascimento='2003-04-22',
            genero='masculino',
            estado_civil='solteiro',
            nacionalidade='brasileiro',
            telefone='(37) 98765-4321',
            endereco=Endereco.objects.create(
                cep='39800000',
                rua='Av. Brasil',
                numero='200',
                bairro='Jardim América',
                cidade=cidade,
                estado=estado,
            ),
            objetivo_profissional=ProfessionalTarget.objects.create(
                cargo_pretendido='Desenvolvedor de Software',
                area_interesse='Tecnologia da Informação',
                disponibilidade='Imediata',
                remoto=True,
                pretensao_salarial=3000.00,
            ),
            social_media=SocialMedia.objects.create(),
        )
        Idioma.objects.create(usuario=usuario2, language='Inglês', fluency='Intermediário')

        # --- Usuário 3 ---
        user_marco = UsuarioBase.objects.create_user(
            email='m.tulio.m.carvalho@gmail.com',
            password='123',
            nome='Marco Tulio Carvalho',
            tipo='usuario'
        )
        Usuario.objects.create(
            user=user_marco,
            nome_social='Marco',
            data_nascimento='2002-07-11',
            genero='masculino',
            estado_civil='solteiro',
            nacionalidade='brasileiro',
            telefone='(37) 99838-1976',
            endereco=Endereco.objects.create(
                cep='39800000',
                rua='rua teste',
                numero='981',
                bairro='teste',
                cidade=cidade,
                estado=estado,
                complemento='complemento blablabla',
            ),
            objetivo_profissional=ProfessionalTarget.objects.create(
                pretensao_salarial=15.00,
            ),
        )

        # --- Vínculo Empresa x Hub e Produtos ofertados (alimentam o Match nos Hubs) ---
        EmpresaHub.objects.create(empresa=empresa, hub=hub1)
        EmpresaHub.objects.create(empresa=empresa, hub=hub6)

        Produto.objects.create(
            empresa=empresa,
            nome_produto='Café Arábica Especial',
            categoria_produto='Café',
            descricao_produto='Café arábica torrado artesanalmente, produzido na região da Canastra',
            preco_produto=45.90,
            quantidade_disponivel=200,
        )
        Produto.objects.create(
            empresa=empresa,
            nome_produto='Mel Silvestre da Canastra',
            categoria_produto='Apicultura',
            descricao_produto='Mel puro produzido por apicultores parceiros da região da Canastra',
            preco_produto=25.00,
            quantidade_disponivel=150,
        )

        # --- Notícias Agro ---
        caminho_agro_noticia_1 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'noticia_agro_1.png'
        with open(caminho_agro_noticia_1, 'rb') as f:
            noticia_agro_1 = Noticia.objects.create(
                titulo_noticia='Minas Gerais lidera ranking dos melhores cafés do Brasil em 2025',
                descricao_noticia='Produtores mineiros conquistaram as três categorias do Cup of Excellence, o mais prestigiado concurso de qualidade do setor.',
                fonte='Paloma Santos',
                url='https://agro.estadao.com.br/agricultura/minas-gerais-lidera-ranking-dos-melhores-cafes-do-brasil-em-2025',
                isActive=True,
                isHome=False,
                imagem_noticia=File(f, name=caminho_agro_noticia_1.name)
            )
        NoticiaHub.objects.create(noticia=noticia_agro_1, hub=hub1)

        caminho_agro_noticia_2 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'noticia_agro_2.jpeg'
        with open(caminho_agro_noticia_2, 'rb') as f:
            noticia_agro_2 = Noticia.objects.create(
                titulo_noticia='O futuro sustentável do agronegócio passa pela boa gestão',
                descricao_noticia='No Brasil, anualmente, os dados econômicos demonstram que o agro permanece no centro da economia.',
                fonte='André Paranhos',
                url='https://globorural.globo.com/google/amp/opiniao/vozes-do-agro/noticia/2025/11/o-futuro-sustentavel-do-agronegocio-passa-pela-boa-gestao.ghtml',
                isActive=True,
                isHome=True,
                imagem_noticia=File(f, name=caminho_agro_noticia_2.name)
            )
        NoticiaHub.objects.create(noticia=noticia_agro_2, hub=hub1)

        caminho_agro_noticia_3 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'noticia_agro_3.png'
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

        # --- Notícias Grãos ---
        caminho_grao_noticia_1 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'graos' / 'noticia_graos1.png'
        with open(caminho_grao_noticia_1, 'rb') as f:
            noticia_grao_1 = Noticia.objects.create(
                titulo_noticia='A jornada dos grãos pelo Tapajós rumo ao mercado externo',
                descricao_noticia='Reportagem viajou em empurrador e acompanhou transporte de grãos pela hidrovia',
                fonte='Raphael Salomão',
                url='https://globorural.globo.com/google/amp/especiais/caminhos-da-safra/noticia/2025/11/a-jornada-dos-graos-pelo-tapajos-rumo-ao-mercado-externo.ghtml',
                isActive=True,
                isHome=True,
                imagem_noticia=File(f, name=caminho_grao_noticia_1.name)
            )
        NoticiaHub.objects.create(noticia=noticia_grao_1, hub=hub6)

        caminho_grao_noticia_2 = settings.BASE_DIR / 'resources' / 'static' / 'img' / 'hubs' / 'graos' / 'noticia_graos2.png'
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


        # --- Vagas com campos de matching ---
        vaga1 = Vagas.objects.create(
            cargo_vaga='Operador de Máquinas Agrícolas',
            descricao_vaga='Responsável por operar tratores, colheitadeiras e outros equipamentos agrícolas durante o plantio e a colheita.',
            requisito_vaga='Experiência comprovada na operação de máquinas agrícolas e conhecimento básico em manutenção preventiva.',
            local='Fazenda Primavera',
            status='ativa',
            anos_experiencia_req=2.0,
            nivel_formacao_req=3,  # Ensino Médio Completo
            empresa=empresa
        )

        vaga2 = Vagas.objects.create(
            cargo_vaga='Desenvolvedor Júnior',
            descricao_vaga='Estamos em busca de um Desenvolvedor Júnior motivado e comprometido para integrar nossa equipe de tecnologia.',
            requisito_vaga='Conhecimento básico em linguagens de programação como Python, JavaScript ou Java.',
            local='Home Office',
            status='ativa',
            anos_experiencia_req=0.0,
            nivel_formacao_req=5,  # Ensino Superior Incompleto
            empresa=empresa
        )
        CursoVaga.objects.create(vaga=vaga2, curso='Ciência da Computação')
        CursoVaga.objects.create(vaga=vaga2, curso='Sistemas de Informação')

        vaga3 = Vagas.objects.create(
            cargo_vaga='Apicultor',
            descricao_vaga='Estamos em busca de um profissional dedicado para atuar no manejo de colmeias, extração de mel e cuidado com abelhas em fazenda de produção apícola.',
            requisito_vaga='Experiência com manejo de abelhas ou interesse em aprender sobre apicultura. Disposição para trabalho ao ar livre.',
            local='Fazenda Mel da Canastra',
            status='ativa',
            anos_experiencia_req=1.0,
            nivel_formacao_req=3,  # Ensino Médio Completo
            empresa=empresa
        )

        # --- Candidaturas às vagas ---
        UsuarioVaga.objects.create(
            vaga=vaga1,
            usuario=usuario1,
        )
        UsuarioVaga.objects.create(
            vaga=vaga2,
            usuario=usuario2,
            status=UsuarioVaga.STATUS_CONTRATADO,
            data_status=timezone.now(),
            ifmg_no_momento_contratacao=usuario2.ifmg,
        )
        UsuarioVaga.objects.create(
            vaga=vaga3,
            usuario=usuario1,
            status=UsuarioVaga.STATUS_REJEITADO,
            data_status=timezone.now(),
            ifmg_no_momento_contratacao=usuario1.ifmg,
        )

        # --- Interesses de compra ---
        # Compatível com o produto 'Café Arábica Especial' -> deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario1,
            categoria_interesse='Café',
            descricao_interesse='Procuro café arábica de produtor local para revenda',
            preco_maximo=60.00,
        )
        # Sem produto compatível cadastrado -> não deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario2,
            categoria_interesse='Tecnologia',
            descricao_interesse='Interessado em soluções de automação e sensores para agricultura',
        )

        # --- Eventos ---
        evento1 = Evento.objects.create(
            nome_evento='Feira do Café da Canastra',
            data_evento_inicio='2026-09-10',
            data_evento_fim='2026-09-10',
            horario_evento='09:00',
            local_evento='Fazenda Primavera',
            publico_evento='Produtores e público geral',
            descricao_evento='Exposição e degustação dos melhores cafés da região da Canastra.',
            vagas_disponiveis=100,
            hub=hub1
        )
        Evento.objects.create(
            nome_evento='Encontro do Milho',
            data_evento_inicio='2026-10-05',
            data_evento_fim='2026-10-05',
            horario_evento='14:00',
            local_evento='Hub Milho',
            publico_evento='Produtores de milho',
            descricao_evento='Encontro anual sobre novas técnicas de cultivo de milho.',
            vagas_disponiveis=50,
            hub=hub4
        )
        InscricaoEvento.objects.create(evento=evento1, usuario=user1)

        # --- Treinamentos ---
        treinamento1 = Treinamento.objects.create(
            nome='Boas Práticas em Apicultura',
            data_inicio='2026-09-20',
            data_fim='2026-09-20',
            local='Fazenda Mel da Canastra',
            publico_alvo='Apicultores',
            descricao='Treinamento sobre manejo de colmeias e extração de mel.',
            vagas_disponiveis=30,
            hub=hub6
        )
        SessaoTreinamento.objects.create(
            treinamento=treinamento1,
            data='2026-09-20',
            horario='08:00'
        )

        treinamento2 = Treinamento.objects.create(
            nome='Manutenção de Máquinas Agrícolas',
            data_inicio='2026-11-02',
            data_fim='2026-11-03',
            local='Fazenda Primavera',
            publico_alvo='Operadores de máquinas',
            descricao='Curso prático de manutenção preventiva de tratores e colheitadeiras.',
            vagas_disponiveis=20,
            hub=hub1
        )
        SessaoTreinamento.objects.create(
            treinamento=treinamento2,
            data='2026-11-02',
            horario='13:00'
        )
        InscricaoTreinamento.objects.create(treinamento=treinamento1, usuario=user1)

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
