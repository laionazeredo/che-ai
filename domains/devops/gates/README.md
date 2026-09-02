# Gates — devops domain

> Every gate file in this folder MUST:
> 1. Have a PASS/FAIL rule with a NUMERIC threshold (no subjective language alone).
> 2. Have ONE section called "Fail remediation steps" with concrete actions.
> 3. Have retry policy (max 1 free retry). Human required on second fail.
> 4. Fail without a threshold defined = default HARD FAIL.
>
> Pattern copy from working pilot: `domains/ux/gates/pixel-check-gate.md`
