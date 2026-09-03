# Gate G-ENG-2: Coverage (Lines · Branches · New Code)

Rodado AUTOMATICALLY pelo ship §0.9.5 DOMAIN GATES quando domain=engineering.

---

## Thresholds numéricos (Defaults)
| Métrica | Threshold | O que exclui do cálculo |
|---|---|---|
| **Lines coverage GERAL** (todo o pacote) | `≥ 70.0%` | `*.{test,spec}.{ts,rs,py}`, `**/migrations/**`, `**/*.config.*`, `**/vendor/**` |
| **New code coverage** (apenas linhas alteradas no diff atual vs base branch main) | `≥ 80.0%` | Idem |
| **Branch coverage GERAL** | `≥ 65.0%` | Idem |
| **Critical paths** definidos no SPEC como obrigatório cobrir | `100%` (ou EXPLICIT_OVERRIDE) | Payment flow, auth gate, RLS, refund. |

> 💡 **Override regra**: thresholds NUMÉRICOS NUNCA são alterados pelo agente sem EXPLICIT_OVERRIDE do user logado em decisions.log. Valores acima são defaults razoáveis.

---

## Exemplos ferramentas por stack
| Stack | Comando canônico coverage | Output format |
|---|---|---|
| Vitest (TS/JS) | `vitest run --coverage` | `coverage/cobertura.xml` + `json-summary` |
| Jest | `jest --coverage` | `coverage/lcov.info` |
| Pytest (Python) | `pytest --cov=src --cov-report=xml:coverage/cobertura.xml --cov-report=term-missing` | cobertura.xml |
| Cargo tarpaulin (Rust) | `cargo tarpaulin --out Xml` | cobertura.xml |

---

## Retry + 2nd falha
### 1st FAIL:
- 1 retry automático re-roda coverage report (seed mesmo). Se mudou diff no workspace, roda diff coverage só nas linhas novas.
- Reporta top 5 arquivos com coverage mais baixo + 10 linhas uncovered mais críticas.

### 2nd FAIL → HARD STOP (3 opções user):
(A) Corrigir adicionando testes nas linhas faltantes. **Recomendado.**
(B) **EXPLICIT_OVERRIDE** user literal logado em decisions.log com formato exato:
```
[EXPLICIT_OVERRIDE] GATE=G-ENG-2
  original_thresholds={lines=70, new_code=80, branches=65}
  new_thresholds={lines=60, new_code=70, branches=55}
  reason="<user verbatim literal 3 frases mínimo explicando PORQUÊ abaixou>"
  approver="<user_login>"
```
(C) Cancelar ship.

---

## Artifacts
```
reports/domain-gates/
└── G-ENG-2--coverage_<timestamp>.json
    {
      "gate_id": "G-ENG-2",
      "lines_total_pct": 76.4, "lines_pass": true,
      "new_code_pct": 83.2, "new_code_pass": true,
      "branches_pct":   67.0, "branches_pass": true,
      "uncovered_top5": [ {"file":"src/db.ts","lines_missing":14} ],
      "diff_size_added_lines": 187, "diff_covered_lines": 154,
      "retry_applied": false, "override_applied": null,
      "result": "PASS | FAIL"
    }
```

---

## Casos especiais
| Cenário | Ação |
|---|---|
| Refactor gigante sem novas features | Pode cair overall coverage um pouco. Requer EXPLICIT_OVERRIDE. |
| Só docs / markdown mudou | Skip GATE, report `SKIPPED` com justificativa no JSON. |
| 1 arquivo inteiro "não testável" (ex: binding gerado automaticamente) | Adicionar nos paths excluídos de coverage pelo config da ferramenta. Logar decision. |
