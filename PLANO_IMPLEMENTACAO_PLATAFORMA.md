# Plataforma de Controle do Contrato 9291/2025 (SEIA × CELEPAR) — Plano de Implementação

Status: **PLANO. Nada foi implementado.** Versão 0.1 — 27/10/2026.
Autor: Claude (visão de engenharia sênior + cibersegurança + gestão do contrato).

---

## 1. Princípios (o que guia todas as decisões)

1. **O banco é a fonte da verdade.** Tudo (contrato, OS, protocolos, custos, RMEC, notas, empenhos, documentos) vive em PostgreSQL estruturado. Planilha e PDF são *entrada* e *saída*, nunca o sistema.
2. **Nada se sobrescreve.** Todo valor editável é versionado (quem, quando, por quê, valor anterior). Dá flexibilidade total de edição *e* trilha de auditoria completa. É o que protege o gestor num eventual questionamento do TCE/CGE.
3. **Estimado ≠ Documental ≠ Realizado.** Três camadas de valor por OS: o que o PDF da OS diz (imutável, referência), o que você decide vigente (editável) e o que a CELEPAR realmente consumiu/faturou (vem do RMEC).
4. **Chave de identidade da OS = número da pasta** (`OS_01…OS_27`), não o cabeçalho do PDF.
5. **Cadastro aberto.** Nova OS, novo protocolo, novo pilar, novo tipo de linha de custo: tudo por tela, sem mexer em código.
6. **Segurança por padrão, não por remendo.** Zero confiança, menor privilégio, segredos fora do código, auditoria imutável, dados pessoais minimizados.
7. **Simples de operar.** Monólito modular, um banco, poucos serviços gerenciados. Complexidade só onde ela compra segurança ou valor.

---

## 2. Escopo funcional — a "torre de controle" do gestor

### 2.1 Visão do Contrato (nível 1)
- Valor global (R$ 133.155.352,08), quantidades contratadas (68.089.068 USN; 42.984 UST), **saldo** em USN, UST e R$.
- Executado × cronograma físico-financeiro do TR (Ano 1: 20% · Ano 2: 35% · Ano 3: 45%).
- Burn rate mensal, projeção de esgotamento e de vigência (36 meses desde a publicação no DOE de 18/11/2025).
- Comprometido (soma dos tetos vigentes das OS) × executado (RMEC) × faturado (NF) × pago (OB).
- Cobertura de empenho: empenhos emitidos (2025NE000365, 2026NE000055, 2026NE000298…) × execução projetada → alerta de reforço antes de faltar.
- Quebras por **pilar**, por **órgão demandante**, por **tipo (USN/UST)**, por mês.

### 2.2 Visão do Projeto / OS (nível 2)
- Ficha: órgão, pilar (um por projeto), protocolo(s), Plano de Trabalho, SOW, pontos focais, projetos GCP vinculados, datas, documentos.
- **Matriz de custo editável** (linhas: recurso, métrica USN/UST, cobrança mensal/única, quantidade, preço unitário, fator de complexidade, total). Mostra lado a lado: *documental · vigente · realizado*.
- Histórico mensal de consumo (RMEC) e desvio vs. estimativa (a estimativa é só referência; paga-se o consumo real).
- Linha do tempo: protocolo → aprovação COIA → OS → provisionamento → execução → encerramento.
- Relação mãe/filha: OS_06 (Data Foundation) como projeto-mãe; projetos entram e saem com **vigência temporal** (hoje nenhum vinculado).

### 2.3 Fechamento mensal (RMEC → NF → pagamento)
- Importar/registrar o RMEC do mês (consumo USN por projeto GCP; UST do relatório da CELEPAR).
- Conciliação automática: soma por OS = total da NF? Divergências destacadas linha a linha.
- Composição da NF única a partir das OS; dossiê de ateste em PDF/XLSX (OS, evidências, glosas, totais).
- Rastro financeiro: NF → atesto → liquidação (NL) → ordem bancária (OB) → empenho (NE).

