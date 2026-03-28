#!/usr/bin/env python3
"""Tests for cross-config discovery duplicate detection."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import yaml

from tests.support import r1setup


class TestDiscoveryDuplicateClaims(unittest.TestCase):
    """Ensure discovery can warn when a runtime is already tracked elsewhere."""

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
                "children": {"gpu_nodes": {"hosts": {}}},
            }
        }
        self.app.print_debug = MagicMock()
        self.app.print_colored = MagicMock()

        self.cm = r1setup.ConfigurationManager(self.app)
        self.cm._save_active_config = MagicMock()
        self.cm._update_hosts_symlink = MagicMock()

    def test_find_runtime_identity_claims_returns_other_config_claims(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "imported_mainnet": {
                                "ansible_host": "10.0.0.2",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-b",
                                "r1setup_topology_mode": "standard",
                                "r1setup_runtime_name_policy": "preserve",
                                "edge_node_service_name": "edge_node2",
                                "mnl_docker_container_name": "edge_node2",
                                "mnl_docker_volume_path": "/var/cache/edge_node2/_local_cache",
                                "mnl_r1setup_metadata_host_path": "/var/cache/edge_node2/_local_cache/_data/r1setup/metadata.json",
                                "r1setup_runtime_exit_status_path": "/tmp/edge_node2.exit",
                                "node_status": "running",
                                "last_status_update": "2026-03-20T00:00:00",
                            }
                        }
                    }
                }
            }
        }
        fleet_state = self.cm.build_fleet_state(inventory)

        (self.app.configs_dir / "other_config.yml").write_text(yaml.safe_dump(inventory), encoding="utf-8")
        (self.app.configs_dir / "other_config.json").write_text(json.dumps({
            "config_name": "other_config",
            "fleet_state": fleet_state,
        }, indent=2), encoding="utf-8")

        claims = self.cm.find_runtime_identity_claims(
            {
                "ansible_host": "10.0.0.2",
                "ansible_user": "root",
                "ansible_port": 22,
            },
            "edge_node2",
            exclude_config_name="current_config",
        )

        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["config_name"], "other_config")
        self.assertEqual(claims[0]["instance_name"], "imported_mainnet")
