# Runbook de Decisão GO/NO-GO — G4

Este runbook converte as evidências PR-18 a PR-25 numa única decisão
fail-closed. Um build verde ou uma evidência local nunca torna G4 verde.

## Preparação

Para PR-18, executar primeiro o workflow manual
`.github/workflows/pr18-release-evidence.yml` no SHA exacto do RC. O workflow
deve terminar verde e o relatório/SBOM publicado deve ser reconciliado com as
attestations das imagens verificadas em PR-19. Um artefacto local ou um workflow
vermelho não permite marcar os controlos PR-18 como verdadeiros.

O controlo PR-18 chama-se `no_unwaived_high_critical`. O caminho normal é zero
high/critical. Quando uma correcção suportada ainda não existe, apenas findings
`high` podem ser cobertos pelo manifesto formal em
`infra/release/waivers/`; cada finding precisa de range e advisories exactos,
owner, ticket HTTPS, dois controlos compensatórios, expiração máxima de 30 dias
e aprovações distintas SEC/TL ligadas ao SHA. Findings `critical` nunca são
waivable. O template possui `approved=false` e não constitui aprovação.

1. Copiar `infra/release/G4_RELEASE_MANIFEST.example.json` para o directório
   privado de evidência do RC.
2. Definir o SHA integral do RC.
3. Manter exactamente os oito workstreams PR-18 a PR-25.
4. Marcar um controlo `true` apenas depois de a evidência real existir.
5. Calcular SHA-256 de cada artefacto e registar caminho e hash.
6. Calcular o digest do workstream concatenando, por ordem lexical, os hashes
   dos artefactos e aplicando SHA-256 ao resultado.
7. Recolher os sign-offs nominais exigidos, ligados ao SHA do RC e ao digest do
   workstream.

Os artefactos podem ficar fora do repositório. Caminhos relativos são
resolvidos a partir do directório do manifesto.

## Sign-offs obrigatórios

| Workstream | Papéis |
| --- | --- |
| PR-18 | SEC, TL |
| PR-19 | SRE, TL |
| PR-20 | SRE, BE |
| PR-21 | SRE, QA |
| PR-22 | QA, SRE |
| PR-23 | SEC, TL |
| PR-24 | FE-M, FE-D, PO |
| PR-25 | SRE, PO |

Um aprovador não pode assinar duas vezes o mesmo workstream.
Cada sign-off contém `release_sha`, `evidence_digest`, `signed_at`, `approver`,
`role` e `approved=true`.

## Execução

```powershell
.\.venv\Scripts\python.exe -m scripts.release_gate `
  --manifest <directorio-evidencia>\G4_RELEASE_MANIFEST.json `
  --output <directorio-evidencia>\G4_RELEASE_DECISION.json
```

Exit code `0` significa `GO`. Qualquer campo ausente, controlo falso, hash
inválido, artefacto alterado ou sign-off incompleto devolve exit code `1` e
`NO-GO`, com a lista de bloqueios.

## Regras

- O manifesto pede `GO`; o script decide.
- Evidência local não substitui artefactos do mesmo SHA do RC.
- Alterar um artefacto depois do sign-off invalida o seu hash.
- Não existem excepções implícitas para high/critical, performance, DR,
  isolamento tenant, acessibilidade ou resposta a incidentes.
- Waiver PR-18 formal não torna `sbom_attested` verdadeiro e não substitui a
  evidência de imagem do PR-19.
- PR-26 permanece bloqueado enquanto a decisão não for `GO`.
