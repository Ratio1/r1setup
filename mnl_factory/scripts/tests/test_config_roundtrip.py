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

