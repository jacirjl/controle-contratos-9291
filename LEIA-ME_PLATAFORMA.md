# Plataforma de Controle do Contrato 9291/2025 — onde está e como abrir

O código **não fica no Drive** (o Drive sincronizando repositório e dependências corrompe arquivos).

- **Código:** `/Users/padilha/dev/plataforma-controle-9291` (repositório Git local)
- **Dados reais:** `data_private/` e `.env` dentro dessa pasta — nunca vão para o Git nem para o Drive.

## Abrir a plataforma
```bash
/Users/padilha/dev/plataforma-controle-9291/scripts/iniciar.sh
```
Abre em **http://127.0.0.1:8000** (banco, migrations, carga inicial, interface e API, tudo numa porta).
Para parar o banco: `scripts/parar.sh`.

## Continuar a implementação
Abra uma sessão do Claude Code **na pasta `~/dev/plataforma-controle-9291`**. O arquivo `CLAUDE.md` dessa pasta
carrega o contexto, as regras e a lista do que falta. O plano completo está em
`PLANO_IMPLEMENTACAO_PLATAFORMA.md` (nesta pasta do Drive).

## O que já existe (v0.1)
Cadastro de OS/protocolos/órgãos/pilares · matriz de custo editável com histórico · projetos GCP por OS ·
lançamentos mensais independentes (estimado → realizado) · painel do contrato · auditoria imutável com
verificação · 27 OS carregadas.

## O que falta
Notas fiscais/empenhos/pagamentos (telas) · ingestão do RMEC · IMR/SLA/glosas · importador de PDFs ·
dossiê de ateste · login real (SSO) · deploy no GCP.
