#!/usr/bin/env python3
"""Focused tests for configuration normalization and metadata round-trips."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestConfigurationSchemaMetadata(unittest.TestCase):
    """Tests schema-version metadata persistence and normalization helpers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_path = Path(self.temp_dir.name)

        self.app = MagicMock()
        self.app.config_dir = self.base_path
        self.app.configs_dir = self.base_path / "configs"
        self.app.configs_dir.mkdir(parents=True, exist_ok=True)
        self.app.config_file = self.base_path / "hosts.yml"
        self.app.vars_file = self.base_path / "group_vars" / "variables.yml"
        self.app.active_config_file = self.base_path / "active_config.json"
        self.app.inventory = {
            "all": {
                "vars": {"mnl_app_env": "mainnet"},
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            }
                        }
                    }
                },
            }
        }
        self.app.print_debug = MagicMock()
        self.app.print_colored = MagicMock()

        self.cm = r1setup.ConfigurationManager(self.app)
        self.cm._save_active_config = MagicMock()
        self.cm._update_hosts_symlink = MagicMock()

    def test_save_config_with_metadata_persists_schema_version(self):
        self.cm._save_config_with_metadata("demo", "mainnet", 1, update_symlink=False)

        metadata_path = self.app.configs_dir / "demo.json"
        metadata = json.loads(metadata_path.read_text())

        self.assertEqual(metadata["config_schema_version"], r1setup.CONFIG_SCHEMA_VERSION)
        self.assertIn("fleet_state", metadata)
        self.assertIn("node-1", metadata["fleet_state"]["fleet"]["instances"])

    def test_normalize_inventory_backfills_missing_fields(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "last_status_check": "legacy",
                            }
                        }
                    }
                }
            }
        }

        changed = self.cm._normalize_inventory(inventory)
        host = inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-1"]

        self.assertTrue(changed)
        self.assertEqual(host["node_status"], "unknown")
        self.assertIn("last_status_update", host)
        self.assertEqual(host[r1setup.SERVICE_FILE_VERSION_FIELD], r1setup.DEFAULT_SERVICE_FILE_VERSION)
        self.assertNotIn("last_status_check", host)

    def test_load_configuration_merges_persisted_empty_machines_into_fleet_state(self):
        config_name = "demo"
        self.cm.active_config["config_name"] = config_name
        self.app.config_file.write_text(
            "all:\n"
            "  children:\n"
            "    gpu_nodes:\n"
            "      hosts:\n"
            "        node-1:\n"
            "          ansible_host: 10.0.0.1\n"
            "          ansible_user: root\n"
        )
        metadata_path = self.app.configs_dir / f"{config_name}.json"
        metadata_path.write_text(json.dumps({
            "config_name": config_name,
            "environment": "mainnet",
            "nodes_count": 1,
            "fleet_state": {
                "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
                "fleet": {
                    "machines": {
                        "machine-b": {
                            "machine_id": "machine-b",
                            "ansible_host": "10.0.0.2",
                            "ansible_user": "root",
                            "ansible_port": 22,
                            "topology_mode": "standard",
                            "deployment_state": "empty",
                            "instance_names": [],
                        }
                    },
                    "instances": {},
                },
            },
        }))

        loaded = self.cm.load_configuration()

        self.assertTrue(loaded)
        self.assertIn("machine-b", self.cm.fleet_state["fleet"]["machines"])
        self.assertIn("root@10.0.0.1:22", self.cm.fleet_state["fleet"]["machines"])
        self.assertIn("node-1", self.cm.fleet_state["fleet"]["instances"])

    def test_normalize_inventory_reuses_existing_machine_id_for_same_endpoint(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                            },
                            "node-2": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            },
                        }
                    }
                }
            }
        }
        self.cm.fleet_state = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {
                        "machine_id": "machine-a",
                        "ansible_host": "10.0.0.1",
                        "ansible_user": "root",
                        "ansible_port": 22,
                        "topology_mode": "standard",
                        "deployment_state": "active",
                        "instance_names": ["node-1"],
                    }
                },
                "instances": {
                    "node-1": {
                        "assigned_machine_id": "machine-a",
                    }
                },
            },
        }

        changed = self.cm._normalize_inventory(inventory)

        self.assertTrue(changed)
        self.assertEqual(
            inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-2"]["r1setup_machine_id"],
            "machine-a",
        )
        self.assertEqual(
            inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-2"]["r1setup_topology_mode"],
            "standard",
        )
        self.assertEqual(
            inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-2"]["r1setup_machine_deployment_state"],
            "active",
        )

    def test_bind_host_to_existing_machine_uses_canonical_machine_id(self):
        self.cm.fleet_state = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-b": {
                        "machine_id": "machine-b",
                        "ansible_host": "10.0.0.2",
                        "ansible_user": "root",
                        "ansible_port": 22,
                        "topology_mode": "standard",
                        "deployment_state": "prepared",
                        "instance_names": [],
                    }
                },
                "instances": {},
            },
        }

        bound = self.cm.bind_host_to_existing_machine(
            "node-2",
            {
                "ansible_host": "10.0.0.2",
                "ansible_user": "root",
            },
        )

        self.assertEqual(bound["r1setup_machine_id"], "machine-b")
        self.assertEqual(bound["r1setup_topology_mode"], "standard")
        self.assertEqual(bound["r1setup_machine_deployment_state"], "prepared")
