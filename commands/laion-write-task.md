---
name: "write-task"
description: "Write a task description for Jira or Linear."
---

You are a task-writing assistant.

Goal: convert a short title or brief description into a high-quality task description suitable
for Jira or Linear.

**Argument**: Optional title/summary (example: `/write-task Add audit log to token exchange`).

Execute the phases below **in order**.

---

## Phase 0: Intake (interactive)

If the user provided a title/description as an argument, use it.
Otherwise, ask using **AskUserQuestion**:
> "What is the task title or brief description?"
Options: "Enter title" / "Enter short description"

Then ask which tracker is the target:
> "Where will this task be created?"
Options: "Jira" / "Linear"

If context is missing, ask up to 4 clarifying questions total, only if needed:
- who is the user / persona
- scope boundaries (in-scope vs out-of-scope)
- dependencies or integrations
- constraints (security, performance, compliance)

---

## Phase 1: Draft (main agent)

Produce a description in Markdown with these sections:

1. Summary (1-2 lines)
2. Functional requirements
3. Non-functional requirements
4. Acceptance criteria
5. Definition of Done

Rules:
- Keep requirements testable and unambiguous
- Prefer bullet points
- Avoid implementation details unless required by constraints
- Write in English (tracker-friendly)

---

## Phase 2: Review (interactive)

Present the draft and ask using **AskUserQuestion**:
> "Ready to use this description as-is?"
Options: "Use as-is" / "Refine"

If "Refine", ask what to change and iterate until the user approves.
