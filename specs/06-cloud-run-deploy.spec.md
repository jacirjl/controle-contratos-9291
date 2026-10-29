# ☁️ Spec 06 — Containerização e Deploy no Google Cloud Run

## 1. Visão Geral
Especifica a infraestrutura de empacotamento Docker e os requisitos arquiteturais para publicação da **Plataforma de Controle e Auditoria do Contrato 9291/2025** no **Google Cloud Run**.

---

## 2. Requisitos do Google Cloud Run Atendidos no Projeto

1. **Escuta Dinâmica na Variável `PORT` ([`server.py`](../server.py)):**
   - O Cloud Run injeta automaticamente a variável de ambiente `PORT=8080` e exige que o servidor escute em `0.0.0.0:$PORT`.
   - `server.py` lê `PORT = int(os.environ.get("PORT", 8092))`, funcionando tanto localmente na porta `8092` quanto no Cloud Run na porta `8080`.
2. **Health Check (`GET /healthz`):**
   - Rota dedicada em `server.py` que responde `200 OK` (`{"ok": true, "status": "healthy"}`) para sondas de *startup* e *liveness* do Cloud Run.
3. **Imagem Docker Enxuta ([`Dockerfile`](../Dockerfile) + [`requirements.txt`](../requirements.txt)):**
   - Baseada em `python:3.12-slim` com `PyMuPDF>=1.24.0` (tempo de build $\approx 20\text{s}$).
4. **Banco Vetorial e Cronológico Embarcado ([`db/contrato_9291.sqlite`](../db/contrato_9291.sqlite)):**
   - Como o arquivo `db/contrato_9291.sqlite` (9,9 MB) já está versionado no GitHub e incluído no container (respeitado pelo [`.dockerignore`](../.dockerignore)), a instância no Cloud Run sobe **imediatamente populada** com as 3.308 páginas indexadas, 270 chunks vetoriais e 136 eventos cronológicos, sem gastar CPU nem tokens na inicialização.

---

## 3. Como Realizar o Deploy no Cloud Run

### Opção 1 — Deploy Contínuo Direto pelo GitHub (Painel Web GCP — Recomendado)
Como o repositório já está publicado em `https://github.com/jacirjl/controle-contratos-9291`:
1. Acesse o console do **Google Cloud Run** $\rightarrow$ **Criar Serviço (Create Service)**.
2. Selecione **"Implantar continuamente novas revisões de um repositório de origem" (Continuously deploy from a repository)** e clique em **Configurar com o Cloud Build**.
3. Selecione o repositório **`jacirjl/controle-contratos-9291`**, branch **`^main$`** e tipo de compilação **Dockerfile** (`/Dockerfile`).
4. Em **Autenticação**, escolha *"Permitir invocação não autenticada"* (se desejar acesso público via link) ou IAM, e clique em **Criar**.
5. A cada `backup.bat` ou `git push origin main`, o Cloud Run atualizará a plataforma automaticamente!

### Opção 2 — Deploy via Linha de Comando (`gcloud CLI`)
Para subir diretamente da máquina local (incluindo os PDFs locais dentro da imagem se desejar):
```powershell
gcloud run deploy controle-contratos-9291 `
  --source . `
  --region southamerica-east1 `
  --platform managed `
  --allow-unauthenticated `
  --memory 512Mi
```

---

## 4. Persistência em Produção (Observação Arquitetural sobre Containers Stateless)
* **Consultas, Buscas Vetoriais e Simulações:** Funcionam 100% nativamente no Cloud Run porque `db/contrato_9291.sqlite` e `js/data.js` já vão embarcados na imagem.
* **Atualização de Novos PDFs (Ingestão Delta):** Como o sistema de arquivos do Cloud Run é *stateless* (efêmero entre reinicializações), o fluxo ideal e mais econômico é:
  1. Baixar os novos PDFs na máquina local e clicar em **Sincronizar Delta (Append-Only)** localmente (ou rodar `python ingest_engine.py`).
  2. Executar `backup.bat` — que envia o `db/contrato_9291.sqlite` e `js/data.js` atualizados para o GitHub e aciona o redeploy automático no Cloud Run!
  *(Alternativamente, se desejar armazenar os 240 MB de PDFs brutos na nuvem, basta montar um bucket do **Google Cloud Storage — GCS Volume Mount** no Cloud Run apontando para `/app/Ordens_De_Serviço`).*

---

## 5. Critérios de Aceite
- [x] `Dockerfile`, `.dockerignore` e `requirements.txt` presentes na raiz do repositório.
- [x] `server.py` configurado com `PORT = int(os.environ.get("PORT", 8092))` e endpoint `/healthz`.
