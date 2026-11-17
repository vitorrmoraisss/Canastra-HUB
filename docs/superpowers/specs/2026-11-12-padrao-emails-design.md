# Padrão único de e-mails — Design Spec

**Data:** 2026-11-12
**Branch:** feature/mail_template
**Escopo:** Todos os e-mails enviados pelo Django passam a seguir o mesmo padrão de assunto, estrutura, tom de voz e visual, montados por um serviço central com templates HTML e texto puro.

---

## Contexto

Os e-mails saem do Django pelo web app do Google Apps Script (`doPost`, campos `secret`, `para`, `assunto`, `mensagem`, `html`). O transporte já está centralizado em `core.servico_email.ServicoEmail.enviar`, mas cada chamador monta o próprio assunto e corpo. Resultado: três estilos visuais diferentes, assuntos sem padrão e HTML montado com f-string.

### Inventário atual

| # | E-mail | Onde | Assunto atual | Formato |
|---|---|---|---|---|
| 1 | Código 2FA | `core/dois_fatores.py` | `Código de verificação — Canastra HUB` | template próprio, 480px |
| 2 | Recuperação de senha | `core/views.py` (`recuperar_senha`) | `Redefinição de senha — Canastra HUB` | template próprio, 480px |
| 3 | Novo contato (para a equipe) | `core/views.py` (`contato`) | `Novo contato — {tipo}` | texto puro (`html=False`) |
| 4 | Resposta ao contato | `administrador/views.py` | `Resposta ao seu contato — Canastra HUB` | HTML inline em f-string |
| 5 | Aprovação de reserva noturna (HUB) | `agendamento/utils.py` | `[Aprovação Pendente] Reserva HUB - {sala}` | HTML inline em f-string |
| 6 | Aprovação de reserva FAST (professores) | `agendamento/utils.py` | `[Aprovação Pendente] Reserva FAST - {sala}` | HTML inline em f-string |
| 7 | Vagas semanais | `matching/recomendacoes_email.py` | `Vagas compatíveis com o seu perfil — Canastra HUB` | template próprio, 560px, com descadastro |

### Problemas encontrados

- Os e-mails 5 e 6 interpolam `reserva.finalidade` e `reserva.empresa_projeto` (texto digitado pelo usuário) direto no HTML, sem escape. Isso permite injeção de HTML no e-mail enviado ao HUB e aos professores.
- `agendamento.services.GoogleEmailService` só repassa para `ServicoEmail` com suporte a lista de destinatários; é uma segunda porta de entrada sem padrão.
- O endpoint não tem campo para versão em texto puro, então não há e-mail multipart.

---

## Decisões

| Tema | Decisão |
|---|---|
| Tratamento | "você" |
| Nome no assunto | `[Canastra HUB]` |
| Texto puro | Novo campo `texto` no payload; o Apps Script passa a enviar multipart |
| Logo | URL pública configurável em `EMAIL_LOGO_URL`; padrão `https://raw.githubusercontent.com/vitorrmoraisss/Canastra-HUB/main/resources/static/img/logoCanastra.jpeg` (depende do repositório continuar público) |
| Contato de suporte no rodapé | Link para a página de contato (`{SITE_URL}/contato/`) |
| Abordagem | Registro de tipos + templates `.html` e `.txt` escritos à mão por tipo |
| `GoogleEmailService` | Removido; chamadores migram para `enviar_email` |

---

## Guia de estilo

Este guia também é publicado em `docs/emails/guia-de-estilo.md` para quem criar novos e-mails.

### Assunto

- Formato: `[Canastra HUB] Ação ou assunto objetivo`.
- Máximo de 60 caracteres no total (o prefixo ocupa 15). Limite técnico do endpoint: 200.
- Sem CAIXA ALTA, sem excesso de pontuação, sem emojis.

### Estrutura do corpo

1. Saudação: `Olá, {nome},`.
2. Mensagem principal em 1 ou 2 parágrafos curtos.
3. Um único botão de ação (CTA), quando houver ação a tomar, seguido do link por extenso.
4. Informações complementares, se necessário.
5. Encerramento: `Atenciosamente,` e `Equipe Canastra HUB`.

### Tom de voz

- Português do Brasil, cordial e objetivo, tratando o leitor por "você".
- Frases curtas, sem gírias e sem jargão técnico.

