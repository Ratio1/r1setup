# Changelog

All notable changes to `r1setup` and the `ratio1.multi_node_launcher`
Ansible collection are recorded here. The CLI version (`scripts/ver.py`)
and the collection version (`mnl_factory/galaxy.yml`) track separate
lineages and may bump independently.

## CLI 1.9.0 / Collection 1.5.0 — 2026-04-24

Minor release covering five themes from the `refactor/config-management`
branch: a Configuration Management refactor, discovery/import hardening,
the first-class Backup Node Data action, operational fixes, and
Ansible 2.24 readiness.

### Added

- **Backup Node Data** (Advanced Menu → 💾 DATA → 7). Streams a
  `tar.gz` of the selected instance's volume to the operator's local
  filesystem via a direct SSH pipe (no Ansible `fetch`, no remote
  tmp staging). Defaults to stopping the node during archive for
  file-consistency safety and restarts it in a `finally` block. Does
  a pre-flight `du -sb` vs local `shutil.disk_usage` check with 10%
  headroom, cleans up partial archives on failure or `KeyboardInterrupt`,
  and reports the archive's size + SHA256 on success.
- **Env mismatch prompt at discovery import.** When a discovered
  service's environment differs from the active config's env, the
  operator is now prompted to either Abort or Switch+Import — no more
  silent filtering that led to containers stacking on the wrong
  network. Env is surfaced via a short badge (`env=devnet (meta)` etc.)
  at every candidate list. See `_format_env_badge` and
  `_prompt_env_mismatch_resolution` in the r1setup script.
- **Config `mode` field (schema v2).** Each configuration now carries
  an explicit `simple` or `advanced` mode, preserved on import +
  restore (legacy configs are migrated on load). Simple mode hides
  fleet machine-level controls and offers a one-way upgrade to
  advanced. Advanced mode exposes Register Machine / Fleet Summary.
- **`--debug-ansible` CLI flag** for verbose Ansible tracing during
  deploys — helpful when debugging a stubborn host without cluttering
  normal runs.
- **Read-only `remote_cmds/` bundle** (`get_allowed`, `get_config_app`,
  `get_e2_pem_file`, `get_node_history`, `get_node_info`,
  `get_startup_config`) shipped with the collection as a fallback
  source when a host's installed wrapper is missing or older than
  the edge_node CLI expects.

### Changed

- **Configuration / Deployment / Operations / Advanced menus** render
  with emoji-grouped sections; the redundant Name banner below the
  `=== Menu ===` header is gone. Manage Configurations is a
  list-then-action picker, not a flat numbered list.
- **Discovery** runs host probes + specs probes in parallel, supports
  multi-select import, and the discovery image regex skips commented
  lines and matches the GPU image variant suffix.
- **Deployment status reconciliation** now syncs the per-config
  metadata file alongside `active_config.json`, so the status flag
  does not flip back to `deleted` on the next config save.
- **Migration probe** hardened for very outdated fleets that lack
  modern metadata.
- Install phases use `playbook_timeout` as a floor; real-work
  playbooks get a 30-minute `playbook_timeout` so long driver
  installs do not hit the default connection timeout.
- **Reuse credentials path** no longer re-prompts for the username
  after the operator confirms reuse.

### Fixed

- Node Status filter used the wrong dict key (stale field lookup
  after the schema change) and the Node Status view now shows only
  machines that have instances.
- `get_node_info` falls back to `docker exec` when the host wrapper
  is missing, and failures are surfaced instead of swallowed silently.
- Main menu entries are gated when no active config exists, and the
  no-active state is cleaned up on deleting the active config.
- SSH discovery probe is hardened against `yes/no/[fingerprint]`
  host-key prompts on fresh machines.

### Ansible 2.24 readiness

- 80 occurrences across 7 files migrated from top-level `ansible_*`
  facts (deprecated via `INJECT_FACTS_AS_VARS`) to
  `ansible_facts['...']`. Mechanical rewrite, no logic changes.
  Removes the deprecation warnings during installs and unblocks the
  eventual ansible-core 2.24 upgrade.

