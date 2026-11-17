Baixar o código do repositório (git pull).

Instalar as dependências (pip install -r requirements.txt ou via conda).

Atualizar o banco de dados:
python manage.py makemigrations
python manage.py migrate

Iniciar o servidor (python manage.py runserver).

E-mail semanal de vagas compatíveis (matching):
- Disparo manual (pode ser repetido na mesma semana sem duplicar envios): python manage.py enviar_vagas_semanais
  - Só para alguns candidatos (e-mail ou id): python manage.py enviar_vagas_semanais --usuario ana@exemplo.com --usuario 42
  - Simular sem enviar nem gravar nada: python manage.py enviar_vagas_semanais --simular
  - No Docker: docker compose exec web python manage.py enviar_vagas_semanais
- Agendador contínuo, no dia/horário de VAGAS_EMAIL_DIA_SEMANA e VAGAS_EMAIL_HORARIO (serviço "scheduler" do docker-compose): python manage.py agendador_vagas_semanais
- Configuração no .env: SITE_URL, VAGAS_EMAIL_DIA_SEMANA, VAGAS_EMAIL_HORARIO (HH:MM), VAGAS_EMAIL_SCORE_MINIMO, VAGAS_EMAIL_LIMITE, VAGAS_EMAIL_TENTATIVAS. Ver .env.example.
- Resultado de cada envio (enviado/falha, vagas, tentativas, erro) fica em "Envio vagas emails" no admin.
