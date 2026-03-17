#!/usr/bin/env python3
"""Tests for fleet machine-registration persistence helpers."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestMachineRegistrationPersistence(unittest.TestCase):
    """Tests persisting machine-only fleet records without node deployment."""

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
                        "hosts": {}
                    }
                },
            }
        }
        self.app.print_debug = MagicMock()
        self.app.print_colored = MagicMock()

        self.cm = r1setup.ConfigurationManager(self.app)
        self.cm._save_active_config = MagicMock()
        self.cm._update_hosts_symlink = MagicMock()

    def test_ensure_configuration_shell_persists_zero_node_config(self):
        self.cm.ensure_configuration_shell("fleet", "mainnet")

        metadata = json.loads((self.app.configs_dir / "fleet.json").read_text())

        self.assertEqual(metadata["nodes_count"], 0)
        self.assertEqual(metadata["config_schema_version"], r1setup.CONFIG_SCHEMA_VERSION)
        self.assertIn("fleet_state", metadata)

    def test_upsert_machine_record_persists_empty_machine(self):
        self.cm.ensure_configuration_shell("fleet", "mainnet")

        self.cm.upsert_machine_record("machine-b", {
            "ansible_host": "10.0.0.2",
            "ansible_user": "root",
            "ansible_port": 22,
            "topology_mode": "standard",
            "deployment_state": "empty",
            "instance_names": [],
        })

        metadata = json.loads((self.app.configs_dir / "fleet.json").read_text())
        machine = metadata["fleet_state"]["fleet"]["machines"]["machine-b"]

        self.assertEqual(machine["ansible_host"], "10.0.0.2")
        self.assertEqual(machine["deployment_state"], "empty")
        self.assertEqual(machine["instance_names"], [])

