# Unificar Gravação de Experiência Profissional — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `cadastro_completo` persist professional-experience data to `ExperienciaProfissional` (the same table `perfil` already uses), instead of silently discarding it.

**Architecture:** `cadastro_completo` (core/views.py) currently assigns `usuario.nome_empresa1`, `usuario.cargo1`, `usuario.data_inicio1`, `usuario.data_fim1` (and `2`/`3` variants) directly on the `Usuario` instance. **`Usuario` has never had those fields** — they only exist on `ExperienciaProfissional` (core/models.py:195). So these assignments are dead code: Python happily sets arbitrary attributes on model instances, but `usuario.save()` only writes real model fields, so the values are silently dropped on every "cadastro completo" submission. `perfil/views.py:_atualizar_experiencias` (line 297) already does this correctly via `ExperienciaProfissional.objects.get_or_create(usuario=usuario)`. Fix: replace the dead assignments in `cadastro_completo` with the same get_or_create + setattr pattern, parsing dates the same way `perfil` does.

**Tech Stack:** Django (core app), no new migrations needed.

## Global Constraints

- No DB migration required — confirmed via `core/migrations/`: `Usuario` was never defined with `nome_empresa*`/`cargo*`/`data_inicio*`/`data_fim*` columns (checked `0001_initial.py` and all `RemoveField` migrations — none touch these on `Usuario`). `ExperienciaProfissional` has been a separate model since `0001_initial.py`.
- No data migration/backfill needed — because the `Usuario` columns never existed, no experience data was ever persisted through the `cadastro_completo` path; there is nothing on `Usuario` to move.
- Template field names (`txtNomeEmpresa1`, `txtCargo1`, `txtDataProf1`, `txtDataFimProf1`, …) in `core/templates/cadastro_usuario_completo.html` stay unchanged — only the view-side handling changes.
- Keep `_parse_date` behavior identical to `perfil/views.py:334` (`%Y-%m-%d`, returns `None` on falsy/invalid input).

---

### Task 1: Fix `cadastro_completo` to persist experience via `ExperienciaProfissional`

