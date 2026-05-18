# Security Policy

## Supported versions

coord-smith is pre-release software (current version `0.0.1`).
Only the `main` branch / latest commit receives security fixes.

| Version | Supported |
|---------|-----------|
| `main` (current) | ✅ |
| Older tags | ❌ |

## Threat model

coord-smith executes OS-level clicks and takes full-screen
screenshots on the user's machine, driven by recipes supplied by
an external orchestrator (e.g. OpenClaw). Relevant exposures:

- **Click target injection.** A malicious or malformed recipe
  could direct clicks to unintended coordinates. Mitigations:
  - Recipes are validated against a Pydantic schema before any
    click fires.
  - Coordinates are bounds-checked against the screen
    dimensions; out-of-bounds clicks raise
    `ClickCoordinatesOutOfBounds`.
  - The coordinate priority chain (`payload → step.coord →
    step.image → no-click`) is fixed in code, not configurable
    from recipes.
- **Screenshot exfiltration.** Screenshots are written to a
  user-controlled `artifacts/runs/<run_id>/` tree. coord-smith
  does not transmit them anywhere — the caller (OpenClaw)
  reads them locally. Operators are responsible for the
  artifact directory's filesystem permissions and retention.
- **Concurrent invocation.** The per-host advisory lock
  (`fcntl.flock`) prevents two coord-smith processes from
  racing on the cursor; it is advisory and does not defend
  against an adversarial neighbour bypassing the lock.

## Reporting a vulnerability

If you believe you've found a security issue:

1. **Do not open a public GitHub issue.**
2. Email the maintainers (placeholder address until the project
   is moved to its production org) with:
   - A description of the vulnerability.
   - Reproduction steps or a minimal proof-of-concept recipe.
   - The version / commit hash you observed it on.
3. Expect an acknowledgement within 7 days. Disclosure timing
   is coordinated case-by-case; high-impact issues get fixes
   shipped within 14 days where possible.

## What's out of scope

- Bugs in `pyautogui`, `langgraph`, `pydantic`, `opencv-python`,
  or other upstream dependencies. Report those upstream and
  optionally cc us.
- macOS Accessibility / Screen Recording permission grants —
  these are operator-controlled; coord-smith only inherits them.
- Recipes that intentionally crash the runtime (out-of-bounds
  coordinates, malformed images) — those produce typed errors
  and exit code 1, by design.
