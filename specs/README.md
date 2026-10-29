# 📚 Spec-Kit (SDD) — Plataforma de Controle e Auditoria do Contrato 9291/2025

Bem-vindo à especificação formal de arquitetura, banco de dados híbrido, motor de ingestão incremental e regras de negócio da **Plataforma de Controle e Auditoria do Contrato 9291/2025 (SEIA-PR / Consórcio SENAI-FUNPAR)**.

Este diretório adota a metodologia **SDD (Spec-Driven Development / Spec-Kit)**, atuando como **Fonte Única de Verdade (*Single Source of Truth*)** para o desenvolvimento, auditoria contínua, rastreabilidade de mudanças e reversibilidade via Git/GitHub.

---

## 🗂️ Estrutura de Especificações

| Documento | Módulo | Descrição |
| :--- | :--- | :--- |
| [`SYSTEM_SPEC.md`](./SYSTEM_SPEC.md) | **Especificação Geral** | Visão unificada da arquitetura em 4 camadas, fluxo cronológico de 10 etapas, motor vetorial delta e diretrizes |
| [`01-database-schema.spec.md`](./01-database-schema.spec.md) | **Persistência Híbrida (SQLite + Vetorial)** | Esquemas de tabelas (`document_registry`, `os_lifecycle_events`, `document_pages_vector`, `rmec_monthly_execution`), views e índices |
| [`02-delta-ingestion-engine.spec.md`](./02-delta-ingestion-engine.spec.md) | **Motor de Ingestão Delta & IA** | Algoritmo *Append-Only Delta* por marca d'água SHA-256, extração das 10 etapas (`instruções.md`) e indexação semântica 384-dim |
| [`03-api-server.spec.md`](./03-api-server.spec.md) | **Servidor HTTP/REST (`server.py`)** | Especificação dos endpoints REST (`/api/status`, `/api/vector-search`, `/api/ingest-delta`, `/api/timeline`), contratos JSON e tratamento de erros |
| [`04-audit-control-platform.spec.md`](./04-audit-control-platform.spec.md) | **Plataforma Web UI/UX** | Especificação das 9 abas da interface analítica, KPIs executivos, matriz das 27 OS, conciliação SIGA/RMEC e simuladores IMR/UST/SLA |
| [`05-sdd-changelog-reversibilidade.spec.md`](./05-sdd-changelog-reversibilidade.spec.md) | **Rastreabilidade & Rollback Git** | Matriz de rastreabilidade `Spec <-> Commit/Tag Git`, histórico cronológico de todas as alterações e guia prático de reversão (`reverter.bat`) |
| [`../ARQUITETURA_CRONOLOGICA_E_VETORIAL_DELTA.md`](../ARQUITETURA_CRONOLOGICA_E_VETORIAL_DELTA.md) | **Documento Arquitetural** | Estudo técnico detalhado da estratégia de economia de tokens de IA e armazenamento cronológico |
| [`../LEIA-ME_PLATAFORMA.md`](../LEIA-ME_PLATAFORMA.md) | **Guia Rápido de Operação** | Instruções de inicialização e uso da plataforma |

---

## 📐 Diretrizes do SDD (Spec-Driven Development)

1. **Especificação como Contrato:** Qualquer alteração de código em [`ingest_engine.py`](../ingest_engine.py), [`server.py`](../server.py) ou [`plataforma-controle-9291/`](../plataforma-controle-9291/) deve estar respaldada por sua respectiva especificação em `specs/`.
2. **Rastreabilidade Bidirecional:** Toda mudança implementada recebe um registro formal em [`05-sdd-changelog-reversibilidade.spec.md`](./05-sdd-changelog-reversibilidade.spec.md) vinculado a um commit semântico e uma tag Git.
3. **Reversibilidade Garantida:** Qualquer estado anterior do sistema pode ser restaurado instantaneamente via Git/GitHub utilizando o utilitário [`reverter.bat`](../reverter.bat) ou comandos nativos (`git revert` / `git checkout <tag>`).
