# Padrão único de e-mails — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Todos os e-mails do Django saem por `enviar_email(para, tipo, contexto)`, com assunto `[Canastra HUB] ...`, template HTML base de 600px e versão em texto puro.

**Architecture:** `core/servico_email.py` continua sendo o transporte (Apps Script) e ganha o campo `texto`. O novo `core/emails.py` guarda o registro `TIPOS`, renderiza `<template>.html` + `<template>.txt` (filhos de `email/base_email.html|.txt`), valida limites e chama o transporte. Os 7 e-mails existentes migram um a um; `GoogleEmailService` sai.

**Tech Stack:** Django (templates, `render_to_string`, management commands), `unittest.mock`, testes com `manage.py test`.

**Spec:** `docs/superpowers/specs/2026-11-12-padrao-emails-design.md`

**Como rodar testes:** `.venv/bin/python manage.py test <labels> --settings=config.settings_test` (SQLite em memória; `GAS_EMAIL_URL` vazio).

## Global Constraints

- Assunto: `[Canastra HUB] <assunto>`, no máximo 60 caracteres; acima de 200 o envio é recusado.
- HTML e texto: no máximo 20.000 caracteres cada.
- Tratamento por "você"; saudação `Olá, {nome},` (sem nome: `Olá,`); assinatura `Atenciosamente,` / `Equipe Canastra HUB`.
- Rodapé: `Canastra HUB · Dúvidas? Fale com a gente: <link_contato>` e `Esta é uma mensagem automática. Não responda a este e-mail.`
- Layout: tabelas, CSS inline, `width="600"` + `max-width:600px`; cores `#28a745` (destaque), `#1f2d24` (títulos), `#4a534e` (corpo), `#8a938e` (secundário), `#f4f6f5` (fundo); Arial 15px, line-height 1.6.
- Logo: `settings.EMAIL_LOGO_URL`, padrão `https://raw.githubusercontent.com/vitorrmoraisss/Canastra-HUB/main/resources/static/img/logoCanastra.jpeg`, 180px, `alt="Canastra HUB"`.
- Nunca montar HTML de e-mail com f-string; variáveis só via template com autoescape.
- Nenhum código fora de `core/emails.py` chama `ServicoEmail.enviar`.
- `docs/` está no `.gitignore`: arquivos novos ali exigem `git add -f`.
- `.env.example` tem alteração do usuário ainda não commitada (remoção do bloco `RECUPERACAO_*`). Não commitar esse arquivo sem perguntar.

## Review Focus

1. Destinatário sem nome (`nome` vazio ou `None`): a saudação deve sair `Olá,`, nunca `Olá, ,`. Teste na Task 2.
2. Caracteres especiais no texto puro: `Ana & Bia` deve sair literal no `.txt` (sem `&amp;`) e escapado no HTML. Teste na Task 2.
3. Data da reserva em UTC: o e-mail de aprovação deve mostrar o horário de São Paulo (23:00 UTC → 20:00). O código atual mostra UTC. Teste na Task 6.
4. Texto do usuário com HTML e quebras de linha (contato, resposta, finalidade da reserva): sai escapado no HTML, com `<br>` nas quebras. Testes nas Tasks 4, 5 e 6.
5. E-mail de vagas com o máximo de vagas e descrições longas deve caber em 20.000 caracteres; senão o envio semanal falharia toda semana. Coberto pelo exemplo de 5 vagas no teste de todos os tipos (Task 7).

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `core/servico_email.py` (mod) | Transporte Apps Script; novo parâmetro `texto` |
| `core/emails.py` (novo) | `TIPOS`, `renderizar_email`, `enviar_email`, limites |
| `core/emails_exemplos.py` (novo) | `EXEMPLOS`: contexto de exemplo por tipo |
| `core/templates/email/base_email.html` / `.txt` (novo) | Layout, saudação, CTA, assinatura, rodapé |
| `core/templates/email/<tipo>.html` / `.txt` (novo) | Conteúdo de cada tipo |
| `core/templates/email/_detalhes_reserva.html` / `.txt` (novo) | Bloco de dados da reserva (HUB e FAST) |
| `matching/templates/email/vagas_semanais.html` / `.txt` (novo) | Conteúdo das vagas |
| `core/management/commands/enviar_emails_exemplo.py` (novo) | Envio manual de todos os tipos |
| `core/tests_emails.py` (novo) | Testes da camada central e de todos os tipos |
| `agendamento/tests_notificacoes.py` (novo) | Testes das aprovações |
| `docs/emails/guia-de-estilo.md` (novo) | Guia para novos e-mails + trecho do Apps Script |

---

### Task 1: Transporte aceita `texto`

**Files:**
- Modify: `core/servico_email.py`
- Test: `core/tests_servico_email.py`

**Interfaces:**
- Produces: `ServicoEmail.enviar(para, assunto, mensagem, html=True, texto=None) -> bool`. Com `texto`, o payload JSON ganha a chave `'texto'`.

- [ ] **Step 1: Write the failing test**

Em `core/tests_servico_email.py`, dentro de `ServicoEmailTest`, depois de `test_permite_texto_puro`:

```python
    @patch('core.servico_email.requests.post')
    def test_envia_versao_texto_quando_informada(self, post):
        post.return_value = resposta_gas()
        ServicoEmail.enviar('a@example.com', 'Assunto', '<p>Oi</p>', texto='Oi')
        self.assertEqual(post.call_args.kwargs['json']['texto'], 'Oi')

    @patch('core.servico_email.requests.post')
    def test_sem_texto_nao_envia_a_chave(self, post):
        post.return_value = resposta_gas()
        ServicoEmail.enviar('a@example.com', 'Assunto', '<p>Oi</p>')
        self.assertNotIn('texto', post.call_args.kwargs['json'])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test core.tests_servico_email.ServicoEmailTest --settings=config.settings_test`
Expected: FAIL/ERROR em `test_envia_versao_texto_quando_informada` com `TypeError: ... unexpected keyword argument 'texto'`.

- [ ] **Step 3: Write minimal implementation**

Em `core/servico_email.py`, troque a assinatura e a montagem do payload:

```python
    @classmethod
    def enviar(cls, para, assunto, mensagem, html=True, texto=None):
        """Retorna True só quando o provedor confirma o envio.

        `texto` é a versão em texto puro (multipart) quando a mensagem é HTML.
        """
        if not settings.GAS_EMAIL_URL or not settings.GAS_API_SECRET:
            logger.error('E-mail não enviado: GAS_EMAIL_URL ou GAS_API_SECRET não configurados')
            return False

        payload = {
            'secret': settings.GAS_API_SECRET,
            'para': para,
            'assunto': assunto,
            'mensagem': mensagem,
            'html': html,
        }
        if texto is not None:
            payload['texto'] = texto

        try:
            resposta = requests.post(settings.GAS_EMAIL_URL, json=payload, timeout=cls.TIMEOUT)
            resposta.raise_for_status()
            dados = resposta.json()
        except (requests.RequestException, ValueError):
            logger.exception('Falha ao enviar e-mail')
            return False
```

(O restante do método, a checagem de `status == 'sucesso'`, fica igual.)

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python manage.py test core.tests_servico_email.ServicoEmailTest --settings=config.settings_test`
Expected: PASS (todos, incluindo `test_envia_payload_do_apps_script`, que segue sem `texto`).

- [ ] **Step 5: Commit**

```bash
git add core/servico_email.py core/tests_servico_email.py
git commit -m "ServicoEmail aceita versão em texto puro (campo texto)"
```

---

### Task 2: Serviço central, template base e primeiro tipo

**Files:**
- Create: `core/emails.py`, `core/emails_exemplos.py`
- Create: `core/templates/email/base_email.html`, `core/templates/email/base_email.txt`
- Create: `core/templates/email/codigo_verificacao.html`, `core/templates/email/codigo_verificacao.txt`
- Modify: `config/settings.py` (logo)
- Test: `core/tests_emails.py`

**Interfaces:**
- Consumes: `ServicoEmail.enviar(..., html=True, texto=...)` (Task 1).
- Produces:
  - `core.emails.TIPOS: dict[str, TipoEmail]`; `TipoEmail(assunto: str, template: str)`.
  - `core.emails.renderizar_email(tipo: str, contexto: dict) -> EmailRenderizado(assunto, html, texto)`; `ValueError` para tipo desconhecido.
  - `core.emails.enviar_email(para: str | list[str], tipo: str, contexto: dict) -> bool`.
  - Constantes `PREFIXO_ASSUNTO`, `LIMITE_ASSUNTO_ESTILO=60`, `LIMITE_ASSUNTO_ENDPOINT=200`, `LIMITE_CORPO=20_000`.
  - `core.emails_exemplos.EXEMPLOS: dict[str, dict]` — **toda task que adiciona um tipo em `TIPOS` adiciona a entrada correspondente aqui** (o teste `test_todo_tipo_tem_exemplo` exige).
  - Blocos da base: `preheader`, `titulo`, `saudacao`, `conteudo`, `cta`, `complementar`, `assinatura`, `rodape_extra`. CTA automático a partir de `cta_texto` + `cta_link` no contexto.
  - Contexto global injetado: `site_url`, `logo_url`, `link_contato`, `assunto`.

- [ ] **Step 1: Write the failing tests**

Crie `core/tests_emails.py`:

```python
"""Testes do serviço central de e-mails (core/emails.py) e de todos os tipos."""
import re
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core import emails
from core.emails_exemplos import EXEMPLOS

