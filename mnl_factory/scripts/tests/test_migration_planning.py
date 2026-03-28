#!/usr/bin/env python3
"""Tests for migration planning and persistence helpers."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestMigrationPlanPersistence(unittest.TestCase):
    """Tests persisting migration-plan state in config metadata."""

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
        self.cm.ensure_configuration_shell("fleet", "mainnet")

    def test_set_migration_plan_state_persists_to_metadata(self):
        plan = {
            "plan_id": "migration-node-1",
            "status": "planned",
            "instance_name": "node-1",
            "target_machine_id": "machine-b",
        }

        self.cm.set_migration_plan_state(plan)

        metadata = json.loads((self.app.configs_dir / "fleet.json").read_text())
        self.assertEqual(metadata["migration_plan_state"]["plan_id"], "migration-node-1")
        self.assertEqual(self.cm.active_config["migration_plan_state"]["target_machine_id"], "machine-b")


class TestMigrationPlanBuilder(unittest.TestCase):
    """Tests MigrationPlanner.build_migration_plan()."""

    def _build_app(self, fleet_state):
        app = MagicMock()
        app.get_fleet_state_copy.return_value = fleet_state
        app._default_migration_temp_dir.return_value = Path("/tmp/r1setup-migration")
        app.config_manager = MagicMock()
        app.config_manager._normalize_fleet_state.side_effect = lambda fleet: fleet
        app.config_manager.resolve_runtime_names.side_effect = (
            lambda logical_name, **kwargs: r1setup.ConfigurationManager.resolve_runtime_names(logical_name, **kwargs)
        )
        app.config_manager._sanitize_runtime_suffix.side_effect = (
            lambda value: r1setup.ConfigurationManager._sanitize_runtime_suffix(value)
        )
        return app

    def test_build_migration_plan_preserve_mode_includes_controller_transfer_route(self):
        fleet_state = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {
                        "machine_id": "machine-a",
                        "ansible_host": "10.0.0.1",
                        "ansible_user": "root",
                        "topology_mode": "standard",
                        "deployment_state": "active",
                        "instance_names": ["node-1"],
                    },
                    "machine-b": {
                        "machine_id": "machine-b",
                        "ansible_host": "10.0.0.2",
                        "ansible_user": "root",
                        "topology_mode": "standard",
                        "deployment_state": "prepared",
                        "instance_names": [],
                    },
                },
                "instances": {
                    "node-1": {
                        "logical_name": "node-1",
                        "assigned_machine_id": "machine-a",
                        "runtime": {
                            "service_name": "edge_node",
                            "container_name": "edge_node",
                            "volume_path": "/var/cache/edge_node/_local_cache",
                        },
                    }
                },
            },
        }

        app = self._build_app(fleet_state)
        app.config_manager.detect_runtime_collisions.return_value = {}
        planner = r1setup.MigrationPlanner(app)
        planner._collect_preflight = MagicMock(return_value={
            "local_temp_dir": "/tmp/r1setup-migration",
            "source_reachability": {"status": "success"},
            "target_reachability": {"status": "success"},
            "source_volume_probe": {"status": "success", "bytes": 1024},
            "local_free_probe": {"status": "success", "bytes": 1024 * 1024},
            "target_free_probe": {"status": "success", "bytes": 1024 * 1024},
        })

        plan = planner.build_migration_plan("node-1", "machine-b", runtime_name_policy="preserve")

        self.assertEqual(plan["status"], "planned")
        self.assertEqual(plan["target_runtime"]["service_name"], "edge_node")
        self.assertEqual(plan["transfer"]["route"], "machine-a -> local temp -> machine-b")
        self.assertEqual(plan["transfer"]["checksum_algorithm"], "sha256")
        self.assertEqual(plan["preflight"]["source_volume_bytes"], 1024)
        self.assertFalse(plan["validation"]["errors"])

    def test_build_migration_plan_blocks_standard_target_with_collision(self):
        fleet_state = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {
                        "machine_id": "machine-a",
                        "ansible_host": "10.0.0.1",
                        "ansible_user": "root",
                        "topology_mode": "standard",
                        "deployment_state": "active",
                        "instance_names": ["node-1"],
                    },
                    "machine-b": {
                        "machine_id": "machine-b",
                        "ansible_host": "10.0.0.2",
                        "ansible_user": "root",
                        "topology_mode": "standard",
                        "deployment_state": "prepared",
                        "instance_names": ["node-2"],
                    },
                },
                "instances": {
                    "node-1": {
                        "logical_name": "node-1",
                        "assigned_machine_id": "machine-a",
                        "runtime": {
                            "service_name": "edge_node",
                            "container_name": "edge_node",
                            "volume_path": "/var/cache/edge_node/_local_cache",
                        },
                    },
                    "node-2": {
                        "logical_name": "node-2",
                        "assigned_machine_id": "machine-b",
                        "runtime": {
                            "service_name": "edge_node",
                            "container_name": "edge_node",
                            "volume_path": "/var/cache/edge_node/_local_cache",
                        },
                    },
                },
            },
        }

        app = self._build_app(fleet_state)
        app.config_manager.detect_runtime_collisions.return_value = {"service_name": ["node-2"]}
        planner = r1setup.MigrationPlanner(app)
        planner._collect_preflight = MagicMock(return_value={
            "local_temp_dir": "/tmp/r1setup-migration",
            "source_reachability": {"status": "success"},
            "target_reachability": {"status": "success"},
            "source_volume_probe": {"status": "success", "bytes": 1024},
            "local_free_probe": {"status": "success", "bytes": 1024 * 1024},
            "target_free_probe": {"status": "success", "bytes": 1024 * 1024},
        })

        plan = planner.build_migration_plan("node-1", "machine-b", runtime_name_policy="preserve")

        self.assertEqual(plan["status"], "blocked")
        joined_errors = " ".join(plan["validation"]["errors"])
        self.assertIn("collides", joined_errors)
        self.assertIn("standard mode", joined_errors)


class TestMigrationPlanningFlow(unittest.TestCase):
    """Tests the interactive planning wrapper."""

    def test_plan_instance_migration_saves_reviewed_plan(self):
        app = MagicMock()
        app.active_config = {"config_name": "fleet"}
        app.load_configuration = MagicMock()
        app.get_fleet_state_copy.return_value = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {"machine_id": "machine-a"},
                },
                "instances": {
                    "node-1": {"assigned_machine_id": "machine-a", "runtime": {}},
                },
            },
        }
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.print_section = MagicMock()
        app.wait_for_enter = MagicMock()
        app.get_input = MagicMock(return_value="y")
        app.set_migration_plan_state = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager._format_machine_connection_display.return_value = "root@10.0.0.1"

        planner = r1setup.MigrationPlanner(app)
        planner._get_plannable_instances = MagicMock(return_value={"node-1": {"assigned_machine_id": "machine-a", "runtime": {}}})
        planner._select_migration_source_instance = MagicMock(return_value="node-1")
        planner._confirm_source_machine = MagicMock(return_value=True)
        planner._select_migration_target_machine = MagicMock(return_value="machine-b")
        planner._select_runtime_name_policy = MagicMock(return_value="preserve")
        planner.build_migration_plan = MagicMock(return_value={
            "plan_id": "migration-node-1",
            "status": "planned",
            "instance_name": "node-1",
            "source_machine_id": "machine-a",
            "target_machine_id": "machine-b",
            "runtime_name_policy": "preserve",
            "target_runtime": {},
            "transfer": {},
            "preflight": {},
            "validation": {"errors": [], "warnings": []},
        })
        planner._display_migration_plan = MagicMock()

        planner.plan_instance_migration()

        app.set_migration_plan_state.assert_called_once()

    def test_plan_instance_migration_warns_when_saving_blocked_plan(self):
        app = MagicMock()
        app.active_config = {"config_name": "fleet"}
        app.load_configuration = MagicMock()
        app.get_fleet_state_copy.return_value = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {"machine_id": "machine-a"},
                },
                "instances": {
                    "node-1": {"assigned_machine_id": "machine-a", "runtime": {}},
                },
            },
        }
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.print_section = MagicMock()
        app.wait_for_enter = MagicMock()
        app.get_input = MagicMock(return_value="y")
        app.set_migration_plan_state = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager._format_machine_connection_display.return_value = "root@10.0.0.1"

        planner = r1setup.MigrationPlanner(app)
        planner._get_plannable_instances = MagicMock(return_value={"node-1": {"assigned_machine_id": "machine-a", "runtime": {}}})
        planner._select_migration_source_instance = MagicMock(return_value="node-1")
        planner._confirm_source_machine = MagicMock(return_value=True)
        planner._select_migration_target_machine = MagicMock(return_value="machine-b")
        planner._select_runtime_name_policy = MagicMock(return_value="preserve")
        planner.build_migration_plan = MagicMock(return_value={
            "plan_id": "migration-node-1",
            "status": "blocked",
            "instance_name": "node-1",
            "source_machine_id": "machine-a",
            "target_machine_id": "machine-b",
            "runtime_name_policy": "preserve",
            "target_runtime": {},
            "transfer": {},
            "preflight": {},
            "validation": {"errors": ["target unreachable"], "warnings": []},
        })
        planner._display_migration_plan = MagicMock()

        planner.plan_instance_migration()

        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("Blocked migration plan saved locally for review.", rendered_text)
