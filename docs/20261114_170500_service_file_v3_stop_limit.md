# Service File v3: Stop Limit

Date: 2026-11-14

Status: **prepared, not released and not applied to any host.** The collection version is set at
release; nothing below has been run against a machine.

This note covers what service file `v3` changes, the measurements behind it, and how an operator
applies and verifies it.

## Stop limit

### Problem (measured 2026-11-13 and 2026-11-14)

- Service files `v1` and `v2` stop the node with `docker stop -t 20`: SIGTERM, then SIGKILL 20 s
  later. They set no `TimeoutStopSec` and no `--stop-timeout`.
- Since node core 7.7.357 the node handles SIGTERM and closes in order: it stops its plugins and
  container apps and saves its state. That close does not fit in 20 s. **0 of 6** observed stops
  that came from the host finished (3 of them on worker nodes, where the customer app containers
  were killed with the node); complete closes took **61-94 s** to process exit where they were
  measured, and 12-65 s on workers before that release.
- In 1 of the 6 stops the container runtime restarted in the same systemd transaction; the stop
  signal could not be delivered and the node was killed after 2 s.

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
- `After=containerd.service` also sets the stop order: the node is stopped before the container
  runtime when both stop in one transaction.
- The numbers are fixed in the template; there is no new variable.

### What an operator sees

- `Node Status & Info` and the start-up check report every deployed `v1` or `v2` unit as outdated
  and offer `Operations -> Update Service File`. **A unit changes only when r1setup applies it.**
- The update re-renders the unit and **restarts the node once**. After `daemon-reload` the running
  service already stops with the new command, so this restart is the first one with 120 s.
- A stop or restart can now take up to 120 s (150 s at most) instead of 20 s. A node older than core
  7.7.357 ignores SIGTERM and always takes the full 120 s.
- Rollback of a migration removes the node copy on the target with a command that waits
  `connection_timeout x 3` (90 s by default). If the target node needs longer than that to stop, the
  step reports a timeout; the stop itself continues on the host and `Rollback Migration` can be
  retried. Raising `Settings -> Connection Timeout` to 60 s avoids it.

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