### Visual

- Coluna única com `width="600"` e `max-width:600px`, montada com tabelas e CSS inline.
- Fundo externo `#f4f6f5`, cartão branco.
- Topo: logo (`EMAIL_LOGO_URL`, exibido com 180px de largura, `alt="Canastra HUB"`) e filete verde `#28a745`.
- Fonte Arial/Helvetica, 15px, `line-height:1.6`.
- Cores: títulos `#1f2d24`, corpo `#4a534e`, secundário `#8a938e`, destaque `#28a745`.
- Botão "à prova de Outlook": `<table><tr><td bgcolor="#28a745">` com o `<a>` dentro.
- Preheader oculto com o texto de prévia da caixa de entrada.

### Rodapé

- `Canastra HUB · Dúvidas? Fale com a gente: <link da página de contato>`.
- `Esta é uma mensagem automática. Não responda a este e-mail.`
- Link de descadastro quando aplicável (hoje, só nas vagas semanais).

### Exceções ao CTA único

- **Aprovações de reserva:** botão "Aprovar reserva" e, abaixo, link de texto "Rejeitar reserva".
- **Vagas semanais:** cada vaga tem um link de texto "Ver vaga"; o botão único é "Ver todas as vagas".

---

## Arquitetura

### Arquivos

```
core/
├── servico_email.py          # transporte (Apps Script); ganha o parâmetro texto
├── emails.py                 # NOVO: TIPOS, renderizar_email, enviar_email
├── emails_exemplos.py        # NOVO: contexto de exemplo por tipo (testes e comando)
├── management/commands/
│   └── enviar_emails_exemplo.py   # NOVO: envia os tipos com dados de exemplo
└── templates/email/
    ├── base_email.html       # NOVO
    ├── base_email.txt        # NOVO
    ├── codigo_verificacao.html / .txt
    ├── recuperar_senha.html / .txt
    ├── contato_recebido.html / .txt
    ├── contato_resposta.html / .txt
    ├── aprovacao_reserva_hub.html / .txt
    └── aprovacao_reserva_fast.html / .txt
matching/templates/email/
    └── vagas_semanais.html / .txt
docs/emails/guia-de-estilo.md # NOVO
```

Saem: `core/templates/email/codigo_verificacao_email.html`, `core/templates/email/recuperar_senha_email.html`, `matching/templates/email/vagas_compativeis_email.html` e a classe `GoogleEmailService`.

### Transporte — `core/servico_email.py`

```python
@classmethod
def enviar(cls, para, assunto, mensagem, html=True, texto=None) -> bool
```

Quando `texto` não é `None`, o payload ganha `'texto': texto`. O resto do comportamento não muda: retorna `True` só quando o Apps Script responde `{"status": "sucesso"}`, e loga e retorna `False` nos demais casos. Continua sendo o único módulo que conhece o provedor.

### Serviço central — `core/emails.py`

```python
PREFIXO_ASSUNTO = '[Canastra HUB]'
LIMITE_ASSUNTO_ESTILO = 60
LIMITE_ASSUNTO_ENDPOINT = 200
LIMITE_CORPO = 20_000

@dataclass(frozen=True)
class TipoEmail:
    assunto: str    # pode ter campos de str.format com chaves do contexto
    template: str   # caminho sem extensão; renderiza .html e .txt

@dataclass(frozen=True)
class EmailRenderizado:
    assunto: str
    html: str
    texto: str

TIPOS = {
    'codigo_verificacao':     TipoEmail('Código de verificação', 'email/codigo_verificacao'),
    'recuperar_senha':        TipoEmail('Redefinição de senha', 'email/recuperar_senha'),
    'contato_recebido':       TipoEmail('Novo contato: {tipo}', 'email/contato_recebido'),
    'contato_resposta':       TipoEmail('Resposta ao seu contato', 'email/contato_resposta'),
    'aprovacao_reserva_hub':  TipoEmail('Reserva noturna aguarda aprovação', 'email/aprovacao_reserva_hub'),
    'aprovacao_reserva_fast': TipoEmail('Reserva no FAST aguarda aprovação', 'email/aprovacao_reserva_fast'),
    'vagas_semanais':         TipoEmail('Vagas compatíveis com o seu perfil', 'email/vagas_semanais'),
}

def renderizar_email(tipo: str, contexto: dict) -> EmailRenderizado
def enviar_email(para: str | list[str], tipo: str, contexto: dict) -> bool
```

