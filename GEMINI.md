# Regras do Projeto - Antigravity Agent (Contrato 9291/2025)

## 1. Execução Direta e Autônoma
- **Não crie planos de implementação ou etapas de aprovação prévia** a menos que seja explicitamente solicitado pelo usuário.
- Execute diretamente as alterações de código, modificações de layout, consultas ao banco de dados, ingestões incrementais e testes necessários.
- Proativamente teste, edite e valide os arquivos sem interromper o fluxo para pedir permissões a cada passo.

## 2. Idioma
- Sempre responda estritamente em **Português do Brasil (PT-BR)**.

## 3. Metodologia SDD / Spec-Kit (Spec-Driven Development)
- Todas as especificações formais de arquitetura, banco de dados híbrido (relacional + vetorial), motor de ingestão incremental (*append-only delta*), API e regras de negócio residem no diretório [`specs/`](./specs/).
- Nenhuma alteração estrutural ou funcional deve ficar sem registro: mantenha sempre os documentos `.spec.md` e o registro de rastreabilidade ([`specs/05-sdd-changelog-reversibilidade.spec.md`](./specs/05-sdd-changelog-reversibilidade.spec.md)) atualizados como **Fonte Única de Verdade (Single Source of Truth)**.

## 4. Reversibilidade Total e Sincronização Contínua com GitHub
- **Commits Atômicos e Rastreáveis:** Toda alteração deve ser registrada em commits semânticos vinculados à respectiva especificação SDD (`feat(spec-XX): ...`, `fix(spec-XX): ...`, `docs(sdd): ...`) e marcada com tags de versão quando representar um marco estável.
- **Sempre sincronize com o GitHub:** Após finalizar modificações, implementações ou documentações solicitadas, faça o commit das alterações pertinentes e execute `git push origin main --tags` para garantir backup remoto imediato e reversibilidade total a qualquer ponto no tempo.
