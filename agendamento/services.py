import requests
import json


class GoogleAgendaService:
    # 1. COLE AQUI A URL ATUALIZADA DO SEU DEPLOYMENT DO GOOGLE APPS SCRIPT
    URL_WEB_APP = "https://script.google.com/macros/s/AKfycbymv1RJ7XNXTsyt39Q1DvC2DKdxdMayacOrQJFenXdy_CygFs1jMbHkzxgEr2ca0jh8/exec"

    # 2. O MESMO TOKEN QUE VOCÊ FIXOU NO APPS SCRIPT
    TOKEN = "CANASTRA123"

    @classmethod
    def enviar_para_google(cls, nome_sala, titulo, data_inicio, data_fim, email_cliente):
        """
        Interpreta o nome ou identificador da sala vindo do Django
        e mapeia para o ID esperado pelo Google Apps Script.
        """
        # Limpa e formata o texto para bater com as chaves do dicionário do Google
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
                f"⚠️ Alerta: A sala '{nome_sala}' não possui um mapeamento correspondente para o Google Calendar.")
            return None

        # Monta os dados que o seu Apps Script lê em 'e.postData.contents'
        payload = {
            "token": cls.TOKEN,
            "sala_id": sala_id_mapeado,
            "titulo": titulo,
            "inicio": data_inicio,
            "fim": data_fim,
            "email_cliente": email_cliente
        }

        headers = {
            'Content-Type': 'application/json'
        }

        try:
            resposta = requests.post(
                cls.URL_WEB_APP,
                data=json.dumps(payload),
                headers=headers,
                allow_redirects=True,  # Garante que o Python siga o redirect 302 do Google
                timeout=15
            )

            if resposta.status_code == 200:
                dados_retorno = resposta.json()

                if dados_retorno.get("status") == "sucesso":
                    print(
                        f"✅ Sincronizado no Google Calendar com sucesso! Event ID: {dados_retorno.get('event_id')}")
                    return dados_retorno.get("event_id")
                else:
                    print(
                        f"❌ Erro retornado pelo script do Google: {dados_retorno.get('message')}")
                    return None
            else:
                print(
                    f"❌ Falha de comunicação HTTP com o Google. Status: {resposta.status_code}")
                return None

        except Exception as erro:
            print(
                f"💥 Erro crítico ao chamar o service do Google Calendar: {erro}")
            return None
