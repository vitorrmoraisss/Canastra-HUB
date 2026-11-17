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

Exceções já existentes: as aprovações de reserva têm o botão "Aprovar reserva" e um link de texto "Rejeitar reserva"; as vagas semanais têm um link "Ver vaga" por item e o botão "Ver todas as vagas".

## Tom de voz

- Português do Brasil, cordial e objetivo, tratando o leitor por "você".
- Frases curtas, sem gírias e sem jargão técnico.

## Visual

- Coluna única de 600px, tabelas e CSS inline (Gmail e Outlook ignoram CSS externo).
- Cores: destaque `#28a745`, títulos `#1f2d24`, corpo `#4a534e`, secundário `#8a938e`, fundo `#f4f6f5`.
- Fonte Arial, 15px, line-height 1.6.
- Logo: `EMAIL_LOGO_URL` (URL pública e absoluta). O padrão aponta para a imagem no GitHub e só carrega enquanto o repositório for público.

## Rodapé

Automático: link da página de contato e o aviso "Esta é uma mensagem automática. Não responda a este e-mail." Linhas extras (como o descadastro das vagas) vão no bloco `rodape_extra`.

## Como criar um e-mail novo

1. Acrescente o tipo em `core/emails.py` (`TIPOS`):
   `'meu_tipo': TipoEmail('Assunto objetivo', 'email/meu_tipo')`.
2. Crie `email/meu_tipo.html` (`{% extends 'email/base_email.html' %}`) e `email/meu_tipo.txt` (`{% extends 'email/base_email.txt' %}`). Preencha os blocos `preheader` (só HTML), `titulo`, `conteudo` e, se preciso, `complementar` e `rodape_extra`.
3. Acrescente um contexto de exemplo em `core/emails_exemplos.py`. O teste `core.tests_emails` exige isso e confere o padrão.
4. Envie: `enviar_email(usuario.email, 'meu_tipo', {...})`. O retorno é `True` só se o provedor confirmar.
5. Confira o visual: `python manage.py enviar_emails_exemplo seu@email.com --tipo meu_tipo`.

## Apps Script (`mailer.js`)

O Django envia `mensagem` (HTML) e `texto` (texto puro). O `mailer.js` usa `texto` como corpo alternativo e `mensagem` como `htmlBody`, então o e-mail sai multipart. Os dois campos têm limite de 20.000 caracteres. Depois de alterar o arquivo, cole o conteúdo no projeto do Apps Script e publique uma nova versão da implantação.
