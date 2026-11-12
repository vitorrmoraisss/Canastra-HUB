// ===== Configurações =====
// Chave secreta compartilhada com o Django (defina em
// Configurações do Projeto → Propriedades do Script)
const API_SECRET = PropertiesService.getScriptProperties().getProperty("API_SECRET");

// Domínios/e-mails de destino permitidos (opcional, mas recomendado).
// Deixe null para não restringir.
const DESTINATARIOS_PERMITIDOS_DOMINIO = null; // ex.: "@meusite.com" ou null

function doPost(e) {
  try {
    if (!API_SECRET) {
      // Falha de configuração, não deixa o endpoint aberto por engano
      return respostaErro("Endpoint não configurado.", 500);
    }

    if (!e.postData || !e.postData.contents) {
      return respostaErro("Requisição inválida.");
    }

    var data;
    try {
      data = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return respostaErro("JSON inválido.");
    }

    // ---- Autenticação por chave secreta ----
    if (!data.secret || data.secret !== API_SECRET) {
      registrarLog("AUTH_FALHOU", data.para || "-");
      return respostaErro("Não autorizado.", 401);
    }

    var para = data.para;
    var assunto = data.assunto;
    var mensagem = data.mensagem;
    var isHtml = data.html === true;
    // Versão em texto puro (opcional). Com HTML, o e-mail sai multipart.
    var texto = typeof data.texto === "string" ? data.texto : "";

    // ---- Validação dos campos ----
    if (!para || !assunto || !mensagem) {
      return respostaErro("Campos obrigatórios: para, assunto, mensagem.");
    }
    if (!validarFormatoEmail(para)) {
      return respostaErro("E-mail de destino inválido.");
    }
    if (assunto.length > 200) {
      return respostaErro("Assunto muito longo.");
    }
    if (mensagem.length > 20000) {
      return respostaErro("Mensagem muito longa.");
    }
    if (texto.length > 20000) {
      return respostaErro("Texto muito longo.");
    }
    if (DESTINATARIOS_PERMITIDOS_DOMINIO && !para.toLowerCase().endsWith(DESTINATARIOS_PERMITIDOS_DOMINIO)) {
      registrarLog("DESTINATARIO_NAO_PERMITIDO", para);
      return respostaErro("Destinatário não permitido.");
    }

    // ---- Envio ----
    var opcoes = { name: "Canastra HUB" };
    var corpo = mensagem;
    if (isHtml) {
      opcoes.htmlBody = mensagem;
      corpo = texto || " ";
    }
    GmailApp.sendEmail(para, assunto, corpo, opcoes);

    registrarLog("EMAIL_ENVIADO", para);

    return ContentService
      .createTextOutput(JSON.stringify({ status: "sucesso" }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    // Nunca expõe detalhes internos do erro na resposta
    registrarLog("ERRO_ENVIO", "-", error.message);
    return respostaErro("Erro ao processar a requisição.", 500);
  }
}

// ===== Utilitários =====

function respostaErro(mensagem, codigoStatusInterno) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: "erro", mensagem: mensagem }))
    .setMimeType(ContentService.MimeType.JSON);
  // Obs.: Apps Script Web Apps sempre retornam HTTP 200; o "codigoStatusInterno"
  // é só para você documentar/logar a natureza do erro. O Django deve
  // checar o campo "status" no corpo da resposta, não o status HTTP.
}

function validarFormatoEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email));
}

function registrarLog(evento, destinatario, detalhe) {
  try {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const abaLog = ss.getSheetByName("Log") || ss.insertSheet("Log");
    abaLog.appendRow([new Date(), evento, destinatario, detalhe || ""]);
  } catch (e) {
    // Se o log falhar, não deve derrubar o envio de e-mail
  }
}