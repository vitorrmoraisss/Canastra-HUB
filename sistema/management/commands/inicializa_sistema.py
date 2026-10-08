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

    def _cria_empresa(self, email, nome, cidade, hubs, **dados):
        user = UsuarioBase.objects.create_user(email=email, password='123', nome=nome, tipo='empresa')
        empresa = Empresa.objects.create(
            user=user,
            cidade=cidade,
            estado=cidade.estado_cidade,
            **dados,
        )
        for hub in hubs:
            EmpresaHub.objects.create(empresa=empresa, hub=hub)
        return empresa

    def _cria_usuario(self, email, nome, cidade, perfil, objetivo, formacao=None,
                      competencias_tecnicas=(), competencias_comportamentais=(),
                      hobbies=(), experiencias=(), cursos=(), idiomas=(), social=None):
        """Cria um Usuario completo. Experiências, cursos e idiomas respeitam o limite de 3 do LimitedModel."""
        user = UsuarioBase.objects.create_user(email=email, password='123', nome=nome, tipo='usuario')
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
            *[Competencia.objects.create(nome_competencia=nome_c, tipo_competencia='tecnica')
              for nome_c in competencias_tecnicas],
            *[Competencia.objects.create(nome_competencia=nome_c, tipo_competencia='comportamental')
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
            formacao_academica=AcademyGraduation.objects.create(
                instituicao_nome='IFMG Campus Bambuí',
                grau_escolaridade='Superior Incompleto',
                curso_graduacao='Ciência da Computação',
                situacao_academica='Cursando',
                data_acad_inicio='2022-02-01',
            ),
            social_media=SocialMedia.objects.create(),
        )
        usuario2.competencias.add(
            Competencia.objects.create(nome_competencia='Python', tipo_competencia='tecnica'),
            Competencia.objects.create(nome_competencia='JavaScript, HTML e CSS', tipo_competencia='tecnica'),
            Competencia.objects.create(nome_competencia='Banco de dados SQL', tipo_competencia='tecnica'),
            Competencia.objects.create(nome_competencia='Proatividade', tipo_competencia='comportamental'),
        )
        usuario2.interesses_hobbies.add(
            Hobby.objects.get_or_create(nome_hobby='Programação de jogos')[0],
            Hobby.objects.get_or_create(nome_hobby='Xadrez')[0],
        )
        Idioma.objects.create(usuario=usuario2, language='Inglês', fluency='Intermediário')

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
        Produto.objects.create(
            empresa=empresa_tech,
            nome_produto='Sensor IoT de Umidade do Solo',
            categoria_produto='Tecnologia',
            descricao_produto='Sensor sem fio para monitoramento de umidade e temperatura do solo, com automação de irrigação',
            preco_produto=890.00,
            quantidade_disponivel=40,
        )
        Produto.objects.create(
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
        Produto.objects.create(
            empresa=empresa_graos,
            nome_produto='Milho em Grão a Granel',
            categoria_produto='Grãos',
            descricao_produto='Milho amarelo seco e classificado, vendido a granel para ração e indústria',
            preco_produto=75.00,
            quantidade_disponivel=5000,
        )
        Produto.objects.create(
            empresa=empresa_graos,
            nome_produto='Sementes de Milho Híbrido',
            categoria_produto='Insumos agrícolas',
            descricao_produto='Sementes de milho híbrido de alta produtividade, tratadas e certificadas',
            preco_produto=520.00,
            quantidade_disponivel=300,
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

        vaga4 = Vagas.objects.create(
            cargo_vaga='Engenheiro(a) Agrônomo(a)',
            descricao_vaga='Planejamento e acompanhamento técnico das lavouras de milho e soja de produtores parceiros, com recomendações de adubação e manejo.',
            requisito_vaga='Graduação em Agronomia, CREA ativo, experiência com análise de solo e agricultura de precisão.',
            local='Formiga - MG',
            status='ativa',
            anos_experiencia_req=2.0,
            nivel_formacao_req=6,  # Ensino Superior Completo
            empresa=empresa_graos,
            hub=hub4,
        )
        CursoVaga.objects.create(vaga=vaga4, curso='Agronomia')

        vaga5 = Vagas.objects.create(
            cargo_vaga='Analista de Logística de Grãos',
            descricao_vaga='Coordenar recebimento, armazenagem e expedição de grãos, controlando estoques e roteirizando o transporte até os clientes.',
            requisito_vaga='Formação em Logística ou Administração, domínio de Excel e experiência com gestão de estoques.',
            local='Formiga - MG',
            status='ativa',
            anos_experiencia_req=2.0,
            nivel_formacao_req=6,  # Ensino Superior Completo
            empresa=empresa_graos,
            hub=hub6,
        )
        CursoVaga.objects.create(vaga=vaga5, curso='Logística')
        CursoVaga.objects.create(vaga=vaga5, curso='Administração')

        vaga6 = Vagas.objects.create(
            cargo_vaga='Desenvolvedor Python/Django Pleno',
            descricao_vaga='Desenvolver e manter a plataforma web de gestão agrícola, criando APIs REST e integrações com sensores IoT.',
            requisito_vaga='Experiência com Python, Django, APIs REST, PostgreSQL e Docker. Desejável conhecimento em React.',
            local='Remoto',
            status='ativa',
            anos_experiencia_req=2.0,
            nivel_formacao_req=6,  # Ensino Superior Completo
            empresa=empresa_tech,
            hub=hub1,
        )
        CursoVaga.objects.create(vaga=vaga6, curso='Sistemas de Informação')
        CursoVaga.objects.create(vaga=vaga6, curso='Ciência da Computação')

        vaga7 = Vagas.objects.create(
            cargo_vaga='Técnico em Agricultura de Precisão',
            descricao_vaga='Instalar e calibrar sensores de solo, operar drones de mapeamento e apoiar produtores no uso da plataforma de gestão.',
            requisito_vaga='Curso técnico em Agropecuária ou áreas afins, conhecimento em georreferenciamento.',
            local='Bambuí - MG',
            status='ativa',
            anos_experiencia_req=1.0,
            nivel_formacao_req=4,  # Ensino Técnico
            empresa=empresa_tech,
            hub=hub1,
        )

        vaga8 = Vagas.objects.create(
            cargo_vaga='Classificador(a) e Provador(a) de Café',
            descricao_vaga='Realizar classificação física e sensorial (prova de xícara) dos lotes de café especial e acompanhar a torra.',
            requisito_vaga='Curso técnico em Cafeicultura ou certificação em classificação de café. Experiência com cupping.',
            local='Arcos - MG',
            status='ativa',
            anos_experiencia_req=1.0,
            nivel_formacao_req=4,  # Ensino Técnico
            empresa=empresa,
            hub=hub1,
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
        UsuarioVaga.objects.create(vaga=vaga4, usuario=usuario4)
        UsuarioVaga.objects.create(vaga=vaga5, usuario=usuario6)
        UsuarioVaga.objects.create(vaga=vaga6, usuario=usuario7)
        UsuarioVaga.objects.create(vaga=vaga6, usuario=usuario2)
        UsuarioVaga.objects.create(vaga=vaga3, usuario=usuario5)
        UsuarioVaga.objects.create(vaga=vaga8, usuario=usuario8)

        # --- Interesses de compra ---
        # Compatível com o produto 'Café Arábica Especial' -> deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario1,
            categoria_interesse='Café',
            descricao_interesse='Procuro café arábica de produtor local para revenda',
            preco_maximo=60.00,
        )
        # Compatível com 'Sensor IoT de Umidade do Solo' (Canastra Tech) -> deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario2,
            categoria_interesse='Tecnologia',
            descricao_interesse='Interessado em soluções de automação e sensores para agricultura',
        )
        # Compatível com 'Sementes de Milho Híbrido' -> deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario4,
            categoria_interesse='Insumos agrícolas',
            descricao_interesse='Sementes de milho híbrido certificadas para lavoura experimental',
            preco_maximo=600.00,
        )
        # Compatível com 'Milho em Grão a Granel' -> deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario6,
            categoria_interesse='Grãos',
            descricao_interesse='Compra de milho a granel para fábrica de ração',
            preco_maximo=80.00,
        )
        # Compatível com 'Mel Silvestre da Canastra' -> deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario5,
            categoria_interesse='Apicultura',
            descricao_interesse='Mel silvestre puro para revenda em feiras da região',
        )
        # Compatível com 'Café Arábica Especial' -> deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario8,
            categoria_interesse='Café',
            descricao_interesse='Café especial torrado de produtores da Canastra para cafeteria',
            preco_maximo=70.00,
        )
        # Sem produto compatível cadastrado -> não deve gerar Match
        InteresseCompra.objects.create(
            usuario=usuario7,
            categoria_interesse='Artesanato',
            descricao_interesse='Peças de couro e cerâmica feitas à mão',
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