### 2.4 Prazos e alertas (o que um bom gestor não pode perder)
Motor de prazos configurável, com contagem em dias úteis:
- **Aprovação do Relatório Mensal: 3 dias úteis; silêncio = aprovado tacitamente** (contrato 6.8.4–6.8.5).
- Contestação de glosa: 2 dias úteis; reemissão: 2 dias úteis.
- Recebimento provisório (2 d.u.) e definitivo (10 d.u., tácito) (6.6–6.7).
- Pagamento em até 30 dias do atesto; encargos moratórios 6% a.a. se atrasar por culpa da Administração.
- **Reajuste IPCA** (data-base do orçamento: 11/10/2025): depende de requerimento da CELEPAR até 30 dias antes do fim de cada período de 12 meses; sem pedido, não retroage. Monitorar e registrar.
- Fim de vigência, catálogo revisável a cada 6 meses, PGEC trimestral, reavaliação trimestral das estimativas.
- Estouro de teto/saldo, OS sem consumo, projeto GCP sem OS, OS sem RMEC no mês.

### 2.5 Qualidade e sanção (módulo "será implantado")
IMR (7 indicadores e pesos do TR), SLAs, glosas (tabela do TR 15.3), notificação com prazo mínimo de 5 d.u., multas. Nasce **desligado por padrão** e habilitável por OS; o modelo de dados já existe desde a fase 1 para não exigir migração dolorosa depois.

### 2.6 Governança e acervo
- Repositório de documentos (OS, protocolos, PTs, SOWs, NFs, atestos) com hash, versão e busca em texto completo.
- Catálogo USN/UST versionado (baseline v1.0; revisões semestrais com vigência: *OS em curso seguem o item vigente à época*).
- Registro de decisões do COIA (aprovação de cada projeto/OS).
- Relatórios: gerencial mensal, prestação de contas, pacote de auditoria (TCE/CGE) com um clique.

### 2.7 Capacitação (eixo transversal)
Tratamento **indefinido** no contrato. A plataforma terá a dimensão "eixo" no cadastro (pilar + marcação transversal) para não travar quando for definido.

---

## 3. Modelo de dados (PostgreSQL) — desenho lógico

Convenção: toda tabela tem `id (uuid)`, `created_at/by`, `updated_at/by`; entidades editáveis têm tabela de **versões** (`*_version`) com `valid_from`, `valid_to`, `changed_by`, `reason`, `source` (manual | import | rmec).

**Contratual**
- `contrato` (nº 9291/2025, partes, valor, qtd USN/UST, vigência, dispensa 23/2025, DOE).
- `contrato_evento` (aditivo, apostilamento, reajuste, designação gestor/fiscal — Res. 129/2025).
- `catalogo_versao`, `catalogo_item` (códigos: `GES_PROJ_001–005`, `GCP_DEV_001–003`, classes USN, fatores de complexidade).
- `preco_vigente` (USN/UST por período — suporta reajuste IPCA sem perder histórico).

**Política e organização**
- `pilar` (1 Fundação de dados · 2 Agentes de IA · 3 Missão crítica), `eixo` (capacitação), `orgao` (direta/indireta), `pessoa` + `papel_projeto` (pontos focais — dados pessoais, ver §7).

**Demanda e execução**
- `protocolo` (nº e-Protocolo, órgão, assunto, datas), `protocolo_documento`.
- `projeto` (pilar obrigatório, órgão, status, `projeto_mae_id` opcional).
- `projeto_vinculo_mae` (projeto ↔ OS-mãe com `valid_from/valid_to` — Data Foundation).
- `plano_trabalho` (versões 1.1, 2.0…), `decisao_coia`.
- `os` (**chave = pasta `OS_XX`**; nº do documento e do cabeçalho guardados como atributos informativos), `os_tipo` (valorada · provisionamento GCP · mãe), `os_versao`.
- `os_linha_custo` (+ versões): descritor, métrica (USN/UST/outra), cobrança (mensal/única), quantidade, preço, fator, observação, `valor_documental` (imutável) e `valor_vigente`.
- `gcp_projeto` (id do projeto GCP, ambiente DEV/HML/PRD, OS responsável com vigência — **é a chave de atribuição do consumo USN**).

**Realizado e financeiro**
- `periodo` (competência mensal), `rmec` (cabeçalho: fonte, hash do arquivo, status), `rmec_linha` (OS, projeto GCP, métrica, quantidade, valor).
- `nota_fiscal` + `nota_fiscal_item` (rateio por OS), `atesto`, `empenho`, `liquidacao`, `ordem_bancaria`, `pagamento`.
- `glosa`, `imr_avaliacao` + `imr_indicador`, `sla_medicao`, `sancao`.

