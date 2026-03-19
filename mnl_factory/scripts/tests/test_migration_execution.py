#!/usr/bin/env python3
"""Tests for migration execution and assignment finalization."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestMigrationExecution(unittest.TestCase):
    """Tests controller-routed migration execution behavior."""

    def _build_plan(self, temp_dir: str):
        local_archive_path = str(Path(temp_dir) / "node-1.tar.gz")
        return {
            "plan_id": "migration-node-1",
            "status": "planned",
            "instance_name": "node-1",
            "logical_name": "node-1",
            "source_machine_id": "machine-a",
            "target_machine_id": "machine-b",
            "runtime_name_policy": "preserve",
            "source_runtime": {
                "service_name": "edge_node",
                "container_name": "edge_node",
                "volume_path": "/var/cache/edge_node/_local_cache",
            },
            "target_runtime": {
                "service_name": "edge_node",
                "container_name": "edge_node",
                "volume_path": "/var/cache/edge_node/_local_cache",
            },
            "transfer": {
                "route": "machine-a -> local temp -> machine-b",
                "source_archive_path": "/tmp/r1setup_migration_node-1.tar.gz",
                "local_temp_dir": temp_dir,
                "local_archive_path": local_archive_path,
                "target_archive_path": "/tmp/r1setup_migration_node-1.tar.gz",
                "checksum_algorithm": "sha256",
            },
            "preflight": {
                "requires_target_preparation": True,
            },
            "validation": {
                "errors": [],
                "warnings": [],
            },
        }

    def _build_app(self, plan):
        app = MagicMock()
        app.active_config = {"config_name": "fleet", "migration_plan_state": plan}
        app.connection_timeout = 30
        app.get_input = MagicMock(return_value="y")
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.print_section = MagicMock()
        app.wait_for_enter = MagicMock()
        app.set_migration_plan_state = MagicMock()
        app.log_operation_event = MagicMock()
        app.finalize_instance_migration = MagicMock()
        app.record_service_file_version = MagicMock()
        app._update_node_status = MagicMock()
        app.get_fleet_state_copy = MagicMock(return_value={
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {
                        "machine_id": "machine-a",
                        "ansible_host": "10.0.0.1",
                        "ansible_user": "root",
                    },
                    "machine-b": {
                        "machine_id": "machine-b",
                        "ansible_host": "10.0.0.2",
                        "ansible_user": "root",
                    },
                },
                "instances": {
                    "node-1": {
                        "logical_name": "node-1",
                        "assigned_machine_id": "machine-a",
                    }
                },
            },
        })
        return app

    def test_execute_saved_migration_plan_finalizes_only_after_target_verification(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = self._build_plan(temp_dir)
            app = self._build_app(plan)
            planner = r1setup.MigrationPlanner(app)

            verification_complete = {"value": False}

            def verify_target(_plan):
                verification_complete["value"] = True
                return {"status": "success", "app_health": True}

            def finalize_assignment(*args, **kwargs):
                self.assertTrue(verification_complete["value"])

            app.finalize_instance_migration.side_effect = finalize_assignment

            planner._prepare_target_machine_for_migration = MagicMock(return_value={"status": "success", "prepared": True})
            planner._stop_source_instance_for_migration = MagicMock(return_value={"status": "success"})
            planner._create_source_archive = MagicMock(return_value={"status": "success"})
            planner._compute_remote_checksum = MagicMock(side_effect=[
                {"status": "success", "checksum": "abc123"},
                {"status": "success", "checksum": "abc123"},
            ])
            planner._copy_from_machine = MagicMock(return_value={"status": "success"})
            planner._compute_local_checksum = MagicMock(return_value="abc123")
            planner._copy_to_machine = MagicMock(return_value={"status": "success"})
            planner._prepare_target_volume_root = MagicMock(return_value={"status": "success"})
            planner._extract_archive_on_target = MagicMock(return_value={"status": "success"})
            planner._apply_target_runtime_definition = MagicMock(return_value={"status": "success"})
            planner._start_target_instance = MagicMock(return_value={"status": "success"})
            planner._verify_target_migration_health = MagicMock(side_effect=verify_target)

            planner.execute_saved_migration_plan()

            planner._copy_from_machine.assert_called_once_with(
                {"machine_id": "machine-a", "ansible_host": "10.0.0.1", "ansible_user": "root"},
                "/tmp/r1setup_migration_node-1.tar.gz",
                str(Path(temp_dir) / "node-1.tar.gz"),
            )
            planner._copy_to_machine.assert_called_once_with(
                {"machine_id": "machine-b", "ansible_host": "10.0.0.2", "ansible_user": "root"},
                str(Path(temp_dir) / "node-1.tar.gz"),
                "/tmp/r1setup_migration_node-1.tar.gz",
            )
            app.finalize_instance_migration.assert_called_once()
            finalize_kwargs = app.finalize_instance_migration.call_args.kwargs
            self.assertEqual(finalize_kwargs["runtime_name_policy"], "preserve")
            self.assertEqual(finalize_kwargs["migration_plan_state"]["status"], "executed")
            app.record_service_file_version.assert_called_once_with(["node-1"])
            self.assertEqual(
                [call.args for call in app._update_node_status.call_args_list],
                [("node-1", "stopped"), ("node-1", "running")],
            )
            self.assertEqual(
                [call.args[:2] for call in app.log_operation_event.call_args_list],
                [("migration_execution", "started"), ("migration_execution", "success")],
            )

    def test_execute_saved_migration_plan_checksum_mismatch_fails_without_finalizing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = self._build_plan(temp_dir)
            app = self._build_app(plan)
            planner = r1setup.MigrationPlanner(app)

            planner._prepare_target_machine_for_migration = MagicMock(return_value={"status": "success", "prepared": True})
            planner._stop_source_instance_for_migration = MagicMock(return_value={"status": "success"})
            planner._create_source_archive = MagicMock(return_value={"status": "success"})
            planner._compute_remote_checksum = MagicMock(return_value={"status": "success", "checksum": "abc123"})
            planner._copy_from_machine = MagicMock(return_value={"status": "success"})
            planner._compute_local_checksum = MagicMock(return_value="different456")
            planner._copy_to_machine = MagicMock(return_value={"status": "success"})

            planner.execute_saved_migration_plan()

            app.finalize_instance_migration.assert_not_called()
            app.record_service_file_version.assert_not_called()
            planner._copy_to_machine.assert_not_called()
            self.assertEqual(
                [call.args[:2] for call in app.log_operation_event.call_args_list],
                [("migration_execution", "started"), ("migration_execution", "failed")],
            )
            self.assertEqual(
                [call.args for call in app._update_node_status.call_args_list],
                [("node-1", "stopped")],
            )
            self.assertEqual(app.set_migration_plan_state.call_count, 2)
            self.assertEqual(app.set_migration_plan_state.call_args_list[0].args[0]["status"], "executing")
            self.assertEqual(app.set_migration_plan_state.call_args_list[1].args[0]["status"], "failed")

