# JobMatcher Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar `matching/` em Django app que sincroniza automaticamente Usuários e Vagas com o JobMatcher via `post_save` signals e expõe dois endpoints JSON para consulta de matches.

**Architecture:** Singleton `get_matcher()` em `service.py` instancia o `JobMatcher` com ChromaDB persistido em `settings.CHROMADB_PATH`. Signals `post_save` em `Usuario` e `Vagas` disparam sincronização. Dois endpoints GET retornam JSON com resultados rankeados por similaridade semântica.

**Tech Stack:** Django 4.1, ChromaDB, SentenceTransformer (`rufimelo/bert-large-portuguese-cased-sts`), `unittest.mock`

---

## Mapa de arquivos

| Arquivo | Ação |
|---|---|
| `matching/__init__.py` | Criar (vazio) |
| `matching/apps.py` | Criar |
| `matching/service.py` | Criar |
| `matching/text_builders.py` | Criar |
| `matching/signals.py` | Criar |
| `matching/views.py` | Criar |
| `matching/urls.py` | Criar |
| `matching/tests.py` | Criar (incrementalmente por task) |
| `matching/matcher.py` | Modificar — corrigir import relativo linha 13 |
| `config/settings.py` | Modificar — `INSTALLED_APPS` + `CHROMADB_PATH` |
| `config/urls.py` | Modificar — adicionar rota `matching/` |

---

## Task 1: Bootstrap do app Django

**Files:**
- Create: `matching/__init__.py`
- Create: `matching/apps.py`
- Create: `matching/tests.py`
- Modify: `matching/matcher.py` (linha 13)
- Modify: `config/settings.py`
- Modify: `config/urls.py`

- [ ] **Step 1: Criar `matching/__init__.py`**

Crie o arquivo vazio:

```python
# matching/__init__.py
```

- [ ] **Step 2: Criar `matching/apps.py`**

Sem o `ready()` ainda — será adicionado na Task 4 junto com os signals.

```python
# matching/apps.py
from django.apps import AppConfig


class MatchingConfig(AppConfig):
    name = "matching"
    default_auto_field = "django.db.models.BigAutoField"
```

- [ ] **Step 3: Corrigir import relativo em `matching/matcher.py`**

Na linha 13 de `matching/matcher.py`, altere:

```python
from schemas import ResumeChunk, JobChunk, MatchResult
```

para:

```python
from .schemas import ResumeChunk, JobChunk, MatchResult
```

Esse import funcionava quando o arquivo era executado diretamente do diretório `matching/`. Como agora é um pacote Django, precisa do ponto.

- [ ] **Step 4: Atualizar `config/settings.py`**

Adicione `"matching"` ao final de `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "empresa",
    "sistema",
    "vagas",
    "administrador",
    "treinamento",
    "perfil",
    "eventos",
    "matching",
]
```

Logo após a linha `BASE_DIR = Path(__file__).resolve().parent.parent`, adicione:

```python
CHROMADB_PATH = BASE_DIR / "chromadb"
```

- [ ] **Step 5: Atualizar `config/urls.py`**

```python
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', include('core.urls')),
    path('empresa/', include('empresa.urls')),
    path('vagas/', include('vagas.urls')),
    path('administrador/', include('administrador.urls')),
    path('treinamento/', include('treinamento.urls')),
    path('perfil/', include('perfil.urls')),
    path('eventos/', include('eventos.urls')),
    path('matching/', include('matching.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Step 6: Criar `matching/tests.py` com smoke test**

```python
# matching/tests.py
from django.test import TestCase


class MatchingAppSmoke(TestCase):
    def test_app_installed(self):
        from django.apps import apps
        self.assertTrue(apps.is_installed("matching"))
```

- [ ] **Step 7: Rodar o smoke test**

```bash
python manage.py test matching.tests.MatchingAppSmoke -v 2
```

Esperado: `Ran 1 test in ...s  OK`

- [ ] **Step 8: Commit**

```bash
git add matching/__init__.py matching/apps.py matching/matcher.py config/settings.py config/urls.py matching/tests.py
git commit -m "feat: bootstrap matching como Django app"
```

---

## Task 2: service.py — Singleton do JobMatcher

**Files:**
- Create: `matching/service.py`
- Modify: `matching/tests.py` (append)

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao final de `matching/tests.py`:

```python
from unittest.mock import patch, MagicMock
from django.test import override_settings