**Plataforma**
- `documento` (GCS URI, SHA-256, tipo, versão, texto extraído), `prazo`/`alerta`, `usuario`, `papel`, `permissao`, `auditoria` (append-only, ver §7), `importacao` (lote, origem, revisão humana).

Integridade: FKs sempre, `CHECK` em quantidades/preços ≥ 0, `NUMERIC(18,4)` para dinheiro e USN (nunca float), unicidade `(os, competência, projeto GCP, métrica)` no RMEC, exclusão lógica apenas.

---

## 4. Arquitetura

```
Usuário (@…pr.gov.br, MFA)
   │ HTTPS
Cloud Load Balancer + Cloud Armor (WAF, rate limit)
   │
Identity-Aware Proxy (SSO Google Workspace)
   │
Cloud Run: web (React estático) + api (FastAPI)  ── Cloud Run Jobs: importadores / fechamento / alertas
   │ (VPC conector, IP privado)                     ▲ Cloud Scheduler
Cloud SQL PostgreSQL (CMEK, PITR, réplica p/ DR)    │
Cloud Storage (documentos, CMEK, versionamento, retenção)
Secret Manager · Cloud KMS · Cloud Logging/Audit Logs · BigQuery (somente leitura de billing, se aplicável)
```

**Stack recomendada**
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic. Python por causa de PDF/planilha/BigQuery/ETL (já validei extração de texto dos PDFs do acervo).
- **Frontend:** React + TypeScript (Vite), TanStack Query/Table, grade editável tipo planilha para a matriz de custo, gráficos ECharts.
- **Banco:** PostgreSQL 16 (Cloud SQL). Extensões: `pgcrypto`, `pg_trgm`; `pgaudit` via flags do Cloud SQL.
- **Arquivos:** Cloud Storage com URLs assinadas de vida curta.
- **IaC:** Terraform (infra reproduzível; nada criado "no clique").
- **CI/CD:** repositório privado, pipeline com testes + varreduras; deploy por identidade federada (sem chave JSON).
- **Estilo:** monólito modular (módulos: contrato, demanda, custos, fechamento, prazos, documentos, auditoria). Sem microsserviços.

**Desenvolvimento local → GCP com paridade**
- Docker Compose local: Postgres 16 (mesma versão), emulador de GCS, mesmo conjunto de migrations.
- Auth local por flag de ambiente **impossível de ativar em produção** (teste automatizado barra).
- **Repositório de código fora do Google Drive** (ex.: `~/dev/plataforma-controle-9291`). O Drive sincronizando `.git`/dependências corrompe e vaza; no Drive ficam só documentos (como este plano).
- **Dados reais nunca entram no Git.** Fixtures sintéticas para testes; importação real só por script local → banco local/GCP.

---

## 5. Importação inicial (as 27 OS e o acervo)

1. Extrair texto dos PDFs (já feito para a análise; reaproveitar o extrator).
2. Parser por padrão de OS (há 3 gerações de modelo: valoradas 01–05; "ambiente GCP" 08–11; "desmembramento de faturamento" 12–17, 19, 21, 23; mais as formais 18, 22, 24–27).
3. **Tela de revisão humana:** nenhum dado do PDF entra sem você confirmar (valores, datas, órgão, pilar).
4. Carga da planilha `AcompanhamentoContrato-OS.gsheet` (precisa ser exportada ou lida via API autorizada — o arquivo local é só atalho do Drive).
5. Carga dos documentos financeiros do protocolo-mãe (NE, NF, NL, OB, despachos) como eventos financeiros.
6. Relatório de qualidade da carga: o que bateu, o que divergiu (ex.: valor do contrato R$ 133.155.352,08 × dotação R$ 133.151.893,80; erro de digitação 2.064→208 na OS_04).

---

## 6. Ingestão do RMEC / dashboard (aguardando o link)

- Hipótese de trabalho: consumo USN atribuído **por projeto GCP** (confirmado por você). Se o dashboard for alimentado por *billing export* no BigQuery, a plataforma lê com conta de serviço **somente leitura** e escopo mínimo.
- UST: relatório da CELEPAR (PDF/planilha) → importador com revisão.
- Toda ingestão: idempotente, com hash do arquivo, lote rastreável, reprocessamento seguro, e "diferença vs. mês anterior" antes de confirmar.
- Regras de órfão: projeto GCP sem OS → fila de pendências (não some, não é atribuído automaticamente).

