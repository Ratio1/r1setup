#!/usr/bin/env python3
"""End-to-end tests for the machine-first onboarding flow (Phases 0-4).

These tests use real SSH connections to remote machines.  They do NOT deploy
anything — they only exercise registration, discovery probes, config
persistence, and inventory building.

All persistent state is created inside temporary directories so that the
operator's real ~/.ratio1 is never touched.

Run with:
    cd mnl_factory/scripts
    python3 -m unittest tests.e2e.test_machine_first_onboarding -v
"""

import json
import os
import subprocess
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.support import r1setup

# ---------------------------------------------------------------------------
# Test machines — update these if the IPs change
# ---------------------------------------------------------------------------
MACHINES = [
    {"label": "machine-1", "host": "35.228.69.214", "user": "vitalii", "port": 22},
    {"label": "machine-2", "host": "34.88.90.109", "user": "vitalii", "port": 22},
]

SSH_TIMEOUT = 15  # seconds


def _ssh_reachable(host: str, user: str, port: int = 22) -> bool:
    """Quick SSH connectivity check."""
    cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no",
        "-o", f"ConnectTimeout={SSH_TIMEOUT}",
        "-o", "BatchMode=yes",
        "-p", str(port),
        f"{user}@{host}",
        "true",
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=SSH_TIMEOUT + 5)
        return True
    except Exception:
        return False


def _require_ssh():
    """Skip the entire test class if machines are unreachable."""
    for m in MACHINES:
        if not _ssh_reachable(m["host"], m["user"], m["port"]):
            raise unittest.SkipTest(
                f"SSH to {m['user']}@{m['host']} failed — skipping e2e tests"
            )


# ---------------------------------------------------------------------------
# Helpers to build a real ConfigurationManager with temp-dir isolation
# ---------------------------------------------------------------------------

def _make_real_app():
    """Build a real R1Setup instance with settings_manager initialized.

    Uses __new__ + selective attribute initialization to avoid the full
    constructor (which needs Ansible, venv, etc.) while still providing
    the properties that SSH probes and discovery rely on.
    """
    app = r1setup.R1Setup.__new__(r1setup.R1Setup)
    app.print_colored = MagicMock()
    app.print_debug = MagicMock()
    app.print_section = MagicMock()
    app.print_header = MagicMock()
    app.wait_for_enter = MagicMock()
    # SettingsManager needs a real __init__ for self.settings
    # We give it a minimal app-like object with the paths it needs
    sm_app = MagicMock()
    sm_app.r1_setup_dir = Path(tempfile.mkdtemp(prefix="r1setup_sm_"))
    sm_app.print_debug = MagicMock()
    app.settings_manager = r1setup.SettingsManager(sm_app)
    return app


def _make_isolated_app_and_cm():
    """Build a real ConfigurationManager backed by a temp directory.

    Returns (app_mock, cm, temp_dir) where app_mock has real paths but
    mocked UI methods.
    """
    temp_dir = tempfile.mkdtemp(prefix="r1setup_e2e_")
    base = Path(temp_dir)

    app = MagicMock()
    app.config_dir = base
    app.configs_dir = base / "configs"
    app.configs_dir.mkdir(parents=True, exist_ok=True)
    app.config_file = base / "hosts.yml"
    app.vars_file = base / "group_vars" / "variables.yml"
    app.active_config_file = base / "active_config.json"
    app.inventory = {
        "all": {
            "vars": {},
            "children": {"gpu_nodes": {"hosts": {}}},
        },
    }
    app.print_debug = MagicMock()
    app.print_colored = MagicMock()
    app.print_section = MagicMock()
    app.print_header = MagicMock()
    app.wait_for_enter = MagicMock()

    # Wire real R1Setup static/class methods that the CM needs
    app._extract_machine_access_config = r1setup.R1Setup._extract_machine_access_config
    app._get_valid_hostname = MagicMock(side_effect=lambda prompt, default, **kw: default)

    cm = r1setup.ConfigurationManager(app)
    cm._save_active_config = MagicMock()
    cm._update_hosts_symlink = MagicMock()

    return app, cm, temp_dir


def _cleanup_temp(temp_dir: str):
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


# ===================================================================
# Test cases
# ===================================================================