class GetMatcherTest(TestCase):
    def setUp(self):
        import matching.service as svc
        svc._matcher = None

    def tearDown(self):
        import matching.service as svc
        svc._matcher = None

    def test_retorna_instancia_job_matcher(self):
        mock = MagicMock()
        with patch('matching.service.JobMatcher', return_value=mock):
            with override_settings(CHROMADB_PATH='/tmp/test_chroma'):
                from matching.service import get_matcher
                result = get_matcher()
        self.assertEqual(result, mock)

    def test_retorna_mesma_instancia_em_chamadas_repetidas(self):
        mock = MagicMock()
        with patch('matching.service.JobMatcher', return_value=mock) as MockCls:
            with override_settings(CHROMADB_PATH='/tmp/test_chroma'):
                from matching.service import get_matcher
                r1 = get_matcher()
                r2 = get_matcher()
        self.assertIs(r1, r2)
        MockCls.assert_called_once()
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python manage.py test matching.tests.GetMatcherTest -v 2
```

Esperado: `ERROR` com `ModuleNotFoundError: No module named 'matching.service'`

- [ ] **Step 3: Criar `matching/service.py`**

```python
# matching/service.py
from __future__ import annotations

from django.conf import settings

from .matcher import JobMatcher

_matcher: JobMatcher | None = None


def get_matcher() -> JobMatcher:
    global _matcher
    if _matcher is None:
        _matcher = JobMatcher(persist_directory=str(settings.CHROMADB_PATH))
    return _matcher
```

- [ ] **Step 4: Rodar os testes para confirmar passagem**

```bash
python manage.py test matching.tests.GetMatcherTest -v 2
```

Esperado: `Ran 2 tests in ...s  OK`

- [ ] **Step 5: Commit**

```bash
git add matching/service.py matching/tests.py
git commit -m "feat: add matching service singleton"
```

---

## Task 3: text_builders.py — Montagem de texto para indexação

**Files:**
- Create: `matching/text_builders.py`
- Modify: `matching/tests.py` (append)

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao final de `matching/tests.py`:

```python
def _mock_usuario(**kwargs):
    """Retorna um MagicMock com interface mínima de Usuario."""
    u = MagicMock()
    u.cargo_pretendido = kwargs.get('cargo_pretendido', 'Desenvolvedor Python')
    u.area_interesse = kwargs.get('area_interesse', 'Backend')
    u.disponibilidade = kwargs.get('disponibilidade', 'Imediata')
    u.remoto = kwargs.get('remoto', False)
    u.curso = kwargs.get('curso', 'Sistemas de Informação')
    u.interesses_hobbies = kwargs.get('interesses_hobbies', None)
    for n in ('1', '2', '3'):
        setattr(u, f'instituicao_nome{n}', None)
        setattr(u, f'grau_escolaridade{n}', None)
        setattr(u, f'curso_graduacao{n}', None)
        setattr(u, f'situacao_academica{n}', None)
        setattr(u, f'competencias_tecnicas{n}', None)
        setattr(u, f'competencias_comportamentais{n}', None)
    return u


def _mock_vaga(**kwargs):
    """Retorna um MagicMock com interface mínima de Vagas."""
    v = MagicMock()
    v.cargo_vaga = kwargs.get('cargo_vaga', 'Dev Python')
    v.descricao_vaga = kwargs.get('descricao_vaga', 'Vaga de backend')
    v.requisito_vaga = kwargs.get('requisito_vaga', 'Python, Django')
    v.local = kwargs.get('local', 'Patos de Minas')
    v.empresa.nomefantasia = kwargs.get('nomefantasia', 'TechCo')
    v.empresa.segmento = kwargs.get('segmento', 'Tecnologia')
    return v


