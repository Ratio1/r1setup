#!/usr/bin/env python3
"""Tests for schema-aware configuration upgrade helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestSchemaAwareFleetStateHelpers(unittest.TestCase):
    """Tests helper behavior around fleet-state normalization and merging."""

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

    def test_normalize_fleet_state_backfills_expected_structure(self):
        normalized = self.cm._normalize_fleet_state({})

        self.assertEqual(normalized["config_schema_version"], r1setup.CONFIG_SCHEMA_VERSION)
        self.assertEqual(normalized["fleet"]["machines"], {})
        self.assertEqual(normalized["fleet"]["instances"], {})

    def test_merge_fleet_state_preserves_empty_machine_records(self):
        persisted = {
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
        }
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            }
                        }
                    }
                }
            }
        }

        merged = self.cm._merge_fleet_state(persisted, inventory)

        self.assertIn("machine-b", merged["fleet"]["machines"])
        self.assertIn("root@10.0.0.1:22", merged["fleet"]["machines"])
        self.assertEqual(
            merged["fleet"]["machines"]["machine-b"]["instance_names"],
            [],
        )
        self.assertIn("node-1", merged["fleet"]["instances"])

