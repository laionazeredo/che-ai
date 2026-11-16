---
name: "che-manual-test-executor"
description: "Executes a manual test plan's EXECUTABLE CONTRACTS step by step using the Chrome DevTools MCP for UI and the terminal for HTTP/API calls, producing evidence per step (screenshots, optional video, console and network logs, API responses) and a structured pass/fail report per acceptance criterion. Requires a plan that passes `che manual-plan validate`; migrates nothing itself. Call it AFTER che-manual-plan and BEFORE che-ship, or standalone with a worktree + plan path."
---

# Che — Manual Test Executor (Chrome DevTools MCP + terminal)

It **runs** the contracts written by `che-manual-plan`. It never authors them, never edits them and
never issues a merge verdict.

> **SHARED REFERENCES (CANONICAL — DO NOT DUPLICATE body here):**
>
> - Contract vocabulary, MP-checks and scaffolding: `che-manual-plan` skill + `che manual-plan` CLI
> - Plan file shape (sections, AC headings, severity): `che-act` `references/MANUAL_TEST_PLAN_TEMPLATE.md`
> - Report shape: `references/MANUAL_TEST_EXECUTION_REPORT.md`
> - Storage boundary + paths: `contracts/path-canonicity-che.md` · binding (§19) and chat budget (§18): `engineering-contracts`
> - Stack startup commands: `_shared_checklists/NX_PNPM_COMMON.md` and the repository's own scripts

## 🆚 Boundary vs the neighbours

| Concern | `che-qa` | `che-manual-plan` | `che-manual-verification` | **`che-manual-test-executor`** |
| --- | --- | --- | --- | --- |
| Input | Repository | SPEC / ticket / diff | The plan | **A validated plan** |
| Does | lint / typecheck / build / tests | Authors the contracts | Renders a guide for a human | **Runs the contracts** |
| Output | Command results | `manual_test_plan.md` | A guide | **Report + evidence** |
| Tools | Shell | Shell | None | **Chrome DevTools MCP + terminal** |

## 0. Preconditions (non-negotiable)

1. `WORKTREE_ROOT` confirmed (ask when missing — never infer from the current directory).
2. `PLAN_PATH` resolved: explicit argument, or `che manual-plan sync "$WORKTREE_ROOT"` prints the
   newest plan. Never guess a path by hand.
3. **The gate runs first.** `che manual-plan validate "$PLAN_PATH"` must exit 0. If it fails, stop and
   hand the `MP-` failures back: the plan is not runnable, and executing a prose plan by intuition is
   exactly the unreliability this contract removed. Offer `/che-manual-plan` to fix it.
4. **Capability probe — before any setup command.** Record what is available, because a missing tool
   must degrade the run, not crash it halfway:

   | Capability | Probe | If absent |
   | --- | --- | --- |
   | Browser automation | one read-only `list_pages` call | every `ui` AC becomes `BLOCKED_EXECUTION`; `api` and `manual` still run |
   | Terminal HTTP | resolve `curl` on `PATH` with the terminal tool | every `api` step becomes `BLOCKED`; `ui` still runs |
   | Video | `screencast_start` accepts a `filePath` | drop `video` from the evidence and say so in the report |

   The probe result is a `CAPABILITIES` block in the report. Never silently pretend a lane ran.
5. **Storage boundary** — every artifact goes outside the worktree; see §0.1.

### 0.1 Storage boundary

```bash
command -v che >/dev/null 2>&1 || { echo "❌ FATAL: 'che' CLI not found on PATH. Zero writes allowed. exit 98"; exit 98; }
SESSION_ID="${CHE_SESSION_ID:-${HARNESS_SESSION_ID:-fallback-manual-execution-session}}"
eval "$(che compute_paths "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD")"
che ensure_dirs "$WORKTREE_ROOT" "$SESSION_ID" --cwd "$PWD"
che assert_outside_worktree "$CHE_SESSION_DIR" "$WORKTREE_ROOT" --label "CHE_SESSION_DIR (execution evidence)"
```

Build every artifact path with `che output_path "qa" "<kind>" "<task-id>" "session" "<ext>"` —
screenshots, video, logs, report. Nothing lands inside the user's repository.

## 1. Environment setup (§0 of the plan)

1. Show the setup commands and ask for approval: **A** run them · **B** the app is already running
   (ask for the base URL) · **C** cancel.
2. Run them inside `WORKTREE_ROOT`, capturing stdout+stderr to `ENVIRONMENT_SETUP.log`.
3. Non-zero exit → stop before any AC. Report the command and the last 20 lines, then offer: retry
   with an alternative · skip with a known base URL · cancel.
4. Confirm the base URL answers before the first `ui` step.

## 2. Execution — contract-driven, one step at a time

Read the executable YAML block of the current AC and execute its `steps` in order. **No
natural-language guessing**: if a step is missing from the contract, the contract is wrong — stop and
say which AC.

