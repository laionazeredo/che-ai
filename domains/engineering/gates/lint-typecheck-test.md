# Gate G-ENG-1: Lint · Typecheck · Test Pass Rate (100% obrigatório)

Rodado AUTOMATICAMENTE pelo ship §0.9.5 DOMAIN GATES quando `domain=engineering` (default).

---

## Thresholds numéricos (OBRIGATÓRIO, sem números vira gate HUMAN ONLY)
| Métrica | Threshold HARD PASS | O que mede |
|---|---|---|
| Lint errors | **`0`** | Biome check --error-on-warnings=false, eslint max-warnings 0 |
| Lint warnings | `N` (permitido, mas HIGH review comment automaticamente) | Code review §0.9.2 sugere correção se warnings ≥5. Não falha o gate |
| Typecheck errors | **`0`** | tsc --noEmit / cargo check / mypy strict |
| Typecheck warnings | `N` (permitido) | HIGH se ≥10 |
| Test pass rate (unit + integration) | **`100.0%`** (0 FAIL, 0 ERROR) | Nenhum teste pode estar FAILING em CI. Flaky = retry seed 2x |
| Test total count ≥ | `1` por AC definida no SPEC | Mínimo absoluto. Não é substituto de coverage G-ENG-2. |

---

## Detecção & Retry policy
### 1st FAIL:
- Retry 1 automático GRÁTIS com mesmo seed.
- Se 2a execução PASSA = marcado "FLAKY" no log, gate = PASS e warn.
- Se 2a ainda FAIL = reporta top 3 FAILURES com stack trace.

### 2nd FAIL (após retry ou deterministic fail):
→ **HARD STOP HUMAN REQUIRED**.
Agente não corrige testes quebrados de arquitetura ou refactors grandes SEM SPEC atualizado. User escolhe: (A) corrigir manualmente (B) EXPLICIT_OVERRIDE logado (só em casos extremos, como teste obsoleto removido) (C) cancelar ship.

---

## Como executar manualmente (se quiser rodar antes de ship)
Cada projeto define `lint`, `typecheck`, `test` via Nx targets / package scripts.
```bash
# Exemplo monorepo pnpm + nx:
corepack pnpm nx run-many --all --target=lint --tui false
corepack pnpm nx run-many --all --target=typecheck --tui false
corepack pnpm nx run-many --all --target=test --tui false
```

---

## Artifacts gerados (obrigatório anexar a PR description se ship)
```
reports/domain-gates/
└── G-ENG-1--lint-typecheck-test_<timestamp>.json
    {
      "gate_id": "G-ENG-1",
      "timestamp": "...",
      "lint_errors": 0, "lint_warnings": 4,
      "typecheck_errors": 0, "typecheck_warnings": 0,
      "test_total": 137, "test_pass_rate": 100.0, "test_failures": [],
      "retry_applied": false,
      "result": "PASS | FAIL"
    }
```

---

## Casos especiais
| Cenário | Ação |
|---|---|
| Monorepo multi-pacote | Roda G1 separadamente por pacote. Falha 1 = falha geral. Relatório agregado. |
| Worktree-only mudou markdown/docs | Skip typecheck/lint/TEST automático (mas não se mudou .ts/.rs/.py) — detecta via diff. |
| Projeto sem testes definido no SPEC? | 1st gate FAIL. Exigir EXPLICIT_OVERRIDE user SEMPRE. NÃO pode passar gate sem override. |
