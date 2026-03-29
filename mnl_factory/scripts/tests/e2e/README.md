# E2E Tests for Machine-First Onboarding Flow

These tests exercise the Phases 0–7 machine-first onboarding flow against real
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

Machines are configured via environment variables (or a `.env` file):

```bash
export E2E_MACHINE1_HOST=<ip-or-hostname>
export E2E_MACHINE1_USER=<ssh-user>
export E2E_MACHINE2_HOST=<ip-or-hostname>
export E2E_MACHINE2_USER=<ssh-user>
```

Tests auto-skip when these variables are not set.

## What Is Tested

### Phases 0-4

1. **SSH connectivity** — verify both machines are reachable
2. **Spec probe** — verify CPU/RAM extraction works
3. **Discovery probe** — verify remote discovery script runs and returns valid JSON
4. **Config shell creation** — verify empty config with fleet metadata persists
5. **Machine registration** — verify machine records are persisted in fleet state
6. **Discovery scan** — verify scan results are cached in fleet metadata
7. **Fresh host building** — verify inventory host entry is synthesized correctly
8. **Gap fill** — verify fresh instances are added to inventory from machine records
9. **Full onboarding flow** — verify complete orchestration with real SSH connections
10. **Zero-host shell** — verify config shell validity without inventory hosts

### Phases 5-7

11. **Mode selection gate** — verify simple/advanced mode selection with exact-word confirmation
12. **Advanced instance counts** — verify capacity math against real machine specs
13. **Advanced gap fill** — verify multi-instance expert-mode creation with unique runtime names
14. **EE_ID template** — verify edge_node.service.j2 uses logical name with fallback
15. **Unified registration** — verify standalone register_machine delegates to shared helper
16. **Dead code removal** — verify node-first methods are removed from codebase
