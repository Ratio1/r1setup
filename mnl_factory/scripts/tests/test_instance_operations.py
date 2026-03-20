#!/usr/bin/env python3
"""Tests for edit/delete instance persistence behavior."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from tests.support import r1setup


class TestInstanceOperations(unittest.TestCase):
    """Focused tests for edit/remove persistence on shared machines."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_path = Path(self.temp_dir.name)

        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "nodea": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                                "r1setup_topology_mode": "expert",
                                "r1setup_runtime_name_policy": "preserve",
                                "edge_node_service_name": "edge_node",
                                "mnl_docker_container_name": "edge_node",
                                "mnl_docker_volume_path": "/var/cache/edge_node/_local_cache",
                                "mnl_r1setup_metadata_host_path": "/var/cache/edge_node/_local_cache/_data/r1setup/metadata.json",
                                "r1setup_runtime_exit_status_path": "/tmp/edge_node.exit",
                            },
                            "nodeb": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                                "r1setup_topology_mode": "expert",
                                "r1setup_runtime_name_policy": "normalize_to_target",
                                "edge_node_service_name": "edge_node_nodeb",
                                "mnl_docker_container_name": "edge_node_nodeb",
                                "mnl_docker_volume_path": "/var/cache/edge_node_nodeb/_local_cache",
                                "mnl_r1setup_metadata_host_path": "/var/cache/edge_node_nodeb/_local_cache/_data/r1setup/metadata.json",
                                "r1setup_runtime_exit_status_path": "/tmp/edge_node_nodeb.exit",
                            },
                        }
                    }
                }
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
        app.print_section = MagicMock()
        app._display_node_status = MagicMock()
        app._update_node_status = MagicMock()

        app.config_manager = r1setup.ConfigurationManager(app)
        app.config_manager._save_active_config = MagicMock()
        app.config_manager._update_hosts_symlink = MagicMock()
        app.config_manager.active_config["config_name"] = "demo"
        app.config_manager.active_config["environment"] = "mainnet"
        app.config_manager.fleet_state = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {
                        "machine_id": "machine-a",
                        "ansible_host": "10.0.0.1",
                        "ansible_user": "root",
                        "ansible_port": 22,
                        "topology_mode": "expert",
                        "deployment_state": "active",
                        "instance_names": ["nodea", "nodeb"],
                    }
                },
                "instances": {
                    "nodea": {
                        "assigned_machine_id": "machine-a",
                        "runtime_name_policy": "preserve",
                    },
                    "nodeb": {
                        "assigned_machine_id": "machine-a",
                        "runtime_name_policy": "normalize_to_target",
                    },
                },
            },
        }

        self.app = app

    def _read_metadata(self):
        metadata_path = self.app.configs_dir / "demo.json"
        return json.loads(metadata_path.read_text())

    def _read_inventory(self):
        config_path = self.app.configs_dir / "demo.yml"
        return yaml.safe_load(config_path.read_text())

    def test_delete_node_removes_instance_from_yaml_and_metadata(self):
        self.app.get_input = MagicMock(side_effect=["2", "y"])

        self.app._delete_node()

        saved_inventory = self._read_inventory()
        saved_hosts = saved_inventory["all"]["children"]["gpu_nodes"]["hosts"]
        self.assertEqual(sorted(saved_hosts.keys()), ["nodea"])

        metadata = self._read_metadata()
        self.assertEqual(sorted(metadata["fleet_state"]["fleet"]["instances"].keys()), ["nodea"])
        self.assertEqual(
            metadata["fleet_state"]["fleet"]["machines"]["machine-a"]["instance_names"],
            ["nodea"],
        )
        rendered_text = " ".join(
            str(call.args[0])
            for call in self.app.print_colored.call_args_list
            if call.args
        )
        self.assertIn("remains in expert mode", rendered_text)
        self.assertIn("No automatic downgrade to standard was performed", rendered_text)

    def test_delete_last_instance_retains_machine_as_prepared(self):
        del self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["nodeb"]
        self.app.config_manager.fleet_state["fleet"]["machines"]["machine-a"]["instance_names"] = ["nodea"]
        self.app.config_manager.fleet_state["fleet"]["instances"] = {
            "nodea": {
                "assigned_machine_id": "machine-a",
                "runtime_name_policy": "preserve",
            }
        }
        self.app.get_input = MagicMock(side_effect=["1", "y"])

        self.app._delete_node()

        metadata = self._read_metadata()
        self.assertEqual(metadata["fleet_state"]["fleet"]["instances"], {})
        self.assertEqual(
            metadata["fleet_state"]["fleet"]["machines"]["machine-a"]["instance_names"],
            [],
        )
        self.assertEqual(
            metadata["fleet_state"]["fleet"]["machines"]["machine-a"]["deployment_state"],
            "prepared",
        )

    def test_update_node_preserves_machine_binding_and_runtime_fields(self):
        self.app.get_input = MagicMock(side_effect=["2", "n"])
        self.app._configure_single_node = MagicMock(return_value={
            "ansible_host": "10.0.0.1",
            "ansible_user": "root",
            "node_status": "running",
            "last_status_update": "2026-03-20T00:00:00",
            r1setup.SERVICE_FILE_VERSION_FIELD: "v1",
        })

        self.app._update_node()

        saved_inventory = self._read_inventory()
        nodeb = saved_inventory["all"]["children"]["gpu_nodes"]["hosts"]["nodeb"]
        self.assertEqual(nodeb["r1setup_machine_id"], "machine-a")
        self.assertEqual(nodeb["r1setup_topology_mode"], "expert")
        self.assertEqual(nodeb["r1setup_runtime_name_policy"], "normalize_to_target")
        self.assertEqual(nodeb["edge_node_service_name"], "edge_node_nodeb")
        self.assertEqual(nodeb["mnl_docker_container_name"], "edge_node_nodeb")