class BuildResumeTextTest(TestCase):
    def _call(self, usuario):
        from core.models import ExperienciaProfissional
        with patch('matching.text_builders.ExperienciaProfissional') as MockExp:
            MockExp.DoesNotExist = ExperienciaProfissional.DoesNotExist
            MockExp.objects.get.side_effect = ExperienciaProfissional.DoesNotExist
            from matching.text_builders import build_resume_text
            return build_resume_text(usuario)

    def test_inclui_cargo_pretendido(self):
        text = self._call(_mock_usuario(cargo_pretendido='Analista de Dados'))
        self.assertIn('Analista de Dados', text)

    def test_inclui_area_interesse(self):
        text = self._call(_mock_usuario(area_interesse='Data Science'))
        self.assertIn('Data Science', text)

    def test_inclui_competencias_tecnicas(self):
        u = _mock_usuario()
        u.competencias_tecnicas1 = 'Python, SQL'
        text = self._call(u)
        self.assertIn('Python, SQL', text)

    def test_campos_nulos_sao_omitidos(self):
        u = _mock_usuario(cargo_pretendido=None, area_interesse=None)
        text = self._call(u)
        self.assertNotIn('objetivo:', text)
        self.assertNotIn('área de interesse:', text)

    def test_remoto_incluido_quando_verdadeiro(self):
        text = self._call(_mock_usuario(remoto=True))
        self.assertIn('remoto', text)


class BuildJobTextTest(TestCase):
    def _call(self, vaga):
        with patch('matching.text_builders.CursoVaga') as MockCurso:
            MockCurso.objects.filter.return_value.values_list.return_value = []
            from matching.text_builders import build_job_text
            return build_job_text(vaga)

    def test_inclui_cargo_vaga(self):
        text = self._call(_mock_vaga(cargo_vaga='Engenheiro de Software'))
        self.assertIn('Engenheiro de Software', text)

    def test_inclui_requisito_vaga(self):
        text = self._call(_mock_vaga(requisito_vaga='Django, REST'))
        self.assertIn('Django, REST', text)

    def test_inclui_nome_empresa(self):
        text = self._call(_mock_vaga(nomefantasia='StartupXYZ'))
        self.assertIn('StartupXYZ', text)

    def test_inclui_segmento(self):
        text = self._call(_mock_vaga(segmento='Agronegócio'))
        self.assertIn('Agronegócio', text)
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python manage.py test matching.tests.BuildResumeTextTest matching.tests.BuildJobTextTest -v 2
```

Esperado: `ERROR` com `ModuleNotFoundError: No module named 'matching.text_builders'`

- [ ] **Step 3: Criar `matching/text_builders.py`**

```python
# matching/text_builders.py
from __future__ import annotations

from core.models import Usuario, ExperienciaProfissional
from vagas.models import Vagas, CursoVaga


def build_resume_text(usuario: Usuario) -> str:
    parts = []

    if usuario.cargo_pretendido:
        parts.append(f"objetivo: {usuario.cargo_pretendido}")
    if usuario.area_interesse:
        parts.append(f"área de interesse: {usuario.area_interesse}")
    if usuario.disponibilidade:
        parts.append(f"disponibilidade: {usuario.disponibilidade}")
    if usuario.remoto:
        parts.append("disponível para trabalho remoto")
    if usuario.curso:
        parts.append(f"curso: {usuario.curso}")

    for n in ('1', '2', '3'):
        instituicao = getattr(usuario, f'instituicao_nome{n}')
        grau = getattr(usuario, f'grau_escolaridade{n}')
        curso = getattr(usuario, f'curso_graduacao{n}')
        situacao = getattr(usuario, f'situacao_academica{n}')
        if any([instituicao, grau, curso]):
            linha = " ".join(filter(None, [grau, curso, "em", instituicao, situacao]))
            parts.append(f"formação: {linha}")

    for n in ('1', '2', '3'):
        tec = getattr(usuario, f'competencias_tecnicas{n}')
        comp = getattr(usuario, f'competencias_comportamentais{n}')
        if tec:
            parts.append(f"competências técnicas: {tec}")
        if comp:
            parts.append(f"competências comportamentais: {comp}")

    try:
        exp = ExperienciaProfissional.objects.get(usuario=usuario)
        for n in ('1', '2', '3'):
            cargo = getattr(exp, f'cargo{n}')
            empresa = getattr(exp, f'nome_empresa{n}')
            if cargo or empresa:
                parts.append(f"experiência: {cargo or ''} em {empresa or ''}")
    except ExperienciaProfissional.DoesNotExist:
        pass

    if usuario.interesses_hobbies:
        parts.append(f"interesses: {usuario.interesses_hobbies}")

    return "\n".join(parts)