**`renderizar_email`**

1. Busca o tipo em `TIPOS`. Tipo desconhecido gera `ValueError`, porque é erro de programação.
2. Junta ao contexto as chaves globais: `site_url` (`settings.SITE_URL`), `logo_url` (`settings.EMAIL_LOGO_URL`), `link_contato` (`SITE_URL + reverse('core:contato')`).
3. Monta o assunto: `f'{PREFIXO_ASSUNTO} {tipo.assunto.format(**contexto)}'`. Quebras de linha são trocadas por espaço.
4. Renderiza `<template>.html` e `<template>.txt` com `render_to_string`. O autoescape do Django protege as variáveis do HTML. O `.txt` usa `{% autoescape off %}` na base, porque não é HTML.

**`enviar_email`**

1. Normaliza `para`: string vira lista com um item. Remove espaços e ignora vazios. Lista vazia retorna `False` com log de erro.
2. Chama `renderizar_email`.
3. Validações:
   - Assunto com mais de 60 caracteres: `logger.warning` e segue o envio.
   - Assunto com mais de 200 caracteres, ou HTML/texto com mais de 20.000: `logger.error` e retorna `False` sem chamar o endpoint.
4. Para cada destinatário, chama `ServicoEmail.enviar(destinatario, assunto, html, html=True, texto=texto)`.
5. Retorna `True` só se todos os envios retornaram `True`. Mesmo com uma falha, tenta os demais destinatários.

### Templates base

`email/base_email.html` define estes blocos:

| Bloco | Uso | Padrão |
|---|---|---|
| `preheader` | texto de prévia oculto | vazio |
| `titulo` | título `<h1>` do cartão | vazio |
| `saudacao` | primeira linha | `Olá, {{ nome }},` (ou `Olá,` sem nome) |
| `conteudo` | 1 ou 2 parágrafos | obrigatório no filho |
| `cta` | botão + link por extenso | renderiza se o contexto tiver `cta_texto` e `cta_link` |
| `complementar` | informações extras | vazio |
| `assinatura` | encerramento | `Atenciosamente,<br>Equipe Canastra HUB` |
| `rodape_extra` | linhas extras no rodapé | vazio |

`email/base_email.txt` tem os mesmos blocos, em texto: saudação, conteúdo, `{{ cta_texto }}: {{ cta_link }}`, complementar, assinatura e rodapé com o link de contato e o aviso de mensagem automática.

### Configuração

Em `config/settings.py`:

```python
EMAIL_LOGO_URL = os.getenv(
    'EMAIL_LOGO_URL',
    'https://raw.githubusercontent.com/vitorrmoraisss/Canastra-HUB/main/resources/static/img/logoCanastra.jpeg',
)
```

Em `.env.example`, a variável aparece comentada, com explicação.

---

## Migração dos e-mails

| Tipo | Chamador | Contexto |
|---|---|---|
| `codigo_verificacao` | `core/dois_fatores.py` | `nome`, `codigo`, `expiracao_minutos` |
| `recuperar_senha` | `core/views.py` `recuperar_senha` | `nome`, `cta_texto='Redefinir minha senha'`, `cta_link`, `expiracao_minutos` |
| `contato_recebido` | `core/views.py` `contato` | `nome_remetente`, `email_remetente`, `tipo` (rótulo legível), `mensagem`; saudação fixa `Olá, equipe Canastra HUB,` |
| `contato_resposta` | `administrador/views.py` | `nome`, `mensagem_original`, `resposta` (ambas com `linebreaksbr` no HTML) |
| `aprovacao_reserva_hub` | `agendamento/utils.py` | `sala`, `solicitante`, `inicio`, `fim`, `finalidade`, `cta_texto='Aprovar reserva'`, `cta_link`, `link_rejeitar`, `validade_horas=48` |
| `aprovacao_reserva_fast` | `agendamento/utils.py` | igual ao HUB, sem `sala` no corpo principal e com `empresa_projeto` |
| `vagas_semanais` | `matching/recomendacoes_email.py` | `nome`, `vagas`, `cta_texto='Ver todas as vagas'`, `cta_link`, `link_descadastro` |