class Test01SSHConnectivity(unittest.TestCase):
    """Verify SSH access to both test machines."""

    @classmethod
    def setUpClass(cls):
        _require_ssh()

    def test_machine_1_reachable(self):
        m = MACHINES[0]
        self.assertTrue(_ssh_reachable(m["host"], m["user"], m["port"]))

    def test_machine_2_reachable(self):
        m = MACHINES[1]
        self.assertTrue(_ssh_reachable(m["host"], m["user"], m["port"]))


class Test02SpecProbe(unittest.TestCase):
    """Verify spec probe works against real machines."""

    @classmethod
    def setUpClass(cls):
        _require_ssh()

    def _probe(self, machine_info):
        """Run the real spec probe against a machine."""
        machine_config = {
            "ansible_host": machine_info["host"],
            "ansible_user": machine_info["user"],
            "ansible_port": machine_info["port"],
        }
        app = _make_real_app()
        return app._probe_machine_specs(machine_config)

    def test_machine_1_specs(self):
        result = self._probe(MACHINES[0])
        self.assertEqual(result["status"], "success", f"Probe failed: {result}")
        self.assertGreater(result["cpu_total"], 0)
        self.assertGreater(result["memory_gb_total"], 0)
        self.assertIn("hostname", result)
        print(f"  machine-1: {result['hostname']}, {result['cpu_total']} CPU, "
              f"{result['memory_gb_total']:.1f} GiB RAM")

    def test_machine_2_specs(self):
        result = self._probe(MACHINES[1])
        self.assertEqual(result["status"], "success", f"Probe failed: {result}")
        self.assertGreater(result["cpu_total"], 0)
        self.assertGreater(result["memory_gb_total"], 0)
        print(f"  machine-2: {result['hostname']}, {result['cpu_total']} CPU, "
              f"{result['memory_gb_total']:.1f} GiB RAM")


class Test03DiscoveryProbe(unittest.TestCase):
    """Verify the remote discovery probe script runs and returns valid JSON."""

    @classmethod
    def setUpClass(cls):
        _require_ssh()

    def _discover(self, machine_info):
        """Run the real discovery against a machine."""
        machine_config = {
            "ansible_host": machine_info["host"],
            "ansible_user": machine_info["user"],
            "ansible_port": machine_info["port"],
            "machine_id": machine_info["label"],
        }
        app = _make_real_app()
        app.config_manager = MagicMock()
        app.config_manager._format_machine_display_label = MagicMock(return_value=machine_info["label"])
        return app.discover_existing_edge_node_services(machine_config)

    def test_machine_1_discovery(self):
        result = self._discover(MACHINES[0])
        self.assertEqual(result["status"], "success", f"Discovery failed: {result}")
        self.assertIsInstance(result["candidates"], list)
        print(f"  machine-1: {result['candidate_count']} candidate(s)")

    def test_machine_2_discovery(self):
        result = self._discover(MACHINES[1])
        self.assertEqual(result["status"], "success", f"Discovery failed: {result}")
        self.assertIsInstance(result["candidates"], list)
        print(f"  machine-2: {result['candidate_count']} candidate(s)")


class Test04ConfigShellCreation(unittest.TestCase):
    """Verify an empty config shell with fleet metadata can be persisted."""

    def test_create_config_shell(self):
        app, cm, temp_dir = _make_isolated_app_and_cm()
        try:
            cm.ensure_configuration_shell("test_20260329_1200_0m", "testnet")

            # Config YAML should exist
            config_path = app.configs_dir / "test_20260329_1200_0m.yml"
            self.assertTrue(config_path.exists(), "Config YAML not created")

            # Metadata JSON should exist
            meta_path = app.configs_dir / "test_20260329_1200_0m.json"
            self.assertTrue(meta_path.exists(), "Metadata JSON not created")

            # Metadata should have correct fields
            metadata = json.loads(meta_path.read_text())
            self.assertEqual(metadata["config_name"], "test_20260329_1200_0m")
            self.assertEqual(metadata["environment"], "testnet")
            self.assertEqual(metadata["nodes_count"], 0)
            self.assertIn("fleet_state", metadata)
            self.assertIn("machines_count", metadata)
        finally:
            _cleanup_temp(temp_dir)