def build_job_text(vaga: Vagas) -> str:
    parts = []

    if vaga.cargo_vaga:
        parts.append(f"cargo: {vaga.cargo_vaga}")
    if vaga.descricao_vaga:
        parts.append(f"descrição: {vaga.descricao_vaga}")
    if vaga.requisito_vaga:
        parts.append(f"requisitos: {vaga.requisito_vaga}")
    if vaga.local:
        parts.append(f"local: {vaga.local}")

    cursos = CursoVaga.objects.filter(vaga=vaga).values_list('curso', flat=True)
    if cursos:
        parts.append(f"cursos desejados: {', '.join(filter(None, cursos))}")

    try:
        parts.append(f"empresa: {vaga.empresa.nomefantasia}")
        if vaga.empresa.segmento:
            parts.append(f"segmento: {vaga.empresa.segmento}")
    except Exception:
        pass

    return "\n".join(parts)
```

- [ ] **Step 4: Rodar os testes**

```bash
python manage.py test matching.tests.BuildResumeTextTest matching.tests.BuildJobTextTest -v 2
```

Esperado: `Ran 9 tests in ...s  OK`

- [ ] **Step 5: Commit**

```bash
git add matching/text_builders.py matching/tests.py
git commit -m "feat: add text builders for resume and job indexing"
```

---

## Task 4: signals.py — Sincronização automática

**Files:**
- Create: `matching/signals.py`
- Modify: `matching/apps.py` (adicionar `ready()`)
- Modify: `matching/tests.py` (append)

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao final de `matching/tests.py`:

```python
class SyncUsuarioSignalTest(TestCase):
    def test_chama_update_resume_ao_salvar_usuario(self):
        mock_matcher = MagicMock()
        mock_usuario = MagicMock()
        mock_usuario.pk = 7
        mock_usuario.user.nome = 'João'

        with patch('matching.signals.get_matcher', return_value=mock_matcher):
            with patch('matching.signals.build_resume_text', return_value='texto currículo'):
                from matching.signals import sync_usuario
                sync_usuario(sender=None, instance=mock_usuario)

        mock_matcher.update_resume.assert_called_once_with(
            text='texto currículo',
            candidate_name='João',
            candidate_id='7',
        )

    def test_nao_propaga_excecao_do_matcher(self):
        mock_matcher = MagicMock()
        mock_matcher.update_resume.side_effect = Exception("ChromaDB error")
        mock_usuario = MagicMock()
        mock_usuario.pk = 99
        mock_usuario.user.nome = 'Ana'

        with patch('matching.signals.get_matcher', return_value=mock_matcher):
            with patch('matching.signals.build_resume_text', return_value='texto'):
                from matching.signals import sync_usuario
                try:
                    sync_usuario(sender=None, instance=mock_usuario)
                except Exception:
                    self.fail("sync_usuario propagou Exception — deve silenciar erros do matcher")


class SyncVagaSignalTest(TestCase):
    def test_chama_update_job_ao_salvar_vaga(self):
        mock_matcher = MagicMock()
        mock_vaga = MagicMock()
        mock_vaga.id = 3
        mock_vaga.cargo_vaga = 'Dev Python'
        mock_vaga.empresa.nomefantasia = 'TechCo'

        with patch('matching.signals.get_matcher', return_value=mock_matcher):
            with patch('matching.signals.build_job_text', return_value='texto vaga'):
                from matching.signals import sync_vaga
                sync_vaga(sender=None, instance=mock_vaga)

        mock_matcher.update_job.assert_called_once_with(
            text='texto vaga',
            job_title='Dev Python',
            company='TechCo',
            job_id='3',
        )

    def test_nao_propaga_excecao_do_matcher(self):
        mock_matcher = MagicMock()
        mock_matcher.update_job.side_effect = Exception("erro")
        mock_vaga = MagicMock()
        mock_vaga.id = 5
        mock_vaga.cargo_vaga = 'Analista'
        mock_vaga.empresa.nomefantasia = 'Corp'

        with patch('matching.signals.get_matcher', return_value=mock_matcher):
            with patch('matching.signals.build_job_text', return_value='texto'):
                from matching.signals import sync_vaga
                try:
                    sync_vaga(sender=None, instance=mock_vaga)
                except Exception:
                    self.fail("sync_vaga propagou Exception — deve silenciar erros do matcher")
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python manage.py test matching.tests.SyncUsuarioSignalTest matching.tests.SyncVagaSignalTest -v 2
```

Esperado: `ERROR` com `ImportError: cannot import name 'sync_usuario' from 'matching.signals'`

- [ ] **Step 3: Criar `matching/signals.py`**

```python
# matching/signals.py
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models import Usuario
from vagas.models import Vagas
from .service import get_matcher
from .text_builders import build_resume_text, build_job_text

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Usuario)
def sync_usuario(sender, instance, **kwargs):
    try:
        get_matcher().update_resume(
            text=build_resume_text(instance),
            candidate_name=instance.user.nome,
            candidate_id=str(instance.pk),
        )
    except Exception:
        logger.exception("Erro ao sincronizar candidato %s com o JobMatcher", instance.pk)


