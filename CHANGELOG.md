# Changelog

All notable changes to `r1setup` and the `ratio1.multi_node_launcher`
Ansible collection are recorded here. The CLI version (`scripts/ver.py`)
and the collection version (`mnl_factory/galaxy.yml`) track separate
lineages and may bump independently.

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
