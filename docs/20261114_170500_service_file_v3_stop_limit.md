# Service File v3: Stop Limit And needrestart Deferral

Date: 2026-11-14

Status: **prepared, not released and not applied to any host.** The collection version is set at
release; nothing below has been run against a machine.

This note covers what service file `v3` changes, the reasons for it, and how an operator
applies and verifies it. `v3` has two parts: the stop limit of the unit, and a needrestart file that
is rendered together with the unit.

## Stop limit

### Problem

- Service files `v1` and `v2` stop the node with `docker stop -t 20`: SIGTERM, then SIGKILL 20 s
  later. They set no `TimeoutStopSec` and no `--stop-timeout`.
- Since node core 7.7.357 the node handles SIGTERM and closes in order: it stops its plugins and
  container apps and saves its state. That close does not fit in 20 s: where it was measured, a
  complete close took **61-94 s** to process exit. A stop that comes from the host therefore ends
  in SIGKILL part-way through the close, and the app containers the node runs are most likely
  stopped with it, without their own orderly stop.
- If the container runtime is restarted just before the node is stopped, the stop signal cannot be
  delivered and the node is killed after 2 s, whatever the grace.

### Change

`roles/setup/templates/edge_node.service.j2`, with `mnl_service_version: "v3"`:

| Setting | v2 | v3 |
|---|---|---|
| `ExecStop` | `docker stop -t 20` | `docker stop -t 120` |
| `ExecStartPre` (leftover container) | `docker stop -t 20` | `docker stop -t 120` |
| `TimeoutStopSec` | not set (systemd default, 90 s) | `150` |
| `docker run` | no stop timeout | `--stop-timeout 120` |
| `After=` | `docker.service` | `docker.service containerd.service` |

- 150 s for the unit is 30 s more than the 120 s the node gets, so systemd never ends the stop
  command first.
- `--stop-timeout` covers a stop that does not come from the unit: `docker stop` or
  `docker restart` without `-t`, and a daemon shutdown.
- `After=containerd.service` also sets the stop order when both units are stopped together: at a
  host shutdown, and in a command that names the node's unit before the runtime. `systemctl` sends
  one request per unit in the order of the command line, so a command that names the runtime first
  restarts it at once; the ordering does not help there. The needrestart file described below
  removes the usual source of such a command.
- A unit that is still `v1` also gets what `v2` introduced when it is updated: the restart
  watchdog (the host reboots when the unit is started 30 times within 1800 s) and a 60 s delay
  before each restart of the unit (`v1`: systemd's 100 ms default). Set `mnl_service_restart_sec`
  for a host where that delay is not wanted.
- The numbers are fixed in the template; there is no new variable.

### What an operator sees

- `Node Status & Info` and the start-up check report every deployed `v1` or `v2` unit as outdated
  and offer `Operations -> Update Service File`. **A unit changes only when r1setup applies it.**
- The update re-renders the unit and **restarts the node once**. After `daemon-reload` the running
  service already stops with the new command, so this restart is the first one with 120 s.
- A stop or restart can now take up to 120 s (150 s at most) instead of 20 s. A node older than core
  7.7.357 ignores SIGTERM and always takes the full 120 s.
- The CLI step that stops and removes a service over SSH (the target cleanup of a migration
  rollback, `Remove the node copy left on the target`, the source cleanup of `Finalize Migration`)
  now waits at least 180 s. Before, it waited `connection_timeout x 3`, 90 s by default: a node that
  took longer to stop made the step report a failed cleanup while the node was still closing, and
  a rollback then asked whether to restart the source anyway, which can run the node twice. **This
  fix is in the CLI, not in the collection: release the CLI no later than the collection that
  carries `v3`.**

### Apply and verify

1. Update r1setup so that the collection with service file `v3` is installed, then start `r1setup`.
   `Node Status & Info` shows `service v2 / target v3 [UPDATE]` for deployed nodes.
2. `Operations -> Update Service File`, select the nodes, confirm. Do a few nodes first; each
   selected node restarts.
3. `Node Status & Info` shows `service v3 / target v3 [OK]`.
4. On a host (read-only):

   ```bash
   systemctl show edge_node.service -p TimeoutStopUSec -p ExecStop -p After
   docker inspect -f '{{.Config.StopTimeout}}' edge_node
   ```

   Expect `TimeoutStopUSec=2min 30s`, `ExecStop` with `docker stop -t 120 edge_node`, `After=`
   listing `containerd.service`, and `120` from `docker inspect`. Use the instance's own service
   and container names on multi-instance hosts.
5. At the next stop of that node: `journalctl -u docker | grep "failed to exit within"` shows no
   new line for the container, and the node log ends with its normal end-of-close lines.

### Rollback

Install the previous collection version and run `Operations -> Update Service File` again (the
target version is then `v2`), or keep `v3`: the only cost of `v3` is a longer wait when a node does
not close by itself.

### Not covered

- A node whose broker is unreachable while it stops, or a host with several container apps (each
  may take up to 45 s to stop), can need more than 120 s.
- Nodes installed without r1setup keep the unit they have.

## needrestart deferral

### Problem

- On Ubuntu, unattended-upgrades installs library updates in a daily window, and needrestart then
  restarts every unit whose processes map a replaced library. For the node unit that is only the
  docker client of the unit: the node runs in a container on the libraries of its image, so the
  restart patches nothing.
- An upgrade of a widely used library, such as the C library, therefore restarts the node on every
  host that installs it, each in its own upgrade window.
- Each such restart also runs the unit's image pull, so an operating-system update deploys whatever
  the image tag points to at that moment.

### Change

The service definition (`roles/setup/tasks/render_edge_node_definition.yml`) now also renders
`/etc/needrestart/conf.d/50-r1setup-<service>.conf` from
`roles/setup/templates/needrestart-edge-node.conf.j2`:

```perl
$nrconf{override_rc}{'^edge_node\.service$'} = 0;
```

- One file per service name, so several instances on one machine each defer their own unit.
- The line adds one pattern to needrestart's table and keeps the stock entries. `0` means:
  never restart this unit automatically, list it under "Service restarts being deferred".
- The file is written only on a host that has `/etc/needrestart/conf.d` (needrestart installed),
  and it is compiled with `perl -c` before it is installed.
- `Delete Edge Node` removes the file with the unit.
- Nothing else is deferred: host daemons such as `containerd` use the host libraries and are still
  restarted.

### Apply and verify

The file comes with the unit: `Operations -> Update Service File` (or a deployment) installs it.
On a host (read-only):

```bash
cat /etc/needrestart/conf.d/50-r1setup-edge_node.conf
perl -c /etc/needrestart/conf.d/50-r1setup-edge_node.conf
```

After the next library upgrade, `/var/log/unattended-upgrades/unattended-upgrades-dpkg.log` lists
the unit under "Service restarts being deferred" and the container's `StartedAt` is unchanged.

To see the full effect before relying on it, use a disposable Ubuntu 24.04 host, not a production
node: `apt-get install --reinstall libc6` must list the unit as deferred and leave the container
running; with the file removed the restart must happen.

### Rollback

Delete the file. needrestart reads its configuration at every run.

### Not covered

- A host where needrestart is installed after the last service-file update gets the file at the
  next update.
- A deferred unit keeps its old docker client until its next restart; `needrestart -b` lists what
  is pending.
- Hosts installed without r1setup: see the FAQ line in `mnl_factory/scripts/README_r1setup.md`.
- A migration's target cleanup does not remove the file; it names a unit that no longer exists and
  matches nothing.