@receiver(post_save, sender=Vagas)
def sync_vaga(sender, instance, **kwargs):
    try:
        get_matcher().update_job(
            text=build_job_text(instance),
            job_title=instance.cargo_vaga or "",
            company=instance.empresa.nomefantasia,
            job_id=str(instance.id),
        )
    except Exception:
        logger.exception("Erro ao sincronizar vaga %s com o JobMatcher", instance.id)
```

- [ ] **Step 4: Atualizar `matching/apps.py` para registrar os signals**

```python
# matching/apps.py
from django.apps import AppConfig


class MatchingConfig(AppConfig):
    name = "matching"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import matching.signals  # noqa
```

- [ ] **Step 5: Rodar os testes**

```bash
python manage.py test matching.tests.SyncUsuarioSignalTest matching.tests.SyncVagaSignalTest -v 2
```

Esperado: `Ran 4 tests in ...s  OK`

- [ ] **Step 6: Commit**

```bash
git add matching/signals.py matching/apps.py matching/tests.py
git commit -m "feat: add signals to sync Usuario and Vagas with JobMatcher"
```

---

## Task 5: views.py + urls.py — Endpoints JSON

**Files:**
- Create: `matching/views.py`
- Create: `matching/urls.py`
- Modify: `matching/tests.py` (append)

- [ ] **Step 1: Escrever os testes que falham**

Acrescente ao final de `matching/tests.py`:

```python
import json
from django.test import Client
from matching.schemas import MatchResult


class CandidatosParaVagaViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_retorna_200_com_lista_de_candidatos(self):
        resultados = [
            MatchResult(entity_id='1', name='João', score=0.9),
            MatchResult(entity_id='2', name='Maria', score=0.75),
        ]
        mock_matcher = MagicMock()
        mock_matcher.match_resumes_for_job.return_value = resultados

        with patch('matching.views.get_matcher', return_value=mock_matcher):
            response = self.client.get('/matching/candidatos/42/')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['resultados']), 2)
        self.assertEqual(data['resultados'][0]['nome'], 'João')
        self.assertAlmostEqual(data['resultados'][0]['score'], 0.9)

    def test_retorna_404_quando_vaga_nao_indexada(self):
        mock_matcher = MagicMock()
        mock_matcher.match_resumes_for_job.side_effect = ValueError("Vaga '42' não encontrada.")

        with patch('matching.views.get_matcher', return_value=mock_matcher):
            response = self.client.get('/matching/candidatos/42/')

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn('erro', data)

    def test_retorna_400_com_parametro_top_invalido(self):
        mock_matcher = MagicMock()
        mock_matcher.match_resumes_for_job.return_value = []

        with patch('matching.views.get_matcher', return_value=mock_matcher):
            response = self.client.get('/matching/candidatos/1/?top=abc')

        self.assertEqual(response.status_code, 400)

    def test_repassa_parametro_top_ao_matcher(self):
        mock_matcher = MagicMock()
        mock_matcher.match_resumes_for_job.return_value = []

        with patch('matching.views.get_matcher', return_value=mock_matcher):
            self.client.get('/matching/candidatos/1/?top=3')

        mock_matcher.match_resumes_for_job.assert_called_once_with(
            job_id='1', top_k=3, min_score=0.0
        )


