# AGENTS.md

This file is the durable, long-term operating memory for future agents working in this repository.

Rules for maintaining this file:
- Keep the stable reference sections current when workflows, repo structure, execution paths, or conventions materially change.
- Keep `Memory Log (append-only)` append-only. Never rewrite or delete old log entries.
- If an older memory entry is wrong, add a new entry that references the older one and corrects it.
- Only record critical or fundamental project changes and horizontal insights that matter across future tasks.

## Repository Purpose

This repository serves two linked purposes:
- end-user installation and operation of the `r1setup` CLI for Ratio1 multi-node deployment
- source for the `ratio1.multi_node_launcher` Ansible collection under `mnl_factory/`

The CLI and the collection are versioned and released separately.

## How To Run

End-user install:
```bash
bash install.sh
```

Network install:
```bash
curl -sSL https://raw.githubusercontent.com/Ratio1/r1setup/refs/heads/main/install.sh | bash
```

Run the CLI after installation:
```bash
r1setup
```

Manual collection use:
```bash
cd mnl_factory
ansible-galaxy collection install -r requirements.yml
ansible-playbook -i inventory/hosts.yml playbooks/site.yml
```

Build the collection locally:
```bash
cd mnl_factory
ansible-galaxy collection build --force
```

## How To Test

Primary CLI test entrypoints:
```bash
cd mnl_factory/scripts
python3 test_r1setup.py
python3 -m unittest discover tests
python3 -m py_compile r1setup
```

Targeted SSH key management tests:
```bash
cd mnl_factory/scripts
python3 -m unittest tests.test_ssh_key_manager
python3 -m unittest tests.test_structural_invariants
```

Notes:
- `mnl_factory/scripts/test_r1setup.py` is the compatibility runner for the modular `tests/` package.
- Prefer the modular test suite over ad hoc script execution.

## Repo Map

Top level:
- `install.sh`: bootstrap installer that downloads `r1setup` scripts into `~/.ratio1/r1_setup` and symlinks `/usr/local/bin/r1setup`
- `README.md`: root project overview
- `docs/`: dated operational/design notes
- `.github/workflows/`: release and publish automation

Ansible collection:
- `mnl_factory/galaxy.yml`: collection metadata and collection version source of truth
- `mnl_factory/requirements.yml`: external Ansible collection dependencies
- `mnl_factory/playbooks/`: operational playbooks including deploy, status, SSH key management, and SSH hardening
- `mnl_factory/roles/`: Ansible roles for prerequisites, Docker, NVIDIA GPU setup, and final setup
- `mnl_factory/group_vars/`: collection variables; `mnl.yml` contains the service-unit version marker `mnl_service_version`
- `mnl_factory/inventory/`: manual inventory examples

CLI:
- `mnl_factory/scripts/r1setup`: main CLI implementation
- `mnl_factory/scripts/ver.py`: CLI version source of truth
- `mnl_factory/scripts/update.py`: CLI updater support
- `mnl_factory/scripts/1_prerequisites.sh`: local machine prerequisite installer
- `mnl_factory/scripts/2_ansible_setup.sh`: local Ansible collection setup under `~/.ratio1/ansible_config`
- `mnl_factory/scripts/README_r1setup.md`: CLI/operator-focused documentation
- `mnl_factory/scripts/tests/`: modular CLI test suite

## Versioning And Release Conventions

CLI version:
- source of truth: `mnl_factory/scripts/ver.py`
- fallback copy must match: `CLI_VERSION = "..."` inside `mnl_factory/scripts/r1setup`
- automatic CLI release workflow trigger: changes to `mnl_factory/scripts/ver.py` on `main`

Collection version:
- source of truth: `mnl_factory/galaxy.yml`
- automatic Galaxy publish workflow trigger: changes to `mnl_factory/galaxy.yml` on `main`, but publish proceeds only if the `version` field changed

Release workflows:
- `.github/workflows/release.yml`: CLI asset release workflow
- `.github/workflows/publish-ansible-galaxy.yml`: collection build/publish workflow

## Conventions

