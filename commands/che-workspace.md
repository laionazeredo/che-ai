---
description: "Gerencia workspaces Che (L1 ~/.che-workspaces/<slug>). 5 subcommands: add NAME | list | remove NAME [--dry-run|--no-dry-run --confirm] | restore TRASH_SLUG | trash-list. Workspaces são a camada L1 da hierarquia 4-nível do Che."
arguments:
  - name: subcommand
    description: "Required positional: add <NAME> | list | remove <NAME> [--no-dry-run --confirm] | restore <TRASH_SLUG> | trash-list. Remoção NUNCA apaga: move para .trash/. Dry-run DEFAULT. Exemplos: /che-workspace add flockr / /che-workspace list / /che-workspace remove foo / /che-workspace remove foo --no-dry-run --confirm / /che-workspace restore workspace--foo--20260904-235959 / /che-workspace trash-list"
    required: true
---

Gerencia a **camada L1 (Workspace Root)** da hierarquia 4-nível do Che. Workspaces agrupam projetos logicamente (ex: por cliente, time, iniciativa). Path canônico: `~/.che-workspaces/<workspace-slug>/`.

**Safety gates DESTRUTIVOS (remove NÃO apaga):**
1. **`--dry-run` é DEFAULT.** Sem flags: só exibe `action_would_be`, NÃO move nada.
2. Para efetivar: **dupla flag** `--no-dry-run` + `--confirm` (as duas, juntas).
3. Mesmo confirmado: **move para `~/.che-workspaces/.trash/workspace--<slug>--<ts>/`** (nunca rm -rf). Recuperável via `restore`.

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `add <NAME> [--worktree-root WT]` | `python3 -m che_core.cli workspace add "<NAME>" [--worktree-root "..."] --json` | Cria pasta `~/.che-workspaces/<slug>/` + `_MANIFEST.json`. Se `--worktree-root` foi passado → workspace é marcado como "default" para esse worktree. Report `created=True`, slug e path absoluto. |
| `list` | `python3 -m che_core.cli workspace list --json` | Print tabela formatada: `Slug │ Name │ Projects count │ Default worktree │ Created`. |
| `remove <NAME> [--dry-run \| --no-dry-run --confirm]` | `python3 -m che_core.cli workspace remove "<NAME>" [flags] --json` | **1st run SEMPRE dry-run** (segurança). Agent só roda `--no-dry-run --confirm` APÓS user revisar a saída do dry-run e confirmar verbalmente. Report `dry_run=True/False`, `aborted=True` se confirm faltou, `moved_to_trash=` path se efetivou. |
| `restore <TRASH_SLUG>` | `python3 -m che_core.cli workspace restore "<TRASH_SLUG>" --json` | Restaura entrada da lixeira de volta para `~/.che-workspaces/`. Trata conflito de slug: sufixo `--restored-<ts>` se nome já ocupado. Report `restored=True` + path final. |
| `trash-list` | `python3 -m che_core.cli workspace trash-list --json` | Lista conteúdo da lixeira: `Kind │ Slug │ Original path │ Moved at`. Útil antes do `restore`. |
