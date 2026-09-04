---
description: "Gerencia projects Che (L2 .registry/projects/<slug>/). 4 subcommands: init WTPATH | list | remove SLUG [--dry-run|--no-dry-run --confirm] | restore TRASH_SLUG. Inicializa scaffold determinístico: architecture.md + project_profile.md + product_context.md + roadmap.md + roles/ + registry.jsonl + _db/ e garante L3 .wt/__<branch>/."
arguments:
  - name: worktree
    description: "Absolute worktree path (obrigatório para `init`). Para list/remove/restore usa bindings atuais se omitido."
    required: false
  - name: subcommand
    description: "Required positional: init <WORKTREE_ROOT> [--workspace WS] [--domain engineering] [--name FRIENDLY] [--session-id SID] | list | remove <PROJECT_SLUG> [--no-dry-run --confirm] | restore <TRASH_SLUG>. Domínios Politburo válidos: engineering | ux | product | devops | copywriting | social | seo-analytics. Default=engineering."
    required: true
---

Gerencia a **camada L2 (Project Durable Registry)** da hierarquia 4-nível do Che. Projects vivem em:
- **Che registry path**: `~/.che-workspaces/<workspace-slug>/.registry/projects/<project-slug>/` — durável, cross-worktree, contém os 8 artefatos canônicos.
- **No worktree**: pasta `.wt/__<branch-slug>/` (L3 compartilhado por branch) criada/garantida no `init`.

**Scaffold `init` cria 8 artefatos determinísticos** em `.registry/projects/<slug>/`:
1. `architecture.md` (C4 L1/L2 + ADR index + Data Model + QA)
2. `project_profile.md` (stack auto-detectada via file probe: pnpm/uv/go/Cargo/etc + git origin + workspace + deployment roles)
3. `product_context.md` (pitche, personas placeholder, roadmap skeleton)
4. `roadmap.md` (milestones placeholder, epic templates)
5. `roles/index.md` (PO/TechLead/UX/DevOps/QA ownership table + CODEOWNERS placeholder)
6. `registry.jsonl` (Level 2 registry, append-only. Primeira entry = `PROJECT_INIT`.)
7. `_db/README.txt` (local para SQLites state+rag; instruções de rebuild/backup/purge)
8. **No worktree alvo**: garante existência de `.wt/__<branch>/sessions/` (L3) + `.che-export-manifest.json`.

**Safety gates DESTRUTIVOS (remove = mesma regra workspace):**
1. `--dry-run` DEFAULT.
2. Efetivar = `--no-dry-run` + `--confirm` (dupla flag).
3. Destino = `~/.che-workspaces/.trash/project--<slug>--<ts>/` + `_MANIFEST.json`.

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `init <WT> [--workspace WS] [--domain D] [--name N] [--session-id S]` | `python3 -m che_core.cli project init "<WT>" [flags] --json` | **Entrada recomendada para onboarding:** roda `che project init` ANTES de che-xray/che-onboarding. Agent: (1) resolve workspace default via `resolve_workspace_name(WT)` se `--workspace` omitido; (2) mostra domínio default=engineering e pergunta se quer trocar (só lista 7 Politburo válidos); (3) detecta stack via probe de arquivos + git remote origin; (4) scaffold 8 files + ensure L3 dirs; (5) report `{project_slug, workspace, domain, stack, origin, files_created: 8, l3_created: true}`. |
| `list` | `python3 -m che_core.cli project list --json` | Tabela: `Slug │ Workspace │ Domain │ Stack │ Has arch? │ Has profile? │ Has DB?` |
| `remove <SLUG> [flags]` | `python3 -m che_core.cli project remove "<SLUG>" [flags] --json` | Mesmo protocolo 2-pass do `/che-workspace remove`: 1) dry-run → mostrar plano ao user; 2) user confirma → rodar com `--no-dry-run --confirm`. |
| `restore <TRASH_SLUG>` | `python3 -m che_core.cli project restore "<TRASH_SLUG>" --json` | Restaura projeto da lixeira. Conflito slug → `--restored-<ts>` sufixo. |