## CLI 1.8.1 — 2026-04-20

Patch release. CLI-only — no collection changes, Galaxy stays at 1.4.0.

### Fixed

- Self-heal `<collection>/hosts.yml` symlink on startup. `ensure_active_configuration()`
  now reconciles the two sources of truth about the active fleet
  (`active_config.json` + `configs/<name>.yml` vs the runtime symlink) before
  any gating check. Fixes the false-positive "No nodes configured!" error
  that hit when the symlink was missing despite a valid active config (fresh
  dev HOME, deleted symlink, `<collection>` dir rebuilt from template, etc.).
  Idempotent and cheap.

## CLI 1.8.0 / Collection 1.4.0 — 2026-04-19

Mixed CPU/GPU fleets with per-host install tracking.

### Added

- **Three install modes**, chosen from the deployment menu:
  - **Install CPU Nodes** — deploys the CPU image
    (`ratio1/edge_node:{env}`), skips all NVIDIA setup.
  - **Install GPU Nodes (r1setup manages drivers)** — runs the
    `nvidia_gpu` role to install NVIDIA drivers + the NVIDIA Container
    Toolkit, then deploys the GPU image (`ratio1/edge_node_gpu:{env}`).
  - **Install GPU Nodes (user-managed drivers)** — skips the
    `nvidia_gpu` role entirely, runs a preflight `nvidia-smi` check
    on the target host, and deploys the GPU image. r1setup does NOT
    touch NVIDIA packages on the host in this mode.
- **Per-host install tracking** persisted in `hosts.yml` for each host:
  last successful variant, driver owner (r1setup / user / n/a),
  timestamp, collection version; plus last-attempted variant, owner,
  timestamp, and result (success / failed). Visible in the
  host-selection menu as `GPU (r1) • 2026-03-12` / `CPU • 2026-02-01`
  / `—  • never`, with a "last attempt" column highlighting failures
  or divergence.
- **Image Summary** block after each successful deploy reads the new
  fetched metadata JSON and lists the image variant + URL per host.
- **Mode-specific failure hints** for GPU deploys that had failed hosts:
  Mode 2 points at the driver-cleanup rescue and CPU recovery path;
  Mode 3 explicitly states that r1setup did not touch drivers and asks
  the user to repair or re-run with driver management enabled.

### Changed

- GPU-install failures no longer silently fall back to CPU. Failed
  hosts are listed for retry in the final report; surviving hosts
  continue to deploy normally.
- Docker image name is now variant-aware via new group_vars
  `mnl_docker_image_name_cpu` / `mnl_docker_image_name_gpu`. CLI
  passes the variant via `mnl_image_variant_cli`; host_vars can pin
  `mnl_image_variant: gpu|cpu` to override the CLI choice on a per-host
  basis. User overrides of `mnl_docker_image_url` via CUSTOMIZABLE_VARS
  still win (Ansible extra-vars beat group_vars).
- `site.yml` and `prepare_machine.yml` converted to `tasks:` structure
  with `block/rescue` around the `nvidia_gpu` role. Mode-2 failures
  run `apt autoremove nvidia*` cleanup and then re-raise (no silent
  fallback). Mode 3 skips the block entirely — user-managed drivers
  are never touched.
- Per-host metadata is now fetched back to the controller at
  `/tmp/r1setup-fetched/{host}.json` so the CLI reads structured per-host
  data instead of parsing Ansible stdout.
- Deployment menu labels: "Deploy with GPU" → **"Install GPU Nodes"**;
  "Deploy CPU Only" → **"Install CPU Nodes"**.

### Removed

- Fleet-level `last_deployment_type` config field (it lied on mixed
  fleets). Stale values are popped from metadata on load. Replaced by a
  per-host variant rollup `GPU: N, CPU: M, Never: K` derived from
  `r1setup_last_install_variant`.

### Migration

- Old inventories gain the eight new per-host install-tracking fields
  as `None` on first load under 1.8.0; the menu renders them as
  `— • never` until the first successful install populates them.
- `last_deployment_type` is removed on load; callers should derive the
  variant summary from per-host state.
