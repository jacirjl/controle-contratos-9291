# 🔄 Spec 05 — Rastreabilidade SDD, Registro de Alterações e Guia de Reversibilidade (Git / GitHub)

## 1. Visão Geral
Este documento é o registro central de **Rastreabilidade SDD (Spec-Driven Development)** e **Controle de Reversibilidade (Rollback)** da Plataforma de Controle e Auditoria do Contrato 9291/2025.

Toda alteração realizada no sistema segue três regras obrigatórias:
1. **Registro na Especificação (`specs/*.spec.md`):** Nenhuma funcionalidade ou correção é aplicada sem estar documentada na sua respectiva Spec.
2. **Commit Atômico e Tag Semântica no Git:** Cada etapa concluída gera um commit isolado e uma tag nomeada (`vX.Y.Z-sdd-...`), sincronizados automaticamente no GitHub (`origin/main`).
3. **Reversibilidade Não-Destrutiva:** Qualquer alteração pode ser desfeita a qualquer momento sem perda de histórico nem impacto nos PDFs locais baixados do e-Protocolo.

---

## 2. Matriz de Rastreabilidade SDD $\leftrightarrow$ Tags Git

| Tag / Marco SDD | Especificação Vinculada | Escopo e Alterações Registradas | Arquivos Afetados | Comando de Reversão Direta |
| :--- | :--- | :--- | :--- | :--- |
| **`v1.0.0-sdd-base`** | Base Contratual & Regras (`instruções.md`) | Estrutura inicial do Contrato 9291/2025, planilha de acompanhamento das OS, minuta PT JACA/CEASA e plano arquitetural base. | `instruções.md`, `AcompanhamentoContrato-OS.xlsx`, `PLANO_IMPLEMENTACAO_PLATAFORMA.md`, `.gitignore` | `reverter.bat v1.0.0-sdd-base` |
| **`v1.1.0-sdd-spec04-ui`** | [`04-audit-control-platform.spec.md`](./04-audit-control-platform.spec.md) | Implementação da Plataforma Web UI/UX (Dashboard Executivo, Matriz das 27 OS, Conciliação Financeira, 14 Achados de Auditoria, Simuladores UST/IMR/SLA). | `plataforma-controle-9291/index.html`, `css/styles.css`, `js/data.js`, `js/app.js`, `LEIA-ME_PLATAFORMA.md` | `reverter.bat v1.1.0-sdd-spec04-ui` |
| **`v1.2.0-sdd-spec01-02-delta-db`** | [`01-database-schema.spec.md`](./01-database-schema.spec.md)<br/>[`02-delta-ingestion-engine.spec.md`](./02-delta-ingestion-engine.spec.md) | Motor de Ingestão Incremental (*Append-Only Delta* com SHA-256), Banco Híbrido SQLite (`document_watermarks`, `chronological_events`, `rmec_monthly_os`, `vector_chunks`) e 136 eventos cronológicos das 10 etapas. | `ingest_engine.py`, `db/contrato_9291.sqlite`, `ARQUITETURA_CRONOLOGICA_E_VETORIAL_DELTA.md` | `reverter.bat v1.2.0-sdd-spec01-02-delta-db` |
| **`v1.2.1-sdd-spec03-fix-api`** | [`03-api-server.spec.md`](./03-api-server.spec.md) | Correção do argumento `filter_os` na rota `GET /api/vector-search` de `server.py` (resolvendo `TypeError: got an unexpected keyword argument 'os_filter'`) e alinhamento dos atributos JSON com `js/app.js`. | `server.py`, `plataforma-controle-9291/js/app.js` | `reverter.bat v1.2.1-sdd-spec03-fix-api` |
| **`v1.3.0-sdd-spec-kit-completo`** | [`SYSTEM_SPEC.md`](./SYSTEM_SPEC.md)<br/>[`05-sdd-changelog-reversibilidade.spec.md`](./05-sdd-changelog-reversibilidade.spec.md) | Governança SDD / Spec-Kit completa (`GEMINI.md`, `specs/01..05`), endpoint `/api/git-history` e utilitários de automação (`backup.bat`, `reverter.bat`, `iniciar_plataforma.bat`). | `GEMINI.md`, `specs/*`, `backup.bat`, `reverter.bat`, `iniciar_plataforma.bat`, `server.py` | `reverter.bat v1.3.0-sdd-spec-kit-completo` |
| **`v1.4.0-sdd-spec06-cloudrun`** | [`06-cloud-run-deploy.spec.md`](./06-cloud-run-deploy.spec.md) | Preparação completa para deploy no Google Cloud Run (`Dockerfile`, `.dockerignore`, `requirements.txt`, variável de ambiente `PORT` dinâmica e `/healthz` em `server.py`). | `Dockerfile`, `.dockerignore`, `requirements.txt`, `server.py`, `specs/06-cloud-run-deploy.spec.md` | `reverter.bat v1.4.0-sdd-spec06-cloudrun` |

