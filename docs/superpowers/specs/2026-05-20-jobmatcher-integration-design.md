# JobMatcher Integration — Design Spec

**Data:** 2026-05-20  
**Branch:** Matching  
**Escopo:** Integrar o `JobMatcher` existente ao Django, sincronizando automaticamente Usuários e Vagas, e expondo endpoints JSON para consulta de matches.

---

## Contexto

O diretório `matching/` já contém uma implementação completa do `JobMatcher` (`matcher.py` + `schemas.py`) usando ChromaDB e SentenceTransformer (BERT Português). Atualmente é um módulo Python isolado, sem integração com o Django.

O objetivo é:
1. Transformar `matching/` em Django app
2. Sincronizar automaticamente com o `JobMatcher` ao salvar `Usuario` ou `Vagas`
3. Expor dois endpoints JSON: melhores candidatos por vaga e melhores vagas por candidato

---

## Arquitetura

### Estrutura de arquivos

```
matching/
├── __init__.py
├── apps.py             # registra signals no ready()
├── service.py          # singleton do JobMatcher
├── text_builders.py    # monta texto de Usuario e Vagas para indexação
├── signals.py          # post_save em Usuario e Vagas
├── views.py            # endpoints JSON
├── urls.py             # rotas
├── matcher.py          # (existente — sem alterações)
└── schemas.py          # (existente — sem alterações)
```

### Configurações adicionadas em `settings.py`

```python
INSTALLED_APPS = [
    ...
    "matching",
]

CHROMADB_PATH = BASE_DIR / "chromadb"
```

---

## Componentes

### `service.py` — Singleton do JobMatcher

Mantém uma única instância do `JobMatcher` por processo Django, com ChromaDB persistido em disco em `CHROMADB_PATH`.

```python
_matcher: JobMatcher | None = None

def get_matcher() -> JobMatcher:
    global _matcher
    if _matcher is None:
        _matcher = JobMatcher(persist_directory=str(settings.CHROMADB_PATH))
    return _matcher
```

### `text_builders.py` — Montagem de texto para indexação

**`build_resume_text(usuario: Usuario) -> str`**

Concatena os seguintes campos do modelo `Usuario` e seus relacionamentos:

- Objetivo profissional: `cargo_pretendido`, `area_interesse`, `disponibilidade`, `remoto`
- Formação acadêmica (blocos 1–3): `instituicao_nome`, `grau_escolaridade`, `curso_graduacao`, `situacao_academica`
- Competências (blocos 1–3): `competencias_tecnicas`, `competencias_comportamentais`
- Experiências (`ExperienciaProfissional`): `cargo1-3` + `nome_empresa1-3`
- Informações adicionais: `curso`, `interesses_hobbies`

**`build_job_text(vaga: Vagas) -> str`**

Concatena:

- `cargo_vaga`, `descricao_vaga`, `requisito_vaga`, `local`
- Cursos via `CursoVaga` (related)
- `empresa.nomefantasia`, `empresa.segmento`

### `signals.py` — Sincronização automática

Usa `post_save` do Django nos models `Usuario` e `Vagas`. Chama `update_resume` / `update_job` (que internamente fazem delete + re-insert no ChromaDB), funcionando para criação e edição.

```python
@receiver(post_save, sender=Usuario)
def sync_usuario(sender, instance, **kwargs): ...

@receiver(post_save, sender=Vagas)
def sync_vaga(sender, instance, **kwargs): ...
```

### `apps.py` — Registro dos signals

```python
class MatchingConfig(AppConfig):
    name = "matching"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import matching.signals  # noqa
```

---

## Endpoints

### `GET /matching/candidatos/<vaga_id>/`

Retorna os melhores candidatos para uma vaga.

**Parâmetros query:** `top` (default 5), `min_score` (default 0.0)

**Resposta 200:**
```json
{
  "resultados": [
    {"id": "12", "nome": "João Silva", "score": 0.87},
    ...
  ]
}
```

**Erros:** `404 {"erro": "Vaga não encontrada"}` | `400 {"erro": "..."}`

---

### `GET /matching/vagas-para/<usuario_pk>/`

Retorna as melhores vagas para um candidato.

**Parâmetros query:** `top` (default 5), `min_score` (default 0.0)

**Resposta 200:**
```json
{
  "resultados": [
    {"id": "42", "cargo": "Dev Python", "empresa": "TechCo", "score": 0.87},
    ...
  ]
}
```

**Erros:** `404 {"erro": "Candidato não encontrado"}` | `400 {"erro": "..."}`

---

### `config/urls.py` — Registro das rotas

```python
path("matching/", include("matching.urls")),
```

---

## Fluxo de dados

```
Usuário salva perfil
  └─► post_save(Usuario)
        └─► build_resume_text(usuario)
              └─► get_matcher().update_resume(text, name, pk)
                    └─► ChromaDB (chromadb/ em disco)

Empresa cria/edita Vaga
  └─► post_save(Vagas)
        └─► build_job_text(vaga)
              └─► get_matcher().update_job(text, title, company, id)
                    └─► ChromaDB (chromadb/ em disco)

GET /matching/candidatos/<vaga_id>/
  └─► get_matcher().match_resumes_for_job(vaga_id, top_k, min_score)
        └─► JsonResponse(resultados)
```

---

## Tratamento de erros

- Se o `JobMatcher` lançar exceção no signal, o erro é capturado e logado (`logger.exception`) sem interromper o save do Django.
- Se a vaga ou candidato não estiver indexado (recém-criado e ainda sem chunks), os endpoints retornam lista vazia com status 200.
- Parâmetros `top` e `min_score` inválidos retornam 400.

---

## Fora do escopo

- Indexação retroativa de registros existentes (pode ser feito via management command futuro)
- Autenticação nos endpoints de matching
- Celery / processamento assíncrono
