---
description: "Helper skill ui-testing-contracts: entrega snippets RTL Priority Order (Kent Dodds) + Playwright byTestId boilerplate Flockr + regex lint data-testid convention 3-partes (G8.3) + cross-reference Category8 UI Hygiene (code-review gate ONDA1 + SbE Selector Contract ONDA2)."
arguments:
  - name: scope
    description: "Contexto: 'RTL' para Testing Library order, 'Playwright' para boilerplate Flockr, 'Convention' para regex lint G8.3, 'Cat8' para Category8 enforcement, 'Full' para todas as seções (default)."
    required: false
---

IMMEDIATELY invoke **`ui-testing-contracts`** Skill.

Output esperado por seção:
1. §1 — RTL Priority Order + ByTestId guard clause snippet (se scope=RTL ou Full)
2. §2 — Playwright byTestId wrapper snippet verbatim Flockr convention 3-partes (se scope=Playwright ou Full)
3. §3 — Regex canônico + grep one-liner lint para contagem violações G8.3 (se scope=Convention ou Full)
4. §4 — Tabela Category8 G8.1 HIGH / G8.2 HIGH / G8.3 MEDIUM / G8.4 LOW + integração SbE UI Selector Contract (se scope=Cat8 ou Full)