**Files:**
- Modify: `core/views.py` (function `cadastro_completo`, currently starting at `core/views.py:235`)
- Test: `core/tests.py` (create if it doesn't already cover this view — check first with `ls core/tests*.py core/tests/ 2>/dev/null`)

**Interfaces:**
- Consumes: `core.models.ExperienciaProfissional` (fields `usuario`, `nome_empresa{1,2,3}`, `cargo{1,2,3}`, `data_inicio{1,2,3}`, `data_fim{1,2,3}`), `core.models.Usuario`.
- Produces: nothing new consumed elsewhere — this is a leaf fix.

- [ ] **Step 1: Write failing test asserting experience data is persisted**

Add to `core/tests.py` (adjust imports/fixtures to match existing test setup conventions in that file — check how `Usuario`/`UsuarioBase` test users are built elsewhere in the file before writing this):

```python
from django.test import TestCase, Client
from core.models import ExperienciaProfissional, Usuario

class CadastroCompletoExperienciaTest(TestCase):
    def setUp(self):
        # Reuse whatever helper/pattern existing tests in this file use to
        # create a UsuarioBase + Usuario and log the session in as
        # 'email_atual'. If no such helper exists yet, create the user
        # directly and set request.session['email_atual'] via client session.
        self.usuario = self._criar_usuario_completo_para_teste()
        self.client = Client()
        session = self.client.session
        session['email_atual'] = self.usuario.user.email
        session.save()

    def test_experiencia_profissional_1_e_persistida(self):
        self.client.post('/core/cadastro-completo/', {
            'txtNomeEmpresa1': 'Empresa Teste',
            'txtCargo1': 'Desenvolvedor',
            'txtDataProf1': '2020-01-01',
            'txtDataFimProf1': '2021-01-01',
        })
        exp = ExperienciaProfissional.objects.get(usuario=self.usuario)
        self.assertEqual(exp.nome_empresa1, 'Empresa Teste')
        self.assertEqual(exp.cargo1, 'Desenvolvedor')
        self.assertEqual(str(exp.data_inicio1), '2020-01-01')
        self.assertEqual(str(exp.data_fim1), '2021-01-01')
```

Note: confirm the actual URL name/path for `cadastro_completo` in `core/urls.py` before running — use `reverse('core:cadastro_completo')` (or whatever name is registered) instead of a hardcoded path if the codebase's other tests use `reverse`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test core.tests.CadastroCompletoExperienciaTest -v 2`
Expected: FAIL — `ExperienciaProfissional.DoesNotExist` (no row created), because current code writes to non-existent `usuario.nome_empresa1` etc.

- [ ] **Step 3: Replace dead `usuario.nome_empresa*` block with real persistence**

In `core/views.py`, inside `cadastro_completo`, find this block (originally around line 391, right after the "Experiencia profissional" comment):

```python
        # Experiencia profissional  
        usuario.nome_empresa1 = nome_empresa1
        usuario.cargo1 = cargo1
        usuario.data_inicio1 = data_inicio1
        usuario.data_fim1 = data_fim1
        # 2 
        usuario.nome_empresa2 = nome_empresa2
        usuario.cargo2 = cargo2
        usuario.data_inicio2 = data_inicio2
        usuario.data_fim2 = data_fim2
        # 3  
        usuario.nome_empresa3 = nome_empresa3
        usuario.cargo3 = cargo3
        usuario.data_inicio3 = data_inicio3
        usuario.data_fim3 = data_fim3
        # end Experiencia
        #  ------------------
```

Delete it entirely (the local variables `nome_empresa1..3`, `cargo1..3`, `data_inicio1..3`, `data_fim1..3` read earlier in the function from `request.POST` stay — they're now consumed below instead).

- [ ] **Step 4: Add `ExperienciaProfissional` persistence after `usuario.save()`**

Still in `cadastro_completo`, find the tail of the function:

```python
        usuario.save()

        # del request.session['usuario_email']
        messages.success(request, 'Cadastro realizado com sucesso!')
        return render(request, 'home.html')
```

Replace with:

```python
        usuario.save()

        exp, _ = ExperienciaProfissional.objects.get_or_create(usuario=usuario)
        exp.nome_empresa1 = nome_empresa1 or None
        exp.cargo1 = cargo1 or None
        exp.data_inicio1 = _parse_date(data_inicio1)
        exp.data_fim1 = _parse_date(data_fim1)
        exp.nome_empresa2 = nome_empresa2 or None
        exp.cargo2 = cargo2 or None
        exp.data_inicio2 = _parse_date(data_inicio2)
        exp.data_fim2 = _parse_date(data_fim2)
        exp.nome_empresa3 = nome_empresa3 or None
        exp.cargo3 = cargo3 or None
        exp.data_inicio3 = _parse_date(data_inicio3)
        exp.data_fim3 = _parse_date(data_fim3)
        exp.save()

        # del request.session['usuario_email']
        messages.success(request, 'Cadastro realizado com sucesso!')
        return render(request, 'home.html')
```

- [ ] **Step 5: Remove now-dead entries from `campos_verif`**

In the same function, find:

```python
        campos_verif = [
            'data_nascimento', 'data_admissao', 'data_demissao',

            'pretensao_salarial',

            # Formação Acadêmica
            'data_acad_inicio1', 'data_acad_fim1',
            'data_acad_inicio2', 'data_acad_fim2',
            'data_acad_inicio3', 'data_acad_fim3',
            
            # Experiência Profissional
            'data_inicio1', 'data_fim1',
            'data_inicio2', 'data_fim2',
            'data_inicio3', 'data_fim3',
            
            # Cursos Extracurriculares
            'data_conclusao1', 'data_conclusao2', 'data_conclusao3'
        ]
```

Remove the `# Experiência Profissional` block (those `getattr(usuario, 'data_inicio1', None)` lookups were always `None` since `Usuario` never had these fields — the loop below was a no-op for them; deleting is safe cleanup, not a behavior change for `usuario`):

```python
        campos_verif = [
            'data_nascimento', 'data_admissao', 'data_demissao',

            'pretensao_salarial',

            # Formação Acadêmica
            'data_acad_inicio1', 'data_acad_fim1',
            'data_acad_inicio2', 'data_acad_fim2',
            'data_acad_inicio3', 'data_acad_fim3',

            # Cursos Extracurriculares
            'data_conclusao1', 'data_conclusao2', 'data_conclusao3'
        ]
```

- [ ] **Step 6: Add `_parse_date` helper to `core/views.py`**

`cadastro_completo` now calls `_parse_date`, which only exists in `perfil/views.py` today. Add near the top of `core/views.py` (after the imports, before the first view function) — verify no existing `_parse_date` already exists in `core/views.py` first (`grep -n "_parse_date" core/views.py`):

```python
def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return None
```

Ensure `datetime` is imported at the top of `core/views.py` (`grep -n "^from datetime\|^import datetime" core/views.py` — add `from datetime import datetime` if missing).

- [ ] **Step 7: Run test to verify it passes**

Run: `python manage.py test core.tests.CadastroCompletoExperienciaTest -v 2`
Expected: PASS

- [ ] **Step 8: Run full core test suite to check for regressions**

Run: `python manage.py test core -v 2`
Expected: all PASS (no test should have depended on the dead `usuario.nome_empresa1` etc. attributes, since they were never persisted)

- [ ] **Step 9: Commit**

```bash
git add core/views.py core/tests.py
git commit -m "fix: persist experiência profissional from cadastro_completo to ExperienciaProfissional"
```

---

## Notes for the executor — deviation from the original ticket

The original ticket assumed `Usuario` has `nome_empresa1..3`/`cargo1..3`/`data_inicio1..3`/`data_fim1..3` columns that need a migration + backfill + column removal. **That's not the current state of the code.** `ExperienciaProfissional` has been its own model since the initial migration; `Usuario` never had those columns. The only real bug is that `cadastro_completo` was writing to non-existent attributes on `Usuario` (silently discarded, never an error, never persisted). This plan fixes that root cause without any schema change. If you find evidence otherwise (e.g., a column that actually exists in production but is missing from migrations), stop and flag it before proceeding — that would mean migration history is out of sync with the live DB, which needs separate handling.

**Known related bug out of scope:** the same dead-attribute pattern exists in `cadastro_completo` for `CursoExtraCurricular` (`usuario.nome_curso1` etc., core/views.py ~line 423) — `Usuario` has no such fields either, so cursos extracurriculares submitted at initial cadastro are also silently dropped. Not touched here since the ticket only covers experience; flag to the user as a likely follow-up ticket.