class Test05MachineRegistration(unittest.TestCase):
    """Verify machine records are persisted in fleet state."""

    def test_register_two_machines(self):
        app, cm, temp_dir = _make_isolated_app_and_cm()
        try:
            # Create shell first
            cm.ensure_configuration_shell("test_20260329_1200_2m", "testnet")

            # Register both machines
            for m in MACHINES:
                machine_data = {
                    "topology_mode": "standard",
                    "deployment_state": "empty",
                    "instance_names": [],
                    "ansible_host": m["host"],
                    "ansible_user": m["user"],
                    "ansible_port": m["port"],
                }
                cm.upsert_machine_record(m["label"], machine_data)

            # Verify fleet state
            fleet = cm.get_fleet_state_copy()
            machines = fleet["fleet"]["machines"]
            self.assertEqual(len(machines), 2)
            self.assertIn("machine-1", machines)
            self.assertIn("machine-2", machines)
            self.assertEqual(machines["machine-1"]["ansible_host"], "35.228.69.214")
            self.assertEqual(machines["machine-2"]["ansible_host"], "34.88.90.109")
            self.assertEqual(machines["machine-1"]["topology_mode"], "standard")

            # Verify metadata persisted machines_count
            meta_path = app.configs_dir / "test_20260329_1200_2m.json"
            metadata = json.loads(meta_path.read_text())
            self.assertEqual(metadata["machines_count"], 2)
            self.assertEqual(metadata["nodes_count"], 0)

            print(f"  Registered {len(machines)} machines in fleet state")
        finally:
            _cleanup_temp(temp_dir)


class Test06DiscoveryScan(unittest.TestCase):
    """Verify batch discovery scan and result caching."""

    @classmethod
    def setUpClass(cls):
        _require_ssh()

    def test_batch_discover_both_machines(self):
        app, cm, temp_dir = _make_isolated_app_and_cm()
        try:
            # Create shell and register machines
            cm.ensure_configuration_shell("test_20260329_1200_2m", "testnet")
            for m in MACHINES:
                cm.upsert_machine_record(m["label"], {
                    "topology_mode": "standard",
                    "deployment_state": "empty",
                    "instance_names": [],
                    "ansible_host": m["host"],
                    "ansible_user": m["user"],
                    "ansible_port": m["port"],
                })

            # Wire real discovery through the app mock
            real_app = _make_real_app()
            app.discover_existing_edge_node_services = real_app.discover_existing_edge_node_services

            # Run batch discovery
            scan_buffer = cm._batch_discover_machines(["machine-1", "machine-2"])

            # Both should succeed (clean machines)
            self.assertEqual(scan_buffer["machine-1"]["status"], "success")
            self.assertEqual(scan_buffer["machine-2"]["status"], "success")

            # Classify
            classified = cm._classify_scan_results(scan_buffer)
            # These machines should be clean (no edge_node services)
            print(f"  clean: {classified['clean']}")
            print(f"  discovered: {classified['discovered']}")
            print(f"  failed: {classified['failed']}")

            # Persist results
            cm._persist_batch_discovery_results(scan_buffer)

            # Verify scan cached in fleet state
            fleet = cm.get_fleet_state_copy()
            for mid in ["machine-1", "machine-2"]:
                machine = fleet["fleet"]["machines"][mid]
                self.assertIn("discovery", machine)
                self.assertIn("last_scanned_at", machine["discovery"])
                self.assertIsInstance(machine["discovery"]["candidates"], list)

            print(f"  Scan results cached for both machines")
        finally:
            _cleanup_temp(temp_dir)


class Test07FreshHostBuilding(unittest.TestCase):
    """Verify fresh host entry is built correctly from machine record."""

    def test_build_fresh_host_from_registered_machine(self):
        app, cm, temp_dir = _make_isolated_app_and_cm()
        try:
            # Create shell and register a machine
            cm.ensure_configuration_shell("test_20260329_1200_1m", "testnet")
            cm.upsert_machine_record("machine-1", {
                "topology_mode": "standard",
                "deployment_state": "empty",
                "instance_names": [],
                "ansible_host": "35.228.69.214",
                "ansible_user": "vitalii",
                "ansible_port": 22,
            })

            # Build fresh host
            host = cm._build_fresh_host_entry("machine-1", "machine-1")

            # Verify SSH fields copied from machine record
            self.assertEqual(host["ansible_host"], "35.228.69.214")
            self.assertEqual(host["ansible_user"], "vitalii")
            self.assertEqual(host["ansible_port"], 22)

            # Verify instance identity
            self.assertEqual(host["r1setup_machine_id"], "machine-1")
            self.assertEqual(host["r1setup_instance_logical_name"], "machine-1")
            self.assertEqual(host["r1setup_topology_mode"], "standard")
            self.assertEqual(host["r1setup_runtime_name_policy"], "normalize_to_target")

            # Verify status
            self.assertEqual(host["node_status"], "never_deployed")
            self.assertIn("last_status_update", host)

            # Verify standard runtime names were resolved
            self.assertEqual(host.get("edge_node_service_name"), "edge_node")
            self.assertEqual(host.get("mnl_docker_container_name"), "edge_node")
            self.assertIn("edge_node", host.get("mnl_docker_volume_path", ""))

            print(f"  Fresh host built: {host['ansible_user']}@{host['ansible_host']}")
            print(f"  Runtime: service={host.get('edge_node_service_name')}, "
                  f"container={host.get('mnl_docker_container_name')}")
        finally:
            _cleanup_temp(temp_dir)


