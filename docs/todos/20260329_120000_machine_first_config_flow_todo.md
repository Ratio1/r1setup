# Machine-First Configuration Flow

Created At: `2026-03-29T12:00:00+03:00`
Revised At: `2026-03-29T23:25:00+03:00`

## Problem

The current config creation flow is still node-first:

1. ask "How many nodes?"
2. collect SSH details per node
3. save inventory hosts immediately
4. push `Would you like to deploy now? (y/n)` with default `y`

That flow is no longer a good fit for the current product:

- the repo now has a machine-aware fleet model
- discovery/import of existing remote services already exists
- migration planning/execution already treats machine identity as first-class
- a machine may already be running one or more `edge_node` services before onboarding

The current first-run flow therefore risks guiding operators toward redeploying onto a machine that should first be scanned and possibly imported.

Additionally, the codebase still has two config creation paths with duplicated logic:

- `ConfigurationManager._create_new_configuration_with_management`
- `R1Setup._create_initial_configuration`

Those paths already diverged in validation, credential reuse, environment sync, and post-save behavior.

## Goal

After this change:

1. onboarding starts from machines, not pre-created node instances
2. machine registration is explicit and preserved in fleet metadata
3. discovery is offered before fresh instance creation
4. existing live services are imported, not blindly replaced
5. fresh instance creation is only offered on machines known to be clean, or via an explicit higher-friction override in a later phase
6. deployment is only prompted when the flow actually created new deployable instances
7. the duplicated config-creation paths share common implementation primitives

## Non-Goals

- breaking existing saved configurations
- changing the existing discovery candidate normalization logic
- changing migration planning/execution
- changing `register_machine_without_deployment` in the same PR as the onboarding refactor
- rewriting every menu in one step from "node" to "machine"

## Backward Compatibility And Migration Strategy

Compatibility is mandatory. The machine-first rollout must not strand operators with older saved configs.

Stable rules:

- existing configs must continue to load successfully after upgrade
- old configs do not need a manual export/import cycle
- additive metadata/schema changes are allowed only when they auto-normalize on load and auto-persist forward on the next save
- old config filenames do not need to be renamed retroactively
- imported already-running services must preserve their current live identity unless the operator performs an explicit rename workflow

### Compatibility Model

Keep the current distinction explicit:

- `check_hosts_config()` continues to mean: "this config has deployable inventory hosts"
- a new helper should be introduced for the broader concept: "this config has a valid active configuration shell, even if it currently has zero hosts"

Recommended helper names:

- `has_active_config_shell()`
- or `check_active_configuration_shell()`

Do not silently redefine `check_hosts_config()` to return true for zero-host shells. Too much existing code already uses it to gate host/instance operations.

### Schema Evolution Policy

If the final design introduces new persisted config metadata such as:

- `config_creation_style`
- `machines_count`
- other machine-first-only config fields

then:

1. bump `CONFIG_SCHEMA_VERSION`
2. add one normalization helper for config metadata, similar in spirit to the existing fleet-state normalization path
3. run that normalization on:
   - active-config load
   - named-config load
   - normal config load
   - config save
4. rewrite normalized metadata back to disk on the next save/activation

Recommended normalization entry point:

- `_normalize_config_metadata(metadata, inventory)`

This should:

- backfill missing new fields for legacy configs
- infer safe defaults from existing persisted state
- avoid destructive rewrites of inventory hosts

### Config Mode Compatibility

For Phases 0-5, do not introduce an authoritative persisted config-wide `configuration_mode` field.

Compatibility-safe rule:

- the persisted truth remains per-machine `topology_mode` plus per-host `r1setup_topology_mode`
- onboarding may track `simple` vs `advanced` as flow/session state while the wizard is running
- any config-wide "mode" shown in UI should be derived from normalized persisted state, not treated as a separate source of truth

Derived rule:

- `advanced` if any machine in fleet metadata is `expert`
- `advanced` if any persisted or derived host has `r1setup_topology_mode='expert'`
- otherwise `simple`

This avoids introducing a second authoritative mode flag that older flows such as manual discovery and `_add_node` could fail to maintain.

### Legacy Config Mode Inference

If a persisted config-level mode is introduced in a later cleanup phase, old configs missing that field should be inferred as follows:

- `advanced` if any machine in fleet metadata is already `expert`
- `advanced` if any persisted or derived host has `r1setup_topology_mode='expert'`
- otherwise `simple`

This preserves the meaning of already-existing expert-mode deployments without requiring manual migration.

### Metadata Naming Compatibility

Keep existing `nodes_count` semantics unchanged for backward compatibility:

- `nodes_count` continues to mean deployable inventory host count
- machine-first flows may legitimately have `nodes_count=0` after registration-only completion

Additive machine-first metadata is allowed:

- introduce `machines_count` as the count of registered machines in fleet metadata
- old configs missing `machines_count` should infer it from normalized fleet metadata, or `0` if no machines are registered

UI guidance:

- config lists and summary lines must not present a machine-first shell as merely `0 node(s)` without context
- when `machines_count > 0` and `nodes_count == 0`, prefer wording such as `3 machines, 0 instances`
- older views that still rely on `nodes_count` alone should be updated rather than redefining the field

### Config Naming Compatibility

Do not globally redefine `_generate_config_name()` in a way that rewrites old assumptions for every caller.

Preferred implementation:

- extend `_generate_config_name(count, custom_name, *, unit='n')`
- default stays `unit='n'` for existing node-first callers
- machine-first flows call it with `unit='m'`

Result:

- old config names stay unchanged
- machine-first shells avoid misleading names like `0n`
- rename/restore flows remain backward compatible

### Zero-Host Shell Compatibility

A machine-only configuration shell must be considered valid for:

- startup activation
- config restore/relink
- config switching
- fleet summary
- machine registration/discovery flows

But it must still be considered insufficient for:

- node operations
- node log streaming
- node deployment status actions that require inventory hosts

