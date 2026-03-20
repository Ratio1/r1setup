#!/usr/bin/env python3
"""Tests for legacy migration-plan repair on load."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestMigrationPlanRepair(unittest.TestCase):
    """Ensure only clearly recoverable stale rollback states are repaired."""

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
                            "nodea": {
                                "ansible_host": "10.0.0.10",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                                "node_status": "running",
                            }
                        }
                    }
                },
            }
        }
        self.app.print_debug = MagicMock()
        self.app.print_colored = MagicMock()

        self.cm = r1setup.ConfigurationManager(self.app)
        self.cm.active_config["config_name"] = "fleet"
        self.cm.active_config["migration_plan_state"] = {
            "plan_id": "migration-nodea",
            "instance_name": "nodea",
            "source_machine_id": "machine-a",
            "target_machine_id": "machine-b",
            "status": "rollback_failed",
            "last_step": "rollback_failed_source_restart",
        }
        self.cm.fleet_state = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {
                        "machine_id": "machine-a",
                        "ansible_host": "10.0.0.10",
                        "ansible_user": "root",
                        "ansible_port": 22,
                        "topology_mode": "standard",
                        "deployment_state": "active",
                        "instance_names": ["nodea"],
                    }
                },
                "instances": {
                    "nodea": {
                        "logical_name": "nodea",
                        "assigned_machine_id": "machine-a",
                        "runtime_name_policy": "preserve",
                        "runtime": {"service_name": "edge_node"},
                        "status": {"node_status": "running", "service_file_version": "v1"},
                    }
                },
            },
        }

    def test_reconcile_legacy_plan_repairs_running_source_assignment(self):
        result = self.cm.reconcile_legacy_migration_plan_state(self.app.inventory)

        self.assertTrue(result["changed"])
        self.assertEqual(result["plan"]["status"], "rolled_back")
        self.assertEqual(result["plan"]["last_step"], "rollback_completed")
        self.assertEqual(result["plan"]["legacy_repair"]["reason"], "source_runtime_already_running")

    def test_reconcile_legacy_plan_does_not_repair_ambiguous_assignment(self):
        self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["nodea"]["r1setup_machine_id"] = "machine-b"

        result = self.cm.reconcile_legacy_migration_plan_state(self.app.inventory)

        self.assertFalse(result["changed"])
        self.assertEqual(result["reason"], "instance_not_on_source_machine")
        self.assertEqual(self.cm.active_config["migration_plan_state"]["status"], "rollback_failed")

    def test_reconcile_legacy_plan_can_persist_repaired_state(self):
        self.cm.set_migration_plan_state = MagicMock()

        result = self.cm.reconcile_legacy_migration_plan_state(self.app.inventory, persist=True)

        self.assertTrue(result["changed"])
        self.cm.set_migration_plan_state.assert_called_once()
        self.assertEqual(self.cm.set_migration_plan_state.call_args.args[0]["status"], "rolled_back")