class Test08GapFill(unittest.TestCase):
    """Verify gap fill creates inventory hosts from machine records."""

    def test_gap_fill_two_clean_machines(self):
        app, cm, temp_dir = _make_isolated_app_and_cm()
        try:
            # Create shell and register machines
            cm.ensure_configuration_shell("test_20260329_1200_2m", "testnet")
            for m in MACHINES:
                cm.upsert_machine_record(m["label"], {
                    "topology_mode": "standard",
                    "deployment_state": "empty",
                    "instance_names": [],
                    "ansible_host": m["host"],
                    "ansible_user": m["user"],
                    "ansible_port": m["port"],
                })

            # Mock user accepting gap fill
            app.get_input = MagicMock(return_value="Y")

            count = cm._onboarding_gap_fill_clean_machines(
                ["machine-1", "machine-2"], "testnet",
            )

            self.assertEqual(count, 2)

            # Verify hosts were added to inventory
            hosts = r1setup._get_gpu_hosts(app.inventory)
            self.assertEqual(len(hosts), 2)
            self.assertIn("machine-1", hosts)
            self.assertIn("machine-2", hosts)

            # Verify each host has correct fields
            for label in ["machine-1", "machine-2"]:
                host = hosts[label]
                self.assertEqual(host["node_status"], "never_deployed")
                self.assertEqual(host["r1setup_machine_id"], label)
                self.assertEqual(host["r1setup_topology_mode"], "standard")

            # Verify fleet state updated
            fleet = cm.get_fleet_state_copy()
            for label in ["machine-1", "machine-2"]:
                machine = fleet["fleet"]["machines"][label]
                self.assertEqual(machine["deployment_state"], "active")
                self.assertIn(label, machine["instance_names"])

            # Verify metadata was saved with correct node count
            meta_path = app.configs_dir / "test_20260329_1200_2m.json"
            metadata = json.loads(meta_path.read_text())
            self.assertEqual(metadata["nodes_count"], 2)
            self.assertEqual(metadata["machines_count"], 2)

            print(f"  Gap fill created {count} instances")
            print(f"  Inventory hosts: {list(hosts.keys())}")
        finally:
            _cleanup_temp(temp_dir)


