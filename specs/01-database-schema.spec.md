# 🗄️ Spec 01 — Esquema de Banco de Dados Híbrido (Event Store Cronológico + Vector DB)

## 1. Visão Geral
Define o modelo de persistência híbrido em **SQLite** ([`db/contrato_9291.sqlite`](file:///c:/ProgsAntigravity/Contratos/db/contrato_9291.sqlite)), gerenciado pelo módulo [`ingest_engine.py`](file:///c:/ProgsAntigravity/Contratos/ingest_engine.py):
1. **Controle de Watermark SHA-256 por Documento/Página (`document_watermarks`):** Permite ingestão *Append-Only Delta* processando apenas páginas $> \text{last\_ingested\_page}$.
2. **Event Store Cronológico (`chronological_events`):** Rastreia as 10 etapas formais de cada Ordem de Serviço (`instruções.md`) ordenadas por `date_iso ASC, page_num ASC`.
3. **Conciliação Mensal RMEC (`rmec_monthly_os`):** Relaciona as medições de USN e UST do processo de cobrança `25.609.621-8` com atestos, Notas Fiscais, Notas de Liquidação (NL) e Ordens Bancárias (OB) do processo mãe `24.574.062-0`.
4. **Vector Store Semântico (`vector_chunks`):** Armazena o trecho textual, o parecer analítico pré-computado da IA (`ai_summary`) e o vetor denso normalizado L2 de **128 dimensões** (`embedding_json`).

---

## 2. Esquema de Tabelas

### 2.1. `document_watermarks`
Controla o estado de ingestão e a marca d'água criptográfica (*watermark*) de cada um dos 29 arquivos PDF monitorados.
* `doc_id` (TEXT PRIMARY KEY) — Identificador único do documento (Ex: `PROC_MAE_245740620`, `PROC_RMEC_256096218`, `OS_01_PROC`)
* `protocolo` (TEXT) — Número do e-Protocolo (Ex: `24.574.062-0`, `25.609.621-8`, `25.289.226-5`)
* `os_id` (TEXT) — Identificador da OS vinculada (`CONTRATO_GERAL`, `COBRANCA_RMEC`, `OS_01` a `OS_27`)
* `rel_path` (TEXT) — Caminho relativo do arquivo PDF
* `file_size` (INTEGER) — Tamanho do arquivo em bytes
* `total_pages` (INTEGER) — Total de páginas do PDF ($M$)
* `last_ingested_page` (INTEGER) — Última página já processada e indexada ($N$)
* `first_page_sha256` (TEXT) — Hash SHA-256 do texto da página 1
* `last_page_sha256` (TEXT) — Hash SHA-256 do texto da página $N$ (garantia de imutabilidade das páginas anteriores)
* `tokens_cached` (INTEGER) — Total de tokens economizados/cacheados no documento
* `last_sync_at` (TEXT) — Data/hora da última sincronização
* `status_integrity` (TEXT) — Ex: `'INTEGRO_CACHE_COMPLETO'`, `'DELTA_APPENDED'`

### 2.2. `chronological_events`
Event Store cronológico das 10 etapas definidas em [`instruções.md`](file:///c:/ProgsAntigravity/Contratos/instru%C3%A7%C3%B5es.md).
* `event_id` (TEXT PRIMARY KEY)
* `date_iso` (TEXT) — Data/hora no formato `YYYY-MM-DD HH:MM` para ordenação cronológica estrita
* `date_br` (TEXT) — Data formatada em PT-BR (`DD/MM/YYYY HH:MM`)
* `protocolo` (TEXT) — Protocolo de origem do evento
* `os_id` (TEXT) — `OS_01` a `OS_27`, `COBRANCA_RMEC` ou `CONTRATO_GERAL`
* `competencia` (TEXT) — Competência de referência (`Out/2025`, `Nov/2025`, `Dez/2025`, `Jan/2026`, `Fev/2026`)
* `step_number` (INTEGER) — Etapa de `1` a `10` conforme `instruções.md`
* `step_code` (TEXT) — Código da etapa (Ex: `ETAPA_1_SOLICITACAO_PT`, `ETAPA_8_RMEC_EXECUCAO`, `ETAPA_10_PAGAMENTO_SIAFIC`)
* `actor_from` (TEXT) — Órgão/Agente emissor
* `actor_to` (TEXT) — Órgão/Agente destinatário
* `doc_type` (TEXT) — Tipo da peça (Ofício, Plano de Trabalho, OS, RMEC, Atesto, NFS-e, NL/OB)
* `title` (TEXT) — Título resumido do evento
* `detail` (TEXT) — Descrição analítica detalhada e evidências
* `usn` (REAL) — Quantidade de USN envolvida no evento
* `ust` (REAL) — Quantidade de UST envolvida no evento
* `valor_brl` (REAL) — Valor financeiro em R$
* `page_num` (INTEGER) — Página exata no PDF de origem
* `pdf_link` (TEXT) — Caminho relativo com âncora de página (`#page=X`)

### 2.3. `rmec_monthly_os`
Conciliação mensal por Ordem de Serviço cruzando `Processo_25.609.621-8_1.pdf` (RMEC, Fechamento e Atesto) e `Processo_24.574.062-0_1.pdf` (Notas Fiscais, Liquidação SIAFIC e Ordem Bancária).
* `id` (TEXT PRIMARY KEY)
* `competencia` (TEXT) — `Outubro/2025`, `Novembro/2025`, `Dezembro/2025`, `Janeiro/2026`, `Fevereiro/2026`
* `competencia_ordem` (INTEGER) — Ordem cronológica da competência (`1` a `5`)
* `os_id` (TEXT) — Identificador da OS
* `usn` (REAL) / `valor_usn` (REAL) — Consumo e valor de Nuvem (USN)
* `ust` (REAL) / `valor_ust` (REAL) — Consumo e valor de Serviços Técnicos (UST)
* `valor_total` (REAL) — Soma apurada na competência para a OS
* `rmec_page` (INTEGER) / `fechamento_page` (INTEGER) / `atesto_page` (INTEGER) — Páginas das evidências no processo `25.609.621-8`
* `atesto_data` (TEXT) — Data formal do Termo de Atesto SEIA
* `nf_usn` (TEXT) / `nf_ust` (TEXT) — Números das Notas Fiscais emitidas
* `nl_numeros` (TEXT) / `ob_numeros` (TEXT) — Notas de Liquidação (`2026NL...`) e Ordens Bancárias (`2026OB...`)
* `proc_mae_page` (INTEGER) — Página no processo mãe `24.574.062-0`
* `status_ciclo` (TEXT) — Status do ciclo financeiro (`PAGO_INTEGRAL`, `ATESTADO_AGUARDANDO_NL`, `GLOSA_RETIFICACAO`)
* `observacao` (TEXT)

### 2.4. `vector_chunks`
Banco de dados vetorial com resumos de IA pré-computados por página/bloco.
* `chunk_id` (TEXT PRIMARY KEY) — Ex: `PROC_RMEC_256096218_P0055`
* `doc_id` (TEXT) — Referência a `document_watermarks(doc_id)`
* `protocolo` (TEXT)
* `os_id` (TEXT)
* `competencia` (TEXT)
* `doc_type` (TEXT)
* `page_num` (INTEGER) — Página no PDF
* `page_sha256` (TEXT) — Hash SHA-256 do conteúdo da página
* `pdf_link` (TEXT) — Link direto para abertura do PDF na página exata
* `snippet` (TEXT) — Trecho textual extraído da página
* `ai_summary` (TEXT) — Síntese analítica pré-processada pela IA para economia de tokens
* `embedding_json` (TEXT) — Vetor denso de 128 dimensões (`float32` normalizado L2) em JSON
* `ingested_at` (TEXT)

---

## 3. Índices de Performance
* `idx_chrono_date`: `chronological_events(date_iso ASC, page_num ASC)`
* `idx_chrono_os`: `chronological_events(os_id, date_iso ASC)`
* `idx_chrono_step`: `chronological_events(step_number, date_iso ASC)`
* `idx_vec_doc_page`: `vector_chunks(doc_id, page_num)`
* `idx_vec_os`: `vector_chunks(os_id)`

---

## 4. Critérios de Aceite
- [x] Conexões SQLite configuradas com `PRAGMA journal_mode=WAL` e `PRAGMA synchronous=NORMAL`.
- [x] Todos os 29 PDFs (3.308 páginas) registrados em `document_watermarks` com `first_page_sha256` e `last_page_sha256`.
- [x] Ordenação cronológica determinística garantida via `date_iso ASC, step_number ASC, page_num ASC`.
