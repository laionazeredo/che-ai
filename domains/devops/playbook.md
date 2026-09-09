---
domain: "devops"
playbook_version: "0.1"
gate_files_required:
  - "gates/first-gate-template.md"
  - "gates/second-gate-template.md"
---

# Playbook — devops (POLITBURO member domain, CI/CD + Infra + Observability)

## 0. Preconditions (run before anything in this domain)
- [ ] Session has **domain:** field set correctly in SPEC frontmatter or Scrum Master flag.
- [ ] Domain `profile.md` loaded successfully by Scrum Master Step 0.3.
- [ ] All required connectors in `connectors/` directory have config present (if used).
- [ ] **Provider Pointer Pattern (G vs E NON-NEGOTIABLE — CRITICAL for this domain)**:
  Structural delivery stages LIVE HERE. Infra / Cloud / Tooling-specific rules → 100% delegated to:
  - (a) **`skills/devops-infra-expert/SKILL.md`** — §XI E05 CHE_RULES companion (B04 CloudNative Docker/Kind/K8s/Helm/Kustomize/Terraform + B05 Observability 3Pillars RED 4GS + Prometheus + OTel + Grafana Loki Tempo + Sentry + Datadog + B-P1 ArgoCD/Crossplane/OpenCost/Gatekeeper).
  - (b) **`skills/terraform-engineer`** — module structure / provider pin / remote state s3 + dynamodb rules (IF infra-as-code terraform)
  - (c) **`skills/observability`** + §X CHE_RULES S14 SLO/SLI companion
  - (d) **`skills/k8s-kind`** — kind cluster local development (devops-infra B04 §2 companion)
  - NUMBERS → CHE_RULES §X "per Sxx". NEVER redefine SLO numbers in this playbook.
  - **PII / SECURITY (shared with engineering-contracts §19)**: NEVER log or track secrets (Stripe/Supabase/JWT). Use `NOTIFICATION_PII_HASH_SECRET` correlation.

---

## 1. Phase 1 — Brief / Discovery / Intake (DevOps skeletal)
0.1 **Topology 1-sentence**: Are we deploying (A) Vercel-only Frontend apps, (B) K8s Stateful workloads with databases, (C) Multi-cloud hybrid, (D) Serverless functions-only?
0.2 **SLO targets (S14 CHE_RULES companion — observability pointer)**:
  | SLI | Target (S14 compliant) | Where defined? |
  |---|---|---|
  | Availability (monthly) | ≥ 99.9% (43m 49s downtime max) | devops-infra B05 §Methodologies pointer 4 Golden Signals |
  | p95 Latency API | ≤ 350ms | RED method (Requests, Errors, Duration) pointer |
  | Error budget burn | ≤ 2% / day alert | S14 LEAN SLO gates companion |
  | MTTR (incidents P0/P1) | ≤ 25 min | eng §20 Fire Drill companion |
0.3 **Environments inventory 4 (minimum): local · dev · staging · prod**. Each = separate AWS account / GCP project / Vercel project (per Sentry B05 rule NEVER share DSN).
0.4 **Approved gate**: Topology + SLO + Envs sent. Literal "DevOps Architecture Approved" required.

### Output:
- `docs/devops/<slug>-01-architecture.md`

---

## 2. Phase 2 — Design / Draft / Implementation (Pipeline + Infra as Code)
0.1 **CI/CD pipeline 5 mandatory stages (non-negotiable order)**:
  | Stage | What it does | CHE_RULES §X companion |
  |---|---|---|
  | 1. **Install + Cache** | Restore lockfile exact (uv --frozen / pnpm frozen-lockfile / go mod verify / cargo --locked). ANY drift → FAIL immediately. | S14 reproducibility |
  | 2. **SAST + Lint + Typecheck** | Biome / Ruff / golangci-lint / clippy + TruffleHog secret scan + Semgrep security rules. 0 lint errors / 0 secrets → PASS. | S14 + compliance |
  | 3. **Unit + Integration tests + coverage** | Coverage lines ≥ 70% global / new code ≥ 80%. | Engineering playbook Stage 2 G-ENG-2 gate → shared rule here. |
  | 4. **Build + Push artifact** | Multi-stage Dockerfile USER nonroot · Sign image (cosign / Sigstore). | devops-infra B04 §1 Dockerfile rules |
  | 5. **Deploy · env separation** | dev → auto. staging → auto. prod → **manual approval required** (S08 scope gate companion). Rollback ≤ 1 click. | B04 §7 Terraform / GitOps ArgoCD |