This is why the new shell-valid helper must exist alongside the old host-valid helper.

## Product Decisions

- Simple mode remains the default.
- Advanced multi-instance-per-machine mode remains explicit and opt-in.
- "Machine" is the right term for SSH registration and fleet grouping.
- "Instance" remains the right term for deployable/configured runtime entries under one machine.
- Operator-entered machine labels remain the primary machine identity in fleet metadata.
- Endpoint-derived identity remains a canonicalization and matching mechanism, not the user-facing ID.
- Discovery/import must stay explicit and selective.
- Fresh instance creation must not happen after a failed scan or after the user declined import of discovered services.
- Existing saved configs remain backward compatible.
- If additive metadata fields are introduced, old configs will be auto-normalized to the new format on load/save.
- Config-wide simple/advanced state should remain derived, not authoritative, during the early rollout phases.
- Inventory host keys may remain stable internal identifiers even when the operator chooses a separate display/runtime name for an instance.
- In expert mode, the operator should be able to choose a logical name for each `edge_node` instance; that logical name is displayed in the UI and applied as the runtime `EE_ID`.
- Machine labels are the primary operator-facing IDs in early phases; later introduction of a hidden immutable machine UUID remains optional future work, not a rollout prerequisite.

---

## Architecture Analysis

### Current State

Two config creation paths currently exist:

| Aspect | `ConfigurationManager._create_new_configuration_with_management` | `R1Setup._create_initial_configuration` |
|---|---|---|
| Owner | `ConfigurationManager` | `R1Setup` |
| Callers | config management and startup recovery flows | `configure_nodes_menu` / reset-and-start-fresh |
| Credential reuse | Yes | No |
| Duplicate-name check | No | Yes |
| Environment persistence | Missing `set_mnl_app_env()` | Present |
| Progress display | Yes | No |
| Immediate deploy prompt | Yes, default `y` | No |

Relevant fleet/discovery constraints from the current code:

1. fleet machines persist in metadata even without inventory hosts
2. fleet instances are still derived from inventory `hosts[...]`
3. `discover_and_import_existing_services()` rescans the machine itself
4. `upsert_machine_record()` and `record_machine_discovery_scan()` save immediately
5. explicit machine labels already win over endpoint-derived IDs during canonicalization
6. standard runtime naming still resolves to the fixed `edge_node` / `edge_node` / default volume triplet

### Design Constraints

1. A configuration shell must exist on disk before discovery/import helpers that reload configuration can operate.
2. Machine registration can happen without inventory hosts.
3. Deployable instances are only created when inventory hosts are created.
4. Operator-entered machine labels should be stored as `machine_id`.
5. Endpoint-derived identity should be used to match and deduplicate machines, not to replace labels.
6. A batch scan helper must not delegate to a wrapper that rescans again.
7. Fresh standard-mode instance creation is only safe on a machine whose scan succeeded and found zero candidates.
8. If a scan fails, or if the operator declines import of discovered services, the machine should remain registered-only until the operator makes a separate explicit decision.
9. A zero-host configuration shell must behave consistently across menus that currently equate "configured" with "has inventory hosts".
10. Startup/recovery flows currently depend on `check_hosts_config()` as well, so zero-host shell support must cover activation and restore paths, not only interactive menus.
11. Expert-mode instance naming must distinguish between:
    - stable internal inventory host key
    - operator-visible logical/display name
    - runtime/service env identity (`EE_ID`)
12. Old configs missing logical instance names must normalize safely by defaulting the logical/display/runtime name to the existing inventory host key.
13. Gap fill must rely on a fresh-enough discovery result from the current onboarding scan, not on arbitrarily old cached scan data.
14. Per-config machine metadata can diverge across configs until a central machine registry exists; the rollout must tolerate that duplication explicitly.

---

## Revised UX Flow

### Target Flow

1. Config name + environment
2. Configuration mode:
   - `Simple` (recommended): one deployable instance per machine
   - `Advanced`: multiple deployable instances may share a machine
3. `How many machines do you want to register?` `[1]`
4. Per machine:
   - machine label, default `machine-{i}`
   - SSH access details via `_configure_single_node(previous_config=...)`
   - optional/best-effort spec probe
   - advanced only: desired instance count for that machine
5. Save a configuration shell with registered machine records and zero inventory hosts
6. Offer discovery scan:
   - `Check these machines for existing edge_node services now? (Y/n)` `[Y]`
7. Batch scan summary:
   - scanned clean
   - scanned with candidates
   - scan failed
   - scan skipped
8. For machines with discovered candidates:
   - review cached candidates
   - select which services to import
   - import without rescanning
9. Gap fill:
   - simple mode: offer fresh instance creation only on scanned-clean machines
   - advanced mode: offer fresh instance creation for the remaining planned capacity only on scanned-clean machines
   - advanced mode: prompt for a logical/display name for each created instance
10. If no fresh instances were created:
   - do not show a deploy prompt
   - send the operator to Fleet Summary / Node Status guidance instead
11. If fresh instances were created:
   - show `Would you like to deploy now? (y/n)` with default `n`

### Terminology Rules

- Use `machine` for SSH registration, fleet summaries, and discovery scan steps.
- Use `instance` for deployable logical entries that become inventory hosts.
- Avoid changing existing low-level SSH prompts inside `_configure_single_node`; those are connection prompts, not topology prompts.
- In expert mode, distinguish `inventory key` from `instance name` in prompts and summaries. The operator-facing name is the logical/display/runtime name, not necessarily the internal inventory host key.

---

## Required Fixes To The Previous Draft

### Fix 1: Keep Explicit Machine Labels As `machine_id`

Do not derive the registered `machine_id` from SSH access details in the onboarding flow.

Correct behavior:

- prompt for `machine-{i}` or user-supplied label
- store that label as `machine_id`
- keep endpoint-derived identity only for matching, binding, and canonicalization