---

## 7. Segurança (modelo de ameaças e controles)

**Ativos críticos:** valores e execução do contrato, dados de órgãos de segurança pública (SESP/PM/PC/PCiência), documentos de protocolos, dados pessoais de servidores (nome, e-mail institucional; CPF só mascarado).

**Ameaças principais:** acesso indevido por conta comprometida; alteração silenciosa de valores; vazamento de documentos; fraude/conluio (nota inflada); injeção/IDOR; cadeia de suprimentos (dependências); erro humano em edição em massa; **conflito de interesse de infraestrutura** (ver §10).

**Controles**
- *Identidade:* SSO Google Workspace com MFA obrigatório (IAP), sessões curtas, sem senha local. Convites só para domínios institucionais permitidos.
- *Autorização:* RBAC no app + **Row-Level Security no Postgres** (defesa em profundidade). Papéis: `gestor`, `fiscal`, `analista`, `consulta-órgão` (só seus projetos), `auditor` (leitura total, sem escrita), `admin-técnico` (sem acesso a dados de negócio). Segregação de funções: quem edita valor ≠ quem aprova fechamento.
- *Auditoria:* tabela `auditoria` **append-only** (sem UPDATE/DELETE para o usuário da aplicação), com **encadeamento por hash** para detectar adulteração; espelho em Cloud Logging com retenção protegida. Registra leitura de documentos sensíveis e exportações.
- *Edição segura:* toda alteração exige motivo; edição em massa com prévia (diff) e desfazer; limites/validações de domínio; aprovação em duas etapas opcional para mudanças acima de limiar.
- *Dados:* TLS em trânsito; CMEK em repouso (Cloud SQL e GCS); Cloud SQL com **IP privado**, sem IP público; backups + PITR; teste de restauração periódico; região `southamerica-east1`.
- *Segredos:* Secret Manager; zero segredo em código/imagem/variável de CI; contas de serviço com menor privilégio e sem chaves exportadas (Workload Identity).
- *Aplicação:* OWASP ASVS nível 2 (nível 3 nos módulos financeiro e auditoria); validação de entrada por esquema; consultas parametrizadas; CSP estrita, HSTS, cookies `HttpOnly/Secure/SameSite`; CSRF; rate limiting; sem dados sensíveis em logs.
- *Upload de arquivos:* lista de tipos permitidos, limite de tamanho, varredura antivírus, armazenamento isolado, nunca servido inline do mesmo domínio.
- *Cadeia de suprimentos:* dependências fixadas por hash, SCA e SAST no CI, varredura de imagem, SBOM, imagens mínimas (distroless), Binary Authorization para deploy.
- *Rede:* Cloud Armor, ingress restrito, egress controlado; VPC Service Controls avaliado para o perímetro de dados.
- *Operação:* alertas de segurança (login anômalo, exportação em massa, mudança de papel), plano de resposta a incidentes, pentest antes do go-live e anual.
- *LGPD:* mapeamento de dados pessoais, base legal (execução de política pública/contrato), minimização (sem CPF completo), política de retenção, trilha de acesso, RIPD curto.

---

## 8. Qualidade e testes

- Pirâmide: testes unitários (regras de cálculo, prazos em dias úteis), integração (banco real em container), contrato de API, E2E nos 5 fluxos críticos (cadastrar OS, editar matriz, fechar mês, conciliar NF, exportar dossiê).
- **Testes de reconciliação financeira** com dados conhecidos (ex.: 1.891.363 × 36 = 68.089.068; 1.194 × 36 = 42.984) como oráculo.
- Teste automatizado de autorização (matriz papel × endpoint) e de RLS.
- Migrations reversíveis e testadas contra cópia do banco.

---

## 9. Fases, entregáveis e critério de saída

