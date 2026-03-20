#!/usr/bin/env python3
"""Tests for migration rollback and finalization flows."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestMigrationRollbackAndFinalization(unittest.TestCase):
    """Verify rollback and finalization safety behavior."""

    def _build_plan(self, temp_dir: str, *, status: str):
        local_archive_path = str(Path(temp_dir) / "node-1.tar.gz")
        return {
            "plan_id": "migration-node-1",
            "status": status,
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
            "validation": {
                "errors": [],
                "warnings": [],
            },
        }

    def _build_app(self, plan, *, input_side_effect):
        app = MagicMock()
        app.active_config = {"config_name": "fleet", "migration_plan_state": plan}
        app.connection_timeout = 30
        app.get_input = MagicMock(side_effect=input_side_effect)
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.print_section = MagicMock()
        app.wait_for_enter = MagicMock()
        app.set_migration_plan_state = MagicMock()
        app.log_operation_event = MagicMock()
        app._update_node_status = MagicMock()
        app.status_tracker = MagicMock()
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

    def test_rollback_failed_plan_restarts_source_and_cleans_archives(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = self._build_plan(temp_dir, status="failed")
            local_archive = Path(plan["transfer"]["local_archive_path"])
            local_archive.write_text("archive")

            app = self._build_app(plan, input_side_effect=["y"])
            planner = r1setup.MigrationPlanner(app)
            planner._cleanup_runtime_artifacts = MagicMock(return_value={"status": "success"})
            planner._cleanup_remote_archive = MagicMock(return_value={"status": "success"})
            planner._start_source_instance_after_rollback = MagicMock(return_value={"status": "success"})

            planner.rollback_saved_migration_plan()

            planner._cleanup_runtime_artifacts.assert_called_once_with(
                {"machine_id": "machine-b", "ansible_host": "10.0.0.2", "ansible_user": "root"},
                plan["target_runtime"],
                remove_volume=True,
            )
            self.assertFalse(local_archive.exists())
            self.assertEqual(app.set_migration_plan_state.call_args_list[-1].args[0]["status"], "rolled_back")
            self.assertEqual(app._update_node_status.call_args_list[-1].args, ("node-1", "running"))
            self.assertEqual(
                [call.args[:2] for call in app.log_operation_event.call_args_list],
                [("migration_rollback", "started"), ("migration_rollback", "success")],
            )

    def test_finalize_executed_plan_cleans_source_artifacts_and_marks_finalized(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = self._build_plan(temp_dir, status="executed")
            local_archive = Path(plan["transfer"]["local_archive_path"])
            local_archive.write_text("archive")

            app = self._build_app(plan, input_side_effect=["n", "y"])
            planner = r1setup.MigrationPlanner(app)
            planner._cleanup_runtime_artifacts = MagicMock(return_value={"status": "success"})
            planner._cleanup_remote_archive = MagicMock(return_value={"status": "success"})

            planner.finalize_saved_migration_plan()

            planner._cleanup_runtime_artifacts.assert_called_once_with(
                {"machine_id": "machine-a", "ansible_host": "10.0.0.1", "ansible_user": "root"},
                plan["source_runtime"],
                remove_volume=False,
            )
            self.assertFalse(local_archive.exists())
            self.assertEqual(app.set_migration_plan_state.call_args_list[-1].args[0]["status"], "finalized")
            self.assertEqual(
                [call.args[:2] for call in app.log_operation_event.call_args_list],
                [("migration_finalization", "started"), ("migration_finalization", "success")],
            )

    def test_start_source_instance_after_rollback_uses_runtime_timeout_floor(self):
        plan = self._build_plan("/tmp", status="failed")
        app = self._build_app(plan, input_side_effect=["y"])
        planner = r1setup.MigrationPlanner(app)
        app.run_generated_playbook = MagicMock(return_value=(True, "ok", [], {}))

        result = planner._start_source_instance_after_rollback("node-1")

        self.assertEqual(result["status"], "success")
        self.assertEqual(app.run_generated_playbook.call_args.kwargs["timeout"], 180)

    def test_rollback_reconciles_to_rolled_back_when_source_restart_times_out_but_status_verifies_running(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = self._build_plan(temp_dir, status="failed")
            app = self._build_app(plan, input_side_effect=["y"])
            planner = r1setup.MigrationPlanner(app)
            planner._cleanup_runtime_artifacts = MagicMock(return_value={"status": "success"})
            planner._cleanup_remote_archive = MagicMock(return_value={"status": "success"})
            planner._cleanup_local_archive = MagicMock(return_value={"status": "success"})
            planner._start_source_instance_after_rollback = MagicMock(return_value={"status": "error", "message": "Command timed out after 30 seconds"})
            planner._verify_source_instance_after_rollback = MagicMock(return_value={"status": "success", "runtime_health": "verified"})

            planner.rollback_saved_migration_plan()

            final_plan = app.set_migration_plan_state.call_args_list[-1].args[0]
            self.assertEqual(final_plan["status"], "rolled_back")
            self.assertEqual(final_plan["last_step"], "rollback_completed")
            self.assertIsNone(final_plan["last_error"])
            self.assertTrue(final_plan["rollback_recovery"]["reconciled_after_error"])
            self.assertEqual(final_plan["rollback_recovery"]["original_error"], "Command timed out after 30 seconds")
            self.assertEqual(app._update_node_status.call_args_list[-1].args, ("node-1", "running"))
            self.assertEqual(
                [call.args[:2] for call in app.log_operation_event.call_args_list],
                [("migration_rollback", "started"), ("migration_rollback", "failed"), ("migration_rollback", "success")],
            )

    def test_verify_source_instance_after_rollback_returns_error_when_runtime_is_not_running(self):
        plan = self._build_plan("/tmp", status="failed")
        app = self._build_app(plan, input_side_effect=["y"])
        app.run_generated_playbook = MagicMock(return_value=(True, "status-output", ["node-1"], {}))
        app.status_tracker._parse_ansible_status_lines.return_value = {
            "node-1": {"status": "stopped"},
        }
        planner = r1setup.MigrationPlanner(app)

        result = planner._verify_source_instance_after_rollback("node-1")

        self.assertEqual(result["status"], "error")
        self.assertIn("stopped", result["message"])
        self.assertEqual(app.run_generated_playbook.call_args.kwargs["timeout"], 60)
