# bindings/ — Nível 1 binding local (REGISTRY.JSONL)

⚠️ **ESTA PASTA LOCAL NÃO TEM DADOS NO REPO PÚBLICO.**

O arquivo único de verdade aqui é `registry.jsonl` — ele é **ESCRITO APENAS pelo helper oficial do contracts** `che_registry_append_jsonl` durante sessões de trabalho na SUA máquina.

## Por que NÃO está versionado (blacklist no `.gitignore`)?

- Cada `registry.jsonl` guarda session_ids e worktree paths HARDCODED da máquina LOCAL.
- Fazer pull de registry.jsonl de outra pessoa → binding quebrado + paths inexistentes.
- Cada sessão do che bootstrappa **em runtime** quando você roda `/che-start` ou `/che-spec`.

## Quando esta pasta ganha conteúdo?

```
1. Você: /che-start <worktree>
   → contracts helper cria entrada BOUND no registry.jsonl LOCAL
   → hook pretooluse-worktree-binding.sh lê ela e faz scissor dos paths
2. Fim da sessão: /che-ship ou /che-abort
   → entrada CLOSED no mesmo registry.jsonl
```

Escritor único = contracts. Nunca edite este arquivo na mão (REGRA 7.8 contracts).
