Given failed AINL validation diagnostics, produce the smallest patch to restore strict validity.

Rules:
- Follow `llm_repair_hint` first.
- Keep unchanged labels untouched.
- Preserve endpoint contracts and exits.

Diagnostic -> patch example:
- Error: `Targeted label '42' does not exist`
- Hint: `Declare L42 or retarget the branch to an existing label`
- Patch:
```ainl
L42: J "fallback"
```