Rationale:

- this is how the current machine-registration flow behaves
- current canonicalization logic already prefers explicit IDs
- deriving the ID from endpoint would throw away the UX value of asking for a label

### Fix 2: Split Batch Scan From Import

Do not implement batch scan by:

1. scanning all machines, then
2. calling `discover_and_import_existing_services(machine_id)` for each machine

That would rescan each machine again.

Correct design:

- add a new helper that scans machines and returns/persists cached candidates
- add a second helper that reviews and imports already-scanned candidates without rescanning
- keep the existing single-machine `discover_and_import_existing_services()` flow for manual use

### Fix 3: Safe Gap Fill

Do not treat scan failure as equivalent to "no services found".

Correct behavior:

- scan success + zero candidates -> eligible for fresh-instance creation
- scan success + candidates discovered -> import path only; no automatic fresh-instance fallback in the same flow
- scan failed -> leave machine registered-only; tell the operator to retry scan or proceed manually in a later explicit action
- scan skipped -> leave machine registered-only in early phases

This avoids creating a second `edge_node` service on a machine that already has one.

### Fix 4: Gate The Deploy Prompt

Do not always show a final deploy prompt.

Correct behavior:

- show deploy prompt only when the flow created at least one fresh inventory host with `never_deployed`
- if the flow only registered machines and/or imported existing live services, finish with review guidance instead of deployment guidance

### Fix 5: Keep Wording Accurate

Avoid broad wording changes such as:

- `Deploy your configured machines`
- `Configure your machines first`

Deployment still acts on instances/hosts, not bare machine records.

Preferred wording:

- `Create or load a configuration first`
- `Deploy your configured instances`
- `Review fleet status before deploying changes`

---

## Phased Rollout Plan

The rollout should be incremental. Each phase should be landable, testable, and releasable on its own.

### Phase 0: Low-Risk UX Guidance

Goal:

- improve menu guidance without changing onboarding architecture yet

Changes:

- in `_get_deployment_display_state()`, keep the tracked-live-nodes posture but default the deployment menu to review/status instead of deploy
- update operator-facing hint text so tracked-live configurations steer toward review first
- avoid over-broad "machines" wording in deployment guidance; prefer `instances` or `configuration`
- introduce a shell-valid helper without changing the meaning of `check_hosts_config()`

Suggested copy:

- tracked-live suggestion: `Review fleet status before deploying changes`
- no-config suggestion: `Create or load a configuration first`
- never-deployed suggestion: `Deploy your configured instances`

Why first:

- very low risk
- aligns the UI with the current discovery/import reality
- easy to test independently
- establishes the helper split needed for later zero-host-shell support

### Phase 1: Shared Config-Creation Primitives

Goal:

- remove duplication without changing the onboarding model yet

Approach:

- extract shared helpers with explicit ownership:
  - `_prompt_new_config_name()` on `ConfigurationManager`
  - `_prompt_new_config_environment()` on `ConfigurationManager`
  - `_collect_node_connection_entries(...)` on `ConfigurationManager`
  - `_reset_inventory_for_new_config()` on `ConfigurationManager`
  - `_finalize_new_config_save(config_name, env, nodes_count, *, update_symlink=True)` on `ConfigurationManager`
  - `_normalize_config_metadata(metadata, inventory)` on `ConfigurationManager` if new persisted metadata fields are introduced
- the shared collection helper should take flags for:
  - `allow_previous_config_reuse`
  - `enforce_duplicate_name_check`
  - `show_progress_summary`
- all three existing config creation entry points must migrate to these shared primitives:
  1. `ConfigurationManager._create_new_configuration_with_management` - called from startup recovery and config management flows
  2. `R1Setup._create_initial_configuration` - called from `configure_nodes_menu` when no hosts exist
  3. `R1Setup._create_new_configuration` (~line 11738) - called from `configure_nodes_menu` option 4 when hosts already exist and the user wants a fresh config
- keep the three top-level entry points for now, but make caller-specific behavior explicit

Target behavior split:

Shared in Phase 1:

- config name prompt and validation
- environment prompt
- inventory reset helper
- host-entry collection loop mechanics
- duplicate-name validation
- credential reuse support
- metadata save path
- config-metadata normalization path for backward compatibility

Caller-specific in Phase 1:

- section/header copy (`Create New Configuration` vs `Initial Configuration Setup`)
- whether progress summary is shown before each entry
- whether an immediate deploy prompt is shown after save

Normalized in Phase 1:

- all three paths must call `set_mnl_app_env(env)`
- all three paths must reject duplicate logical host names
- old configs with missing new metadata fields must be normalized forward without user action

Deferred until later phases:

- machine-first flow conversion
- removal of the immediate deploy prompt from the management path
- replacement of node-first prompts with machine-first prompts

Important note:

- do not jump straight to one giant `_run_config_creation_flow()` with all future machine-first behavior embedded
- first consolidate primitives, then recompose behavior in later phases
- Phase 1 should end with a documented small API surface, not with hidden inlined shared behavior

Why:

- smaller refactor surface
- easier to prove no regressions
- avoids mixing architectural cleanup with product-flow redesign

### Phase 2: Machine Registration Shell For Simple Mode

Goal:

- switch first-run onboarding from immediate inventory-host creation to machine registration

Scope:

- simple mode only
- one planned instance per machine
- no advanced multi-instance prompts yet

Changes:

- onboarding asks for number of machines, not nodes
- collect machine label + SSH details + optional spec probe
- save a configuration shell with registered machine records and zero hosts
- preserve explicit machine labels as `machine_id`
- use machine count, not host count, for machine-first config naming
- initialize additive metadata for machine-first shells:
  - `nodes_count=0`
  - `machines_count=<registered machine count>`
  - optional `config_creation_style='machine_first'`

Out of scope:

- automatic expert-mode planning
- advanced per-machine instance counts

Why:

- lands the core machine-first architecture with minimal branching

