from django.conf import settings
import requests
import json


class GoogleAgendaService:
    # 1. URL DO DEPLOYMENT DO GOOGLE APPS SCRIPT
    URL_WEB_APP = "https://script.google.com/macros/s/AKfycbymv1RJ7XNXTsyt39Q1DvC2DKdxdMayacOrQJFenXdy_CygFs1jMbHkzxgEr2ca0jh8/exec"

    # 2. TOKEN DE SEGURANÇA FIXADO NO APPS SCRIPT
    TOKEN = "CANASTRA123"

    @classmethod
    def enviar_para_google(cls, nome_sala, titulo, data_inicio, data_fim, email_cliente, dados_extras=None):
        """
        Interpreta o nome ou identificador da sala vindo do Django,
        mapeia para o ID esperado pelo Google Apps Script e repassa os
        dados adicionais necessários para preenchimento dos logs na planilha.
        Retorna uma tupla (event_id, linha_planilha) ou (None, None) em caso de erro.
        """
        sala_higienizada = str(nome_sala).strip().lower()

        sala_id_mapeado = None
        if "treinamento" in sala_higienizada:
            sala_id_mapeado = "treinamentos"
        elif "reunio" in sala_higienizada:  # Captura "Reunião" ou "Reunioes"
            sala_id_mapeado = "reunioes"
        elif "laboratorio" in sala_higienizada or "pratica" in sala_higienizada:
            sala_id_mapeado = "laboratorio"
        elif "fast" in sala_higienizada or "fabrica" in sala_higienizada:
            sala_id_mapeado = "fast"

        if not sala_id_mapeado:
            print(
                f"⚠️ Alerta: A sala '{nome_sala}' não possui um mapeamento correspondente no Service.")
            return None, None

        if dados_extras is None:
            dados_extras = {}

        # Formatação separada de Data, Hora Início e Hora Fim
        data_str = data_inicio.strftime(
            '%d/%m/%Y') if hasattr(data_inicio, 'strftime') else str(data_inicio)
        hora_inicio_str = data_inicio.strftime('%H:%M') if hasattr(
            data_inicio, 'strftime') else str(data_inicio)
        hora_fim_str = data_fim.strftime('%H:%M') if hasattr(
            data_fim, 'strftime') else str(data_fim)

        payload = {
            "token": cls.TOKEN,
            "sala_id": sala_id_mapeado,
            "titulo": titulo,
            "data": data_str,                     # <--- Novo campo explicitando a data
            "hora_inicio": hora_inicio_str,       # <--- Novo campo para Coluna D
            "hora_fim": hora_fim_str,             # <--- Novo campo para Coluna E
            "inicio": data_inicio.isoformat() if hasattr(data_inicio, 'isoformat') else str(data_inicio),
            "fim": data_fim.isoformat() if hasattr(data_fim, 'isoformat') else str(data_fim),
            "email_cliente": email_cliente,
            "empresa_projeto": dados_extras.get("empresa_projeto", "Não informado"),
            "quantidade_pessoas": dados_extras.get("quantidade_pessoas", 0),
            "finalidade": dados_extras.get("finalidade", "Não informado"),
            "equipamentos": dados_extras.get("equipamentos", "Não informado"),
            "observacoes": dados_extras.get("observacoes", "Não informado"),
            "status_checkin": dados_extras.get("status_checkin", "Pendente"),
            "hora_checkin": dados_extras.get("hora_checkin", "")
        }

        headers = {'Content-Type': 'application/json'}

        try:
            resposta = requests.post(
                cls.URL_WEB_APP,
                data=json.dumps(payload),
                headers=headers,
                allow_redirects=True,
                timeout=15
            )

            if resposta.status_code == 200:
                dados_retorno = resposta.json()

                if dados_retorno.get("status") == "sucesso":
                    event_id = dados_retorno.get('event_id')
                    linha_planilha = dados_retorno.get('linha_planilha')
                    print(
                        f"✅ Sincronizado no Google! Event ID: {event_id} | Linha na Planilha: {linha_planilha}")
                    return event_id, linha_planilha
                else:
                    print(
                        f"❌ Erro retornado pelo script do Google: {dados_retorno.get('message')}")
                    return None, None
            else:
                print(
                    f"❌ Falha de comunicação HTTP com o Google. Status: {resposta.status_code}")
                return None, None

        except Exception as erro:
            print(f"💥 Erro crítico ao chamar o service do Google: {erro}")
            return None, None

    @classmethod
    def atualizar_checkin_google(cls, linha_planilha, status_checkin, hora_checkin=""):
        """
        Envia comando para o Apps Script atualizar o Check-in e pintar a célula na planilha.
        """
        if not linha_planilha:
            print(
                "⚠️ Impossível atualizar check-in na planilha: linha_planilha não informada.")
            return False

        hora_str = hora_checkin.strftime(
            "%d/%m/%Y %H:%M") if hasattr(hora_checkin, 'strftime') else str(hora_checkin)

        payload = {
            "token": cls.TOKEN,
            "acao": "atualizar_checkin",
            "linha_planilha": linha_planilha,
            "status_checkin": status_checkin,
            "hora_checkin": hora_str
        }

        headers = {'Content-Type': 'application/json'}

        try:
            resposta = requests.post(
                cls.URL_WEB_APP,
                data=json.dumps(payload),
                headers=headers,
                allow_redirects=True,
                timeout=10
            )

            if resposta.status_code == 200 and resposta.json().get("status") == "sucesso":
                print(
                    f"🎨 Check-in atualizado na linha {linha_planilha} com status '{status_checkin}'")
                return True
            else:
                print(
                    f"❌ Falha ao atualizar check-in na planilha: {resposta.text}")
                return False

        except Exception as erro:
            print(f"💥 Erro ao atualizar check-in no Google: {erro}")
            return False


class GoogleEmailService:
    @staticmethod
    def enviar_email(destinatarios, assunto, mensagem_html):
        url = getattr(settings, 'GAS_EMAIL_URL', '')
        secret = getattr(settings, 'GAS_API_SECRET', '')

        if not url or not secret:
            print("⚠️ GAS_EMAIL_URL ou GAS_API_SECRET não configurados no settings.py.")
            return False

        if isinstance(destinatarios, str):
            lista_destinatarios = [destinatarios]
        else:
            lista_destinatarios = list(destinatarios)

        sucesso = True

        for email in lista_destinatarios:
            if not email:
                continue

            payload = {
                "secret": secret,
                "para": email.strip(),
                "assunto": assunto,
                "mensagem": mensagem_html,
                "html": True
            }

            try:
                response = requests.post(url, json=payload, timeout=10)

                try:
                    dados = response.json()
                    if dados.get('status') == 'sucesso':
                        print(f"✅ E-mail enviado com sucesso para: {email}")
                    else:
                        print(
                            f"❌ Erro do Apps Script para {email}: {dados.get('mensagem')}")
                        sucesso = False
                except Exception:
                    print(
                        f"💥 Resposta inválida do Apps Script (HTML/Erro HTTP {response.status_code}): {response.text[:200]}")
                    sucesso = False

            except Exception as e:
                print(f"💥 Erro na requisição ao Apps Script ({email}): {e}")
                sucesso = False

        return sucesso
