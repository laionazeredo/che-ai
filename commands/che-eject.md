---
description: "Ejeta o Che de forma segura e reversível: desinstala adapters multi-agentes, move arquivos whitelist para lixeira, limpa snippets de .gitignore de projetos clientes e permite restore. 3 subcommands: plan [flags] | trash-list | restore TRASH_SLUG [flags]. 3 safety gates obrigatórios para operações destrutivas. NUNCA usa rm — só move para .trash/che-eject/. Blacklist absoluta (nunca toca): user_rules/, bindings/registry.jsonl, memory/, .git/, node_modules/."
arguments:
  - name: subcommand
    description: "Required positional: plan [--che-home=PATH] [--keep-git-repo|--no-keep-git-repo] [--scan-client-repos PATH ...] [--dry-run (DEFAULT)|--apply --confirmed --i-know-what-im-doing] | trash-list | restore TRASH_SLUG [--dry-run (DEFAULT)|--apply --confirmed]. Exemplos: /che-eject plan / /che-eject plan --apply --confirmed --i-know-what-im-doing / /che-eject plan --scan-client-repos ~/code/foo ~/code/bar / /che-eject trash-list / /che-eject restore che-eject--abc123--20260904-235959 --apply --confirmed"
    required: true
---

Comando canônico para **desinstalar (ejetar) o Che de forma 100% reversível**, voltando ao estado original do ambiente do agente antes da instalação. Implementa a mesma filosofia de safety gates dos comandos de workspace/project:

**3 Safety Gates DESTRUTIVOS (operações NUNCA apagam, só movem):**
1. **`--dry-run` é DEFAULT.** Sem flags: só exibe `eject_plan` completo (`would_uninstall_adapters`, `would_move_to_trash`, `would_cleanup_gitignores`), sem escrever nada em disco.
2. Para efetivar o eject: **TRÊS flags juntas** `--apply --confirmed --i-know-what-im-doing` (as 3, faltando uma = bloqueia com erro).
3. Mesmo confirmado: **move para `~/.che-workspaces/.trash/che-eject/<slug--ts>/`** (nunca rm -rf). Totalmente recuperável via `restore`.

**Install Kinds detectados automaticamente:**
- `git-clone`: `che_home/.git/` existe → DEFAULT `--keep-git-repo=True` (mantém clone/fork do usuário como repo Git comum; só desinstala adapters e limpa snippets de clientes; NÃO move arquivos whitelist). Use `--no-keep-git-repo` explicitamente se quiser mover tudo (incluindo .git).
- `copy-install`: sem `.git/` → sempre move whitelist para trash (blacklist continua intacta).

**Blacklist Absoluta (NUNCA toca em hipótese alguma):**
`user_rules/`, `bindings/registry.jsonl`, `memory/`, `.git/`, `node_modules/`.

**Subcommand dispatch:**

| Subcommand | CLI invocation | Expected agent action after |
|---|---|---|
| `plan [flags]` (default) | `python3 -m che_core.cli eject plan [--che-home PATH] [--keep-git-repo\|--no-keep-git-repo] [--scan-client-repos PATH ...] [--dry-run\|--apply --confirmed --i-know-what-im-doing]` | **1st run SEMPRE dry-run** (segurança). Agent só roda `--apply --confirmed --i-know-what-im-doing` APÓS user revisar a saída do dry-run e confirmar verbalmente. Reporta: `install_kind`, `adapters_detected`, `kept_blacklist_count`, `moved_count`, `uninstalled_adapters`, `cleaned_gitignores`, `trash_destination`. |
| `trash-list` | `python3 -m che_core.cli eject trash-list [--trash-root PATH]` | Lista conteúdo da lixeira `che-eject`: mostra `trash_slug`, `original_che_home`, `ejected_at`, `install_kind`, `manifest_entries_count`. Útil antes do `restore`. |
| `restore <TRASH_SLUG> [flags]` | `python3 -m che_core.cli eject restore "<TRASH_SLUG>" [--dry-run\|--apply --confirmed]` | Restaura eject da lixeira de volta para `che_home` original. Trata conflito de slug: não sobrescreve (avisa com erro). Pós-restore: executa `scripts/setup-adapters.sh` automaticamente para religar symlinks Codex/Claude/Cursor. |