| Fase | Entrega | Critério de saída |
|---|---|---|
| 0. Fechar descoberta | Link do dashboard, formato do RMEC, amostra de NF/relatório CELEPAR, planilha de acompanhamento, decisões da §11 | Dicionário de dados validado por você |
| 1. Fundação | Repo, CI, Terraform base, ambiente local, esquema do banco, SSO, RBAC, auditoria | Login funcionando; auditoria imutável testada |
| 2. Cadastro mestre | Contrato, catálogo, pilares, órgãos, protocolos, OS, projetos, vínculo mãe/filha, versionamento | Criar OS nova ponta a ponta por tela |
| 3. Matriz de custo | Grade editável, 3 camadas (documental/vigente/realizado), histórico, cenários "e se" | Editar valor com motivo e ver trilha |
| 4. Carga inicial | Importadores + tela de revisão das 27 OS e do financeiro | 27 OS conferidas por você, relatório de qualidade |
| 5. Visões | Painel do contrato, por pilar, por órgão, por projeto/OS | Números batem com o protocolo-mãe |
| 6. Fechamento mensal | Ingestão RMEC, conciliação, composição da NF, dossiê de ateste, motor de prazos | Fechar um mês real em paralelo ao processo atual |
| 7. Qualidade/sanção | IMR, SLA, glosas, notificações (habilitável) | Simulação em um mês histórico |
| 8. Endurecimento e deploy | Pentest, DR testado, observabilidade, runbooks, deploy GCP | Go-live com checklist de segurança assinado |
| 9. Operação | Treinamento (eixo capacitação), suporte, revisão trimestral | Primeiro trimestre operado sem planilha paralela |

Ordem proposital: segurança e auditoria **antes** de qualquer dado real entrar (fase 1), e valor visível cedo (visões na fase 5, antes do fechamento mensal).

---

## 10. Riscos e decisões de governança que merecem atenção

1. **Conflito de interesse de infraestrutura.** A CELEPAR é a contratada *e* administra o ambiente GCP do contrato. Hospedar a plataforma que fiscaliza a CELEPAR dentro da conta que ela administra enfraquece a independência da auditoria. Recomendação: projeto/organização GCP **sob administração da SEIA**, com billing separado do contrato, ou no mínimo logs de auditoria exportados para um destino que a CELEPAR não controla. Se rodar dentro do contrato, o custo vira USN e precisa de OS própria.
2. **Fonte do consumo é terceira.** Os dados de USN vêm de quem é fiscalizado. Mitigar com leitura direta do billing export quando possível e conciliação cruzada com a NF.
3. **Silêncio vale aprovação** (3 d.u. no RMEC): o risco operacional mais barato de evitar e mais caro de errar. O motor de prazos é prioridade, não enfeite.
4. **Dados de segurança pública** exigem classificação e acesso por órgão; nada de "todo mundo vê tudo".
5. **Dependência de você como gestor único.** Prever delegação formal, papéis suplentes e trilha para continuidade.
6. **Escopo que cresce.** O módulo IMR/glosa e a capacitação ficam atrás de chaves de funcionalidade até serem definidos.

---

## 11. Decisões que preciso de você antes da Fase 1

1. **Onde hospedar** (organização GCP da SEIA × dentro do contrato)? Há aprovação de TI/segurança do Estado para isso?
   - **DECISÃO (27/10/2026): desenvolver e operar 100% local primeiro; a hospedagem no GCP fica para depois.** As fases 1–7 rodam em ambiente local (Docker Compose). A escolha da conta GCP (organização da SEIA recomendada, ver §10.1) fica adiada para a fase 8, mas o código nasce portável: 12-factor, configuração por variáveis de ambiente, containers, migrations versionadas e Terraform escrito só na fase 8. Enquanto estiver local, os dados reais ficam em banco local criptografado (disco com FileVault) e fora do Git e do Drive.
2. **Quem acessa** além de você e do fiscal: equipe da DIA, Núcleo Fazendário, Setor de Contratos, órgãos demandantes, CELEPAR (leitura limitada?), CGE/TCE?
3. **Link do dashboard** e exemplo de RMEC, NF e relatório de UST da CELEPAR.
4. **A planilha de acompanhamento** continua como fonte durante a transição ou é substituída na carga inicial?
5. **Aprovação em duas etapas** para alterar valores: desejada? Acima de qual valor?
6. **A própria plataforma** será paga como OS (UST/USN) ou construída pela SEIA? Define quem pode ter acesso ao código e ao ambiente.
7. **Marcas/identidade visual** do Estado a seguir no sistema?