---

## 3. Histórico Detalhado de Alterações (SDD Changelog)

### [v1.4.0-sdd-spec06-cloudrun] — 2026-10-29
- **Infraestrutura Cloud Run (`Spec 06`):** Criação de [`Dockerfile`](../Dockerfile), [`.dockerignore`](../.dockerignore) e [`requirements.txt`](../requirements.txt), além da adaptação de [`server.py`](../server.py) para escutar na porta dinâmica `PORT = int(os.environ.get("PORT", 8092))` e responder a *health checks* em `GET /healthz`.

### [v1.3.0-sdd-spec-kit-completo] — 2026-10-29
- **Método SDD (Spec-Kit):** Criação da suíte formal de especificações em `specs/` (`README.md`, `SYSTEM_SPEC.md`, `01` a `05`) e diretrizes permanentes do agente em `GEMINI.md`.
- **Reversibilidade Git/GitHub:** Inicialização do repositório Git com commits granulares retroativos para cada etapa evolutiva do projeto, tags anotadas e sincronização remota com o GitHub.
- **Automação Operacional:** Adição dos scripts `backup.bat`, `reverter.bat` e `iniciar_plataforma.bat` e rota `GET /api/git-history` em `server.py`.

### [v1.2.1-sdd-spec03-fix-api] — 2026-10-29
- **Causa Raiz (`Spec 03`):** Ao clicar nos botões de busca semântica na interface web, `server.py` chamava `ingest_engine.semantic_vector_search(q, top_k=top_k, os_filter=os_filter)` sem passar a conexão SQLite `conn` e usando o nome de parâmetro `os_filter` em vez de `filter_os`.
- **Solução Implementada:**
  - Ajuste em [`server.py`](../server.py) para abrir conexão `sqlite3.connect(ingest_engine.DB_PATH)`, mapear os códigos de filtro (`PROC_RMEC` $\rightarrow$ `COBRANCA_RMEC`, `PROC_MAE` $\rightarrow$ `CONTRATO_GERAL`) e chamar `ingest_engine.semantic_vector_search(conn, q, top_k=top_k, filter_os=mapped_filter)`.
  - Alinhamento em [`plataforma-controle-9291/js/app.js`](../plataforma-controle-9291/js/app.js) para ler `similarity`, `doc_type`, `page_num`, `ai_summary`, `snippet` e `pdf_link`.

### [v1.2.0-sdd-spec01-02-delta-db] — 2026-10-29
- **Implementação (`Specs 01 e 02`):** Criação do motor [`ingest_engine.py`](../ingest_engine.py) e banco [`db/contrato_9291.sqlite`](../db/contrato_9291.sqlite).
- **Indexação Inicial:** 29 arquivos PDF (3.308 páginas), 270 chunks vetoriais de 128 dimensões, 136 eventos cronológicos cobrindo as 10 etapas de `instruções.md` e 1.626.664 tokens cacheados para economia em futuras atualizações incrementais.

### [v1.1.0-sdd-spec04-ui] — 2026-10-29
- **Implementação (`Spec 04`):** Construção da plataforma web de auditoria e controle do Contrato 9291/2025 em [`plataforma-controle-9291/`](../plataforma-controle-9291/).

---

## 4. Como Reverter Qualquer Alteração (Guia Prático)

### Opção A — Usando o Utilitário Interativo (`reverter.bat`)
Basta dar duplo clique em [`reverter.bat`](../reverter.bat) ou executar no terminal:
```bat
:: 1. Desfazer apenas a última alteração feita:
reverter.bat ULTIMO

:: 2. Voltar todo o sistema para um marco SDD específico:
reverter.bat v1.2.1-sdd-spec03-fix-api
```

### Opção B — Usando Comandos Git Diretos
```powershell
# Reverter um commit específico criando um novo commit de reversão (sem apagar o histórico):
git revert <HASH_DO_COMMIT> --no-edit
git push origin main

# Restaurar apenas um arquivo específico de uma versão anterior:
git checkout v1.2.0-sdd-spec01-02-delta-db -- plataforma-controle-9291/js/app.js
```

> [!IMPORTANT]
> **Proteção dos PDFs Locais:** Os arquivos PDF brutos (`Processo_*.pdf` e `Ordens_De_Serviço/**/*.pdf`) estão protegidos no `.gitignore`. Assim, qualquer operação de `git revert` ou `reverter.bat` altera apenas o código-fonte, especificações e banco de dados, **jamais apagando ou sobrescrevendo os PDFs baixados do e-Protocolo**.