class VagasParaUsuarioViewTest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_retorna_200_com_lista_de_vagas(self):
        resultados = [
            MatchResult(entity_id='10', name='Dev Python', company='TechCo', score=0.88),
        ]
        mock_matcher = MagicMock()
        mock_matcher.match_jobs_for_resume.return_value = resultados

        with patch('matching.views.get_matcher', return_value=mock_matcher):
            response = self.client.get('/matching/vagas-para/7/')

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['resultados']), 1)
        self.assertEqual(data['resultados'][0]['cargo'], 'Dev Python')
        self.assertEqual(data['resultados'][0]['empresa'], 'TechCo')

    def test_retorna_404_quando_candidato_nao_indexado(self):
        mock_matcher = MagicMock()
        mock_matcher.match_jobs_for_resume.side_effect = ValueError("Candidato '7' não encontrado.")

        with patch('matching.views.get_matcher', return_value=mock_matcher):
            response = self.client.get('/matching/vagas-para/7/')

        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertIn('erro', data)

    def test_repassa_parametro_min_score_ao_matcher(self):
        mock_matcher = MagicMock()
        mock_matcher.match_jobs_for_resume.return_value = []

        with patch('matching.views.get_matcher', return_value=mock_matcher):
            self.client.get('/matching/vagas-para/7/?min_score=0.5')

        mock_matcher.match_jobs_for_resume.assert_called_once_with(
            candidate_id='7', top_k=5, min_score=0.5
        )

    def test_retorna_400_com_min_score_invalido(self):
        mock_matcher = MagicMock()
        mock_matcher.match_jobs_for_resume.return_value = []

        with patch('matching.views.get_matcher', return_value=mock_matcher):
            response = self.client.get('/matching/vagas-para/7/?min_score=nao_numero')

        self.assertEqual(response.status_code, 400)
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python manage.py test matching.tests.CandidatosParaVagaViewTest matching.tests.VagasParaUsuarioViewTest -v 2
```

Esperado: `ERROR` — URL não encontrada ou `ModuleNotFoundError`

- [ ] **Step 3: Criar `matching/urls.py`**

```python
# matching/urls.py
from django.urls import path
from . import views

app_name = "matching"

urlpatterns = [
    path("candidatos/<int:vaga_id>/", views.candidatos_para_vaga, name="candidatos_para_vaga"),
    path("vagas-para/<int:usuario_pk>/", views.vagas_para_usuario, name="vagas_para_usuario"),
]
```

- [ ] **Step 4: Criar `matching/views.py`**

```python
# matching/views.py
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .service import get_matcher

logger = logging.getLogger(__name__)


@require_GET
def candidatos_para_vaga(request, vaga_id):
    top_k = _parse_int(request.GET.get('top'), default=5, min_val=1, max_val=50)
    min_score = _parse_float(request.GET.get('min_score'), default=0.0)

    if top_k is None or min_score is None:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)

    try:
        resultados = get_matcher().match_resumes_for_job(
            job_id=str(vaga_id), top_k=top_k, min_score=min_score
        )
    except ValueError as e:
        return JsonResponse({"erro": str(e)}, status=404)
    except Exception:
        logger.exception("Erro no matching para vaga %s", vaga_id)
        return JsonResponse({"erro": "Erro interno."}, status=500)

    return JsonResponse({
        "resultados": [
            {"id": r.entity_id, "nome": r.name, "score": r.score}
            for r in resultados
        ]
    })


@require_GET
def vagas_para_usuario(request, usuario_pk):
    top_k = _parse_int(request.GET.get('top'), default=5, min_val=1, max_val=50)
    min_score = _parse_float(request.GET.get('min_score'), default=0.0)

    if top_k is None or min_score is None:
        return JsonResponse({"erro": "Parâmetros inválidos."}, status=400)

    try:
        resultados = get_matcher().match_jobs_for_resume(
            candidate_id=str(usuario_pk), top_k=top_k, min_score=min_score
        )
    except ValueError as e:
        return JsonResponse({"erro": str(e)}, status=404)
    except Exception:
        logger.exception("Erro no matching para candidato %s", usuario_pk)
        return JsonResponse({"erro": "Erro interno."}, status=500)

    return JsonResponse({
        "resultados": [
            {"id": r.entity_id, "cargo": r.name, "empresa": r.company, "score": r.score}
            for r in resultados
        ]
    })


def _parse_int(value, *, default: int, min_val: int, max_val: int):
    if value is None:
        return default
    try:
        v = int(value)
        return v if min_val <= v <= max_val else None
    except (ValueError, TypeError):
        return None


def _parse_float(value, *, default: float):
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
```

- [ ] **Step 5: Rodar todos os testes do app**

```bash
python manage.py test matching -v 2
```

Esperado: todos os testes passam — `OK`

- [ ] **Step 6: Commit final**

```bash
git add matching/views.py matching/urls.py matching/tests.py
git commit -m "feat: add matching endpoints — candidatos por vaga e vagas por candidato"
```
