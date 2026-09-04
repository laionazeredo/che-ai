---
name: "che-plan"
description: "Transforms an Approved SPEC into one or more structured tickets (Jira, Linear, ClickUp). Supports single tickets or Epic/Feature structures with sub-tasks, BDD acceptance criteria, and dependency mapping."
---

# Che Plan (Epic & Ticket Generator)

> **SHARED REFERENCES:**
> - Approved SPEC format: `che-spec` skill
> - Engineering contracts (BDD, KISS, DbC): `engineering-contracts` skill
> - Path resolution: `source "${CHE_HOME:-$HOME/.trae}/contracts/che_sessions_contract.sh"`

This skill acts as a bridge between technical specification and project management. It ensures that implementation tasks are properly documented, categorized, and linked in external tools.

---

## §0 PRECONDITIONS

1. **Approved SPEC required**: This skill MUST fail if no Approved SPEC is found for the current feature/slug.
2. **MCP Access**: Requires access to `mcp_flockr-linear`, `mcp_laion-clickup`, or a browser-based agent for Jira.
3. **User Input**: Requires Project/Board name and Target Language (default: English for code-related, User's language for descriptions).

---

## §1 WORKFLOW

### Step 1: Spec Analysis
1. Read the SPEC from `$CHE_WORKSPACE_SHARED/specs/<slug>/<timestamp>-spec.md`.
2. Extract `B_COUNT`, `AB_COUNT`, and `change_class`.
3. **Structure Decision**:
   - **Single Ticket**: If `B_COUNT <= 3` AND `estimated_files_max <= 5` AND `change_class` is not `feature`.
   - **Epic/Feature**: Otherwise. Create a parent Epic/Feature and decompose into sub-tasks.

### Step 2: Content Formatting (MANDATORY TEMPLATE)
Every ticket (single or sub-task) MUST follow this structure:

```markdown
# [ID] Title (Short & Action-oriented)

## 📝 Problem Description
[Extract from SPEC §1 WHY]

## 🛠 Functional Requirements
[Extract from SPEC §4.2 Behaviors relevant to this task]

## ⚙️ Non-Functional Requirements
[Extract from SPEC §3 Contracts & §7 Hints]

## ⚖️ Mandatory Business Rules
[Extract from SPEC §4.1 Key Rules]

## ✅ Acceptance Criteria (BDD Style)
- **Scenario**: [B-ID / AB-ID title]
  - **Given** [Given column]
  - **When** [When column]
  - **Then** [Then column]
```

### Step 3: Epic Decomposition (if applicable)
If Epic structure is chosen:
1. **Parent Ticket**: Contains a high-level description, **Goals**, and a **Task Graph** (Mermaid) showing execution order and critical path.
2. **Sub-tasks**:
   - Group B-IDs into logical tasks (e.g., Data Layer, API Layer, UI Layer).
   - Each sub-task gets its own ticket with the template above.
   - **Dependencies**: Establish "blocked by" relations between tasks (e.g., API blocks UI).

### Step 4: External Tool Execution
1. Ask user for:
   - **Target Tool**: Linear (Recommended), ClickUp, or Jira.
   - **Project/Board**: Where the tickets should live.
   - **Language**: English (Default) or User's language.
2. Call appropriate tool (e.g., `save_issue` for Linear, `clickup_create_task` for ClickUp).
3. If creating an Epic, save the Parent first to get its ID, then set `parentId` for sub-tasks.

---

## §2 RETURN VALUES

Print the results of the creation:
- `PLAN_STRUCTURE=Single|Epic`
- `PARENT_TICKET_ID=<id>`
- `SUBTASKS_COUNT=<count>`
- `TOOL_URL=<link-to-tickets>`

---

## §3 QUALITY GATES
- **BDD Check**: Every sub-task MUST have at least one B-ID or AB-ID mapped to a BDD scenario.
- **Dependency Check**: Epic MUST have at least one dependency link between sub-tasks if `count > 1`.
- **Language Consistency**: Do not mix languages in the same field.
