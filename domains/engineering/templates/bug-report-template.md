# Template · Engineering Bug Report (científico, reprodutível)

O padrão do Scientific Debugging (che-fix skill). **Sempre preencha ANTES de começar a corrigir.**

---

## 1. 🔴 Metadata
| Campo | Valor |
|---|---|
| ID | `bug-YYYYMMDD-NNN` |
| Reportado por | |
| Data report | DD/MM/YYYY |
| Ambiente | Local · Dev · Staging · Prod |
| Severidade | 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low |
| Domínio | engineering |
| Ticket / issue URL | |

---

## 2. Expected Behavior (comportamento ESPERADO)
Descrever 1 frase o que deveria acontecer + 1 AC literal do SPEC/PRODUTO se existir:

## 3. Actual Behavior (o que REALMENTE está acontecendo)
Anexar screenshot, error message, stack trace, logs:
```
<cole o erro real aqui com --stacktrace completo>
```

## 4. Reproduction Steps (MÍNIMO 5 steps, reproduzível 3x consecutivas)
Step-by-step exato. NÃO pule etapas. Deve funcionar em qualquer máquina:
1. Logar como usuário `admin@acme.com` senha `...` (máscara se necessário)
2. Navegar para `/events/123/manage/refunds`
3. Clicar botão "Refund" no pedido #832
4. Preencher valor 10.00 GBP, reason "duplicate"
5. Clicar Confirm → ERRO: ...

## 5. Hypotheses Iniciais (Top 3)
Scientific Debug: 3 hipóteses plausíveis, ranking de probabilidade:
| # | Hipótese | Probabilidade | Como instrumentar | Status |
|---|---|---|---|---|
| H1 | `isPlatformAdmin` retorna false por worktree binding errado | HIGH | log args da função + authz context | |
| H2 | ... | MEDIUM | | |
| H3 | ... | LOW | | |

## 6. Evidence Collection (cada hipótese → instrumentação → output)
```
H1 Instrumentation: console.log(user_id, role, worktree binding)
Output:
{ user_id: 1, role: 'admin', binding_wt: 'feat-FLO-513', actual_wt: 'main' }
→ Conclusão H1 CONFIRMADA: binding_wt mismatch
```

## 7. Root Cause (FINAL, 1 frase)
Quando todas hipóteses resolvidas, escrever Causa Raiz aqui.

## 8. Fix Descrição Técnica
| Arquivo | Mudança | Linha aproximada | Porquê resolve? |
|---|---|---|---|
| `packages/platform/server/services/RefundService.ts` | Troca worktree binding resolver helper | 795 | Usa helper oficial canônico contracts em vez de hardcoded path |

## 9. Tests adicionais para prevenir regressão
| Tipo | Nome do caso | O que valida |
|---|---|---|
| Unit | `refund.binding.worktree.mismatch → throws authz error` | Manda worktree errada e não deixa passar |

## 10. Verificação manual após fix aplicada
Steps de reprodução do passo 4 rodados de novo, RESULTADO: expected behavior.

---

## 11. Assinatura
| Nome | Cargo | Data | Status |
|---|---|---|---|
| | Reporter | | Bug Report criado |
| | SWE que corrigiu | | Bug fixed + testes passam |
| | QA que validou | | Verificado em staging |