| Contract step | Chrome DevTools MCP | Terminal |
| --- | --- | --- |
| `goto` | `navigate_page` (`type: url`) | — |
| `click` | `take_snapshot` → resolve the node → `click` with its `uid` | — |
| `fill` | `take_snapshot` → resolve the node → `fill` with its `uid` and `value` | — |
| `press` | `press_key` | — |
| `wait` | `wait_for` (`text` + `visible: true`, or a timeout) | — |
| `assert` `expect_visible` / `expect_hidden` | `take_snapshot`, match the accessible text | — |
| `assert` `expect_url` | `list_pages`, match the active page URL | — |
| `assert` `expect_api` / `api` | — | HTTP request with the terminal |
| `manual` | — | human: report `HUMAN_REQUIRED` for that step |

**Locator resolution (the only place a `uid` exists).** A `uid` comes from a snapshot and dies with
it. For every locator step: take a **fresh** `take_snapshot`, find the node whose role and accessible
name match `role` + `name` (or whose label matches `label`, or whose text matches `text`), and use
that `uid` immediately. Never reuse a `uid` from an earlier step, never invent one, and never fall
back to a CSS selector — the contract forbids them on purpose. If no node matches, the step FAILS with
`locator not found: role=button name="Process refund"` and a screenshot; do not try nearby labels.

**API steps** go through the terminal, so they work with or without a browser:

```http
POST /api/bookings/B-1001/refund
Authorization: Bearer <token from the environment>
Content-Type: application/json

{"amount": "10.00"}
```

Send it against `base_url`, then compare `expect_status` and, when the contract names one, the
response body. Save the full response to `api_response`. Never echo the token into a log or a
screenshot.

**Per-AC isolation.** One page per AC: `new_page` at the start, `close_page` at the end. Do not share
browser state between ACs unless the contract says so.

**Anti-flake policy.** An `assert` that fails gets exactly one retry after a `wait_for` of up to 3 s
on the expected text. Two failures = FAIL. Every FAIL captures a screenshot before moving on.

## 3. Evidence (per AC, per the contract's `evidence` list)

| Kind | How | Where |
| --- | --- | --- |
| `screenshot` | `take_screenshot` with `filePath` — the whole viewport, never a cropped element alone | `che output_path "qa" "screenshot" "<task-id>" "session" "png"` |
| `video` | `screencast_start` (with `filePath`) before the first step, `screencast_stop` after the last | `che output_path "qa" "video" "<task-id>" "session" "mp4"` |
| `console_log` | `list_console_messages` | `che output_path "qa" "console" "<task-id>" "session" "log"` |
| `network_log` | `list_network_requests` | `che output_path "qa" "network" "<task-id>" "session" "log"` |
| `api_response` | terminal output of the request | `che output_path "qa" "api-response" "<task-id>" "session" "json"` |
| `log_file` | the dev server's own output captured during setup | `che output_path "qa" "server-log" "<task-id>" "session" "log"` |

A screenshot is only evidence if it shows the URL and the state the assertion is about. Capture at the
moment of the assertion, not at the end of the AC.

## 4. Verdict per AC

| Verdict | When |
| --- | --- |
| ✅ `PASS` | Every step ran and every `assert` matched |
| ⚠️ `PARTIAL` | Some steps passed; at least one `manual` step is `HUMAN_REQUIRED`, or a capability was missing for a non-critical step |
| ❌ `FAIL` | A step errored, a locator was not found, or an assertion did not match after the retry |
| ⏭️ `BLOCKED` | The lane could not be reached (no browser, no terminal, app down) — never reported as PASS |

## 5. Smoke checks (§2 of the plan)

| ID | How |
| --- | --- |
| S1 Build | the repository's build command; exit code + last 10 lines |
| S2 Lint | the repository's lint command; ≤5 warnings passes |
| S3 Login | the login AC, when the plan has one; otherwise `HUMAN_REQUIRED` |
| S4 Navigation | three top-level pages through `navigate_page`; a 500 or a blank page fails |
| S5 Logs | `list_console_messages` filtered to `error`, plus the dev server log tail |

## 6. Report and delivery

Save to `che output_path "qa" "manual-test-execution-report" "<task-id>" "session" "md"`, in the
shape of `references/MANUAL_TEST_EXECUTION_REPORT.md`, with these additions:

- **`CAPABILITIES`** — browser · terminal · video, each `available` / `missing`.
- **Contract fidelity** — for every FAIL, the exact `AC-N` step number and action that broke.
- **Evidence manifest** — SHA256 per evidence file, as the reference report specifies.

Chat delivery (§18 — four sections, ≤400 words, chat language): status and AC counts · the failing
steps · the report and evidence links · one deep-dive offer.

## 7. Safety rules

1. **Never touch production.** A URL with `.prod.` / `.production.` or a known production domain
   without a `test` / `staging` / `dev` marker → block and ask twice.
2. **No secrets in evidence.** Never screenshot a password field, never write a token to a log. Pass
   credentials through environment variables named in the plan.
3. **Doubt means stop.** A locator that matches two nodes, a missing `base_url`, an ambiguous lane →
   ask; never pick the first match silently.
4. **Never rewrite the plan.** If the contract is wrong, report it; `che-manual-plan` fixes it.
5. **One AC at a time.** Finish its evidence before starting the next.
