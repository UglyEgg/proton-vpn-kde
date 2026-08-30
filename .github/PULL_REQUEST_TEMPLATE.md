## Problem

Describe the user-visible or engineering problem.

## Change

Explain the smallest implemented solution and its architectural boundary.

## Verification

- [ ] Relevant regression coverage was added or updated.
- [ ] `ctest --test-dir build --output-on-failure` passes.
- [ ] `scripts/check-static-analysis.sh` passes.
- [ ] No credential, token, account data, or private diagnostic was committed.
- [ ] Material AI assistance is disclosed below.

## Risk

Call out authentication, D-Bus, process lifetime, systemd, packaging, networking,
or Proton Core compatibility effects. Write “None” only after checking each.

## AI assistance

State the tools and material assistance used, or write “None”. The contributor
remains responsible for reviewing and licensing the complete change.