Mandatory audit in this phase:

- review every menu/path that currently uses "has hosts" as a proxy for "has usable configuration"
- explicitly test and, if needed, adapt:
  - every current `check_hosts_config()` gate, classifying it as:
    - "must still require deployable hosts"
    - or "should accept a valid zero-host shell"
  - `ensure_active_configuration()`
  - active-config restore/relink behavior
  - import/restore success checks that currently re-check `check_hosts_config()`
  - startup status-refresh and startup service-update guards
  - main menu summary line
  - configuration menu current-status block
  - deployment menu entry behavior
  - operations menu guards
  - fleet summary for zero-host registered-machine configs

Required zero-host config behavior:

- a configuration shell with registered machines but zero hosts is a valid active configuration
- Fleet Summary must show registered machines with `No Instances`
- menus must not misreport this state as "no config exists"
- startup must not force-create or re-select another config just because the active shell currently has zero hosts

### Phase 3: Batch Discovery Using Cached Candidates

Goal:

- add safe discovery before fresh instance creation

Changes:

- add batch scan helper that:
  - scans each registered machine once
  - buffers scan results in memory during the batch
  - persists scan results in fleet metadata at one explicit save boundary after the scan phase completes
  - summarizes clean / discovered / failed / skipped states
- extract the current discovery review/import UX into reusable pieces:
  - one helper to load cached candidates for a machine
  - one helper for candidate selection UI
  - one helper for pre-import validation UI:
    - environment mismatch confirmation
    - cross-config claim warnings
    - expert-mode confirmation when needed
    - expert-mode logical-name prompt for imported instances
- add a new onboarding-facing import helper that consumes cached candidates without rescanning
- keep `discover_and_import_existing_services()` untouched as the entry point for manual single-machine usage; refactor its internals to call the same shared selection/validation/import helpers after its live scan
- add a simple-mode multi-candidate guardrail (see below)
- keep config mode derived from topology rather than persisting an authoritative `configuration_mode` field in this phase

Persistence rule for Phase 3:

- onboarding batch scan must not call the current immediate-save persistence path once per machine as its primary control flow
- prefer a buffered helper or explicit "save all scans" boundary so an abandoned batch does not leave a half-updated discovery cache by accident
- the existing manual single-machine discovery flow may keep immediate-save behavior because it is already a one-machine action
- gap fill in later phases should only trust scan results produced in the current onboarding session, or explicitly marked fresh by a timestamp/recency rule

Environment-aware candidate filtering:

During batch import, candidates must be filtered by the config environment before presenting the selection UI. Mismatched candidates are shown as informational context but are not selectable:

```
Machine machine-1 has 2 services:
  edge_node        [running] testnet  ← matches this config
  edge_node_devnet [running] devnet   ← different environment

Only testnet services can be imported into this config.
To manage the devnet service, create a separate devnet config later.

Import edge_node from machine-1? (Y/n) [Y]:
```

This replaces the current generic "environment mismatch, continue? (y/n)" prompt with a clearer explanation of why and what to do about it.

Multi-service machine topology rule:

If discovery finds 2+ total service instances on a machine (regardless of how many match the config environment), that machine must be registered with `expert` topology. This reflects the machine's real operational state: multiple services share its resources, even if this config only manages a subset of them.

Example: a machine runs `edge_node` (testnet) and `edge_node_devnet` (devnet). A testnet config can only import `edge_node`, but the machine is still `expert` because two services are running on it. This prevents the tool from later treating it as a single-service machine for capacity planning, helper scripts, or gap fill.

Simple-mode multi-service guardrail:

When the config is in simple mode and a machine has 2+ total discovered services (across all environments), present an explicit decision:

```
Machine machine-1 has 2 running services (1 matches this config's environment).
This machine requires Advanced mode because multiple services share its resources.

  1) Switch to Advanced mode to import matching services
  2) Skip this machine for now

Select (1-2) [2]:
```

Behavior per choice:

- Option 1: switch the onboarding flow to advanced for the remainder of the session; register machine with `expert` topology; show only environment-matching candidates for import selection
- Option 2: leave machine registered-only; skip to next machine in batch (default - safe choice)

There is no "import one and stay simple" option. A machine running multiple services is expert regardless of how many this config tracks.

When the config is already in advanced mode, no mode-switch prompt is needed. The machine is simply registered as `expert` and environment-matching candidates are presented for import.

When a machine has only 1 discovered service total, it stays `standard` topology and the matching service is offered for import normally.

Expert-mode import naming rule:

- when importing an instance onto an expert-topology machine, prompt for an operator-visible logical name
- default that prompt to the discovered service/runtime name so existing deployments remain recognizable
- persist the chosen value as `r1setup_instance_logical_name`
- use that logical name for grouped UI display and runtime `EE_ID`, with fallback to the prior host key for legacy instances

Imported-running-service identity rule:

- importing an already-running service must not be treated as an immediate live rename
- a different logical name may result in a different rendered `EE_ID` in the service file, but the running service keeps its current live identity unless the operator performs the dedicated rename workflow
- explicit rename remains a separate managed operation

This guardrail only applies during batch onboarding discovery. The standalone `discover_and_import_existing_services()` flow (manual single-machine usage from Configuration Menu) keeps its existing reactive expert-mode promotion behavior.

This difference is intentional for rollout safety:

- onboarding is opinionated and conservative
- manual discovery remains backward compatible in early phases
- a later cleanup phase may choose to align the two flows once the machine-first path is proven

Temporary compatibility note:

- after Phase 3, onboarding discovery and manual discovery intentionally do not behave identically on multi-service machines
- this must be documented in operator docs and release notes until the flows are unified

Result:

- onboarding can reuse the discovery validations already present in import logic, but without the double-scan problem
- environment filtering is automatic with clear explanation, not a confusing y/n prompt
- machine topology reflects reality (multi-service = expert), not just what this config imports
- simple-mode users are never silently pushed into expert topology during onboarding
- multi-service machines are either managed properly (advanced) or deferred honestly (skip)

