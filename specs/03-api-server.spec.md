# 🔌 Spec 03 — Servidor HTTP/REST e Integração Vetorial (`server.py`)

## 1. Visão Geral
Especifica a camada de serviço HTTP/REST implementada em [`server.py`](file:///c:/ProgsAntigravity/Contratos/server.py) na porta `8092` (`ThreadingTCPServer`), responsável por servir os ativos estáticos da plataforma (`plataforma-controle-9291/`) e os PDFs de auditoria, além de fornecer endpoints REST JSON conectados ao banco [`db/contrato_9291.sqlite`](file:///c:/ProgsAntigravity/Contratos/db/contrato_9291.sqlite) via [`ingest_engine.py`](file:///c:/ProgsAntigravity/Contratos/ingest_engine.py).

---

## 2. Endpoints da API REST

### 2.1. `GET /api/status`
Retorna o diagnóstico completo do banco híbrido (Event Store + Vector DB) e o estado de marca d'água (*watermarks*) dos 29 documentos monitorados.
* **Resposta JSON (`200 OK`):**
  ```json
  {
    "ok": true,
    "db_path": "db/contrato_9291.sqlite",
    "total_pdfs": 29,
    "total_pages_indexed": 3308,
    "total_vector_chunks": 270,
    "total_chronological_events": 136,
    "estimated_tokens_saved_on_resync": 1626664,
    "watermarks": [...]
  }
  ```

### 2.2. `GET /api/vector-search`
Executa busca semântica vetorial híbrida (similaridade de cosseno em 128 dimensões + *boost* de vocabulário de domínio FinOps/Contratos) sobre `vector_chunks`.
* **Parâmetros de Query (`GET`):**
  * `q` (string): Consulta em linguagem natural ou termos técnicos (Ex: `glosa capricorn iowa`, `rmec dezembro atesto`).
  * `os` (string, opcional): Filtro de processo/OS. Suporta mapeamento automático:
    * `""` ou `"TODOS"` $\rightarrow$ `"TODOS"`
    * `"PROC_RMEC"` $\rightarrow$ `"COBRANCA_RMEC"`
    * `"PROC_MAE"` $\rightarrow$ `"CONTRATO_GERAL"`
    * `"OS_01"` .. `"OS_27"` $\rightarrow$ filtro direto por Ordem de Serviço.
  * `limit` (int, opcional, padrão `15`): Quantidade máxima de resultados (`top_k`).
* **Contrato Interno com `ingest_engine.py`:**
  * Invoca `ingest_engine.semantic_vector_search(conn, q, top_k=top_k, filter_os=mapped_filter)`.
* **Resposta JSON (`200 OK`):**
  ```json
  {
    "ok": true,
    "query": "glosa capricorn",
    "os_filter": "TODOS",
    "count": 15,
    "results": [
      {
        "chunk_id": "...",
        "doc_id": "PROC_RMEC_256096218",
        "protocolo": "25.609.621-8",
        "os_id": "COBRANCA_RMEC",
        "competencia": "Nov/2025",
        "doc_type": "CONTESTACAO_GLOSA_SEIA",
        "page_num": 55,
        "page_sha256": "...",
        "pdf_link": "Processo_25.609.621-8_1.pdf#page=55",
        "snippet": "...",
        "ai_summary": "...",
        "similarity": 0.8742
      }
    ]
  }
  ```

### 2.3. `GET | POST /api/ingest-delta`
Dispara a verificação incremental (*Append-Only Delta*) sobre todos os PDFs da pasta.
* **Comportamento:**
  * Chama `ingest_engine.run_delta_ingestion(conn, force_rebuild=False)`.
  * Se `new_pages_ingested_delta > 0`, atualiza as tabelas estruturadas (`populate_structured_tables`) e sincroniza o bundle frontend (`patch_frontend_data_js`).
  * Se nenhuma página nova foi adicionada aos PDFs (`new_pages_ingested_delta == 0`), retorna imediatamente com 100% de economia de tokens (`pages_skipped_cached = 3308`).

### 2.4. `GET /api/timeline`
Retorna todos os eventos cronológicos das 10 etapas (`instruções.md`) ordenados por `date_iso ASC, step_number ASC, page_num ASC`.

### 2.5. `GET /api/git-history`
Retorna o histórico de commits, tags SDD e status atual do repositório Git local para rastreabilidade e auditoria de versão diretamente na interface.

---

## 3. Critérios de Aceite
- [x] O servidor deve rodar em modo multi-thread (`socketserver.ThreadingTCPServer`) com `allow_reuse_address = True`.
- [x] Todos os endpoints JSON devem retornar cabeçalho `Content-Type: application/json; charset=utf-8` e `Access-Control-Allow-Origin: *`.
- [x] O endpoint `/api/vector-search` deve traduzir corretamente os filtros do frontend (`PROC_RMEC`, `PROC_MAE`, `OS_XX`) e repassar `filter_os` para `ingest_engine.semantic_vector_search` sem erro de argumento (`TypeError`).
