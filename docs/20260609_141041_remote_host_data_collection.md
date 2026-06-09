# Remote Host Data Collection Runbook

Date: 2026-06-09

This document explains how to collect operational data from remote hosts managed
by `r1setup`. It is intentionally conservative: collect read-only snapshots
first, do not expose new public ports by default, and do not copy secrets into
long-lived artifacts.

## Safety Rules

- Use the active r1setup inventory instead of hand-maintaining a second host
  list.
- Prefer existing read-only r1setup playbooks before writing custom remote
  commands.
- Do not collect `.env`, private keys, API tokens, wallet material, or full
  Docker inspect output unless the destination is access-controlled.
- Do not publish node_exporter, Docker API, or application metrics on public
  interfaces. Use SSH tunnels, a private network, or a controlled pull path.
- For expert-mode or multi-instance hosts, service names, volume paths, and
  metadata paths may be instance-specific. Check inventory host vars instead
  of assuming `edge_node.service` and `/var/cache/edge_node`.

## Locate The Active Inventory

Installed r1setup keeps the active collection and inventory here:

```bash
COLLECTION="$HOME/.ratio1/ansible_config/collections/ansible_collections/ratio1/multi_node_launcher"
INV="$COLLECTION/hosts.yml"

test -e "$INV"
readlink "$INV" 2>/dev/null || true
```

The symlink target usually points into:

```text
~/.ratio1/r1_setup/configs/<config-name>.yml
```

Check reachability:

```bash
ansible all -i "$INV" -m ping
```

## Built-In Read-Only Collection

For service status:

```bash
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$HOME/.ratio1/r1_setup/collections/$RUN_ID"
mkdir -p "$OUT"

ansible-playbook -i "$INV" "$COLLECTION/playbooks/service_status.yml" \
  | tee "$OUT/service_status.txt"
```

For node identity and node info:

```bash
ansible-playbook -i "$INV" "$COLLECTION/playbooks/get_node_info.yml" \
  | tee "$OUT/get_node_info.txt"
```

These playbooks understand the r1setup inventory better than ad hoc commands.
Use them as the baseline for fleet snapshots.

## Host Snapshot With Ad Hoc Ansible

Use shell snapshots for host-level context that is not covered by existing
playbooks:

```bash
ansible all -i "$INV" -m shell -a '
set -u
echo "hostname=$(hostname 2>/dev/null || true)"
echo "kernel=$(uname -a 2>/dev/null || true)"
echo "uptime=$(uptime -p 2>/dev/null || true)"
echo "disk_root=$(df -h / 2>/dev/null | tail -1 || true)"
echo "docker_version=$(docker --version 2>/dev/null || true)"
docker ps --format "container={{.Names}} image={{.Image}} status={{.Status}}" 2>/dev/null || true
' | tee "$OUT/host_snapshot.txt"
```

Keep this command read-only. If you need package installation, service
changes, or persistent agents, write a playbook and review it as a mutating
operation.

## Fetch Selected Files

For standard-mode Edge Node hosts, these files are usually safe and useful:

```bash
mkdir -p "$OUT/fetched"

ansible all -i "$INV" -m fetch -a \
  "src=/var/cache/edge_node/_local_cache/_data/local_info.json dest=$OUT/fetched flat=no fail_on_missing=no"

ansible all -i "$INV" -m fetch -a \
  "src=/var/cache/edge_node/_local_cache/_data/r1setup/metadata.json dest=$OUT/fetched flat=no fail_on_missing=no"
```

For expert-mode hosts, inspect the active inventory for the instance-specific
volume path first:

```bash
python3 - <<'PY'
import yaml
from pathlib import Path

inv = yaml.safe_load(Path.home().joinpath(
    ".ratio1/ansible_config/collections/ansible_collections/ratio1/multi_node_launcher/hosts.yml"
).read_text())
hosts = inv.get("all", {}).get("children", {}).get("gpu_nodes", {}).get("hosts", {})
for name, data in sorted(hosts.items()):
    print(name, data.get("mnl_service_name"), data.get("mnl_docker_volume_path"))
PY
```

Do not fetch `.env` files into shared artifact folders. They may contain
credentials.

## Collect Textfile Metrics From Hosts

If a host already runs a loopback-only node_exporter with a textfile collector,
pull the Ratio1 metrics through SSH/Ansible without exposing port `9100`:

```bash
ansible all -i "$INV" -m shell -a '
curl -fsS http://127.0.0.1:9100/metrics 2>/dev/null \
  | grep -E "^(r1_|node_)" \
  || true
' | tee "$OUT/node_exporter_metrics.txt"
```

For continuous collection, run Prometheus on the controller or an internal
monitoring host and scrape each remote loopback exporter through one of:

- SSH local forwards from the Prometheus host
- a private VPN or private VPC interface
- a host-local push/shipper that has explicit retry and auth semantics

Avoid `--web.listen-address=0.0.0.0:9100` on public hosts.

## Suggested Artifact Layout

Use one UTC run id per collection:

```text
~/.ratio1/r1_setup/collections/YYYYMMDDTHHMMSSZ/
  service_status.txt
  get_node_info.txt
  host_snapshot.txt
  node_exporter_metrics.txt
  fetched/
```

Before sharing artifacts, scan for obvious secrets:

```bash
grep -RInE 'password|secret|token|private_key|BEGIN .*PRIVATE' "$OUT" || true
```

If the grep finds real secrets, redact them before moving the folder into a
ticket, repo, or shared drive.

## When To Add A Playbook

Turn the collection into a playbook when:

- the command will be reused
- the output needs a stable schema
- collection needs `become: true`
- files must be fetched from instance-specific paths
- the task will run against production fleets

Use `gather_facts: false` unless full Ansible facts are explicitly needed.
Keep read-only collection separate from mutating installation or remediation
playbooks.
