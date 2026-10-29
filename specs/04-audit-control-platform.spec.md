# 🖥️ Spec 04 — Plataforma Web de Auditoria e Controle Contratual (UI/UX)

## 1. Visão Geral
Especifica a interface analítica e de governança localizada em [`plataforma-controle-9291/`](file:///c:/ProgsAntigravity/Contratos/plataforma-controle-9291/index.html), construída para fiscalização técnica, financeira e cronológica do **Contrato nº 9291/2025 (SEIA-PR $\times$ CELEPAR)**.

---

## 2. Arquitetura de Navegação e Módulos

A plataforma organiza o controle contratual em **9 módulos integrados**:

1. **📊 Dashboard Executivo:**
   - KPIs globais do contrato (Teto R$ 74.668.400,00, Empenhado, Liquidado/Pago, Retido/Glosado, Saldo Disponível).
   - Gráficos de execução mensal por natureza (USN Nuvem $\times$ UST Serviços Técnicos) e distribuição por órgão demandante.
2. **📋 Matriz de 27 OS (Plano de Trabalho $\times$ Execução $\times$ Cobrança):**
   - Visão completa das Ordens de Serviço `OS_01` a `OS_27` com filtro por status, risco, órgão e busca textual.
   - Modal de inspeção profunda (*Deep-Dive Drawer*) exibindo escopo, entregáveis, medição RMEC, links diretos para os PDFs (`OS_XX.pdf` e `Processo_..._1.pdf`) e trilha de auditoria.
3. **⏱️ Linha do Tempo Cronológica & Checklist 10 Etapas (`instruções.md`):**
   - Matriz de conformidade das 10 etapas (`Etapa 1: Solicitação PT` até `Etapa 10: Pagamento SIAFIC`) para todas as 27 OS.
   - Conciliação mensal RMEC (`Out/2025` a `Fev/2026`) do processo `25.609.621-8` $\leftrightarrow$ `24.574.062-0`.
   - Feed cronológico estrito de 136 eventos auditados com abertura do PDF na página exata (`#page=N`).
4. **🧠 Banco Vetorial & Ingestão Delta (Economia de Tokens IA):**
   - Painel de telemetria de marca d'água SHA-256 dos 29 PDFs (3.308 páginas indexadas e 1,62 milhão de tokens economizados).
   - Botão **Sincronizar Delta (Append-Only)** conectado a `/api/ingest-delta`.
   - Buscador semântico vetorial em tempo real conectado a `/api/vector-search` com atalhos de consulta rápida (`Glosa Capricorn`, `RMEC Dezembro`, `Atesto SEIA`, `USN Nuvem`).
5. **💰 Conciliação Financeira (RMEC $\times$ NFS-e $\times$ SIAFIC):**
   - Cruzamento de Notas de Aquisição de Serviço (NAS), Notas Fiscais, Notas de Liquidação (`2026NL`) e Ordens Bancárias (`2026OB`).
6. **🔍 Auditoria & Glosas (14 Achados Técnicos):**
   - Registro detalhado das inconformidades detectadas (ex: projeto `capricorn-408819` em região `us-central1` fora da OS, divergências de USN/UST, falta de desmembramento por OS).
7. **🧮 Simulador de Dimensionamento UST / USN:**
   - Catálogo interativo de serviços para conferência de memória de cálculo de novos Planos de Trabalho (ex: PT JACA - CEASA).
8. **⚡ Calculadora de SLA & IMR:**
   - Simulação automática de descontos e glosas por descumprimento de níveis de serviço.
9. **📁 Repositório Documental:**
   - Acesso rápido aos processos integrais e peças contratuais.

---

## 3. Critérios de Aceite
- [x] Todos os botões de atalho semântico e o botão **Buscar Vetores** devem consultar `/api/vector-search` e renderizar `similarity`, `doc_type`, `os_id`, `protocolo`, `page_num`, `ai_summary`, `snippet` e link para a página exata do PDF.
- [x] Caso o servidor Python não esteja acessível, o frontend deve possuir *fallback* local resiliente sobre `window.CHRONO_VECTOR_DATA` em [`js/data.js`](file:///c:/ProgsAntigravity/Contratos/plataforma-controle-9291/js/data.js).
- [x] Todos os links de documentos devem apontar para o caminho relativo correto com `#page=N` para abertura imediata no visualizador de PDF do navegador.
