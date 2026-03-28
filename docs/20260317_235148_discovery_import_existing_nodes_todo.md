# Discovery And Selective Import TODO

Created At: `2026-03-17T23:51:48+02:00`

## Purpose

Plan a safe discovery and selective-import workflow so `r1setup` can:

- register a machine
- inspect that machine for already deployed Edge Node services
- let the user choose which discovered services to add into the current config
- keep unselected services untouched
- support the same physical machine being represented differently across different saved configs

This feature must work with the already planned `standard` and `expert` topology model and must not break existing deployments or existing configs.

## Product Goals

- Allow an operator to add a machine and discover existing Edge Node services on it.
- Allow the operator to import only selected discovered services into the current config.
- Allow the same machine to have mainnet, testnet, and devnet services while importing only the subset relevant to the current config.
- Preserve discovered runtime names on first import instead of normalizing them automatically.
- Avoid mutating remote state during discovery.

## Core Rules

- Discovery is read-only.
- Import is explicit and selective.
- Discovery must not auto-import all discovered services.
- Service names like `edge_node2` or `edge_node_mainnet` are not topology signals by themselves.
- The same physical machine may appear in multiple saved configs.
- A discovered service may be imported into the current config without forcing other services from that machine into the same config.
- Initial import should use `runtime_name_policy = preserve`.

## Operator Workflow

### 1. Register Or Select A Machine

The user either:

- adds a new machine to the fleet without deploying a node
- or selects an already registered machine

### 2. Run Discovery

`r1setup` connects to the selected machine and gathers candidate Edge Node services.

Discovery must collect, when available:

- systemd unit name
- service file path
- service enabled/running/failed state
- container name
- container existence/running state
- mounted volume source and destination
- metadata file path
- exit-status path
- image name or tag
- environment/network inference
- whether the service appears launcher-managed
- machine specs

### 3. Show Discovery Results

The CLI should present a per-candidate review list with enough detail to decide import.

Suggested columns:

- select
- service name
- status
- inferred environment
- inference source
- container name
- volume path
- managed by `r1setup`
- notes

### 4. Select Candidates To Import

The user must be able to:

- import one candidate
- import many candidates
- import none

Unselected candidates remain only as discovery results and are not added to the current config.

### 5. Confirm Import Behavior

Before import is finalized, `r1setup` should show:

- which services will be added to the current config
- the machine they will be associated with
- whether the machine will remain `standard` or become `expert` in this config
- whether any discovered environment mismatches the current config assumptions
- whether any discovered runtime identity already exists in another saved config

### 6. Persist Imported Instances

Imported candidates should be added to the current config with:

- stable instance identity in `r1setup`
- assigned machine id
- discovered runtime names preserved
- discovered environment stored as imported metadata
- machine-level association preserved

## Discovery Signals And Inference Rules

Discovery should prefer explicit launcher metadata when available, but must also support unmanaged or partially managed services.

### Environment Inference Precedence

Use this precedence order:

1. launcher metadata file
2. systemd service file and `systemctl show` environment
3. Docker image tag or runtime environment
4. `unknown`

Store both:

- inferred environment value
- inference source

Recommended values:

- `mainnet`
- `testnet`
- `devnet`
- `unknown`

### Environment Inference Confidence

Each discovered candidate should also carry an operator-facing confidence level:

- `high`
- `best_effort`

Example:

- `env = mainnet`
- `source = service_file`
- `confidence = high`

### Managed-Service Detection

Treat a service as launcher-managed when one or more of these are found:

- `r1setup` metadata file exists in the expected persistent path
- service file contains launcher-managed markers
- helper registry or helper metadata exists

Managed detection is advisory. It should improve presentation and import defaults, but should not be required for import.

## Config Semantics

### Machine Reuse Across Configs

The same machine may appear in multiple saved configs.

This is required so an operator can keep:

- mainnet nodes in one config
- devnet nodes in another config

on the same physical machine.

### Imported Instance Semantics

A selectively imported service should become a normal instance in the current config, but with imported runtime identity preserved.

Recommended persisted fields:

- `logical_name`
- `assigned_machine_id`
- `runtime_name_policy = preserve`
- `runtime.service_name`
- `runtime.container_name`
- `runtime.volume_path`
- `runtime.metadata_path`
- `imported_from_discovery = true`
- `import_discovered_environment`
- `import_environment_source`
- `imported_at`

### Duplicate Detection Across Configs

`r1setup` should detect when the same runtime identity appears in another saved config.

Recommended duplicate key:

- normalized machine endpoint
- discovered service name

Duplicate behavior:

- warn by default
- allow import only with explicit confirmation
- never silently overwrite another config

## Topology Handling

Discovery must not infer topology from service names.

Recommended topology decision rules inside the current config:

- zero imported services: machine may remain `empty`
- one imported service: default to `standard`
- more than one imported service on the same machine in the same config: require `expert`

If the machine already has a topology mode in the current config:

- preserve it when compatible
- require confirmation before changing `standard -> expert`
- reject impossible `expert -> standard` transitions while multiple instances remain assigned

## Safety Rules

- Discovery must not stop, restart, or mutate services.
- Discovery must not rewrite service files.
- Discovery must not rename service, container, or volume identities during import.
- Discovery must not assume all discovered services belong in the current config.
- Discovery must not assume every discovered service is safe to manage until imported.

## Recommended Remote Inspection Strategy

