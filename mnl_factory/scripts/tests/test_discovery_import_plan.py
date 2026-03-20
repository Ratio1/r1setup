#!/usr/bin/env python3
"""Tests for selective discovery import into the current config."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestDiscoveryImportPlan(unittest.TestCase):
    """Tests the import helper that persists selected discovered services."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_path = Path(self.temp_dir.name)

        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.inventory = {
            "all": {
                "vars": {"mnl_app_env": "mainnet"},
                "children": {"gpu_nodes": {"hosts": {}}},
            }
        }
        app.config_dir = self.base_path
        app.configs_dir = self.base_path / "configs"
        app.configs_dir.mkdir(parents=True, exist_ok=True)
        app.config_file = self.base_path / "hosts.yml"
        app.vars_file = self.base_path / "group_vars" / "variables.yml"
        app.active_config_file = self.base_path / "active_config.json"
        app.print_colored = MagicMock()
        app.print_debug = MagicMock()
        app.wait_for_enter = MagicMock()
        app._load_active_config = MagicMock()
        app.config_manager = r1setup.ConfigurationManager(app)
        app.config_manager._save_active_config = MagicMock()
        app.config_manager._update_hosts_symlink = MagicMock()
        app.status_tracker = MagicMock()
        app.active_config["config_name"] = "fleet_demo"
        app.active_config["environment"] = "mainnet"

        self.app = app
        self.cm = app.config_manager
        self.cm.ensure_configuration_shell("fleet_demo", "mainnet")

        self.cm.upsert_machine_record("machine-a", {
            "machine_id": "machine-a",
            "ansible_host": "10.0.0.10",
            "ansible_user": "root",
            "ansible_port": 22,
            "topology_mode": "standard",
            "deployment_state": "prepared",
            "instance_names": [],
        })

    def test_import_discovery_candidate_preserves_runtime_identity(self):
        result = self.app.import_discovery_candidates(
            "machine-a",
            [{
                "service_name": "edge_node2",
                "service_state": "active",
                "container_name": "edge_node2",
                "container_present": True,
                "container_state": "running",
                "effective_mounts": [
                    {"source": "/var/cache/edge_node2/_local_cache", "destination": "/edge_node/_local_cache", "type": "bind"},
                ],
                "metadata_host_path": "/var/cache/edge_node2/_local_cache/_data/r1setup/metadata.json",
                "service_file_version": "v2",
                "environment": "mainnet",
                "environment_source": "metadata",
            }],
            {"edge_node2": "imported_mainnet"},
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["topology_mode"], "standard")

        hosts = self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]
        imported = hosts["imported_mainnet"]
        self.assertEqual(imported["edge_node_service_name"], "edge_node2")
        self.assertEqual(imported["mnl_docker_container_name"], "edge_node2")
        self.assertEqual(imported["mnl_docker_volume_path"], "/var/cache/edge_node2/_local_cache")
        self.assertTrue(imported["imported_from_discovery"])
        self.assertEqual(imported["node_status"], "running")

        fleet_state = self.cm.get_fleet_state_copy()
        instance = fleet_state["fleet"]["instances"]["imported_mainnet"]
        self.assertTrue(instance["imported_from_discovery"])
        self.assertEqual(instance["runtime"]["service_name"], "edge_node2")
        self.assertEqual(instance["discovery_import"]["environment"], "mainnet")

    def test_importing_second_candidate_on_standard_machine_promotes_to_expert(self):
        existing_host = {
            "ansible_host": "10.0.0.10",
            "ansible_user": "root",
            "r1setup_machine_id": "machine-a",
            "r1setup_topology_mode": "standard",
            "r1setup_machine_deployment_state": "active",
            "r1setup_runtime_name_policy": "preserve",
            "edge_node_service_name": "edge_node",
            "mnl_docker_container_name": "edge_node",
            "mnl_docker_volume_path": "/var/cache/edge_node/_local_cache",
            "mnl_r1setup_metadata_host_path": "/var/cache/edge_node/_local_cache/_data/r1setup/metadata.json",
            "r1setup_runtime_exit_status_path": "/tmp/edge_node.exit",
            "node_status": "running",
            "last_status_update": "2026-03-20T00:00:00",
        }
        self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["nodea"] = existing_host
        self.cm.fleet_state = self.cm.build_fleet_state(self.app.inventory)
        self.cm._save_config_with_metadata("fleet_demo", "mainnet", 1, update_symlink=False)

        result = self.app.import_discovery_candidates(
            "machine-a",
            [{
                "service_name": "edge_node2",
                "service_state": "inactive",
                "container_name": "edge_node2",
                "container_present": False,
                "container_state": "",
                "effective_mounts": [
                    {"source": "/var/cache/edge_node2/_local_cache", "destination": "/edge_node/_local_cache", "type": "bind"},
                ],
                "metadata_host_path": "/var/cache/edge_node2/_local_cache/_data/r1setup/metadata.json",
                "service_file_version": "v2",
                "environment": "mainnet",
                "environment_source": "metadata",
            }],
            {"edge_node2": "nodeb"},
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["topology_mode"], "expert")

        hosts = self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]
        self.assertEqual(hosts["nodea"]["r1setup_topology_mode"], "expert")
        self.assertEqual(hosts["nodeb"]["r1setup_topology_mode"], "expert")

        fleet_state = self.cm.get_fleet_state_copy()
        self.assertEqual(fleet_state["fleet"]["machines"]["machine-a"]["topology_mode"], "expert")
        self.assertEqual(sorted(fleet_state["fleet"]["machines"]["machine-a"]["instance_names"]), ["nodea", "nodeb"])