### Phase 4: Safe Gap Fill For Simple Mode

Goal:

- create fresh instances only where it is safe

Changes:

- offer fresh instance creation only for machines whose scan succeeded and returned zero candidates
- for failed or skipped scans, leave machines registered-only
- for discovered-but-not-imported machines, leave them registered-only
- add a helper that builds a fresh inventory host entry from:
  - machine record SSH/access fields
  - logical instance name
  - topology mode
  - runtime naming policy
  - derived runtime names
- create one inventory host per scanned-clean machine when the operator confirms
- mark those hosts as `never_deployed`
- only after that, offer deploy-now with default `n`

Why:

- this is the first phase where onboarding creates deployable instances again
- the safety gate is explicit and testable

Fresh-host builder requirements:

- copy SSH access from the machine record, not from a new `_configure_single_node()` prompt
- set `r1setup_machine_id` from the registered machine label
- set `r1setup_topology_mode='standard'`
- set `r1setup_instance_logical_name` to the operator-visible instance name; default to inventory host key for legacy/simple behavior
- apply resolved standard runtime names
- initialize status and runtime metadata exactly as a newly configured undeployed instance expects
- persist through the same normalized metadata/save path used by old configs so upgraded configs remain structurally valid

### Phase 5: Advanced Mode / Expert Topology

Goal:

- add multi-instance-per-machine planning safely after the simple-mode machine-first path is stable

Changes:

- add explicit advanced-mode confirmation
- ask for desired instance count per machine
- for each expert-mode instance to import or create, prompt for a logical/display name the operator chooses
- compute capacity guidance from spec probe results
- after discovery import, calculate remaining capacity gap per machine
- reuse the fresh-host builder from Phase 4 for expert-mode host synthesis
- offer fresh instance creation only for the unfilled remainder on scanned-clean machines
- keep expert-mode promotion explicit and visible

Expert-mode naming rules:

- preserve a stable internal inventory host key for persistence and references
- store the operator-chosen instance name in `r1setup_instance_logical_name`
- use `r1setup_instance_logical_name` in grouped fleet views and other operator-facing summaries
- use `r1setup_instance_logical_name` as the default source for runtime `EE_ID`
- keep backward-compatible fallback to `inventory_hostname` when `r1setup_instance_logical_name` is missing

Implementation surfaces to align in this phase:

- inventory host synthesis and import paths must preserve or prompt for `r1setup_instance_logical_name`
- `edge_node.service` rendering must source `EE_ID` from `r1setup_instance_logical_name | default(inventory_hostname, true)`
- startup-config / rename maintenance paths that currently rewrite `EE_ID` from `inventory_hostname` must be updated to use the logical name instead

Migration rule:

- old configs that do not have `r1setup_instance_logical_name` must auto-normalize it to the existing host key
- this keeps legacy display and runtime identity unchanged until the operator explicitly renames an instance

Machine-label stability rule:

- machine labels are treated as stable identifiers throughout Phases 0-5
- do not add machine-label rename semantics implicitly as part of this rollout
- if machine-label rename is needed later, it should be designed as a separate migration-safe feature, or backed by a hidden immutable machine ID

Why later:

- advanced mode compounds the naming, collision, and helper-mode complexity
- simple mode should be proven first

### Phase 6: Unify Standalone Machine Registration With Onboarding

Goal:

- remove duplicated per-machine registration logic between:
  - onboarding flow
  - `register_machine_without_deployment`

Changes:

- share the same machine collection helper
- keep standalone register-machine behavior as a thin wrapper around the shared primitive
- decide at this phase whether `_add_node` remains a direct instance-creation flow or becomes machine-aware

Why last:

- do not couple first-run onboarding changes to the standalone registration menu earlier than necessary
- ordering is soft; this phase could move earlier once Phase 2 is stable, but it is intentionally not on the critical path

### Phase 7: Docs, Smoke Tests, and Follow-On Cleanup

Goal:

- align operator docs and manual test paths with the new flow

Changes:

- update `mnl_factory/scripts/README_r1setup.md`
- update any menu copy that still misdescribes machine-vs-instance behavior
- add a dated design note if the final UX differs materially from this plan
- document the settled future of `_add_node`

`_add_node` policy until then:

- `_add_node` remains unchanged through Phases 0-5
- it continues to create an inventory host directly
- a later phase may adapt it to ask whether the new instance should bind to an existing registered machine or create/register a new one

---

## Suggested Implementation Order

Implementation should follow the same phase order:

1. Phase 0 PR
2. Phase 1 PR
3. Phase 2 PR
4. Phase 3 PR
5. Phase 4 PR
6. Phase 5 PR
7. Phase 6 + Phase 7 PRs, or one cleanup PR if the diff is small

Do not bundle Phase 1 through Phase 5 into one branch.

---

## Existing Infrastructure To Reuse

| Method | Owner | Purpose |
|---|---|---|
| `_configure_single_node` | `R1Setup` | SSH connection detail collection |
| `_extract_machine_access_config` | `R1Setup` | Extract machine-level SSH fields from node-style config |
| `_probe_machine_specs` | `R1Setup` | Best-effort remote CPU/RAM probe |
| `_derive_machine_id` | `ConfigurationManager` | Endpoint-derived fallback identity |
| `discover_existing_edge_node_services` | `R1Setup` | Remote service discovery scan |
| `discover_and_import_existing_services` | `R1Setup` | Existing manual single-machine scan+import flow |
| `record_machine_discovery_scan` | `ConfigurationManager` | Persist discovery cache |
| `resolve_runtime_names` | `ConfigurationManager` | Runtime naming for standard/expert mode |
| `detect_runtime_collisions` | `ConfigurationManager` | Runtime collision detection |
| `assess_machine_resource_recommendation` | `ConfigurationManager` | Capacity guidance |
| `ensure_configuration_shell` | `ConfigurationManager` | Persist config shell with zero or more hosts |
| `_run_with_spinner` | `MigrationPlanner` | Optional progress UI for Phase 3 batch scan |