0.2 **IaC repository structure minimum 3 folders**:
  ```
  infra/
    terraform/     # Base infra (VPC / EKS / RDS / IAM roles)
    k8s/           # Helm + Kustomize overlays dev/stg/prod (B04 §5 Helm / §6 Kustomize)
    ci/            # GitHub Actions / GitLab CI pipeline yaml
  ```
0.3 **Observability pipeline (per B05 pointer)**: OTel Collector → Prometheus + Loki + Tempo → Grafana. Sentry env-separated DSN per app per env.

---

## 3. Phase 3 — Quality Gates (run EVERY gate in gates/ folder)
**Gates CONSUME CHE_RULES §X canonical thresholds. Numbers NEVER duplicated here.**
Required gates for devops:
| Gate / ID | Threshold to PASS | CHE_RULES §X ref | Auto-retry allowed (max N) |
|---|---|---|---|
| `gates/first-gate-template.md` | Score ≥ 7.0 / 10 (Scope × Lean geomean ≥ 7.0) | per S11 + per S13 | 1 |
| `gates/second-gate-template.md` | 0 CRITICAL items (hardcoded secret · public DB 0.0.0.0/0 · no rollback · env DSN collision) | per S14 + compliance PII check | 1 |
| **[G-DOPS-1] CI 5-stage + IaC embedded gate** | 5 stages present, no skip. Terraform state REMOTE (S3+DynamoDB) or equivalent (no local tfstate). Kubernetes Deployments all have HPA+PDB+NetworkPolicy. | B04 §3/§7 + B05 per S14 SLO | 1 |
| **[G-DOPS-2] Observability embedded gate** | 4 Golden Signals dashboards exist for every production service (Latency/Traffic/Errors/Saturation). Prometheus alerts use `rate()[5m]` not `irate()`. Sentry DSN separate per env. Datadog 3 mandatory tags every span/log/metric. | per S14 + B05 §Tools Prometheus / Sentry / Datadog | 1 |

Gate failure process (same for every domain, non-negotiable):
1. First fail → ONE free auto-retriable apply recommendations of gate.
2. Second fail → STOP. Ask human (domain owner) before proceeding further.
3. Never skip a gate or lower threshold without decision.log entry + user VERBATIM.

---

## 4. Phase 4 — Delivery / Handoff / Ship integration
After ALL gates PASS:
- Write Runbook: `docs/devops/<slug>-RUNBOOK.md` = Deploy steps · Rollback steps · P0 oncall 24/7 list · Incident comms template.
- Write Disaster Recovery: RTO ≤ 4h. RPO ≤ 15min for stateful services (RDS / Postgres / Kafka).
- Call /che-ship if code/artifacts go to git repo.
- If pure docs-only or creative-only deliverable: write final report + save in `$CHE_SESSION_DIR/reports/` for audit.

---

## Provider Pointer summary (CRITICAL, avoids duplicated rules)
| General Workflow (HERE) | Specific Implementation (100% delegated to skill — never copy paste rule body) |
|---|---|
| Docker + Kind + K8s + Helm + Kustomize + Terraform structural stages | `skills/devops-infra-expert/SKILL.md` (CHE_RULES §XI E05 B04) |
| Prometheus + OTel + Grafana (Loki/Tempo) + Sentry + Datadog 3Pillars/RED/4GS | `skills/devops-infra-expert/SKILL.md` (B05 Observability) + `skills/observability` |
| ArgoCD ApplicationSet · Crossplane XR/XRC · OpenCost labels · OPA Gatekeeper policies | devops-infra B-P1 §CloudNative GitOps/Cost/Policy |
| Terraform module structure + remote state + pin | `skills/terraform-engineer` variants |
| Kind local cluster bootstrap rules | `skills/k8s-kind` skill |
| Pass/fail score numerals | CHE_RULES §X S01-S15 canonical — ZERO duplication |