CONFIG = {'SITE_URL': 'https://canastra.example', 'EMAIL_LOGO_URL': 'https://cdn.example/logo.jpg'}


@override_settings(**CONFIG)
class TodosOsTiposTest(SimpleTestCase):
    def test_todo_tipo_tem_exemplo(self):
        self.assertEqual(set(EXEMPLOS), set(emails.TIPOS))

    def test_padrao_de_cada_tipo(self):
        for tipo in emails.TIPOS:
            with self.subTest(tipo=tipo):
                contexto = EXEMPLOS[tipo]
                email = emails.renderizar_email(tipo, contexto)

                self.assertTrue(email.assunto.startswith('[Canastra HUB] '))
                self.assertLessEqual(len(email.assunto), emails.LIMITE_ASSUNTO_ESTILO)
                self.assertIn('https://cdn.example/logo.jpg', email.html)
                self.assertIn('https://canastra.example/contato/', email.html)
                self.assertIn('https://canastra.example/contato/', email.texto)
                for corpo in (email.html, email.texto):
                    self.assertIn('Olá', corpo)
                    self.assertIn('Equipe Canastra HUB', corpo)
                    self.assertIn('Não responda a este e-mail', corpo)
                    self.assertLessEqual(len(corpo), emails.LIMITE_CORPO)
                self.assertIsNone(re.search(r'<[a-zA-Z/!]', email.texto), 'texto puro com tag HTML')
                if contexto.get('cta_link'):
                    self.assertIn(f'href="{contexto["cta_link"]}"', email.html)
                    self.assertIn(contexto['cta_link'], email.texto)


@override_settings(**CONFIG)
class RenderizarEmailTest(SimpleTestCase):
    def test_tipo_desconhecido_gera_erro(self):
        with self.assertRaises(ValueError):
            emails.renderizar_email('inexistente', {})

    def test_saudacao_sem_nome(self):
        for nome in ('', None):
            with self.subTest(nome=nome):
                email = emails.renderizar_email('codigo_verificacao', {**EXEMPLOS['codigo_verificacao'], 'nome': nome})
                self.assertIn('Olá,', email.texto)
                self.assertNotIn('Olá, ,', email.texto)
                self.assertNotIn('None', email.texto)

    def test_texto_puro_nao_escapa_e_html_escapa(self):
        email = emails.renderizar_email('codigo_verificacao', {**EXEMPLOS['codigo_verificacao'], 'nome': 'Ana & Bia'})
        self.assertIn('Olá, Ana & Bia,', email.texto)
        self.assertIn('Ana &amp; Bia', email.html)

    def test_assunto_com_campo_e_sem_quebra_de_linha(self):
        tipo = emails.TipoEmail('Aviso {x}', 'email/codigo_verificacao')
        with patch.dict(emails.TIPOS, {'teste': tipo}):
            email = emails.renderizar_email('teste', {**EXEMPLOS['codigo_verificacao'], 'x': 'linha 1\nlinha 2'})
        self.assertEqual(email.assunto, '[Canastra HUB] Aviso linha 1 linha 2')

    def test_texto_sem_linhas_em_branco_repetidas(self):
        email = emails.renderizar_email('codigo_verificacao', EXEMPLOS['codigo_verificacao'])
        self.assertNotIn('\n\n\n', email.texto)


@override_settings(**CONFIG)
class EnviarEmailTest(SimpleTestCase):
    contexto = EXEMPLOS['codigo_verificacao']

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_envia_html_e_texto(self, enviar):
        self.assertTrue(emails.enviar_email('a@example.com', 'codigo_verificacao', self.contexto))

        enviar.assert_called_once()
        para, assunto, html = enviar.call_args.args
        self.assertEqual(para, 'a@example.com')
        self.assertEqual(assunto, '[Canastra HUB] Código de verificação')
        self.assertIn(self.contexto['codigo'], html)
        self.assertTrue(enviar.call_args.kwargs['html'])
        self.assertIn(self.contexto['codigo'], enviar.call_args.kwargs['texto'])

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_lista_envia_um_por_destinatario_e_ignora_vazios(self, enviar):
        self.assertTrue(emails.enviar_email(['a@example.com', '', ' b@example.com ', None], 'codigo_verificacao', self.contexto))
        self.assertEqual([c.args[0] for c in enviar.call_args_list], ['a@example.com', 'b@example.com'])

    @patch('core.emails.ServicoEmail.enviar')
    def test_falha_de_um_destinatario_nao_interrompe_os_demais(self, enviar):
        enviar.side_effect = lambda para, *a, **k: para != 'a@example.com'
        self.assertFalse(emails.enviar_email(['a@example.com', 'b@example.com'], 'codigo_verificacao', self.contexto))
        self.assertEqual(enviar.call_count, 2)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_sem_destinatario_nao_envia(self, enviar):
        with self.assertLogs('core.emails', level='ERROR'):
            self.assertFalse(emails.enviar_email(['', None], 'codigo_verificacao', self.contexto))
        enviar.assert_not_called()

    @patch('core.emails.LIMITE_CORPO', 10)
    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_corpo_acima_do_limite_nao_envia(self, enviar):
        with self.assertLogs('core.emails', level='ERROR'):
            self.assertFalse(emails.enviar_email('a@example.com', 'codigo_verificacao', self.contexto))
        enviar.assert_not_called()

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_assunto_acima_do_limite_tecnico_nao_envia(self, enviar):
        with patch.dict(emails.TIPOS, {'teste': emails.TipoEmail('x' * 190, 'email/codigo_verificacao')}):
            with self.assertLogs('core.emails', level='ERROR'):
                self.assertFalse(emails.enviar_email('a@example.com', 'teste', self.contexto))
        enviar.assert_not_called()

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_assunto_longo_avisa_mas_envia(self, enviar):
        with patch.dict(emails.TIPOS, {'teste': emails.TipoEmail('x' * 50, 'email/codigo_verificacao')}):
            with self.assertLogs('core.emails', level='WARNING'):
                self.assertTrue(emails.enviar_email('a@example.com', 'teste', self.contexto))
        enviar.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python manage.py test core.tests_emails --settings=config.settings_test`
Expected: ERROR `ModuleNotFoundError: No module named 'core.emails_exemplos'` (ou `core.emails`).

- [ ] **Step 3: Add the logo setting**

Em `config/settings.py`, logo abaixo de `SITE_URL = ...` (linha ~224):

```python
# Logo dos e-mails: precisa ser uma URL pública e absoluta (clientes de e-mail não leem arquivos locais).
EMAIL_LOGO_URL = os.getenv(
    'EMAIL_LOGO_URL',
    'https://raw.githubusercontent.com/vitorrmoraisss/Canastra-HUB/main/resources/static/img/logoCanastra.jpeg',
)
```

- [ ] **Step 4: Create `core/emails.py`**

```python
"""Montagem e envio padronizado de todos os e-mails do sistema.

Todo e-mail sai por enviar_email(para, tipo, contexto). Cada tipo tem um
assunto e um par de templates (<template>.html e <template>.txt) que herdam
email/base_email.html e email/base_email.txt.

Guia de estilo: docs/emails/guia-de-estilo.md
"""
import logging
import re
from dataclasses import dataclass

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from core.servico_email import ServicoEmail

logger = logging.getLogger(__name__)

PREFIXO_ASSUNTO = '[Canastra HUB]'
LIMITE_ASSUNTO_ESTILO = 60
LIMITE_ASSUNTO_ENDPOINT = 200
LIMITE_CORPO = 20_000


@dataclass(frozen=True)
class TipoEmail:
    assunto: str   # aceita campos de str.format com chaves do contexto
    template: str  # caminho sem extensão; renderiza .html e .txt


@dataclass(frozen=True)
class EmailRenderizado:
    assunto: str
    html: str
    texto: str


TIPOS = {
    'codigo_verificacao': TipoEmail('Código de verificação', 'email/codigo_verificacao'),
}


def _contexto_global():
    return {
        'site_url': settings.SITE_URL,
        'logo_url': settings.EMAIL_LOGO_URL,
        'link_contato': f"{settings.SITE_URL}{reverse('core:contato')}",
    }


def _limpar_texto(texto):
    linhas = [linha.rstrip() for linha in texto.strip().splitlines()]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(linhas))


def renderizar_email(tipo, contexto):
    try:
        definicao = TIPOS[tipo]
    except KeyError:
        raise ValueError(f'Tipo de e-mail desconhecido: {tipo!r}') from None

    dados = {**_contexto_global(), **contexto}
    assunto = ' '.join(f'{PREFIXO_ASSUNTO} {definicao.assunto.format(**dados)}'.split())
    dados['assunto'] = assunto
    html = render_to_string(f'{definicao.template}.html', dados)
    texto = _limpar_texto(render_to_string(f'{definicao.template}.txt', dados))
    return EmailRenderizado(assunto=assunto, html=html, texto=texto)


def enviar_email(para, tipo, contexto):
    """Envia o e-mail do tipo para um ou mais destinatários.

    Retorna True só se todos os envios forem confirmados pelo provedor.
    """
    lista = [para] if isinstance(para, str) else list(para)
    destinatarios = [d.strip() for d in lista if d and d.strip()]
    if not destinatarios:
        logger.error('E-mail %s não enviado: nenhum destinatário', tipo)
        return False

    email = renderizar_email(tipo, contexto)

    if len(email.assunto) > LIMITE_ASSUNTO_ESTILO:
        logger.warning('Assunto do e-mail %s passa de %s caracteres: %r', tipo, LIMITE_ASSUNTO_ESTILO, email.assunto)
    if len(email.assunto) > LIMITE_ASSUNTO_ENDPOINT:
        logger.error('E-mail %s não enviado: assunto com %s caracteres', tipo, len(email.assunto))
        return False
    if len(email.html) > LIMITE_CORPO or len(email.texto) > LIMITE_CORPO:
        logger.error('E-mail %s não enviado: corpo com %s/%s caracteres (HTML/texto)', tipo, len(email.html), len(email.texto))
        return False

    sucesso = True
    for destinatario in destinatarios:
        if not ServicoEmail.enviar(destinatario, email.assunto, email.html, html=True, texto=email.texto):
            sucesso = False
    return sucesso
