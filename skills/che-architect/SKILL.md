---
name: "che-architect"
description: "Iteratively helps architect complete systems from business ideas. Covers stack, infra, modules, data modeling, buy vs build, and resource estimation."
---

# Che Architect (System Design & Strategy)

> **SHARED REFERENCES:**
> - ADR documentation: `adr-architecture` skill
> - Mermaid visualization: `mermaid-diagram-specialist` skill
> - Database modeling: `database-architect` and `database-schema-designer` skills
> - Engineering principles: `engineering-contracts` (KISS, YAGNI, SOLID)

This skill acts as a Strategic Technical Partner. It doesn't just write code; it designs the foundations of a system through an iterative dialogue with the user.

---

## §0 PURPOSE

To transform a high-level business vision into a comprehensive technical blueprint. It balances speed-to-market (Lean) with long-term maintainability.

---

## §1 ITERATIVE WORKFLOW (The 5-Step Design)

Do NOT generate the whole plan at once. Proceed step-by-step, asking for user feedback after each phase.

### Step 1: Discovery & Macro Scope
- **Goal**: Understand the "Why" and the core value proposition.
- **Output**: 
  - Business Problem Statement.
  - Core Personas.
  - **Macro Business Rules**: Key constraints and mandatory behaviors.
  - **Compliance & Privacy**: Initial assessment of PII, regional regulations (GDPR, LGPD), and industry-specific rules (Fintech, Health, etc.).
  - **User Journey Map**: Mermaid User Journey diagram showing the main user flows.
  - **Feature Map**: Structured visual map of features categorized by module/priority.
  - High-level Feature List (MoSCoW).
  - **Constraint Check**: Scale requirements, budget, and accessibility/localization needs.

### Step 2: Technical Stack & Buy vs Build
- **Goal**: Choose the right tools for the job.
- **Output**:
  - **Language/Frameworks**: Frontend (Accessibility/i18n ready), Backend, Mobile.
  - **Data Stores**: SQL, NoSQL, Cache, Vector DB.
  - **Security Profile**: Determine system criticality (e.g., Financial/High vs Landing/Low) and required security depth.
  - **Buy vs Build Matrix**: Analysis for critical components (e.g., Auth, Payments, Search).
  - **Rationale**: Why these choices fit the constraints.

### Step 3: Architecture & Modules
- **Goal**: Design the internal structure and boundaries.
- **Output**:
  - **Pattern Selection**: Monolith vs Microservices vs Serverless.
  - **Module Map**: Responsibility boundaries (Bounded Contexts) and internal components.
  - **C4 Diagrams (Context & Container)**: Mermaid diagrams showing high-level system interactions and container-level breakdown.
  - **C4 Diagram (Component)**: Deep dive into the most critical containers to show internal component relations.
  - **Macro Data Model (ERD)**: Mermaid Entity Relationship Diagram of core entities and their associations.
  - **Security & Privacy Design**: Data encryption, Auth flow, and RLS strategy.
  - **Architecture Decisions**: Key trade-offs documented as initial ADRs.

### Step 4: Infrastructure & Resource Estimation
- **Goal**: Plan the deployment, maintenance, and observability.
- **Output**:
  - **Cloud Provider**: AWS, Vercel, Railway, Supabase, etc.
  - **CI/CD Pipeline**: Deployment strategy (Blue/Green, Canary).
  - **Observability Strategy**: Logs, Metrics, and Tracing from day one.
  - **Operations & Support**: User support plan, incident response, and operational roadmap.
  - **Resource Estimation**: Estimated cost per month (low/high) and effort (Man-months/Sprints).

### Step 5: The Blueprint (Final Artifact)
- **Goal**: Save the durable architecture documentation.
- **Action**: Save the final plan to `$CHE_WORKSPACE_SHARED/projects/<slug>/architecture.md`.
- **Action**: Create initial ADRs for critical decisions.

---

## §2 MANDATORY SECTIONS FOR ARCHITECTURE.MD

Every generated architecture document MUST include:
1. **Executive Summary**: 1-paragraph business vision.
2. **User Journey & Feature Map**: Visual flows and feature hierarchy.
3. **Tech Stack & Strategy**: Versions, choices, and reasoning (Buy vs Build, i18n, Accessibility).
4. **C4 Architecture Diagrams**: Context, Container, and Component levels.
5. **Data Modeling (ERD)**: Mermaid diagram of core entities.
6. **Security, Compliance & Privacy**: Threat modeling, regulatory mapping (GDPR/LGPD), and data protection.
7. **Infrastructure & Observability**: Deployment model and monitoring plan.
8. **Scalability & Performance**: How the system grows.
9. **Operations & Support**: How the system is maintained and how users are supported.
10. **Implementation Roadmap**: Phase 1 (MVP) vs Phase 2 (Growth).
11. **ADR Index**: Link to the detailed Architecture Decision Records.

---

## §3 QUALITY GATES
- **KISS/YAGNI Check**: Avoid over-engineering. If the user asks for a simple app, don't recommend Kubernetes.
- **Portability Check**: Ensure the architecture isn't locked into a single vendor unless requested.
- **Cohesion Check**: Ensure modules have clear boundaries and low coupling.