---

## Error Handling and Recovery

### Concurrent Config Writes

The machine-first flow increases the number of metadata-only save points. The implementation should assume that concurrent `r1setup` sessions against the same config are possible.

Minimum requirement:

- avoid silent clobbering where feasible
- if true locking is not added in the early phases, document last-writer-wins behavior and warn when stale in-memory state is about to overwrite newer disk state

### Cancellation During Machine Collection

If the operator cancels (Ctrl-C) before the configuration shell is saved, nothing is persisted.

### Partial Failure During Machine Collection

Collection should stay in memory until the normal save boundary.

Recommended behavior on one-machine failure:

- offer retry for that machine
- allow skip of that machine and continue the batch
- only persist the successfully collected machines when the operator completes the batch normally

Do not silently persist a partial shell in the middle of the collection loop unless the user explicitly completes or confirms that outcome.

### Spec Probe Failure

Spec probe remains best-effort. The flow continues with a warning.

### Discovery Scan Failure

A failed scan must not be treated as a clean machine. The machine remains registered-only.

### Discovery Declined Or Partial Import

If candidates were found and the operator imports none or only some:

- imported services become tracked instances
- the machine stays registered
- no fresh instance is created automatically for the remaining discovered candidates in the same onboarding flow

### All Machines Already Have Running Services

If discovery finds running services on every machine and the user imports them all, the flow ends with zero fresh instances. This is a valid and common outcome for operators onboarding existing infrastructure.

The messaging must feel like a success, not a dead end:

```
✅ All machines are already running edge_node services.
   Your fleet is imported and ready to manage.

💡 Use Fleet Summary to review your machines,
   or Node Status & Info to check service health.
```

Do not show a deploy prompt in this case.

### Config Saved Before Gap Fill

A valid intermediate state is:

- configuration shell exists
- machines are registered
- zero hosts exist

That state must remain recoverable through:

- `Fleet Summary`
- `Discover Services`
- manual add-instance flows

---

## Test Plan

### Regression

At every phase:

- `python3 -m py_compile r1setup`
- `python3 -m unittest discover tests -v`

### Phase 0 Tests

- tracked-live deployment menu default points to review/status
- suggested-action wording is updated
- no-config guidance uses configuration wording
- shell-valid helper exists and does not change `check_hosts_config()` semantics

### Phase 1 Tests

- both creation entry points delegate to shared primitives
- environment persistence stays correct
- duplicate-name validation stays correct
- credential reuse stays correct
- legacy configs missing new metadata fields normalize forward on load/save without inventory loss
- derived config mode remains consistent with persisted topology; no separate authoritative config-mode write is required

### Phase 2 Tests

- machine-first onboarding saves a config shell with machine records and zero hosts
- operator-entered machine labels become `machine_id`
- no inventory instances are created during registration-only completion
- Fleet Summary shows registered machines with `No Instances` and no false running/deployed status
- `ensure_active_configuration()` accepts a valid zero-host active shell
- restore/import paths do not reject a zero-host shell as "no config"
- config summaries show machine-aware metadata such as `N machines, 0 instances` rather than only `0 node(s)`

### Phase 3 Tests

- batch scan scans each machine once
- cached scan results are persisted
- batch scan persists through one explicit save boundary, not accidental per-machine partial writes
- import-from-cached-candidates does not rescan
- partial scan failure does not block other machines
- the existing manual single-machine discovery flow still works through the extracted shared UI/validation helpers
- candidates are filtered by config environment before selection; mismatched candidates shown as info-only
- gap fill is only enabled from current-session or otherwise explicitly fresh scan results
- machine with 2+ total services (any env) is registered as `expert` topology regardless of import count
- simple-mode machine with 2+ total services triggers mode decision prompt (switch to advanced or skip)
- choosing "switch to advanced" updates the onboarding session mode, registers machine as expert, shows env-matching candidates
- choosing "skip" leaves machine registered-only and proceeds to the next machine
- machine with 1 total service stays `standard` topology, offered for import normally
- there is no "import one and stay simple" option for multi-service machines
- imported expert-mode candidates prompt for a logical/display name and persist it as `r1setup_instance_logical_name`
- importing an already-running service with a different logical name does not by itself count as a live rename

### Phase 4 Tests

- fresh instance creation only happens on scanned-clean machines
- scan failure does not enable fresh instance creation
- discovered-but-declined machines remain registered-only
- deploy prompt is shown only when fresh instances were created
- fresh host entries are synthesized from machine-record SSH fields plus resolved runtime names

### Phase 5 Tests

- advanced confirmation is required
- desired instance count is stored per machine during the flow
- capacity recommendation math is correct
- remaining gap is `desired - imported - already-created`
- expert-mode fresh hosts are synthesized through the shared fresh-host builder
- expert-mode prompts capture an operator-visible logical instance name
- `r1setup_instance_logical_name` is persisted and displayed in fleet views
- rendered runtime identity uses logical name for `EE_ID` with fallback to `inventory_hostname` for legacy instances
- legacy expert instances without `r1setup_instance_logical_name` normalize forward without changing visible/runtime identity unexpectedly
- machine-label rename is not introduced implicitly in this phase

### Manual Smoke Matrix