Remote discovery should inspect all of the following where available:

- `systemctl list-unit-files`
- `systemctl list-units --all`
- `systemctl cat <unit>`
- `systemctl show <unit>`
- known service-file locations under `/etc/systemd/system` and `/lib/systemd/system`
- `docker ps -a`
- `docker inspect`
- volume mount bindings
- expected metadata file locations in persistent storage

The discovery layer should normalize raw remote data into one internal candidate model before any UI rendering or import logic runs.

## Internal Python Model

Recommended typed concepts:

- `DiscoveredServiceCandidate`
- `DiscoveryScanResult`
- `DiscoveryEnvironmentInference`
- `DiscoveryImportPlan`
- `ImportedRuntimeIdentity`

Suggested responsibilities:

- `DiscoveredServiceCandidate`
  - normalized view of one discovered remote service
- `DiscoveryScanResult`
  - machine-level scan result plus candidate list and scan warnings
- `DiscoveryEnvironmentInference`
  - environment, source, confidence
- `DiscoveryImportPlan`
  - selected candidates, duplicate warnings, topology result, pending config mutations
- `ImportedRuntimeIdentity`
  - service/container/volume/runtime metadata preserved from discovery

## UI And UX Requirements

- Discovery should be an explicit operator action, not a silent side effect.
- The UI should show candidates individually, not only as a machine summary.
- The user should be able to import only some candidates from one machine.
- The UI should clearly show inferred environment and the source of that inference.
- The UI should warn when the current config environment appears inconsistent with a selected candidate.
- The UI should explain when importing multiple selected services on one machine will make that machine `expert` in the current config.

## Suggested Phased Implementation

### Phase D1: Discovery Data Model And Remote Scan

Implement:

- internal discovery candidate types
- remote inspection helpers
- environment inference
- managed-service detection
- machine-spec collection reuse

Acceptance criteria:

- a discovery scan returns normalized candidates for known service layouts
- environment inference is captured with value, source, and confidence
- unmanaged but matching services can still appear as candidates
- discovery performs no remote mutations

### Phase D2: Discovery Review UI

Implement:

- machine discovery entrypoint in CLI
- candidate review list
- candidate notes and warnings

Acceptance criteria:

- the operator can review candidates one by one
- service status, runtime identity, and inferred environment are visible
- review output makes no config mutations

### Phase D3: Selective Import Planning

Implement:

- multi-select import planning
- duplicate detection across saved configs
- topology outcome calculation
- current-config mismatch warnings

Acceptance criteria:

- the operator can import a subset of discovered candidates
- unselected candidates remain absent from the current config
- duplicate warnings are shown before import
- importing multiple candidates on one machine in one config produces `expert` topology

### Phase D4: Config Persistence And Imported Instance Materialization

Implement:

- selected candidate import into current config
- preserved runtime-name persistence
- imported metadata stamping

Acceptance criteria:

- imported candidates are persisted as config instances
- imported runtime service/container/volume names are preserved
- machine association is stable after save/reload
- config round-trip keeps imported metadata intact

### Phase D5: Discovery-Aware Fleet UX

Implement:

- fleet summary markers for imported services
- clear display of machine reuse and selected imported instances
- visible distinction between empty machine, discovered-only machine, and imported machine in the current config

Acceptance criteria:

- fleet and status screens do not imply that unimported discovered services belong to the current config
- imported services display clearly in grouped machine views
- the same physical machine can appear sensibly in different configs

## Test Coverage Plan

Coverage should be modular and split into focused files.

Recommended test modules:

- `test_discovery_scan.py`
- `test_discovery_inference.py`
- `test_discovery_import_plan.py`
- `test_discovery_duplicates.py`
- `test_discovery_config_roundtrip.py`
- `test_discovery_ui_rendering.py`

Key cases to cover:

- single discovered managed service on a machine
- multiple discovered services on one machine
- mixed mainnet and devnet services on one machine
- environment inferred from service file
- fallback environment inference from metadata and Docker image
- discovered service with unknown environment
- discovered service not imported
- subset import from multiple discovered services
- duplicate runtime identity already present in another config
- service named `edge_node2` imported as a standard single-node config
- multiple selected services on one machine causing expert topology in the current config
- import round-trip preserves service/container/volume paths exactly

## Non-Goals For First Iteration

- automatic import of all discovered services
- automatic renaming of discovered runtime identities
- automatic migration during import
- automatic cleanup of unimported services
- inference of perfect ownership for unmanaged services

## Open Decisions To Resolve Before Coding

- whether discovery should be offered immediately after machine registration or as a separate menu action only
- whether duplicate detection across saved configs is warning-only or block-by-default
- whether current-config environment mismatch should block import or only require confirmation
- whether imported unmanaged services should be tagged differently in the UI after import

## Recommended First Default Choices

If no stronger requirement appears during implementation, use these defaults:

- discovery is offered as an explicit follow-up after machine registration
- duplicate detection is warning-plus-confirmation
- environment mismatch is warning-plus-confirmation
- imported unmanaged services are visually marked as imported-preserved runtimes

## Implementation Sequence Recommendation

This feature should come after grouped visualization is in place and before migration execution becomes a top priority.

Recommended order relative to the broader roadmap:

1. complete grouped visualization and fleet UX
2. implement discovery data model and scan
3. implement selective import planning and persistence
4. integrate discovery-aware fleet views
5. use imported runtime identities as another valid source when later building migration planning