Detalhes por chamador:

- **2FA:** se `enviar_email` retornar `False`, o código continua sendo apagado, como hoje.
- **Contato recebido:** deixa de ser só texto e passa a ter HTML + texto.
- **Aprovações:** as f-strings saem. As datas são formatadas no template (`|date:"d/m/Y H:i"`). Os destinatários continuam sendo `config.email_hub` e a lista de professores (`enviar_email` aceita lista).
- **Vagas:** `montar_email` vira `montar_contexto_email(usuario, matches) -> dict`. `ASSUNTO` sai. `_enviar_com_tentativas` passa a chamar `enviar_email(destino, 'vagas_semanais', contexto)` a cada tentativa. Idempotência e registro em `EnvioVagasEmail` não mudam.
- **`GoogleEmailService`:** sai de `agendamento/services.py`, junto com os imports em `agendamento/utils.py`, `agendamento/views.py` e `administrador/views.py`.

---

## Apps Script

O `doPost` passa a aceitar o campo opcional `texto`:

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

O código atual do Apps Script não está no repositório; o trecho acima mostra só o ramo novo.

O limite de 20.000 caracteres vale também para `texto`. O script atual ignora campos desconhecidos, então o Django pode ir para produção antes da mudança no script.

---

## Testes

`core/emails_exemplos.py` tem um contexto de exemplo por tipo, usado pelos testes e pelo comando manual.

**`core/tests_emails.py` (novo)**

- Para cada tipo em `TIPOS`, com o contexto de exemplo:
  - assunto começa com `[Canastra HUB] ` e tem no máximo 60 caracteres;
  - HTML contém a saudação, o `logo_url` e o aviso "Não responda a este e-mail";
  - texto não contém `<` seguido de letra (sem tags) e contém o `cta_link`, quando houver;
  - HTML e texto têm no máximo 20.000 caracteres.
- Escape: `finalidade='<script>alert(1)</script>'` aparece como `&lt;script&gt;` no HTML da aprovação.
- `renderizar_email('inexistente', {})` gera `ValueError`.
- `enviar_email` com lista envia um por destinatário e ignora vazios; retorna `False` se algum falhar.
- `enviar_email` com corpo acima do limite retorna `False` sem chamar `ServicoEmail.enviar`.
- `enviar_email` passa `texto` para `ServicoEmail.enviar`.

**`core/tests_servico_email.py`**

- Payload inclui `texto` quando informado e não inclui quando é `None`.
- Os testes de `GoogleEmailService` saem; os testes de "remetentes usam o serviço" passam a verificar `enviar_email`.

**Testes existentes**

Os patches de `core.dois_fatores.ServicoEmail.enviar`, `matching.recomendacoes_email.ServicoEmail.enviar` e `administrador.views.GoogleEmailService.enviar_email` passam a apontar para `enviar_email` no módulo de cada chamador.

**Teste manual em clientes de e-mail**

```bash
python manage.py enviar_emails_exemplo destinatario@exemplo.com            # os 7 tipos
python manage.py enviar_emails_exemplo destinatario@exemplo.com --tipo vagas_semanais
```

Conferir em Gmail (web e app), Outlook (web e desktop) e um app de celular: logo, largura, botão, rodapé e versão em texto.

---

## Critérios de aceite

- [ ] `base_email.html` e `base_email.txt` criados; os 7 tipos conferidos em Gmail, Outlook e celular via `enviar_emails_exemplo`.
- [ ] `enviar_email(para, tipo, contexto)` é o único ponto de envio. Nenhum chamador usa `ServicoEmail.enviar` direto, e `GoogleEmailService` não existe mais.
- [ ] Os 7 e-mails migrados, com assunto `[Canastra HUB] ...` de até 60 caracteres.
- [ ] Versão em texto puro para cada tipo, enviada no campo `texto`.
- [ ] Apps Script atualizado para enviar multipart.
- [ ] Injeção de HTML nas aprovações de reserva corrigida.

## Fora do escopo

- E-mails enviados pelo Apps Script da agenda (`GoogleAgendaService`), que não saem do Django.
- Reply-to no e-mail de contato (o endpoint não suporta).
- Fila assíncrona ou novas tentativas automáticas além das que as vagas semanais já fazem.