class Test09FullOnboardingFlow(unittest.TestCase):
    """Full end-to-end onboarding: register -> discover -> gap fill."""

    @classmethod
    def setUpClass(cls):
        _require_ssh()

    def test_full_machine_first_flow(self):
        app, cm, temp_dir = _make_isolated_app_and_cm()
        try:
            # Wire real discovery and probe via a properly initialized app
            real_app = _make_real_app()
            app.discover_existing_edge_node_services = real_app.discover_existing_edge_node_services
            app._probe_machine_specs = real_app._probe_machine_specs

            # Step 1: Create config shell
            config_name = "e2e-test_20260329_1200_2m"
            env = "testnet"
            cm._reset_inventory_for_new_config()
            cm.ensure_configuration_shell(config_name, env)
            cm.set_mnl_app_env = MagicMock()

            print("\n  === Step 1: Config shell created ===")
            print(f"  Config: {config_name}, env: {env}")

            # Step 2: Register machines (simulate _collect_machine_registration_entries)
            registered_ids = []
            for m in MACHINES:
                machine_data = {
                    "topology_mode": "standard",
                    "deployment_state": "empty",
                    "instance_names": [],
                    "ansible_host": m["host"],
                    "ansible_user": m["user"],
                    "ansible_port": m["port"],
                }
                # Real spec probe
                probe_result = app._probe_machine_specs(machine_data)
                if probe_result.get("status") == "success":
                    machine_data["machine_specs"] = {
                        "hostname": probe_result["hostname"],
                        "cpu_total": probe_result["cpu_total"],
                        "memory_gb_total": probe_result["memory_gb_total"],
                        "last_checked_at": probe_result["last_checked_at"],
                    }

                cm.upsert_machine_record(m["label"], machine_data)
                registered_ids.append(m["label"])

            print(f"\n  === Step 2: {len(registered_ids)} machines registered ===")
            fleet = cm.get_fleet_state_copy()
            for mid in registered_ids:
                machine = fleet["fleet"]["machines"][mid]
                specs = machine.get("machine_specs", {})
                print(f"  {mid}: {machine.get('ansible_user')}@{machine.get('ansible_host')} "
                      f"({specs.get('hostname', '?')}, {specs.get('cpu_total', '?')} CPU, "
                      f"{specs.get('memory_gb_total', '?')} GiB)")

            # Step 3: Batch discovery
            scan_buffer = cm._batch_discover_machines(registered_ids)
            cm._persist_batch_discovery_results(scan_buffer)
            classified = cm._classify_scan_results(scan_buffer)

            print(f"\n  === Step 3: Discovery scan complete ===")
            print(f"  Clean: {classified['clean']}")
            print(f"  Discovered: {classified['discovered']}")
            print(f"  Failed: {classified['failed']}")

            # Verify both scans succeeded
            for mid in registered_ids:
                self.assertEqual(scan_buffer[mid]["status"], "success",
                                 f"Scan failed for {mid}: {scan_buffer[mid]}")

            # Step 4: Gap fill (machines should be clean)
            app.get_input = MagicMock(return_value="Y")
            fresh_count = cm._onboarding_gap_fill_clean_machines(classified["clean"], env)

            print(f"\n  === Step 4: Gap fill created {fresh_count} instances ===")

            # Step 5: Verify final state
            hosts = r1setup._get_gpu_hosts(app.inventory)
            fleet = cm.get_fleet_state_copy()

            print(f"\n  === Step 5: Final state ===")
            print(f"  Inventory hosts: {len(hosts)}")
            for name, cfg in hosts.items():
                print(f"    {name}: {cfg.get('ansible_user')}@{cfg.get('ansible_host')} "
                      f"[{cfg.get('node_status')}] "
                      f"service={cfg.get('edge_node_service_name')} "
                      f"container={cfg.get('mnl_docker_container_name')}")

            print(f"  Fleet machines: {len(fleet['fleet']['machines'])}")
            for mid, rec in fleet["fleet"]["machines"].items():
                print(f"    {mid}: state={rec.get('deployment_state')} "
                      f"instances={rec.get('instance_names')}")

            # Verify metadata
            meta_path = app.configs_dir / f"{config_name}.json"
            metadata = json.loads(meta_path.read_text())
            print(f"  Metadata: nodes_count={metadata['nodes_count']}, "
                  f"machines_count={metadata['machines_count']}")

            # Assertions
            self.assertEqual(len(hosts), len(classified["clean"]))
            self.assertEqual(metadata["machines_count"], 2)
            self.assertEqual(metadata["nodes_count"], len(classified["clean"]))
            for mid in classified["clean"]:
                self.assertIn(mid, hosts)
                self.assertEqual(hosts[mid]["node_status"], "never_deployed")
                self.assertEqual(hosts[mid]["r1setup_topology_mode"], "standard")
                machine = fleet["fleet"]["machines"][mid]
                self.assertEqual(machine["deployment_state"], "active")
                self.assertIn(mid, machine["instance_names"])

            print(f"\n  === E2E PASS: Full machine-first onboarding flow verified ===")
        finally:
            _cleanup_temp(temp_dir)


class Test10HasActiveConfigShell(unittest.TestCase):
    """Verify Phase 0 has_active_config_shell works with real config files."""

    def test_shell_valid_with_zero_hosts(self):
        app, cm, temp_dir = _make_isolated_app_and_cm()
        try:
            cm.ensure_configuration_shell("shell_20260329_1200_0m", "testnet")

            # Simulate has_active_config_shell check
            config_name = cm.active_config.get("config_name")
            self.assertIsNotNone(config_name)

            config_path = app.configs_dir / f"{config_name}.yml"
            self.assertTrue(config_path.exists())

            # Hosts should be empty
            hosts = r1setup._get_gpu_hosts(app.inventory)
            self.assertEqual(len(hosts), 0)

            print(f"  Zero-host shell is valid: {config_name}")
        finally:
            _cleanup_temp(temp_dir)


if __name__ == "__main__":
    unittest.main(verbosity=2)
