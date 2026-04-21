# Remote Command Fallbacks

Verbatim copies of the read-only command scripts from
`ratio1/edge_node/cmds/`. Each script is a thin `cat <FILE>` wrapper
around a JSON/data file inside the edge_node container.

## Why bundle them here

The edge_node Docker image ships these scripts at
`/usr/local/bin/<name>` *inside* the container. r1setup's setup role
then installs a **host-side** wrapper at `/usr/local/bin/<name>` that
runs `docker exec -i <container> bash -lc "<name>"`.

If the host-side wrapper is missing (setup role didn't finish, host
was manually provisioned, or the install was interrupted), r1setup
playbooks that rely on the wrapper fail with `command not found`.

Having the originals mirrored in this repo gives ansible playbooks a
single source of truth for:

1. The *inside-container file path* each command cats. Playbooks can
   `lookup('file', ...)` + regex to extract the `FILE=...` line and
   build an equivalent `docker exec -i <container> bash -lc 'cat
   <file>'` fallback — no host-side wrapper required.
2. A stock copy of each script that a future "self-heal" task could
   push to `/usr/local/bin/<name>` on the host when the wrapper is
   missing.

## Invariants

The scripts here are **read-only** by intent. Each does `cat $FILE`
(or the equivalent) without mutating remote state. Do not add
destructive helpers to this directory — those live in the setup role.

## Keeping in sync with edge_node

When edge_node's `cmds/` changes a file path or adds a new read-only
helper, copy the updated script into this directory in the same PR.
The playbooks that consume these scripts hold the contract; they
assume the `FILE=...` line is present near the top.

## Current contents

- `get_node_info`       — `/edge_node/_local_cache/_data/local_info.json`
- `get_node_history`    — `/edge_node/_local_cache/_data/local_history.json`
- `get_e2_pem_file`     — `/edge_node/_local_cache/_data/e2.pem`
- `get_config_app`      — `/edge_node/_local_cache/_data/box_configuration/config_app.txt`
- `get_startup_config`  — `/edge_node/_local_cache/config_startup.json`
- `get_allowed`         — `/edge_node/_local_cache/authorized_addrs`