| Scenario | Expected result |
|---|---|
| Simple mode, fresh machines | scan clean -> offer fresh instance creation -> deploy prompt default `n` |
| Simple mode, existing services | import path only -> no deploy prompt unless fresh instances were also created |
| Simple mode, scan failure | machine remains registered-only |
| Advanced mode, mixed machine states | imported services preserved, only clean remainder eligible for fresh creation |
| Advanced mode, operator-chosen instance names | logical names appear in UI and map to runtime `EE_ID` while internal host keys remain stable |
| Imported running service with new logical name | tracked logical name may differ from current live identity until explicit rename workflow is run |
| Cancel before shell save | nothing persisted |
| Cancel after shell save | machine-only shell remains valid and recoverable |
| All machines have services | import all -> success messaging -> no deploy prompt |
| Partial batch failure | successful machines saved, failed machine skipped with guidance |
| Env mismatch on discovery | skip with explanation, suggest separate config |
| Same machine in two configs | cross-config claim warning on import, both configs work independently |

---

## Closed Decisions

| Decision | Resolution | Reasoning |
|---|---|---|
| Keep explicit machine label or derive `machine_id` from endpoint? | Keep explicit machine label | Better operator UX; matches current canonicalization rules |
| Batch scan should call existing `discover_and_import_existing_services()`? | No | That wrapper rescans and would double the network work |
| Treat scan failure as "no services found"? | No | Unsafe for standard runtime defaults |
| Always show a deploy prompt at the end? | No | Only makes sense when fresh deployable instances were created |
| Broadly replace `node` wording with `machine` wording? | No | The product model is machine plus instance, not machine-only |
| Should simple-mode onboarding silently promote to expert when discovery finds multiple services? | No | A multi-service machine must be managed in advanced mode or skipped; no "import one and stay simple" option |
| Should `_generate_config_name()` stay `{count}n` for machine-first onboarding? | No | Machine-first flows should use machine count with an `m` suffix to avoid misleading `0n` names |
| Should `nodes_count` be redefined to mean machines for machine-first shells? | No | Keep `nodes_count` as deployable-instance count; add `machines_count` instead |
| Does `_add_node` change immediately as part of machine-first onboarding? | No | Keep it stable through the early phases; revisit once the machine-first path is proven |
| Land as one PR? | No | The risk is too high; phase the rollout |
| Can one config contain machines from different network environments? | No | One config = one `mnl_app_env`. The Docker image tag is derived from this config-wide setting. Mixed envs on one physical machine require separate configs (already supported via cross-config model). |
| Should discovery show env-mismatched candidates as selectable? | No | Filter by config env automatically; show mismatched ones as info-only with guidance to create a separate config |
| If a machine has 2 services but only 1 matches the config env, is the machine still expert? | Yes | Topology reflects the machine's real state (multi-service = expert), not just what this config imports |
| Should early phases persist an authoritative config-wide `configuration_mode` field? | No | Keep config mode derived from topology until all expert-producing flows are unified |
| In expert mode, can the operator choose a per-instance displayed/runtime name separate from the inventory host key? | Yes | Persist `r1setup_instance_logical_name`; use it for UI and `EE_ID` with legacy fallback |
| Should expert-mode `EE_ID` keep following `inventory_hostname`? | No | `EE_ID` should follow the logical instance name, while `inventory_hostname` remains the stable internal host key |
| Does importing a running service with a different logical name immediately rename the live service identity? | No | Live identity is preserved until the operator performs the dedicated rename workflow; service-file `EE_ID` changes alone are not treated as an immediate rename |
| Can gap fill rely on old cached discovery data? | No | Fresh instance creation should depend on discovery results from the current onboarding scan, or a clearly defined recency policy |
| Are machine labels expected to be freely mutable in early phases? | No | Treat them as stable identifiers for now; if later rename support is needed, design it separately or introduce a hidden immutable ID |
| Is there a third config creation path? | Yes | `_create_new_configuration()` on R1Setup (~line 11738) is called from `configure_nodes_menu` option 4 when hosts already exist. Phase 1 must account for this path too. |
| If new persisted machine-first metadata is added, do old configs need manual migration? | No | Old configs must auto-normalize on load and be rewritten forward on next save/activation |

---

## Environment Rule

One configuration = one network environment (`mainnet`, `testnet`, or `devnet`). This is an architectural constraint, not just a UX preference:

- `mnl_app_env` is config-wide and drives the Docker image tag for all instances in that config
- you cannot deploy node-1 as testnet and node-2 as devnet within the same config - they would pull the same image
- this applies equally to simple and advanced mode

For operators who run mixed environments on one physical machine (e.g. testnet + devnet):

- create one config per environment
- each config references the same machine but imports only its own environment's services
- discovery already supports this via environment mismatch warnings and selective import
- the cross-config claim detection warns when two configs track services on the same machine

During onboarding, if discovery finds services that don't match the config environment, the flow should prominently explain:

```
Machine machine-1 is running devnet services, but this config is set to mainnet.

These services belong in a separate devnet config.
You can create one later and import them there.

Skipping machine-1 for this config.
```

This is clearer than the current generic "environment mismatch, continue? (y/n)" prompt because it explains *why* and *what to do about it*.

---

## Post-Onboarding UX Gap: Add Machine vs Add Node

After the machine-first flow ships, there is a known UX inconsistency for adding machines to an existing config:

- `Register Machine` (Config Menu > 5): registers fleet machine only, no instance
- `Add Node` (Config Menu > Configure Nodes > 1): creates an inventory host directly (old node-first flow)

Neither matches the new machine-first-then-discover pattern. An operator who wants to add one more machine to an existing config must either:

1. Use `Register Machine`, then separately use `Discover Services` - two steps, not obvious
2. Use `Add Node`, which bypasses machine registration and discovery entirely

This gap is acknowledged and deferred. Phase 6 begins addressing it. Phase 7 documents the settled behavior.

A longer-term direction would be to unify these into a single "Add Machine" flow that registers, scans, and optionally creates instances - mirroring the onboarding flow for a single machine.

---

## Additional Long-Term Safeguards

