# PR-18 — Workflow Fail-closed de Evidência RC

Data: 2026-07-31  
Estado: `implemented_local`, não executado no GitHub  
Gate afectado: G4 — permanece vermelho

## Lacuna encontrada

O CI validava o código e os testes unitários do
`dependency_security_gate.py`, mas nunca executava o gate real. Assim, era
possível ter um validador correcto no repositório sem produzir evidência
Node/audit/tree/SBOM para o SHA candidato.

## Correcção

Foi criado `.github/workflows/pr18-release-evidence.yml`, exclusivamente manual,
com o seguinte contrato:

1. recebe um `release_sha` integral;
2. faz checkout desse SHA;
3. rejeita divergência entre o input e `GITHUB_SHA`;
4. fixa Node `20.20.2`;
5. instala exactamente o `package-lock.json` por `npm ci --ignore-scripts`;
6. executa o gate em perfil `release_candidate`;
7. liga relatório e SBOM ao SHA;
8. publica os artefactos mesmo quando a decisão é NO-GO;
9. mantém a execução vermelha quando o gate falha.
10. aceita opcionalmente um manifesto de waiver versionado apenas sob
    `infra/release/waivers/`, validado pelo gate contra o mesmo SHA.

Não existe `continue-on-error` no gate.

O input opcional não aprova risco. Sem manifesto, todos os findings
high/critical permanecem bloqueantes. Com manifesto, apenas findings high
exactamente cobertos, não expirados e aprovados por SEC/TL podem deixar de ser
`unwaived`; critical permanece sempre bloqueante.

## Fronteira de attestation

O workflow não usa `attest-sbom` nem declara `sbom_attested=true`. O SBOM
gerado é evidência de dependências do checkout, não attestation das quatro
imagens imutáveis. Assinatura, provenance, scanner e verificação de subject
digest continuam no PR-19/registry.

## Validação local

```text
Pytest PR-18 + workflow + G4: 11 passed
Ruff: green
YAML parse: green
git diff --check: green
```

## Execução remota pendente

```powershell
gh workflow run pr18-release-evidence.yml `
  --ref <release-sha> `
  -f release_sha=<release-sha>
```

Se existir uma decisão humana formal já versionada no RC:

```powershell
gh workflow run pr18-release-evidence.yml `
  --ref <release-sha> `
  -f release_sha=<release-sha> `
  -f waiver_manifest_path=infra/release/waivers/<manifesto>.json
```

O artefacto remoto esperado chama-se
`pr18-dependency-evidence-<github.run_id>`. A sua existência não torna PR-18
verde: o relatório precisa passar e a evidência de imagem/registry precisa ser
atestada e verificada antes dos sign-offs SEC/TL.
