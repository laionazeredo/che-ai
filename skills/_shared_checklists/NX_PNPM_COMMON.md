# SHARED CHECKLIST — pnpm (Corepack) + Nx Common Operations (CANONICAL)

> REFERÊNCIA COMPARTILHADA por: che-developer, che-qa, che-ci-fixer, che-debugger-bugfix (build/run reproducing), che-ship (build/lint smoke before push).
> NÃO duplique comandos pnpm/nx; sempre invoque os formatos abaixo.

---

## 0. Corepack first (mandatory)

**Every invocation MUST go through Corepack.** Never bare `pnpm` or `npm`.
Ensures package-manager version pinned by `package.json#packageManager` is used exactly.

```bash
# Confirmar corepack disponível + versão pinada
corepack pnpm --version
```

---

## 1. Repo-level commands

```bash
# Install (after clone, or after changes to pnpm-lock.yaml / package.json)
corepack pnpm install --frozen-lockfile
# ^ frozen-lockfile: FAILS if lockfile outdated — forces developer to run install locally and commit the updated lockfile. USE in CI and as first step of every session.

# Unit/integration tests across all packages
corepack pnpm test

# API e2e (Vitest)
corepack pnpm test:api-e2e

# Playwright E2E (CI mode: headless)
CI=1 corepack pnpm test:e2e
```

---

## 2. Nx — per-package targets

> Sempre usar `--tui false` para NÃO cair em terminal interativo.
> Nx project name = diretório em `packages/<name>` (ex: `@flockr/platform` → project `platform`).

```bash
# Build um package específico
corepack pnpm nx run platform:build --tui false

# Lint (Biome)
corepack pnpm nx run platform:lint --tui false

# Typecheck (tsc noEmit)
corepack pnpm nx run platform:typecheck --tui false

# Unit tests package específico
corepack pnpm nx run db:test --tui false

# Dev server (Next.js apps)
corepack pnpm nx run platform:dev --tui false

# Run multiple targets de uma vez (ex: lint + typecheck de todos os packages)
corepack pnpm nx run-many --targets=lint,typecheck --tui false

# Affected só roda em packages que tiveram arquivos alterados vs base
corepack pnpm nx affected --targets=lint,typecheck,test --tui false
```

---

## 3. CI failure common fixes (che-ci-fixer)

| Sintoma (log error) | Causa provável | Fix |
|---|---|---|
| `ERR_PNPM_OUTDATED_LOCKFILE` | Package.json editado sem rodar `pnpm install` | `corepack pnpm install` → commit atualiza `pnpm-lock.yaml` |
| `Cannot find module @flockr/<pkg>` | Workspace symlink não criado / build do package não rodou | `corepack pnpm install` + `corepack pnpm nx run <pkg>:build --tui false` |
| `Type error:` em `packages/platform` / `packages/scanner` | TSC typecheck falhou | Roda local: `corepack pnpm nx run platform:typecheck --tui false` + fix |
| `biome lint:` / `violates lint rule` | Biome lint/format falhou | `corepack pnpm nx run-many --targets=lint --tui false` → apply `corepack pnpm biome check --write <files>` + commit |
| `Test failed: vitest` flaky (passa 2ª vez sem code change) | Flaky test; precisa de retry/async fix | Marca R4=Flaky; usa `corepack pnpm nx run <pkg>:test --tui false --retry=2` para confirmar; melhor ainda = estabilizar o teste. |
| `Migration missing` / `typeorm schema:sync` divergência | Entity alterada sem migration up | Roda migration + testa down/up (db package). |

---

## 4. Che QA Standard Run Order (che-qa skill default)

Para cada task envelope após implementation (seguir a ordem — barata → cara):
```bash
# 1. Install (se lockfile mudou)
corepack pnpm install --frozen-lockfile

# 2. Lint / format (Biome) — mais barato, pega mais rápido erros bobos
corepack pnpm nx run <project>:lint --tui false

# 3. Typecheck (TS)
corepack pnpm nx run <project>:typecheck --tui false

# 4. Build — garante não há importação de arquivo não existente etc
corepack pnpm nx run <project>:build --tui false

# 5. Test unit + integration (Vitest)
corepack pnpm nx run <project>:test --tui false
```

Se todos passarem → QA_OK.
