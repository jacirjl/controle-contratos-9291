# ⚡ Spec 02 — Motor de Ingestão Incremental (*Append-Only Delta*) e Busca Vetorial

## 1. Visão Geral
Especifica o funcionamento do módulo [`ingest_engine.py`](file:///c:/ProgsAntigravity/Contratos/ingest_engine.py), responsável por:
1. Mapear e classificar as **10 etapas formais de auditoria** definidas em [`instruções.md`](file:///c:/ProgsAntigravity/Contratos/instru%C3%A7%C3%B5es.md).
2. Garantir **Economia Total de Tokens de IA** por meio da estratégia **Append-Only Page Watermark (SHA-256)**, processando exclusivamente as páginas novas adicionadas ao final dos PDFs baixados do e-Protocolo.
3. Gerar vetores densos de 384 dimensões para busca semântica instantânea por similaridade de cosseno + *boost* lexical/contextual.

---

## 2. Mapeamento das 10 Etapas Cronológicas (`instruções.md`)

Cada página/peça processada nos PDFs das pastas `Ordens_De_Serviço/OS_01..OS_27` e no processo de pagamento `Processo_25.609.621-8_1.pdf` é classificada segundo o fluxo oficial:

| Etapa | Código | Nome da Etapa | Fonte Principal |
| :---: | :--- | :--- | :--- |
| **1** | `ETAPA_01_SOLICITACAO_PT` | Solicitação de Plano de Trabalho (Ofício/Memorando) | Processo da OS (`OS_XX`) |
| **2** | `ETAPA_02_APRESENTACAO_PT` | Apresentação do Plano de Trabalho (SOW/PT Consórcio) | Processo da OS (`OS_XX`) |
| **3** | `ETAPA_03_APROVACAO_PT` | Aprovação Técnica do Plano de Trabalho (Parecer/Informação) | Processo da OS (`OS_XX`) |
| **4** | `ETAPA_04_EMISSAO_OS` | Emissão da Ordem de Serviço (`OS_XX.pdf`) | Arquivo `OS_XX.pdf` / Processo |
| **5** | `ETAPA_05_AUTORIZACAO_OS` | Autorização / Assinatura da Ordem de Serviço (Ordenador/Gestor) | Processo da OS (`OS_XX`) |
| **6** | `ETAPA_06_APROVACAO_OS` | Aprovação Formal / Ciência de Início de Execução | Processo da OS (`OS_XX`) |
| **7** | `ETAPA_07_EXECUCAO_OS` | Execução da OS (Entregáveis Técnicos / Artefatos) | Processo da OS + `25.609.621-8` |
| **8** | `ETAPA_08_RELATORIO_EXECUCAO` | Relatório de Execução (RMEC Mensal / Medição UST) | `Processo_25.609.621-8_1.pdf` |
| **9** | `ETAPA_09_ATESTE_NF` | Termo de Aceite (TAD/TRP) + Ateste de Nota Fiscal | `Processo_25.609.621-8_1.pdf` |
| **10** | `ETAPA_10_PAGAMENTO` | Liquidação e Pagamento Efetivo (NL / OB / SIGA) | `Processo_25.609.621-8_1.pdf` |

---

## 3. Algoritmo de Ingestão Incremental (*Append-Only Delta*)

Os autos digitais exportados do e-Protocolo preservam integralmente as páginas anteriores ($1 \dots N$) e apenas acrescentam novas peças nas páginas $(N+1 \dots M)$.

### Fluxo de Decisão por Arquivo PDF (`ingest_all_pdfs`):
1. **Leitura de Metadados:** Abre o PDF via `pypdf.PdfReader` e obtém `current_total_pages` ($M$).
2. **Consulta ao Watermark:** Busca em `document_registry` os campos `last_processed_page` ($N$) e `last_page_sha256` ($H_N$).
3. **Caso 1 — Documento Inalterado ($M == N$):**
   - Extrai apenas a página $N$ e calcula `sha256(normalize_text(page[N]))`.
   - Se o hash coincidir com $H_N$, o arquivo é marcado como `SKIPPED_UNCHANGED`. **Zero páginas são enviadas para IA/vetorização.**
4. **Caso 2 — Atualização Incremental (*Append-Only Delta*, $M > N$ e $N > 0$):**
   - Verifica se o hash SHA-256 da página $N$ continua igual a $H_N$.
   - Confirmada a integridade da fronteira $N$, o motor ignora as páginas $1 \dots N$ e **processa exclusivamente o intervalo $[N+1, M]$**.
   - Ao concluir, atualiza `last_processed_page = M` e `last_page_sha256 = H_M`.
5. **Caso 3 — Documento Novo ($N == 0$) ou Reescrito ($H_N$ divergente):**
   - Processa o intervalo $[1, M]$ e registra o novo watermark.

---

## 4. Motor de Vetorização Semântica (384 Dimensões)

* **Função `compute_semantic_embedding_384(text, stage_name, os_id)`:**
  - Tokeniza o texto em unigramas, bigramas de domínio contratual e marcadores semânticos ponderados (ex: `glosa`, `ateste`, `nota fiscal`, `rmec`, `ust`, `termo de aceite`, `liquidacao`).
  - Aplica *Feature Hashing* com sinal (*Signed Random Projection / Weinberger et al.*) em espaço $\mathbb{R}^{384}$ e normalização unitária $L_2$ ($\|\mathbf{v}\|_2 = 1$).
* **Função `semantic_vector_search(query, top_k=15, filter_os=None, filter_stage=None)`:**
  - Calcula o produto interno (similaridade de cosseno) entre o vetor da consulta $\mathbf{q}$ e os vetores das páginas $\mathbf{d}_i$, combinado com *boost* de correspondência exata de termos jurídicos/financeiros.
  - Suporta filtragem opcional por Ordem de Serviço (`filter_os`) e por etapa (`filter_stage`).

---

## 5. Critérios de Aceite
- [x] Executar `python ingest_engine.py` duas vezes seguidas sem alterar os PDFs deve resultar em `pages_newly_embedded = 0` e `pages_skipped_cached = 3308` (100% de economia de tokens).
- [x] Adicionar páginas ao final de um PDF existente deve processar exclusivamente as páginas $> N$.
- [x] A função `semantic_vector_search` deve aceitar tanto `filter_os` quanto `os_filter` (compatibilidade retroativa) e retornar resultados ordenados por `score DESC`.
