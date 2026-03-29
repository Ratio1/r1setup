# E2E Tests for Machine-First Onboarding Flow

These tests exercise the Phases 0–4 machine-first onboarding flow against real
remote machines.  They require SSH access and are **not** part of the regular
`python3 -m unittest discover tests` run (they live in a separate `e2e/`
subdirectory that the default `discover` does not recurse into).

## Prerequisites

- SSH access (key-based) to the test machines listed in
  `test_machine_first_onboarding.py`
- No existing `edge_node` services on the test machines (or the tests will
  adapt to whatever is discovered)

## Running

```bash
cd mnl_factory/scripts
python3 -m pytest tests/e2e/ -v          # if pytest is available
python3 -m unittest tests.e2e.test_machine_first_onboarding -v   # stdlib
```

## Test Machines

| Label | Host | User | Purpose |
|-------|------|------|---------|
| machine-1 | 35.228.69.214 | vitalii | GCP instance, clean |
| machine-2 | 34.88.90.109 | vitalii | GCP instance, clean |

## What Is Tested

1. **SSH connectivity** — verify both machines are reachable
2. **Spec probe** — verify CPU/RAM extraction works
3. **Discovery probe** — verify remote discovery script runs and returns valid JSON
4. **Config shell creation** — verify empty config with fleet metadata persists
5. **Machine registration** — verify machine records are persisted in fleet state
6. **Discovery scan** — verify scan results are cached in fleet metadata
7. **Fresh host building** — verify inventory host entry is synthesized correctly
8. **Gap fill** — verify fresh instances are added to inventory from machine records
9. **Full onboarding flow** — verify the complete _create_machine_first_configuration
   orchestration with real SSH connections
10. **Cleanup** — all test state is created in temp directories; no side effects
