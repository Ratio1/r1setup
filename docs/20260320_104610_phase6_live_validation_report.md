## Phase 6 Live Validation Report

Timestamp: `2026-03-20T10:46:10+02:00`

Scope:
- final live validation gate for the remaining discovery/import work
- real hosts:
  - `35.228.69.214` (`r1-vi-g1`)
  - `34.88.90.109` (`r1-vi-g2`)
- repo-local `r1setup` workflow via `scripts/run_r1setup_repo_local.sh --reset`

## Starting State

Remote state before validation:
- `35.228.69.214`
  - `edge_node.service` present and enabled
  - `edge_node` container present
- `34.88.90.109`
  - no `edge_node` systemd units
  - no `edge_node` containers

## Scenario Run

1. Started `r1setup` from a clean isolated dev home.
2. Created a fresh `devnet` config with one undeployed node on `34.88.90.109`.
3. Opened `Configuration Menu -> Register Machine`.
4. Registered `35.228.69.214` as `machineg1` in `standard` mode.
5. Accepted the follow-up discovery prompt.
6. Selected `machineg1` for discovery.
7. Observed one discovered candidate:
   - `edge_node`
   - `state=active`
   - `env=devnet (image_tag)`
   - `container=edge_node`
   - mount `/var/cache/edge_node/_local_cache -> /edge_node/_local_cache`
8. Imported only that service with config node name `g1import`.
9. Opened `Fleet Summary`.
10. Verified grouped machine rendering after import.
11. Returned to main menu and verified the compact deployment/status line.

## Results

Worked:
- clean startup from reset state
- machine registration flow
- spec probe messaging on the near-16 GiB host
- follow-up discovery offer after registration
- real remote discovery of the existing `edge_node`
- selective import of the discovered candidate
- preserved runtime identity on import
- machine remained `standard` when importing a single discovered service
- grouped fleet rendering after import
- compact main-menu state after returning from the flow

Observed CLI state after import:
- `machineg1`: `standard`, `active`, imported instance `g1import`, status `running`
- `34.88.90.109`: separate `standard` machine with undeployed `nodeempty`
- main menu showed `📡 tracking 1 live node(s)` and `Suggested: Review tracked live nodes before deploying changes`

## UX Notes

Good:
- the discovery candidate line was understandable and high-signal
- the near-boundary memory warning was clear and not overly alarming
- the import result message was concise and explicit about retained topology

Minor friction:
- after accepting the post-registration discovery prompt, the CLI still asked the user to select the same machine again instead of preselecting the newly registered machine

No blocking issues were observed in this final live slice.

## Conclusion

The final live validation gate passed for the new discovery/import workflow on real hosts.