```

- [ ] **Step 5: Create `core/emails_exemplos.py`**

```python
"""Contexto de exemplo para cada tipo de e-mail.

Usado pelos testes (core/tests_emails.py) e pelo comando enviar_emails_exemplo.
Todo tipo em core.emails.TIPOS precisa de uma entrada aqui.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

_TZ = ZoneInfo('America/Sao_Paulo')
_SITE = 'https://canastra.example'

EXEMPLOS = {
    'codigo_verificacao': {
        'nome': 'Ana Souza',
        'codigo': '048213',
        'expiracao_minutos': 10,
    },
}
```

(`datetime`, `_TZ` e `_SITE` são usados pelas entradas das próximas tasks; se o linter reclamar de import não usado até lá, mantenha.)

- [ ] **Step 6: Create `core/templates/email/base_email.html`**

```html
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="x-apple-disable-message-reformatting">
<title>{{ assunto }}</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f5;">
  <div style="display:none; max-height:0; overflow:hidden; mso-hide:all; font-size:1px; line-height:1px; color:#f4f6f5;">{% block preheader %}{% endblock %}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#f4f6f5;">
    <tr>
      <td align="center" style="padding:24px 12px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" style="width:100%; max-width:600px; background-color:#ffffff; border-radius:12px;">
          <tr>
            <td align="center" style="padding:24px 32px 16px;">
              <img src="{{ logo_url }}" width="180" alt="Canastra HUB" style="display:block; width:180px; max-width:100%; height:auto; border:0; font-family:Arial, Helvetica, sans-serif; font-size:20px; font-weight:bold; color:#1f2d24;">
            </td>
          </tr>
          <tr>
            <td style="height:4px; line-height:4px; font-size:0; background-color:#28a745;">&nbsp;</td>
          </tr>
          <tr>
            <td style="padding:32px; font-family:Arial, Helvetica, sans-serif; font-size:15px; line-height:1.6; color:#4a534e;">
              <h1 style="margin:0 0 16px; font-family:Arial, Helvetica, sans-serif; font-size:20px; line-height:1.3; color:#1f2d24;">{% block titulo %}{% endblock %}</h1>
              <p style="margin:0 0 16px;">{% block saudacao %}Olá{% if nome %}, {{ nome }}{% endif %},{% endblock %}</p>
              {% block conteudo %}{% endblock %}
              {% block cta %}{% if cta_link %}
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0 8px;">
                <tr>
                  <td align="center" bgcolor="#28a745" style="border-radius:8px; background-color:#28a745;">
                    <a href="{{ cta_link }}" target="_blank" style="display:inline-block; padding:12px 28px; font-family:Arial, Helvetica, sans-serif; font-size:15px; font-weight:bold; color:#ffffff; text-decoration:none; border-radius:8px;">{{ cta_texto }}</a>
                  </td>
                </tr>
              </table>
              <p style="margin:0 0 16px; font-size:12px; line-height:1.5; color:#8a938e;">Se o botão não funcionar, copie este endereço no navegador:<br><a href="{{ cta_link }}" style="color:#1e7e34; word-break:break-all;">{{ cta_link }}</a></p>
              {% endif %}{% endblock %}
              {% block complementar %}{% endblock %}
              <p style="margin:24px 0 0;">{% block assinatura %}Atenciosamente,<br>Equipe Canastra HUB{% endblock %}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px; background-color:#f4f6f5; border-radius:0 0 12px 12px; font-family:Arial, Helvetica, sans-serif; font-size:12px; line-height:1.6; color:#8a938e; text-align:center;">
              <p style="margin:0 0 6px;">Canastra HUB · Dúvidas? Fale com a gente: <a href="{{ link_contato }}" style="color:#1e7e34;">{{ link_contato }}</a></p>
              <p style="margin:0;">Esta é uma mensagem automática. Não responda a este e-mail.</p>
              {% block rodape_extra %}{% endblock %}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
```

- [ ] **Step 7: Create `core/templates/email/base_email.txt`**

```
{% autoescape off %}{% block titulo %}{% endblock %}

{% block saudacao %}Olá{% if nome %}, {{ nome }}{% endif %},{% endblock %}

{% block conteudo %}{% endblock %}

{% block cta %}{% if cta_link %}{{ cta_texto }}: {{ cta_link }}{% endif %}{% endblock %}

{% block complementar %}{% endblock %}

{% block assinatura %}Atenciosamente,
Equipe Canastra HUB{% endblock %}

--
Canastra HUB · Dúvidas? Fale com a gente: {{ link_contato }}
Esta é uma mensagem automática. Não responda a este e-mail.
{% block rodape_extra %}{% endblock %}{% endautoescape %}
```

- [ ] **Step 8: Create `core/templates/email/codigo_verificacao.html`**

```html
{% extends 'email/base_email.html' %}
{% block preheader %}Seu código de verificação do Canastra HUB.{% endblock %}
{% block titulo %}Código de verificação{% endblock %}
{% block conteudo %}
<p style="margin:0 0 16px;">Use o código abaixo para concluir seu login no Canastra HUB.</p>
<p style="margin:0 0 16px; text-align:center;"><span style="display:inline-block; padding:12px 24px; font-size:28px; font-weight:bold; letter-spacing:8px; color:#1f2d24; background-color:#f4f6f5; border-radius:8px;">{{ codigo }}</span></p>
<p style="margin:0 0 16px;">O código expira em {{ expiracao_minutos }} minutos e só pode ser usado uma vez.</p>
{% endblock %}
{% block complementar %}
<p style="margin:0 0 16px; font-size:13px; color:#8a938e;">Se não foi você que tentou entrar, altere sua senha. Alguém pode conhecê-la.</p>
{% endblock %}
```

- [ ] **Step 9: Create `core/templates/email/codigo_verificacao.txt`**

```
{% extends 'email/base_email.txt' %}
{% block titulo %}Código de verificação{% endblock %}
{% block conteudo %}Use o código abaixo para concluir seu login no Canastra HUB.

{{ codigo }}

O código expira em {{ expiracao_minutos }} minutos e só pode ser usado uma vez.{% endblock %}
{% block complementar %}Se não foi você que tentou entrar, altere sua senha. Alguém pode conhecê-la.{% endblock %}
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test core.tests_emails core.tests_servico_email --settings=config.settings_test`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add core/emails.py core/emails_exemplos.py core/tests_emails.py core/templates/email/base_email.html core/templates/email/base_email.txt core/templates/email/codigo_verificacao.html core/templates/email/codigo_verificacao.txt config/settings.py
git commit -m "Serviço central de e-mails com template base HTML e texto"
```

---

### Task 3: Migrar o código de verificação (2FA)

**Files:**
- Modify: `core/dois_fatores.py:1-13`, `core/dois_fatores.py:66-76`
- Delete: `core/templates/email/codigo_verificacao_email.html`
- Modify (patches): `core/tests_dois_fatores.py`, `core/tests.py`

**Interfaces:**
- Consumes: `enviar_email(para, 'codigo_verificacao', {'nome', 'codigo', 'expiracao_minutos'})` (Task 2).

- [ ] **Step 1: Update test patch targets (tests will fail)**

Os testes fazem patch em `core.dois_fatores.ServicoEmail.enviar`, que deixará de existir. Troque para o caminho novo:

```bash
sed -i "s/core\.dois_fatores\.ServicoEmail\.enviar/core.emails.ServicoEmail.enviar/g" core/tests_dois_fatores.py core/tests.py
```

Em `core/tests_dois_fatores.py`, no `test_gera_salva_hash_e_envia_email`, acrescente depois de `self.assertIn('123456', mensagem)`:

```python
        self.assertEqual(_assunto, '[Canastra HUB] Código de verificação')
        self.assertIn('123456', enviar.call_args.kwargs['texto'])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test core.tests_dois_fatores --settings=config.settings_test`
Expected: FAIL em `test_gera_salva_hash_e_envia_email` (assunto ainda é `Código de verificação — Canastra HUB`; `KeyError: 'texto'`).

- [ ] **Step 3: Migrate `core/dois_fatores.py`**

Imports: remova `from django.template.loader import render_to_string` e `from core.servico_email import ServicoEmail`; adicione:

```python
from core.emails import enviar_email
```

Substitua o bloco `corpo_email = render_to_string(...)` + `if not ServicoEmail.enviar(...)` por:

```python
    enviado = enviar_email(usuario.email, 'codigo_verificacao', {
        'nome': usuario.nome,
        'codigo': codigo,
        'expiracao_minutos': int(VALIDADE_CODIGO.total_seconds() // 60),
    })
    if not enviado:
        # Código que não chegou ao usuário não fica ativo nem conta no limite
        registro.delete()
        return False
    return True
```

Confira com `grep -n "render_to_string\|ServicoEmail" core/dois_fatores.py` que não sobrou uso.

- [ ] **Step 4: Delete old template**

```bash
git rm core/templates/email/codigo_verificacao_email.html
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test core.tests_dois_fatores core.tests core.tests_emails --settings=config.settings_test`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/dois_fatores.py core/tests_dois_fatores.py core/tests.py
git commit -m "Código de verificação usa o padrão único de e-mails"
```

---

### Task 4: Recuperação de senha e contato recebido

**Files:**
- Modify: `core/emails.py` (`TIPOS`), `core/emails_exemplos.py`
- Create: `core/templates/email/recuperar_senha.html` / `.txt`, `core/templates/email/contato_recebido.html` / `.txt`
- Modify: `core/views.py:12`, `core/views.py:25`, `core/views.py:180-185` (contato), `core/views.py:1345-1352` (recuperar_senha)
- Delete: `core/templates/email/recuperar_senha_email.html`
- Test: `core/tests_servico_email.py` (`RemetentesUsamServicoEmailTest`)

**Interfaces:**
- Consumes: `enviar_email` (Task 2).
- Produces: tipos `recuperar_senha` (contexto `nome`, `cta_texto`, `cta_link`, `expiracao_minutos`) e `contato_recebido` (contexto `nome_remetente`, `email_remetente`, `tipo`, `mensagem`, `cta_texto`, `cta_link`).

- [ ] **Step 1: Write the failing tests**

Em `core/tests_servico_email.py`, classe `RemetentesUsamServicoEmailTest`, substitua `test_recuperar_senha` e `test_contato_envia_texto_puro_ao_hub` por:

```python
    @patch('core.servico_email.ServicoEmail.enviar', return_value=True)
    def test_recuperar_senha(self, enviar):
        UsuarioBase.objects.create_user(
            email='empresa@example.com', nome='Empresa', tipo='empresa', password='SenhaForte123'
        )
        self.client.post(reverse('core:recuperar_senha'), {'txtEmail': 'empresa@example.com'})

        enviar.assert_called_once()
        para, assunto, html = enviar.call_args.args
        self.assertEqual(para, 'empresa@example.com')
        self.assertEqual(assunto, '[Canastra HUB] Redefinição de senha')
        self.assertIn('Redefinir minha senha', html)
        self.assertIn('/redefinir', enviar.call_args.kwargs['texto'])

    @override_settings(EMAIL_HUB_APROVACAO='hub@example.com', SITE_URL='https://canastra.example')
    @patch('core.servico_email.ServicoEmail.enviar', return_value=True)
    def test_contato_envia_ao_hub_com_html_e_texto(self, enviar):
        self.client.post(reverse('core:contato'), {
            'txtNome': 'João Souza',
            'txtEmail': 'joao@example.com',
            'txtTipo': 'duvida',
            'txtMensagem': 'Linha 1\n<b>Linha 2</b>',
        })

        enviar.assert_called_once()
        para, assunto, html = enviar.call_args.args
        self.assertEqual(para, 'hub@example.com')
        self.assertEqual(assunto, '[Canastra HUB] Novo contato: Dúvida')
        self.assertTrue(enviar.call_args.kwargs['html'])
        self.assertIn('Linha 1<br>&lt;b&gt;Linha 2&lt;/b&gt;', html)
        self.assertIn('https://canastra.example/administrador/mensagens_contato/', html)
        texto = enviar.call_args.kwargs['texto']
        self.assertIn('joao@example.com', texto)
        self.assertIn('Linha 1\n<b>Linha 2</b>', texto)
```

Antes de rodar, confirme o trecho do link de redefinição: `grep -n "redefinir_senha" core/urls.py`. Se o caminho não contiver `/redefinir`, ajuste a asserção para um trecho fixo desse caminho.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test core.tests_servico_email --settings=config.settings_test`
Expected: FAIL nos dois testes (assuntos antigos; `KeyError: 'texto'`).

- [ ] **Step 3: Register types and examples**

Em `core/emails.py`, `TIPOS` passa a ser:

```python
TIPOS = {
    'codigo_verificacao': TipoEmail('Código de verificação', 'email/codigo_verificacao'),
    'recuperar_senha': TipoEmail('Redefinição de senha', 'email/recuperar_senha'),
    'contato_recebido': TipoEmail('Novo contato: {tipo}', 'email/contato_recebido'),
}
```

Em `core/emails_exemplos.py`, acrescente em `EXEMPLOS`:

```python
    'recuperar_senha': {
        'nome': 'Ana Souza',
        'cta_texto': 'Redefinir minha senha',
        'cta_link': f'{_SITE}/redefinir-senha/MQ/token-exemplo/',
        'expiracao_minutos': 30,
    },
    'contato_recebido': {
        'nome_remetente': 'João Souza',
        'email_remetente': 'joao@example.com',
        'tipo': 'Reclamação',
        'mensagem': 'Não consegui reservar a sala de reuniões.\nO sistema mostrou erro.',
        'cta_texto': 'Ver mensagens de contato',
        'cta_link': f'{_SITE}/administrador/mensagens_contato/',
    },
```

- [ ] **Step 4: Create `core/templates/email/recuperar_senha.html`**

```html
{% extends 'email/base_email.html' %}
{% block preheader %}Use o link para criar uma nova senha no Canastra HUB.{% endblock %}
{% block titulo %}Redefinição de senha{% endblock %}
{% block conteudo %}
<p style="margin:0 0 16px;">Recebemos um pedido para redefinir a senha da sua conta no Canastra HUB.</p>
<p style="margin:0 0 16px;">Clique no botão abaixo para criar uma nova senha. O link é pessoal e expira em {{ expiracao_minutos }} minutos.</p>
{% endblock %}
{% block complementar %}
<p style="margin:0 0 16px; font-size:13px; color:#8a938e;">Se você não fez este pedido, ignore esta mensagem. Sua senha continua a mesma.</p>
{% endblock %}
```

- [ ] **Step 5: Create `core/templates/email/recuperar_senha.txt`**

```
{% extends 'email/base_email.txt' %}
{% block titulo %}Redefinição de senha{% endblock %}
{% block conteudo %}Recebemos um pedido para redefinir a senha da sua conta no Canastra HUB.

Acesse o link abaixo para criar uma nova senha. O link é pessoal e expira em {{ expiracao_minutos }} minutos.{% endblock %}
{% block complementar %}Se você não fez este pedido, ignore esta mensagem. Sua senha continua a mesma.{% endblock %}
```

- [ ] **Step 6: Create `core/templates/email/contato_recebido.html`**

```html
{% extends 'email/base_email.html' %}
{% block preheader %}{{ tipo }} enviada por {{ nome_remetente }} pelo site.{% endblock %}
{% block titulo %}Novo contato pelo site{% endblock %}
{% block saudacao %}Olá, equipe Canastra HUB,{% endblock %}
{% block conteudo %}
<p style="margin:0 0 16px;">Uma nova mensagem chegou pelo formulário de contato do site.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px; border:1px solid #e3e8e5; border-radius:8px;">
  <tr>
    <td style="padding:16px 20px; font-family:Arial, Helvetica, sans-serif; font-size:14px; line-height:1.7; color:#4a534e;">
      <strong style="color:#1f2d24;">Nome:</strong> {{ nome_remetente }}<br>
      <strong style="color:#1f2d24;">E-mail:</strong> {{ email_remetente }}<br>
      <strong style="color:#1f2d24;">Tipo:</strong> {{ tipo }}
    </td>
  </tr>
</table>
<p style="margin:0 0 16px; padding:12px 16px; border-left:4px solid #28a745; background-color:#f4f6f5;">{{ mensagem|linebreaksbr }}</p>
{% endblock %}
{% block complementar %}
<p style="margin:0 0 16px; font-size:13px; color:#8a938e;">Responda pela área administrativa. A resposta chega ao remetente por e-mail.</p>
{% endblock %}
```

- [ ] **Step 7: Create `core/templates/email/contato_recebido.txt`**

```
{% extends 'email/base_email.txt' %}
{% block titulo %}Novo contato pelo site{% endblock %}
{% block saudacao %}Olá, equipe Canastra HUB,{% endblock %}
{% block conteudo %}Uma nova mensagem chegou pelo formulário de contato do site.

Nome: {{ nome_remetente }}
E-mail: {{ email_remetente }}
Tipo: {{ tipo }}

Mensagem:
{{ mensagem }}{% endblock %}
{% block complementar %}Responda pela área administrativa. A resposta chega ao remetente por e-mail.{% endblock %}
```

- [ ] **Step 8: Migrate `core/views.py`**

Imports: troque `from core.servico_email import ServicoEmail` por `from core.emails import enviar_email`. Remova `from django.template.loader import render_to_string` (só era usado em `recuperar_senha`; confirme com `grep -n render_to_string core/views.py` depois da troca).

Na view `contato`, substitua a chamada `ServicoEmail.enviar(...)` por:

```python
    enviar_email(settings.EMAIL_HUB_APROVACAO, 'contato_recebido', {
        'nome_remetente': nome,
        'email_remetente': email,
        'tipo': dict(MensagemContato.TIPO_CHOICES)[tipo],
        'mensagem': mensagem,
        'cta_texto': 'Ver mensagens de contato',
        'cta_link': f"{settings.SITE_URL}{reverse('administrador:listar_mensagens_contato')}",
    })
```

Em `recuperar_senha`, substitua `corpo_email = render_to_string(...)` + `ServicoEmail.enviar(...)` por:

```python
                enviar_email(usuario.email, 'recuperar_senha', {
                    'nome': usuario.nome,
                    'cta_texto': 'Redefinir minha senha',
                    'cta_link': link,
                    'expiracao_minutos': 30,
                })
```

- [ ] **Step 9: Delete old template**

```bash
git rm core/templates/email/recuperar_senha_email.html
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test core --settings=config.settings_test`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add core/emails.py core/emails_exemplos.py core/views.py core/tests_servico_email.py core/templates/email/recuperar_senha.html core/templates/email/recuperar_senha.txt core/templates/email/contato_recebido.html core/templates/email/contato_recebido.txt
git commit -m "Recuperação de senha e contato recebido no padrão único de e-mails"
```

---

### Task 5: Resposta ao contato (admin)

**Files:**
- Modify: `core/emails.py` (`TIPOS`), `core/emails_exemplos.py`
- Create: `core/templates/email/contato_resposta.html` / `.txt`
- Modify: `administrador/views.py:6-9`, `administrador/views.py:505-516`
- Test: `administrador/tests.py`

**Interfaces:**
- Consumes: `enviar_email` (Task 2).
- Produces: tipo `contato_resposta` (contexto `nome`, `mensagem_original`, `resposta`).

- [ ] **Step 1: Write the failing tests**

Em `administrador/tests.py`, nos dois testes que usam `@patch('administrador.views.GoogleEmailService.enviar_email', return_value=True)`, troque o decorator por `@patch('administrador.views.enviar_email', return_value=True)`. Em `test_responder_mensagem_salva_resposta_e_redireciona`, troque a última linha por:

```python
        self.assertEqual(mock_enviar.call_args.args[0], self.mensagem.email)
        self.assertEqual(mock_enviar.call_args.args[1], 'contato_resposta')
```

Na mesma classe, acrescente:

```python
    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_resposta_escapa_html_e_preserva_quebras(self, enviar):
        self.client.post(
            reverse('administrador:responder_mensagem_contato', args=[self.mensagem.id]),
            {'txtResposta': 'Linha 1\n<b>Linha 2</b>'}
        )

        enviar.assert_called_once()
        para, assunto, html = enviar.call_args.args
        self.assertEqual(para, self.mensagem.email)
        self.assertEqual(assunto, '[Canastra HUB] Resposta ao seu contato')
        self.assertIn('Linha 1<br>&lt;b&gt;Linha 2&lt;/b&gt;', html)
        self.assertIn('Linha 1\n<b>Linha 2</b>', enviar.call_args.kwargs['texto'])
```

(`patch` e `reverse` já são importados no arquivo.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test administrador --settings=config.settings_test`
Expected: ERROR `AttributeError: <module 'administrador.views'> does not have the attribute 'enviar_email'`.

- [ ] **Step 3: Register type and example**

Em `core/emails.py`, acrescente em `TIPOS`:

```python
    'contato_resposta': TipoEmail('Resposta ao seu contato', 'email/contato_resposta'),
```

Em `core/emails_exemplos.py`, acrescente em `EXEMPLOS`:

```python
    'contato_resposta': {
        'nome': 'João Souza',
        'mensagem_original': 'Não consegui reservar a sala de reuniões.\nO sistema mostrou erro.',
        'resposta': 'Corrigimos o problema da reserva.\nPode tentar de novo.',
    },
```

- [ ] **Step 4: Create `core/templates/email/contato_resposta.html`**

```html
{% extends 'email/base_email.html' %}
{% block preheader %}Respondemos à mensagem que você enviou pelo site.{% endblock %}
{% block titulo %}Resposta ao seu contato{% endblock %}
{% block conteudo %}
<p style="margin:0 0 16px;">Respondemos à mensagem que você enviou pelo site do Canastra HUB.</p>
<p style="margin:0 0 16px;">{{ resposta|linebreaksbr }}</p>
{% endblock %}
{% block complementar %}
<p style="margin:0 0 8px; font-size:13px; color:#8a938e;">Sua mensagem:</p>
<p style="margin:0 0 16px; padding:12px 16px; border-left:4px solid #e3e8e5; font-size:13px; color:#8a938e;">{{ mensagem_original|linebreaksbr }}</p>
{% endblock %}
```

- [ ] **Step 5: Create `core/templates/email/contato_resposta.txt`**

```
{% extends 'email/base_email.txt' %}
{% block titulo %}Resposta ao seu contato{% endblock %}
{% block conteudo %}Respondemos à mensagem que você enviou pelo site do Canastra HUB.

{{ resposta }}{% endblock %}
{% block complementar %}Sua mensagem:
{{ mensagem_original }}{% endblock %}
```

- [ ] **Step 6: Migrate `administrador/views.py`**

Imports: remova `from django.template.defaultfilters import linebreaksbr`, `from django.utils.html import escape` e `from agendamento.services import GoogleEmailService`; adicione `from core.emails import enviar_email`. (Confirme com `grep -n "escape(\|linebreaksbr(" administrador/views.py` que não há outro uso.)

Substitua o bloco `mensagem_html = (...)` + `enviado = GoogleEmailService.enviar_email(...)` por:

```python
        enviado = enviar_email(mensagem.email, 'contato_resposta', {
            'nome': mensagem.nome,
            'mensagem_original': mensagem.mensagem,
            'resposta': resposta,
        })
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test administrador core.tests_emails --settings=config.settings_test`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/emails.py core/emails_exemplos.py administrador/views.py administrador/tests.py core/templates/email/contato_resposta.html core/templates/email/contato_resposta.txt
git commit -m "Resposta ao contato no padrão único de e-mails"
```

---

### Task 6: Aprovações de reserva (HUB e FAST) e remoção do GoogleEmailService

**Files:**
- Modify: `core/emails.py` (`TIPOS`), `core/emails_exemplos.py`
- Create: `core/templates/email/_detalhes_reserva.html` / `.txt`, `core/templates/email/aprovacao_reserva_hub.html` / `.txt`, `core/templates/email/aprovacao_reserva_fast.html` / `.txt`
- Modify: `agendamento/utils.py:8`, `agendamento/utils.py:139-208` (`notificar_aprovacoes_pendentes`)
- Modify: `agendamento/services.py:6`, `agendamento/services.py:147-165` (remove `GoogleEmailService`)
- Modify: `agendamento/views.py:11`
- Modify: `core/tests_servico_email.py` (remove testes e import de `GoogleEmailService`)
- Test: `agendamento/tests_notificacoes.py` (novo)

**Interfaces:**
- Consumes: `enviar_email` (Task 2); `gerar_link_aprovacao(request, reserva_id, tipo_aprovador, acao) -> str` (já existe em `agendamento/utils.py`).
- Produces: tipos `aprovacao_reserva_hub` e `aprovacao_reserva_fast` (contexto `sala`, `solicitante`, `inicio`, `fim`, `empresa_projeto`, `finalidade`, `cta_texto`, `cta_link`, `link_rejeitar`, `validade_horas`).

- [ ] **Step 1: Write the failing tests**

Crie `agendamento/tests_notificacoes.py`:

```python
"""E-mails de aprovação de reserva (agendamento.utils.notificar_aprovacoes_pendentes)."""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from agendamento.models import ConfiguracaoAgendamento, Reserva
from agendamento.utils import notificar_aprovacoes_pendentes
from core.models import UsuarioBase

INICIO_UTC = datetime(2026, 11, 12, 23, 0, tzinfo=dt_timezone.utc)  # 20:00 em São Paulo


@override_settings(SITE_URL='https://canastra.example')
class NotificarAprovacoesTest(TestCase):
    def setUp(self):
        self.usuario = UsuarioBase.objects.create_user(
            email='ana@example.com', nome='Ana <b>Souza</b>', tipo='empresa', password='SenhaForte123'
        )
        self.config = ConfiguracaoAgendamento.get_config()
        self.request = RequestFactory().get('/')

    def _reserva(self, **extra):
        dados = {
            'usuario': self.usuario,
            'sala': 'treinamentos',
            'inicio': INICIO_UTC,
            'fim': INICIO_UTC + timedelta(hours=2),
            'finalidade': '<script>alert(1)</script>',
            'empresa_projeto': 'Projeto X',
            'aprovado_hub': 'N/A',
            'aprovado_professor': 'N/A',
        }
        dados.update(extra)
        return Reserva.objects.create(**dados)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_hub_recebe_email_escapado_com_horario_local(self, enviar):
        reserva = self._reserva(aprovado_hub='Pendente')

        notificar_aprovacoes_pendentes(reserva, self.request, self.config)

        enviar.assert_called_once()
        para, assunto, html = enviar.call_args.args
        texto = enviar.call_args.kwargs['texto']
        self.assertEqual(para, self.config.email_hub)
        self.assertEqual(assunto, '[Canastra HUB] Reserva noturna aguarda aprovação')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('Ana &lt;b&gt;Souza&lt;/b&gt;', html)
        self.assertIn('12/11/2026 20:00', html)
        self.assertIn('12/11/2026 20:00', texto)
        self.assertIn('Aprovar reserva', html)
        self.assertIn('Rejeitar reserva', html)
        self.assertIn('/agendamento/aprovacao/email/', texto)

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_fast_envia_para_os_dois_professores(self, enviar):
        reserva = self._reserva(sala='fast', aprovado_professor='Pendente')

        notificar_aprovacoes_pendentes(reserva, self.request, self.config)

        self.assertEqual(
            [c.args[0] for c in enviar.call_args_list],
            [self.config.email_professor_1, self.config.email_professor_2],
        )
        self.assertEqual(enviar.call_args.args[1], '[Canastra HUB] Reserva no FAST aguarda aprovação')

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_sem_pendencia_nao_envia(self, enviar):
        notificar_aprovacoes_pendentes(self._reserva(), self.request, self.config)
        enviar.assert_not_called()

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_links_de_aprovar_e_rejeitar_sao_diferentes(self, enviar):
        reserva = self._reserva(aprovado_hub='Pendente')
        with patch('agendamento.utils.enviar_email', return_value=True) as enviar_email:
            notificar_aprovacoes_pendentes(reserva, self.request, self.config)
        contexto = enviar_email.call_args.args[2]
        self.assertNotEqual(contexto['cta_link'], contexto['link_rejeitar'])
        self.assertTrue(contexto['cta_link'].startswith('http://testserver/agendamento/aprovacao/email/'))
```

Em `core/tests_servico_email.py`: remova `from agendamento.services import GoogleEmailService` e os métodos `test_agendamento_envia_para_cada_destinatario` e `test_agendamento_informa_falha` (o comportamento de lista agora é testado em `core.tests_emails.EnviarEmailTest`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test agendamento.tests_notificacoes --settings=config.settings_test`
Expected: FAIL (assunto antigo `[Aprovação Pendente] ...`, `<script>` sem escape, `KeyError: 'texto'`).

- [ ] **Step 3: Register types and examples**

Em `core/emails.py`, acrescente em `TIPOS`:

```python
    'aprovacao_reserva_hub': TipoEmail('Reserva noturna aguarda aprovação', 'email/aprovacao_reserva_hub'),
    'aprovacao_reserva_fast': TipoEmail('Reserva no FAST aguarda aprovação', 'email/aprovacao_reserva_fast'),
```

Em `core/emails_exemplos.py`, acrescente:

```python
_RESERVA = {
    'solicitante': 'Ana Souza',
    'inicio': datetime(2026, 11, 12, 19, 0, tzinfo=_TZ),
    'fim': datetime(2026, 11, 12, 21, 0, tzinfo=_TZ),
    'empresa_projeto': 'Queijaria Canastra',
    'finalidade': 'Treinamento da equipe de produção',
    'cta_texto': 'Aprovar reserva',
    'cta_link': f'{_SITE}/agendamento/aprovacao/email/token-aprovar/',
    'link_rejeitar': f'{_SITE}/agendamento/aprovacao/email/token-rejeitar/',
    'validade_horas': 48,
}
```

(acima de `EXEMPLOS`) e, dentro de `EXEMPLOS`:

```python
    'aprovacao_reserva_hub': {**_RESERVA, 'sala': 'Espaço de Treinamentos'},
    'aprovacao_reserva_fast': {**_RESERVA, 'sala': 'FAST - Fábrica de Soluções Tecnológicas'},
```

- [ ] **Step 4: Create `core/templates/email/_detalhes_reserva.html`**

```html
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 16px; border:1px solid #e3e8e5; border-radius:8px;">
  <tr>
    <td style="padding:16px 20px; font-family:Arial, Helvetica, sans-serif; font-size:14px; line-height:1.7; color:#4a534e;">
      <strong style="color:#1f2d24;">Espaço:</strong> {{ sala }}<br>
      <strong style="color:#1f2d24;">Solicitante:</strong> {{ solicitante }}<br>
      <strong style="color:#1f2d24;">Início:</strong> {{ inicio|date:"d/m/Y H:i" }}<br>
      <strong style="color:#1f2d24;">Término:</strong> {{ fim|date:"d/m/Y H:i" }}<br>
      <strong style="color:#1f2d24;">Empresa/projeto:</strong> {{ empresa_projeto|default:"Não informado" }}<br>
      <strong style="color:#1f2d24;">Finalidade:</strong> {{ finalidade|default:"Não informado" }}
    </td>
  </tr>
</table>
```

- [ ] **Step 5: Create `core/templates/email/_detalhes_reserva.txt`**

```
Espaço: {{ sala }}
Solicitante: {{ solicitante }}
Início: {{ inicio|date:"d/m/Y H:i" }}
Término: {{ fim|date:"d/m/Y H:i" }}
Empresa/projeto: {{ empresa_projeto|default:"Não informado" }}
Finalidade: {{ finalidade|default:"Não informado" }}
```

- [ ] **Step 6: Create `core/templates/email/aprovacao_reserva_hub.html`**

```html
{% extends 'email/base_email.html' %}
{% block preheader %}{{ solicitante }} pediu {{ sala }} em {{ inicio|date:"d/m/Y H:i" }}.{% endblock %}
{% block titulo %}Reserva noturna aguarda aprovação{% endblock %}
{% block conteudo %}
<p style="margin:0 0 16px;">Uma reserva em horário noturno precisa da sua aprovação.</p>
{% include 'email/_detalhes_reserva.html' %}
{% endblock %}
{% block complementar %}
<p style="margin:0 0 16px;">Não aprova? <a href="{{ link_rejeitar }}" style="color:#c0392b; font-weight:bold;">Rejeitar reserva</a></p>
<p style="margin:0 0 16px; font-size:13px; color:#8a938e;">Os links valem por {{ validade_horas }} horas.</p>
{% endblock %}
```

- [ ] **Step 7: Create `core/templates/email/aprovacao_reserva_hub.txt`**

```
{% extends 'email/base_email.txt' %}
{% block titulo %}Reserva noturna aguarda aprovação{% endblock %}
{% block conteudo %}Uma reserva em horário noturno precisa da sua aprovação.

{% include 'email/_detalhes_reserva.txt' %}{% endblock %}
{% block complementar %}Rejeitar reserva: {{ link_rejeitar }}

Os links valem por {{ validade_horas }} horas.{% endblock %}
```

- [ ] **Step 8: Create `core/templates/email/aprovacao_reserva_fast.html`**

```html
{% extends 'email/base_email.html' %}
{% block preheader %}{{ solicitante }} pediu o FAST em {{ inicio|date:"d/m/Y H:i" }}.{% endblock %}
{% block titulo %}Reserva no FAST aguarda aprovação{% endblock %}
{% block conteudo %}
<p style="margin:0 0 16px;">Uma reserva na FAST - Fábrica de Soluções Tecnológicas precisa da sua aprovação docente.</p>
{% include 'email/_detalhes_reserva.html' %}
{% endblock %}
{% block complementar %}
<p style="margin:0 0 16px;">Não aprova? <a href="{{ link_rejeitar }}" style="color:#c0392b; font-weight:bold;">Rejeitar reserva</a></p>
<p style="margin:0 0 16px; font-size:13px; color:#8a938e;">Os links valem por {{ validade_horas }} horas.</p>
{% endblock %}
```

- [ ] **Step 9: Create `core/templates/email/aprovacao_reserva_fast.txt`**

```
{% extends 'email/base_email.txt' %}
{% block titulo %}Reserva no FAST aguarda aprovação{% endblock %}
{% block conteudo %}Uma reserva na FAST - Fábrica de Soluções Tecnológicas precisa da sua aprovação docente.

{% include 'email/_detalhes_reserva.txt' %}{% endblock %}
{% block complementar %}Rejeitar reserva: {{ link_rejeitar }}

Os links valem por {{ validade_horas }} horas.{% endblock %}
```

- [ ] **Step 10: Migrate `agendamento/utils.py`**

Troque `from .services import GoogleEmailService` por `from core.emails import enviar_email`.

Substitua a função `notificar_aprovacoes_pendentes` inteira por:

```python
def _contexto_aprovacao(reserva, request, tipo_aprovador):
    usuario = reserva.usuario
    return {
        'sala': reserva.get_sala_display(),
        'solicitante': getattr(usuario, 'nome', '') or usuario.email,
        'inicio': reserva.inicio,
        'fim': reserva.fim,
        'empresa_projeto': reserva.empresa_projeto,
        'finalidade': reserva.finalidade,
        'cta_texto': 'Aprovar reserva',
        'cta_link': gerar_link_aprovacao(request, reserva.id, tipo_aprovador, 'Aprovado'),
        'link_rejeitar': gerar_link_aprovacao(request, reserva.id, tipo_aprovador, 'Rejeitado'),
        'validade_horas': 48,
    }


def notificar_aprovacoes_pendentes(reserva, request, config):
    # Horário noturno: aprovação do HUB
    if reserva.aprovado_hub == 'Pendente':
        enviar_email(config.email_hub, 'aprovacao_reserva_hub',
                     _contexto_aprovacao(reserva, request, 'hub'))

    # Espaço FAST: aprovação dos professores
    if reserva.aprovado_professor == 'Pendente':
        professores = [p for p in [config.email_professor_1, config.email_professor_2] if p]
        if professores:
            enviar_email(professores, 'aprovacao_reserva_fast',
                         _contexto_aprovacao(reserva, request, 'professor'))
```

Se `TimestampSigner` deixar de ser usado fora de `gerar_link_aprovacao`, mantenha o import (ele ainda é usado lá). Confira com `grep -n "TimestampSigner" agendamento/utils.py`.

- [ ] **Step 11: Remove `GoogleEmailService`**

Em `agendamento/services.py`: apague a classe `GoogleEmailService` inteira e o import `from core.servico_email import ServicoEmail` (só era usado por ela; confirme com `grep -n ServicoEmail agendamento/services.py`).

Em `agendamento/views.py:11`: `from .services import GoogleAgendaService, GoogleEmailService` vira `from .services import GoogleAgendaService`.

Confirme que nada mais referencia: `grep -rn "GoogleEmailService" --include=*.py .` deve voltar vazio.

- [ ] **Step 12: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test agendamento core administrador --settings=config.settings_test`
Expected: PASS.

- [ ] **Step 13: Commit**

```bash
git add core/emails.py core/emails_exemplos.py core/tests_servico_email.py agendamento/utils.py agendamento/services.py agendamento/views.py agendamento/tests_notificacoes.py core/templates/email/_detalhes_reserva.html core/templates/email/_detalhes_reserva.txt core/templates/email/aprovacao_reserva_hub.html core/templates/email/aprovacao_reserva_hub.txt core/templates/email/aprovacao_reserva_fast.html core/templates/email/aprovacao_reserva_fast.txt
git commit -m "Aprovações de reserva no padrão único de e-mails; remove GoogleEmailService

Corrige injeção de HTML: finalidade e empresa/projeto agora passam
pelo autoescape do template. Datas saem no fuso local."
```

---

### Task 7: Vagas semanais

**Files:**
- Modify: `core/emails.py` (`TIPOS`), `core/emails_exemplos.py`
- Create: `matching/templates/email/vagas_semanais.html` / `.txt`
- Delete: `matching/templates/email/vagas_compativeis_email.html`
- Modify: `matching/recomendacoes_email.py:24-39` (imports, `ASSUNTO`), `:129-149` (`montar_email`), `:175-182` (`_enviar_com_tentativas`), `:200-202` (chamada)
- Test: `matching/tests_vagas_email.py`

**Interfaces:**
- Consumes: `enviar_email` (Task 2).
- Produces: tipo `vagas_semanais` (contexto `nome`, `vagas: list[dict(cargo, empresa, local, hub, descricao, compatibilidade, link)]`, `cta_texto`, `cta_link`, `link_descadastro`); `montar_contexto_email(usuario, matches) -> dict` substitui `montar_email`.

- [ ] **Step 1: Update tests (they will fail)**

```bash
sed -i "s/matching\.recomendacoes_email\.ServicoEmail\.enviar/core.emails.ServicoEmail.enviar/g" matching/tests_vagas_email.py
sed -i "s/enviar.side_effect = lambda para, \*a: para == 'bia@example.com'/enviar.side_effect = lambda para, *a, **k: para == 'bia@example.com'/" matching/tests_vagas_email.py
```

Confira com `grep -n "side_effect" matching/tests_vagas_email.py` que a lambda agora tem `**k`.

Em `test_envia_um_email_com_vagas_e_links`, depois de `self.assertIn('https://canastra.example/matching/vagas-email/', corpo)`, acrescente:

```python
        self.assertEqual(assunto, '[Canastra HUB] Vagas compatíveis com o seu perfil')
        self.assertIn('Ver todas as vagas', corpo)
        texto = enviar.call_args.kwargs['texto']
        self.assertIn('Queijeiro', texto)
        self.assertIn('https://canastra.example/matching/vagas-email/', texto)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test matching.tests_vagas_email --settings=config.settings_test`
Expected: FAIL em `test_envia_um_email_com_vagas_e_links` (assunto antigo; `KeyError: 'texto'`).

- [ ] **Step 3: Register type and example**

Em `core/emails.py`, acrescente em `TIPOS`:

```python
    'vagas_semanais': TipoEmail('Vagas compatíveis com o seu perfil', 'email/vagas_semanais'),
```

Em `core/emails_exemplos.py`, acrescente em `EXEMPLOS` (5 vagas = `VAGAS_EMAIL_LIMITE` padrão, com descrição longa, para provar o limite de 20.000 caracteres):

```python
    'vagas_semanais': {
        'nome': 'Ana Souza',
        'vagas': [
            {
                'cargo': f'Vaga de exemplo {i}',
                'empresa': 'Queijaria Canastra',
                'local': 'São Roque de Minas - MG',
                'hub': 'Hub do Queijo',
                'descricao': 'Descrição longa da vaga com atividades e requisitos. ' * 60,
                'compatibilidade': 90 - i,
                'link': f'{_SITE}/vagas/{i}/',
            }
            for i in range(1, 6)
        ],
        'cta_texto': 'Ver todas as vagas',
        'cta_link': f'{_SITE}/vagas/',
        'link_descadastro': f'{_SITE}/matching/vagas-email/token-exemplo/',
    },
```

- [ ] **Step 4: Create `matching/templates/email/vagas_semanais.html`**

```html
{% extends 'email/base_email.html' %}
{% block preheader %}{% if vagas|length == 1 %}Uma vaga combina{% else %}{{ vagas|length }} vagas combinam{% endif %} com o seu currículo.{% endblock %}
{% block titulo %}Vagas compatíveis com o seu perfil{% endblock %}
{% block conteudo %}
<p style="margin:0 0 16px;">O Canastra HUB encontrou {% if vagas|length == 1 %}uma vaga aberta{% else %}{{ vagas|length }} vagas abertas{% endif %} que combinam com o seu currículo. Candidate-se enquanto estão disponíveis.</p>
{% for vaga in vagas %}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:0 0 12px; border:1px solid #e3e8e5; border-radius:8px;">
  <tr>
    <td style="padding:16px 20px; font-family:Arial, Helvetica, sans-serif; font-size:14px; line-height:1.6; color:#4a534e;">
      <p style="margin:0 0 4px; font-size:16px; font-weight:bold; color:#1f2d24;">{{ vaga.cargo }}</p>
      <p style="margin:0 0 8px; font-size:13px;">{% if vaga.empresa %}{{ vaga.empresa }}{% endif %}{% if vaga.local %} · {{ vaga.local }}{% endif %}{% if vaga.hub %} · {{ vaga.hub }}{% endif %}</p>
      <p style="margin:0 0 8px; font-size:13px; font-weight:bold; color:#1e7e34;">Compatibilidade: {{ vaga.compatibilidade }}%</p>
      {% if vaga.descricao %}<p style="margin:0 0 8px; font-size:13px;">{{ vaga.descricao|truncatewords:35 }}</p>{% endif %}
      <a href="{{ vaga.link }}" style="font-size:14px; font-weight:bold; color:#1e7e34;">Ver vaga</a>
    </td>
  </tr>
</table>
{% endfor %}
{% endblock %}
{% block complementar %}
<p style="margin:0 0 16px; font-size:13px; color:#8a938e;">É preciso estar logado para ver os detalhes e se candidatar.</p>
{% endblock %}
{% block rodape_extra %}
<p style="margin:6px 0 0;">Você recebe este e-mail semanal porque tem cadastro de candidato no Canastra HUB.</p>
<p style="margin:0;"><a href="{{ link_descadastro }}" style="color:#8a938e;">Não quero mais receber vagas por e-mail</a></p>
{% endblock %}
```

- [ ] **Step 5: Create `matching/templates/email/vagas_semanais.txt`**

```
{% extends 'email/base_email.txt' %}
{% block titulo %}Vagas compatíveis com o seu perfil{% endblock %}
{% block conteudo %}O Canastra HUB encontrou {% if vagas|length == 1 %}uma vaga aberta{% else %}{{ vagas|length }} vagas abertas{% endif %} que combinam com o seu currículo. Candidate-se enquanto estão disponíveis.
{% for vaga in vagas %}
- {{ vaga.cargo }}{% if vaga.empresa %} · {{ vaga.empresa }}{% endif %}{% if vaga.local %} · {{ vaga.local }}{% endif %}{% if vaga.hub %} · {{ vaga.hub }}{% endif %}
  Compatibilidade: {{ vaga.compatibilidade }}%
  Ver vaga: {{ vaga.link }}
{% endfor %}{% endblock %}
{% block complementar %}É preciso estar logado para ver os detalhes e se candidatar.{% endblock %}
{% block rodape_extra %}
Você recebe este e-mail semanal porque tem cadastro de candidato no Canastra HUB.
Não quero mais receber vagas por e-mail: {{ link_descadastro }}{% endblock %}
```

- [ ] **Step 6: Migrate `matching/recomendacoes_email.py`**

Imports: remova `from django.template.loader import render_to_string` e `from core.servico_email import ServicoEmail`; adicione `from core.emails import enviar_email`. Remova a constante `ASSUNTO`.

Substitua `montar_email` por:

```python
def montar_contexto_email(usuario, matches) -> dict:
    vagas = [
        {
            'cargo': m.vaga.cargo_vaga or 'Vaga sem título',
            'empresa': m.vaga.empresa.nomefantasia if m.vaga.empresa else '',
            'local': m.vaga.local or '',
            'hub': m.vaga.hub.nome_hub if m.vaga.hub else '',
            'descricao': m.vaga.descricao_vaga or '',
            'compatibilidade': round(m.score * 100),
            'link': _url_absoluta(reverse('vagas:detalhe_vaga', args=[m.vaga_id])),
        }
        for m in matches
    ]
    return {
        'nome': usuario.nome_social or usuario.user.nome,
        'vagas': vagas,
        'cta_texto': 'Ver todas as vagas',
        'cta_link': _url_absoluta(reverse('vagas:buscar_vagas')),
        'link_descadastro': _url_absoluta(
            reverse('matching:descadastrar_vagas_email', args=[gerar_token_descadastro(usuario.pk)])
        ),
    }
```

Substitua `_enviar_com_tentativas` por:

```python
def _enviar_com_tentativas(destino, contexto) -> tuple[bool, int]:
    tentativas = max(1, settings.VAGAS_EMAIL_TENTATIVAS)
    for tentativa in range(1, tentativas + 1):
        if enviar_email(destino, 'vagas_semanais', contexto):
            return True, tentativa
        if tentativa < tentativas:
            time.sleep(ESPERA_ENTRE_TENTATIVAS * tentativa)
    return False, tentativas
```

Em `enviar_para_usuario`, as duas linhas dentro do `try` viram:

```python
        contexto = montar_contexto_email(usuario, matches)
        sucesso, tentativas = _enviar_com_tentativas(usuario.user.email, contexto)
```

Confira: `grep -rn "montar_email\|ASSUNTO\|ServicoEmail\|render_to_string" matching/` deve voltar vazio.

- [ ] **Step 7: Delete old template**

```bash
git rm matching/templates/email/vagas_compativeis_email.html
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test matching core.tests_emails --settings=config.settings_test`
Expected: PASS (inclui o teste de todos os tipos com 5 vagas dentro de 20.000 caracteres).

- [ ] **Step 9: Commit**

```bash
git add core/emails.py core/emails_exemplos.py matching/recomendacoes_email.py matching/tests_vagas_email.py matching/templates/email/vagas_semanais.html matching/templates/email/vagas_semanais.txt
git commit -m "Vagas semanais no padrão único de e-mails"
```

---

### Task 8: Comando de exemplo, guia de estilo e verificação final

**Files:**
- Create: `core/management/__init__.py`, `core/management/commands/__init__.py`, `core/management/commands/enviar_emails_exemplo.py`
- Create: `docs/emails/guia-de-estilo.md`
- Test: `core/tests_emails.py`

**Interfaces:**
- Consumes: `TIPOS`, `enviar_email` (Task 2), `EXEMPLOS` (Tasks 2-7).
- Produces: `python manage.py enviar_emails_exemplo <para> [--tipo TIPO]`; sai com `CommandError` se algum envio falhar.

- [ ] **Step 1: Write the failing tests**

No fim de `core/tests_emails.py`:

```python
from io import StringIO

from django.core.management import CommandError, call_command


@override_settings(**CONFIG)
class ComandoEnviarEmailsExemploTest(SimpleTestCase):
    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_envia_todos_os_tipos(self, enviar):
        saida = StringIO()
        call_command('enviar_emails_exemplo', 'teste@example.com', stdout=saida)
        self.assertEqual(enviar.call_count, len(emails.TIPOS))
        self.assertEqual({c.args[0] for c in enviar.call_args_list}, {'teste@example.com'})
        self.assertIn('OK', saida.getvalue())

    @patch('core.emails.ServicoEmail.enviar', return_value=True)
    def test_envia_um_tipo(self, enviar):
        call_command('enviar_emails_exemplo', 'teste@example.com', '--tipo', 'recuperar_senha', stdout=StringIO())
        enviar.assert_called_once()
        self.assertEqual(enviar.call_args.args[1], '[Canastra HUB] Redefinição de senha')

    @patch('core.emails.ServicoEmail.enviar', return_value=False)
    def test_falha_gera_erro(self, _enviar):
        with self.assertRaises(CommandError):
            call_command('enviar_emails_exemplo', 'teste@example.com', '--tipo', 'recuperar_senha', stdout=StringIO())
```

(Mova os imports `StringIO`, `CommandError` e `call_command` para o topo do arquivo, junto dos outros.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python manage.py test core.tests_emails.ComandoEnviarEmailsExemploTest --settings=config.settings_test`
Expected: ERROR `CommandError: Unknown command: 'enviar_emails_exemplo'`.

- [ ] **Step 3: Create the command**

Crie `core/management/__init__.py` e `core/management/commands/__init__.py` vazios. Crie `core/management/commands/enviar_emails_exemplo.py`:

```python
"""Envia os e-mails do sistema com dados de exemplo, para conferir o visual nos clientes de e-mail."""
from django.core.management.base import BaseCommand, CommandError

from core.emails import TIPOS, enviar_email
from core.emails_exemplos import EXEMPLOS


class Command(BaseCommand):
    help = 'Envia cada tipo de e-mail com dados de exemplo para o endereço informado.'

    def add_arguments(self, parser):
        parser.add_argument('para', help='Endereço que recebe os e-mails de exemplo.')
        parser.add_argument('--tipo', choices=sorted(TIPOS), help='Envia só este tipo.')

    def handle(self, *args, para, tipo=None, **options):
        tipos = [tipo] if tipo else list(TIPOS)
        falhas = []
        for nome in tipos:
            enviado = enviar_email(para, nome, EXEMPLOS[nome])
            self.stdout.write(f"{'OK   ' if enviado else 'FALHA'} {nome}")
            if not enviado:
                falhas.append(nome)
        if falhas:
            raise CommandError(f"Falha ao enviar: {', '.join(falhas)}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python manage.py test core.tests_emails --settings=config.settings_test`
Expected: PASS.

- [ ] **Step 5: Write `docs/emails/guia-de-estilo.md`**

````markdown
# Guia de estilo dos e-mails do Canastra HUB

Todo e-mail do sistema sai por `core.emails.enviar_email(para, tipo, contexto)`. Não monte HTML de e-mail em f-string e não chame `ServicoEmail.enviar` direto.

## Assunto

- Formato: `[Canastra HUB] Ação ou assunto objetivo`. O prefixo é colocado automaticamente.
- No máximo 60 caracteres no total (o prefixo ocupa 15). Acima de 200, o envio é recusado.
- Sem CAIXA ALTA, sem excesso de pontuação, sem emojis.

## Corpo

1. Saudação: `Olá, {nome},` (automática pela base; sem nome, sai `Olá,`).
2. Mensagem principal em 1 ou 2 parágrafos curtos.
3. Um único botão de ação, quando houver ação: passe `cta_texto` e `cta_link` no contexto.
4. Informações complementares, se necessário (bloco `complementar`).
5. Encerramento automático: `Atenciosamente,` / `Equipe Canastra HUB`.

## Tom de voz

- Português do Brasil, cordial e objetivo, tratando o leitor por "você".
- Frases curtas, sem gírias e sem jargão técnico.

## Visual

- Coluna única de 600px, tabelas e CSS inline (Gmail e Outlook ignoram CSS externo).
- Cores: destaque `#28a745`, títulos `#1f2d24`, corpo `#4a534e`, secundário `#8a938e`, fundo `#f4f6f5`.
- Fonte Arial, 15px, line-height 1.6.
- Logo: `EMAIL_LOGO_URL` (URL pública e absoluta).

## Como criar um e-mail novo

1. Acrescente o tipo em `core/emails.py` (`TIPOS`):
   `'meu_tipo': TipoEmail('Assunto objetivo', 'email/meu_tipo')`.
2. Crie `email/meu_tipo.html` (`{% extends 'email/base_email.html' %}`) e `email/meu_tipo.txt` (`{% extends 'email/base_email.txt' %}`). Preencha os blocos `preheader` (só HTML), `titulo`, `conteudo` e, se preciso, `complementar` e `rodape_extra`.
3. Acrescente um contexto de exemplo em `core/emails_exemplos.py`. O teste `core.tests_emails` exige isso e confere o padrão.
4. Envie: `enviar_email(usuario.email, 'meu_tipo', {...})`. O retorno é `True` só se o provedor confirmar.
5. Confira o visual: `python manage.py enviar_emails_exemplo seu@email.com --tipo meu_tipo`.

## Apps Script (envio multipart)

O Django envia `mensagem` (HTML) e `texto` (texto puro). No `doPost` do Apps Script de e-mail:

```javascript
var dados = JSON.parse(e.postData.contents);
// ... validação existente de secret, para, assunto, mensagem ...
if (dados.texto) {
  GmailApp.sendEmail(dados.para, dados.assunto, dados.texto, {
    htmlBody: dados.mensagem,
    name: 'Canastra HUB',
  });
} else {
  // comportamento atual do script, sem alteração
}
```

O limite de 20.000 caracteres vale para `mensagem` e para `texto`.
````

- [ ] **Step 6: Verify no direct transport use remains**

Run: `grep -rn "ServicoEmail" --include=*.py . | grep -v "tests" | grep -v "^./core/servico_email.py" | grep -v "^./core/emails.py"`
Expected: saída vazia.

Run: `grep -rn "GoogleEmailService\|render_to_string('email/" --include=*.py .`
Expected: saída vazia.

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python manage.py test --settings=config.settings_test`
Expected: PASS em todos os apps.

- [ ] **Step 8: Commit**

```bash
git add core/management/__init__.py core/management/commands/__init__.py core/management/commands/enviar_emails_exemplo.py core/tests_emails.py
git add -f docs/emails/guia-de-estilo.md
git commit -m "Comando enviar_emails_exemplo e guia de estilo dos e-mails"
```

- [ ] **Step 9: `.env.example` (perguntar antes)**

`.env.example` tem alteração não commitada do usuário. Pergunte se pode incluir, logo abaixo de `SITE_URL`, o bloco:

```
# Logo dos e-mails (URL pública e absoluta). Opcional: o padrão é a imagem do repositório no GitHub.
# EMAIL_LOGO_URL=https://raw.githubusercontent.com/vitorrmoraisss/Canastra-HUB/main/resources/static/img/logoCanastra.jpeg
```

e se o commit deve levar junto a alteração já existente. Só então edite e faça o commit.

- [ ] **Step 10: Manual check in email clients (com o usuário)**

Depois que o Apps Script estiver atualizado (trecho no guia), rode com `.env` real:

```bash
.venv/bin/python manage.py enviar_emails_exemplo <seu-email>
```

Conferir em Gmail (web e app), Outlook (web e desktop) e um app de celular: logo, largura, botão, rodapé, versão em texto (no Gmail: "Mostrar original").