Code and repo conventions:
- Treat `mnl_factory/scripts/r1setup` as the primary operational surface for end-user behavior changes.
- Keep inventory mutation in the CLI layer and remote-state mutation in Ansible playbooks.
- Keep `mnl_service_version` in `mnl_factory/group_vars/mnl.yml` as the version marker for `edge_node.service.j2`; it must not replace `mnl_app_env` as the Docker image tag source.
- Keep per-node applied service-unit state in inventory host metadata under `r1setup_service_file_version`; missing values must be normalized to `v0`.
- When refreshing node status, prefer updating `r1setup_service_file_version` from live remote data using non-fatal fallbacks instead of trusting local state alone.
- For SSH key management, use the state model already present in `r1setup` instead of inventing parallel metadata.
- Standard-mode machines keep the existing global helpers such as `get_logs` and `get_node_info`; expert-mode machines must use the `r1service <service> <action>` dispatcher plus per-instance helper registry files under `/var/lib/ratio1/r1setup/helpers/`.
- Prefer generated execution inventories for CLI-driven Ansible operations. The settled Phase 5 split is: machine preparation runs from `playbooks/prepare_machine.yml`, instance runtime application runs from `playbooks/apply_instance.yml`, and the CLI should avoid driving multi-instance operations directly from the full persisted `hosts.yml` when a narrowed temp inventory is more accurate.
- Update docs when user-visible menus, workflows, triggers, or safety guarantees change.
- Prefer adding focused unit tests in `mnl_factory/scripts/tests/` for new logic.

Documentation conventions:
- Root `README.md` is for project need/purpose, quick usage, and technical orientation.
- `mnl_factory/scripts/README_r1setup.md` is for CLI/operator guidance.
- `docs/` stores dated design or operational notes.

## Mandatory BUILDER-CRITIC Loop

For every meaningful modification, future agents must perform and document this loop in their own working notes / user updates:

1. BUILDER
- State the intent.
- State the exact files/surfaces being changed.
- State the expected behavior change.

2. CRITIC
- Adversarially try to break the proposal.
- Check assumptions, regressions, edge cases, security impact, rollout risk, migration impact, docs impact, and missing tests.
- Call out stale-version, workflow-trigger, secret-handling, and lockout risks explicitly when relevant.

3. BUILDER RESPONSE
- Refine the change in response to the critique.
- State what was added/changed to address the critique.
- List verification commands.
- Record actual verification results.

Minimum required critic topics when relevant:
- backward compatibility
- state migration correctness
- release/publish trigger correctness
- secret handling
- remote lockout or rollback safety
- documentation and test coverage

## Pitfalls

- `mnl_factory/build.sh` is a local helper, not a CI-safe publish path. It expects `.env` and echoes the token; do not reuse it in GitHub Actions.
- The CLI release workflow will fail if `ver.py` and the fallback `CLI_VERSION` inside `r1setup` drift.
- The Galaxy publish workflow is triggered by `mnl_factory/galaxy.yml`, not tags.
- The CLI release workflow is triggered by `mnl_factory/scripts/ver.py`, not tags.
- SSH password hardening changes remote sshd policy for the machine, not only `r1setup`. Treat it as a lockout-risk operation.
- Real host integration testing is still required for SSH hardening. The repo currently has unit and CLI regression coverage, not a disposable-host end-to-end SSH daemon test harness.
- `mnl_factory/galaxy.yml` still contains placeholder `documentation`, `homepage`, and `issues` values. Do not assume those URLs are authoritative without fixing them.

## Memory Log (append-only)

- 2026-03-12T12:09:21+02:00 | Established repo-local long-term memory in this file. Stable sections now track execution, tests, repo map, release triggers, conventions, and pitfalls. Future agents must preserve append-only memory semantics.

- 2026-03-12T12:09:21+02:00 | SSH key management Phase 1 and Phase 2 are implemented in `mnl_factory/scripts/r1setup` and related playbooks. Key points:
  - inventory/auth migration is separate from remote sshd hardening
  - key migration requires controller-side verification before switching inventory auth
  - password-auth hardening is gated to verified hosts and uses rollback logic
  - operator docs exist in `mnl_factory/scripts/README_r1setup.md` and `docs/20260312_120330_r1setup_ssh_operations.md`

- 2026-03-12T12:09:21+02:00 | Modular CLI tests live in `mnl_factory/scripts/tests/`; `mnl_factory/scripts/test_r1setup.py` is only a compatibility runner. Preferred verification commands are `python3 -m unittest discover tests` and targeted `python3 -m unittest ...`.

- 2026-03-12T12:09:21+02:00 | Release/publish automation was split by source of truth:
  - CLI release: `.github/workflows/release.yml`, triggered by `mnl_factory/scripts/ver.py` version changes
  - Collection publish: `.github/workflows/publish-ansible-galaxy.yml`, triggered by `mnl_factory/galaxy.yml` version changes

- 2026-03-12T12:09:21+02:00 | Critical horizontal pitfall discovered twice during workflow work: `ver.py` and the fallback `CLI_VERSION` in `r1setup` drift easily. Structural test coverage now exists to catch this mismatch early. Any CLI version bump must keep both values aligned.