- Cache freshness: discovery cache should carry enough timestamp/session context to distinguish "scanned just now during onboarding" from "stale historical scan."
- Cross-config duplication: until a central registry exists, the same machine can still have divergent SSH details, spec probes, and cached discovery results in different configs. This is acceptable short term, but the UI and docs should not imply a global source of truth.
- Concurrency: if file locking is deferred, add explicit warnings or conflict detection around save points that normalize metadata and write buffered scan results.
- Secret handling: machine-first shells store SSH-access data even when no deployable hosts exist yet. Export, backup, debug, and support flows should treat those shells as sensitive configs, not as harmless empty shells.
- Phase 1 scope discipline: keep shared-helper extraction separate from machine-first behavior changes. If a Phase 1 PR starts changing onboarding semantics, split it.
- Zero-host-shell support is a behavioral invariant, not just a UX cleanup. Startup, restore, relink, and activation paths must keep treating a valid zero-host shell as a real configuration.
- Name semantics must stay explicit during implementation:
  - `inventory_hostname` = stable internal inventory key
  - `r1setup_instance_logical_name` = operator-facing logical/display name
  - `EE_ID` = rendered runtime identity for future starts and explicit rename workflows
- When the expert-name phase lands, update every `EE_ID` writer together, not only one template. At minimum this includes `edge_node.service.j2` and `update_node_names.yml`.
- Downgrade expectations should be documented once machine-first additive metadata is introduced. Forward normalization is required; backward CLI compatibility should be treated as an explicit policy decision, not an assumption.
- Even if true file locking is deferred, add tests or at least guarded code paths for stale-write/concurrent-save scenarios so metadata writes do not silently clobber newer disk state.

---

## Future Direction: Central Machine Registry

The current model stores machine records per-config in fleet metadata. The same physical machine may appear independently in multiple configs with no shared state between them.

A future improvement would introduce a central machine registry at `~/.ratio1/r1_setup/machines/` (or similar) where:

- machines are registered once with SSH details, specs, and discovery cache
- configs reference machines by ID instead of duplicating SSH details
- discovery results are shared across configs
- machine preparation state is tracked centrally

This would:

- eliminate duplicate SSH detail entry when the same machine appears in multiple configs
- make cross-config claim detection trivial (central view of what's tracked where)
- enable a unified "Machines" management view independent of any single config
- allow "add machine to config" to pick from already-known machines

This requires backward compatibility with the current per-config fleet model and is explicitly out of scope for the machine-first onboarding work. It should be planned separately once the per-config machine-first flow is proven.

---

## Implementation Tracking

This file is not only the design plan. It should also serve as the implementation ledger for the rollout.

Process rule:

- after each phase lands, update this file before or together with the code PR
- record what actually shipped, what changed from the original phase plan, what tests were run, and the resulting commit SHA
- if a phase is split into sub-PRs, record each sub-PR separately under that phase
- if the implementation diverges materially from the planned behavior, add a short note explaining why

Clean-history rule:

- complete one phase at a time
- run the relevant regression and phase-specific tests at the end of that phase
- make a commit after the phase is green, before starting the next phase
- do not batch multiple phases into one mixed implementation commit unless the plan is explicitly revised first

Recommended per-phase closeout checklist:

- phase behavior implemented
- docs/plan updated to reflect actual shipped behavior
- `python3 -m py_compile r1setup`
- `python3 -m unittest discover tests -v`
- targeted tests for the phase-specific surfaces
- manual smoke check if the phase changes user-facing flow
- commit created with a phase-scoped message

### Implementation Log

#### Phase 0

- Status: completed
- Scope notes: Low-risk UX guidance changes only. No onboarding architecture changes.
- Actual behavior shipped:
  - Added `has_active_config_shell()` on `R1Setup` (after `check_hosts_config()`). Returns True for valid config shells with zero hosts (metadata-only shells created by `ensure_configuration_shell`). Does not change `check_hosts_config()` semantics.
  - Updated `_get_deployment_display_state()` tracking_live_nodes suggested_action: `"Review tracked live nodes before deploying changes"` → `"Review fleet status before deploying changes"`
  - Updated `_get_suggested_action()` no-config fallback: `"Configure your nodes first"` → `"Create or load a configuration first"`
  - Updated `_get_suggested_action()` never-deployed/deleted hint: `"Deploy your configured nodes"` → `"Deploy your configured instances"`
- Tests run:
  - `python3 -m py_compile r1setup` — clean
  - `python3 -m unittest discover tests -v` — 252 tests, all passed
  - New tests added to `tests/test_r1setup_core.py`:
    - `TestHasActiveConfigShell` (4 tests): true_when_hosts_exist, true_for_zero_host_shell, false_when_no_config, false_when_config_file_missing
    - `TestPhase0Wording` (3 tests): suggested_action_no_config_says_create_or_load, suggested_action_never_deployed_says_instances, deployment_display_tracking_live_says_fleet_status
  - Updated existing `test_suggested_action_prefers_review_for_tracked_live_nodes` to match new wording
- Commit(s): (pending)
- Follow-up notes: None. All changes are additive or string-only. No behavioral regressions.

#### Phase 1

- Status: not started
- Scope notes:
- Actual behavior shipped:
- Tests run:
- Commit(s):
- Follow-up notes:

#### Phase 2

- Status: not started
- Scope notes:
- Actual behavior shipped:
- Tests run:
- Commit(s):
- Follow-up notes:

#### Phase 3

- Status: not started
- Scope notes:
- Actual behavior shipped:
- Tests run:
- Commit(s):
- Follow-up notes:

#### Phase 4

- Status: not started
- Scope notes:
- Actual behavior shipped:
- Tests run:
- Commit(s):
- Follow-up notes:

#### Phase 5

- Status: not started
- Scope notes:
- Actual behavior shipped:
- Tests run:
- Commit(s):
- Follow-up notes:

#### Phase 6

- Status: not started
- Scope notes:
- Actual behavior shipped:
- Tests run:
- Commit(s):
- Follow-up notes:

#### Phase 7

- Status: not started
- Scope notes:
- Actual behavior shipped:
- Tests run:
- Commit(s):
- Follow-up notes:
