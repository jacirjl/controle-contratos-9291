# Arquitetura de Armazenamento Cronológico, Banco Vetorial Híbrido e Ingestão Incremental (Delta Append-Only)
**Contrato Administrativo nº 9291/2025 (SEIA/PR × CELEPAR — GMS 47396/2025)**  
**Roteiro de Auditoria:** [`instruções.md`](file:///c:/ProgsAntigravity/Contratos/instru%C3%A7%C3%B5es.md) (10 Etapas)  
**Acervo Indexado:** 29 Arquivos PDF | **3.308 Páginas** (`Processo_24.574.062-0_1.pdf` com 890 fls., `Processo_25.609.621-8_1.pdf` com 766 fls., e 27 Processos de OS com 1.652 fls.)

---

## 1. Qual é a Melhor Forma de Guardar os Dados Cronologicamente para Consulta Futura?

Para garantir que todos os eventos das **10 etapas do arquivo `instruções.md`** estejam **sempre disponíveis em ordem cronológica estrita** e ao mesmo tempo permitir **busca semântica por IA sem gastar tokens repetidamente**, a melhor arquitetura de engenharia de software é um **Banco de Dados Híbrido Local em Arquivo Único (`SQLite WAL + Event Store Cronológico B-Tree + Vector Store de Páginas + Watermark SHA-256`)**, implementado em [`db/contrato_9291.sqlite`](file:///c:/ProgsAntigravity/Contratos/db/contrato_9291.sqlite) pelo motor [`ingest_engine.py`](file:///c:/ProgsAntigravity/Contratos/ingest_engine.py).

### Por que essa arquitetura é superior a bancos separados?
1. **Atomicidade (ACID) entre o Vetor da Página e a Linha do Tempo**: Quando uma nova página é anexada a um PDF do e-Protocolo, a mesma transação grava o vetor semântico da página, o resumo extraído pela IA e o evento cronológico correspondente.
2. **Ordenação Cronológica Determinística ($O(\log N)$ via Índice Composto B-Tree)**:
   - Tabela `chronological_events` indexada por `(event_date ASC, step_number ASC, os_id ASC)` com datas padronizadas em `ISO-8601 (YYYY-MM-DD)`.
   - Permite consultar instantaneamente a evolução histórica de uma OS específica (`OS_01` a `OS_27`), de uma etapa específica (`Etapa 1` a `Etapa 10`) ou de todo o contrato.
3. **Zero Dependência de Servidores Externos Pesados**: Tudo reside em `c:\ProgsAntigravity\Contratos\db\contrato_9291.sqlite`, portável, auditável e integrado ao servidor local [`server.py`](file:///c:/ProgsAntigravity/Contratos/server.py).

---

## 2. Como Funciona a Ingestão Incremental ("Delta Append-Only") para Economizar Tokens de IA?

Os processos administrativos do **e-Protocolo do Estado do Paraná** possuem uma propriedade estrutural fundamental: **são documentos estritamente cumulativos (*append-only*)**. Quando você baixa uma versão atualizada de `Processo_24.574.062-0_1.pdf`, `Processo_25.609.621-8_1.pdf` ou de qualquer processo de OS:
- As páginas anteriores `1 .. N` permanecem **idênticas bit a bit**;
- Apenas as novas movimentações são adicionadas nas páginas `N+1 .. M`.

### Algoritmo de Watermark Criptográfico (`document_watermarks`)
Para cada um dos 29 PDFs, a tabela `document_watermarks` armazena:
- `last_ingested_page` ($N$): o número da última página já processada pela IA e vetorizada;
- `first_page_sha256`: hash SHA-256 do conteúdo da Página 1;
- `last_page_sha256`: hash SHA-256 do conteúdo da Página $N$ (fronteira de corte).

Quando você baixa PDFs atualizados e clica em **"🔄 Sincronizar PDFs (Delta IA)"** na plataforma (ou executa `python ingest_engine.py`):
1. O motor abre cada PDF e verifica o total de páginas atual ($M$).
2. Se $M == N$ e o hash SHA-256 da página $N$ continua idêntico ao `last_page_sha256` salvo no banco:
   - **Resultado:** `SKIPPED_NO_NEW_PAGES` — **0 páginas processadas, 100% dos tokens economizados** (nas 3.308 páginas atuais, isso economiza **~2.811.800 tokens** a cada sincronização!).
3. Se $M > N$ e o hash SHA-256 da página $N$ bate com o `last_page_sha256` salvo:
   - **Resultado:** `APPENDED_DELTA` — O motor **ignora completamente as páginas `1 .. N`** e executa a extração de IA, entidades e geração de embeddings **exclusivamente no intervalo novo `[N+1 .. M]`**, atualizando a marca d'água para $M$ ao final.
4. **Salvaguarda de Segurança:** Caso um arquivo seja substituído por outro documento completamente diferente (o hash da página 1 ou da página $N$ mudou), o motor detecta a divergência (`REBUILT_MODIFIED_BASE`) e reindexa apenas aquele arquivo específico.

---

## 3. Resultado da Checagem das 10 Etapas (`instruções.md`) nos 29 PDFs

### Etapas 1 a 5 — Ciclo de Vida por Ordem de Serviço (`OS_01` a `OS_27`)
| Etapa | Descrição no `instruções.md` | Resultado Auditado nas 27 Pastas de OS |
| :--- | :--- | :--- |
| **Etapa 1** | Solicitação de serviço + Plano de Trabalho (PT) com escopo e cronograma | **21 processos** possuem PT/SOW ou justificativa técnica; **6 processos (`OS_08`, `OS_09`, `OS_10`, `OS_11`, `OS_25`, `OS_27`)** não possuem Plano de Trabalho específico nos autos. |
| **Etapa 2** | SEIA encaminha o protocolo para a CELEPAR levantar custos | Cumprida nas 27 OSs via Despacho/Ofício SEIA/DG ou termo de abertura. |
| **Etapa 3** | CELEPAR retorna para a SEIA os custos (Dimensionamento Inicial USN/UST) | **13 OSs** possuem Dimensionamento Inicial assinado; **10 OSs de Set/2026 (`OS_08` a `OS_17`)** e **4 OSs de Out/2026 (`OS_24` a `OS_27`)** não tiveram orçamento individualizado retornado antes da emissão da OS. |
| **Etapa 4** | SEIA emite a Ordem de Serviço autorizando a execução | **26 OSs** emitidas e assinadas (`OS_01` a `OS_05` e `OS_07` a `OS_27`). **Apenas 6 OSs (`01, 02, 03, 04, 05, 23`)** trazem valores preenchidos no corpo da OS. A **`OS_06` (Data Foundation — R$ 4,32M/mês)** não possui OS assinada nos autos. |
| **Etapa 5** | SEIA recebe confirmação de início / execução | **`OS_07`, `OS_20` e `OS_22`** tiveram ambiente de produção bloqueado até apresentação de orçamento; porém **`OS_24`, `OS_25`, `OS_26` e `OS_27`** liberaram **produção imediata** sem orçamento prévio. |

---

### Etapas 6 a 10 — Ciclo Mensal de Medição (RMEC), Atesto SEIA, NAS (GMS) e Pagamento NFS (SIAFIC)
Cruzamento exato entre o **Protocolo de RMEC (`Processo_25.609.621-8_1.pdf` — 766 fls.)** e o **Protocolo Mãe (`Processo_24.574.062-0_1.pdf` — 890 fls.)**:

| Competência | Etapa 6A: RMEC Celepar (`25.609.621-8`) | Medição (USN + UST) e Valor R$ | Etapa 6B: Atesto Técnico SEIA (`25.609.621-8`) | Etapa 7: NFS-e + Envio ao NAS (`24.574.062-0`) | Etapa 8: NAS lança no GMS ➔ NFS | Etapa 9: NFS Paga (NL/OB SIAFIC) ➔ NAS |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Fev/2026** | Ofício 147/26 (17/03/26, **fls. 21–42**) — 1 OS (`OS_02`) | 107.619,44 USN + 147,53 UST = **R$ 235.122,41** | Atestado em 18/03/26 (**fl. 43**) | NFS-e **1353** (25/03/26, **fl. 747**) | 22/04/26 (**fl. 758**) | **NL 389 / OB 28/04/26** (**fls. 760–762**) — Pago |
| **Mar/2026** | 1ª Submissão (**fls. 45–85**) ➔ Retificado em 30/04/26 (**fls. 89–117**) — 3 OSs (`02, 05, 06`) | 249.476,12 USN + 129,08 UST = **R$ 479.074,22** | **Devolvido/Glosado em 29/04/26 (fls. 86–88)** por atas duplicadas e erro de soma de R$ 10; **Atestado após retificação em 04/05/26 (fl. 118)** | NFS-e **2275** (07/05/26, **fl. 767**) | 11/05/26 (**fl. 775**) | **NL 424 / OB 15/05/26** (**fls. 779–782**) — Pago |
| **Abr/2026** | Ofício 262/26 (22/05/26, **fls. 120–187**) — 5 OSs (`01, 02, 03, 05, 06`) | 609.027,20 USN + 704,65 UST = **R$ 1.290.224,57** | Atestado em 25/05/26 (**fl. 188**) | NFS-e **3008** (15/06/26, **fl. 790**) | 06/07/26 (**fl. 798**) | **NL 594 / OB 13/07/26** (**fls. 800–802**) — Pago |
| **Mai/2026** | Ofício 334/26 (26/06/26, **fls. 190–279**) — 6 OSs (`01..06`) | 1.046.968,26 USN + 954,73 UST = **R$ 2.138.486,79** | Atestado em 29/06/26 (**fl. 280**) | NFS-e **3300** (30/06/26, **fl. 808**) | 20/08/26 (**fl. 816**) | **NL 727 / OB 27/08/26** (**fls. 818–820**) — Pago |
| **Jun/2026** | Ofício 380/26 (22/07/26, **fls. 282–408**) — 6 OSs (`01..06`) | 1.987.340,06 USN + 942,46 UST = **R$ 3.789.740,71** | Atestado em 23/07/26 (**fl. 409**) | NFS-e **3486** (24/07/26, **fl. 832**) | 09/09/26 (**fl. 840**) | **NL 782 / OB 15/09/26** (**fls. 842–845**) — Pago |
| **Jul/2026** | Ofício 472/26 (28/08/26, **fls. 411–550**) — 6 OSs (`01..06`) | 1.488.980,75 USN + 488,00 UST = **R$ 2.771.812,43** | **Atestado c/ 3 Determinações em 31/08/26 (fls. 551–552)**: (1) Migrar dados dos EUA (`us-central1`/`us-east5`) p/ Brasil (LGPD); (2) Rastreabilidade OS-005; (3) Excluir Projeto Capricorn | NFS-e **4336** (03/09/26, **fl. 855**) | 16/09/26 (**fl. 863**) | **NL 811 / OB 22/09/26** (**fls. 865–868**) — Pago |
| **Ago/2026** | Ofício 543/26 (28/09/26, **fls. 554–635**) — 6 OSs (`01..06`) | 1.936.567,54 USN + 488,00 UST = **R$ 3.559.565,67** | Atestado em 29/09/26 (**fl. 636**) | NFS-e **4827** (30/09/26, **fl. 875**) | 09/10/26 (**fl. 883**) | **NLs 893+894 / OBs 15/10/26** (**fls. 886–889**) — Pago |
| **Set/2026** | Ofício 598/26 (23/10/26, **fls. 638–766**) — **21 RMECs (18 OSs c/ consumo)** | 1.906.405,41 USN + 1.360,00 UST = **R$ 3.776.669,52** | *Pendente de Atesto SEIA após fl. 766* | *Aguarda Etapa 6B* | *Aguarda Etapa 7* | *Aguarda Etapa 8* |
