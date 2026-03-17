#!/usr/bin/env python3
"""Tests for schema-aware fleet-state derivation helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestFleetStateDerivation(unittest.TestCase):
    """Tests deriving a fleet view from legacy inventory data."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_path = Path(self.temp_dir.name)

        self.app = MagicMock()
        self.app.config_dir = self.base_path
        self.app.config_file = self.base_path / "hosts.yml"
        self.app.vars_file = self.base_path / "group_vars" / "variables.yml"
        self.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}
        self.app.print_debug = MagicMock()
        self.app.print_colored = MagicMock()

        self.cm = r1setup.ConfigurationManager(self.app)

    def test_build_fleet_state_uses_connection_identity_grouping_for_legacy_hosts(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            },
                            "node-2": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "mnl_docker_container_name": "edge_node2",
                            },
                        }
                    }
                }
            }
        }

        fleet_state = self.cm.build_fleet_state(inventory)

        self.assertEqual(fleet_state["config_schema_version"], r1setup.CONFIG_SCHEMA_VERSION)
        machines = fleet_state["fleet"]["machines"]
        instances = fleet_state["fleet"]["instances"]

        self.assertEqual(list(machines.keys()), ["root@10.0.0.1:22"])
        self.assertEqual(machines["root@10.0.0.1:22"]["instance_names"], ["node-1", "node-2"])
        self.assertEqual(instances["node-1"]["assigned_machine_id"], "root@10.0.0.1:22")
        self.assertEqual(instances["node-2"]["runtime"]["container_name"], "edge_node2")

    def test_build_fleet_state_prefers_explicit_machine_id(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                            }
                        }
                    }
                }
            }
        }

        fleet_state = self.cm.build_fleet_state(inventory)

        self.assertIn("machine-a", fleet_state["fleet"]["machines"])
        self.assertEqual(
            fleet_state["fleet"]["instances"]["node-1"]["assigned_machine_id"],
            "machine-a",
        )