- 2026-03-16T23:43:36+02:00 | Service image selection now has an explicit top-level override in `mnl_factory/group_vars/mnl.yml`: `mnl_service_version`. It defaults to `{{ mnl_app_env }}` so the existing mainnet/testnet/devnet workflow still works, and `mnl_docker_image_url` must continue to derive its tag from `mnl_service_version`.

- 2026-03-16T23:43:36+02:00 | Correction to the previous 2026-03-16 entry: `mnl_service_version` is for tracking the generated `edge_node.service` template revision, not for selecting the Docker image tag. `mnl_docker_image_url` must continue to derive its tag from `mnl_app_env`, and `edge_node.service.j2` should embed `mnl_service_version` as a header comment.

- 2026-03-16T23:43:36+02:00 | `r1setup` now persists per-node applied service-unit state in inventory as `r1setup_service_file_version`. Missing values are treated as `v0`, the collection default `mnl_service_version` starts at `v1`, and successful deploy/customize-service operations should stamp selected hosts with the current service version.

- 2026-03-16T23:43:36+02:00 | Service status refresh should also reconcile `r1setup_service_file_version` from the remote host when possible. The preferred marker is `R1SETUP_SERVICE_FILE_VERSION` in `edge_node.service`, with fallbacks through `systemctl show`, `systemctl cat`, and direct file reads. Retrieval must be best-effort and must not break status checks.

- 2026-03-17T00:31:37+02:00 | `Node Status & Info` (main menu option 4) is the settled diagnostics flow. The initial screen shows the short status summary plus inline service-version health for each node, highlights outdated service versions in red, and ends with explicit recommended actions listing which nodes require a service update. After that, the user may opt into a separate detailed per-node view; that detailed view may call `get_node_info` on demand and should keep upgrade-relevant context such as tracked/target service version and update guidance visible.

- 2026-03-17T01:15:00+02:00 | Service-file updates are now a normal operator workflow under `Operations -> Update Service File`. That flow should preselect nodes whose `r1setup_service_file_version` differs from `mnl_service_version`, reuse the service re-template playbook, best-effort refresh live status afterward, and keep `Advanced -> Customize Service` focused on manual override management rather than routine service-version rollout.

- 2026-03-17T01:34:00+02:00 | On CLI startup, after the normal one-time status refresh path, `r1setup` should surface outdated deployed service files immediately and offer a direct update prompt. That startup guidance must reuse stored/live `r1setup_service_file_version` data, avoid extra status fetches, skip undeployed/deleted nodes, and point to `Operations -> Update Service File` when the user defers.

- 2026-03-17T02:02:00+02:00 | Edge Node deployments now carry launcher-owned runtime metadata in a dedicated JSON file at `/var/lib/ratio1/r1setup/edge_node/metadata.json`, mounted read-only into the container at `/run/r1setup/metadata.json` via `R1SETUP_METADATA_PATH`. Render that file from the same apply path as `edge_node.service`, include service file version plus CLI/collection version and last applied action, and update/remove it whenever the service definition is applied/deleted.

- 2026-03-17T02:22:00+02:00 | Correction to the previous 2026-03-17 metadata-path entry: runtime metadata now lives inside the existing Edge Node persistent volume under `{{ mnl_docker_volume_path }}/_data/r1setup/metadata.json` and is read in-container via `{{ mnl_docker_persistent_folder }}/_data/r1setup/metadata.json`. Do not add a second dedicated Docker mount for the metadata file in this design; keep only `R1SETUP_METADATA_PATH`.

- 2026-03-17T23:01:53+02:00 | Phase 4 helper strategy is implemented. The stable rule is:
  - standard topology keeps machine-global helpers like `get_logs`, `get_node_info`, and `restart_service`
  - expert topology uses `/usr/local/bin/r1service <service> <action>`
  - per-instance helper registry files live under `/var/lib/ratio1/r1setup/helpers/<service>.env`
  - `r1setup` must reject mixed standard/expert helper semantics on one physical machine instead of guessing
  - topology-aware helper command selection is now used by the `get_node_info.yml` playbook and the CLI log-streaming paths

- 2026-03-17T23:15:42+02:00 | Phase 5 generated execution inventory support is implemented. The stable rule is:
  - CLI-driven Ansible operations should prefer temp generated inventories scoped to the selected machines or instances
  - generated execution inventories must enrich hosts with resolved runtime names, helper-mode fields, metadata paths, and derived volume/base-folder values
  - deployment is now split in the CLI into `prepare_machine.yml` followed by `apply_instance.yml`
  - one deploy operation should prepare each unique machine at most once, then apply instance runtime only to instances whose machine preparation succeeded
