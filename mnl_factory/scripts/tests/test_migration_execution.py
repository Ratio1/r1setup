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
            planner._revalidate_saved_migration_plan = MagicMock(return_value=plan)

            verification_complete = {"value": False}

            def verify_target(_plan):
                verification_complete["value"] = True
                return {
                    "status": "success",
                    "runtime_health": "verified",
                    "app_health": True,
                    "app_health_status": "verified",
                }

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

            planner._copy_from_machine.assert_called_once()
            copy_from_args = planner._copy_from_machine.call_args
            self.assertEqual(copy_from_args.args, (
                {"machine_id": "machine-a", "ansible_host": "10.0.0.1", "ansible_user": "root"},
                "/tmp/r1setup_migration_node-1.tar.gz",
                str(Path(temp_dir) / "node-1.tar.gz"),
            ))
            self.assertIn("timeout", copy_from_args.kwargs)
            planner._copy_to_machine.assert_called_once()
            copy_to_args = planner._copy_to_machine.call_args
            self.assertEqual(copy_to_args.args, (
                {"machine_id": "machine-b", "ansible_host": "10.0.0.2", "ansible_user": "root"},
                str(Path(temp_dir) / "node-1.tar.gz"),
                "/tmp/r1setup_migration_node-1.tar.gz",
            ))
            self.assertIn("timeout", copy_to_args.kwargs)
            app.finalize_instance_migration.assert_called_once()
            finalize_kwargs = app.finalize_instance_migration.call_args.kwargs
            self.assertEqual(finalize_kwargs["runtime_name_policy"], "preserve")
            self.assertEqual(finalize_kwargs["migration_plan_state"]["status"], "executed")
            self.assertEqual(finalize_kwargs["migration_plan_state"]["last_step"], "target_verified")
            self.assertEqual(finalize_kwargs["migration_plan_state"]["runtime_health"], "verified")
            self.assertEqual(finalize_kwargs["migration_plan_state"]["app_health_status"], "verified")
            app.record_service_file_version.assert_called_once_with(["node-1"])
            self.assertEqual(
                [call.args for call in app._update_node_status.call_args_list],
                [("node-1", "stopped"), ("node-1", "running")],
            )
            self.assertEqual(
                [call.args[:2] for call in app.log_operation_event.call_args_list],
                [("migration_execution", "started"), ("migration_execution", "success")],
            )

    def test_execute_saved_migration_plan_revalidates_blocked_plan_and_then_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saved_plan = self._build_plan(temp_dir)
            saved_plan["status"] = "blocked"
            saved_plan["validation"] = {"errors": ["Source machine reachability probe failed: timed out"], "warnings": []}
            app = self._build_app(saved_plan)
            planner = r1setup.MigrationPlanner(app)

            refreshed_plan = self._build_plan(temp_dir)
            planner.build_migration_plan = MagicMock(return_value=refreshed_plan)
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
            planner._verify_target_migration_health = MagicMock(return_value={
                "status": "success",
                "runtime_health": "verified",
                "app_health": True,
                "app_health_status": "verified",
            })

            planner.execute_saved_migration_plan()

            planner.build_migration_plan.assert_called_once_with(
                "node-1",
                "machine-b",
                runtime_name_policy="preserve",
                custom_runtime=None,
            )
            self.assertEqual(app.set_migration_plan_state.call_args_list[0].args[0]["status"], "planned")
            app.finalize_instance_migration.assert_called_once()

    def test_execute_saved_migration_plan_stops_when_revalidation_finds_blockers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            saved_plan = self._build_plan(temp_dir)
            app = self._build_app(saved_plan)
            planner = r1setup.MigrationPlanner(app)

            blocked_plan = self._build_plan(temp_dir)
            blocked_plan["status"] = "blocked"
            blocked_plan["validation"] = {
                "errors": ["Target machine reachability probe failed: connection timed out"],
                "warnings": [],
            }
            planner.build_migration_plan = MagicMock(return_value=blocked_plan)

            planner.execute_saved_migration_plan()

            app.get_input.assert_not_called()
            app.finalize_instance_migration.assert_not_called()
            self.assertEqual(app.set_migration_plan_state.call_count, 1)
            self.assertEqual(app.set_migration_plan_state.call_args.args[0]["status"], "blocked")
            rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
            self.assertIn("remains blocked after revalidation", rendered_text)
            self.assertIn("Target machine reachability probe failed: connection timed out", rendered_text)

    def test_execute_saved_migration_plan_checksum_mismatch_fails_without_finalizing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = self._build_plan(temp_dir)
            app = self._build_app(plan)
            planner = r1setup.MigrationPlanner(app)
            planner._revalidate_saved_migration_plan = MagicMock(return_value=plan)

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
            persisted_statuses = [call.args[0]["status"] for call in app.set_migration_plan_state.call_args_list]
            self.assertGreaterEqual(len(persisted_statuses), 5)
            self.assertEqual(persisted_statuses[0], "planned")
            self.assertEqual(persisted_statuses[1], "executing")
            self.assertEqual(app.set_migration_plan_state.call_args_list[-1].args[0]["status"], "failed")
            self.assertEqual(app.set_migration_plan_state.call_args_list[-1].args[0]["last_step"], "source_archived")

    def test_execute_saved_migration_plan_allows_unknown_app_health_when_runtime_is_verified(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan = self._build_plan(temp_dir)
            app = self._build_app(plan)
            planner = r1setup.MigrationPlanner(app)
            planner._revalidate_saved_migration_plan = MagicMock(return_value=plan)

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
            planner._verify_target_migration_health = MagicMock(return_value={
                "status": "success",
                "runtime_health": "verified",
                "app_health": None,
                "app_health_status": "unknown",
            })

            planner.execute_saved_migration_plan()

            finalize_kwargs = app.finalize_instance_migration.call_args.kwargs
            self.assertEqual(finalize_kwargs["migration_plan_state"]["status"], "executed")
            self.assertEqual(finalize_kwargs["migration_plan_state"]["runtime_health"], "verified")
            self.assertIsNone(finalize_kwargs["migration_plan_state"]["app_health"])
            self.assertEqual(finalize_kwargs["migration_plan_state"]["app_health_status"], "unknown")
            rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
            self.assertIn("Application health: unknown", rendered_text)

    def test_apply_and_start_target_runtime_show_output_for_visibility(self):
        plan = self._build_plan("/tmp")
        app = self._build_app(plan)
        planner = r1setup.MigrationPlanner(app)
        planner._run_target_instance_playbook = MagicMock(return_value=(True, "ok"))

        planner._apply_target_runtime_definition(plan)
        planner._start_target_instance(plan)

        self.assertTrue(planner._run_target_instance_playbook.call_args_list[0].kwargs["show_output"])
        self.assertTrue(planner._run_target_instance_playbook.call_args_list[1].kwargs["show_output"])

    def test_verify_target_migration_health_fails_on_explicit_app_probe_failure(self):
        plan = self._build_plan("/tmp")
        app = self._build_app(plan)
        app.status_tracker = MagicMock()
        app.status_tracker._parse_ansible_status_lines.return_value = {
            "node-1": {"status": "running"},
        }
        app._parse_node_info_output = MagicMock(return_value={
            "node-1": {"status": "unreachable"},
        })
        planner = r1setup.MigrationPlanner(app)
        planner._run_target_instance_playbook = MagicMock(side_effect=[
            (True, "status-output"),
            (True, "node-info-output"),
        ])

        result = planner._verify_target_migration_health(plan)

        self.assertEqual(result["status"], "error")
        self.assertIn("Application health check returned status 'unreachable'", result["message"])

    def test_stop_source_instance_for_migration_uses_runtime_timeout_floor(self):
        plan = self._build_plan("/tmp")
        app = self._build_app(plan)
        planner = r1setup.MigrationPlanner(app)
        app.run_generated_playbook = MagicMock(return_value=(True, "ok", [], {}))

        result = planner._stop_source_instance_for_migration("node-1")

        self.assertEqual(result["status"], "success")
        self.assertEqual(app.run_generated_playbook.call_args.kwargs["timeout"], 180)

    def test_target_apply_and_start_use_runtime_timeout_floor_but_probes_do_not(self):
        plan = self._build_plan("/tmp")
        app = self._build_app(plan)
        planner = r1setup.MigrationPlanner(app)
        app.run_custom_inventory_playbook = MagicMock(return_value=(True, "ok", [], {}))

        planner._run_target_instance_playbook(
            plan,
            "apply_instance.yml",
            last_applied_action="migration_apply_target",
        )
        planner._run_target_instance_playbook(
            plan,
            "service_start.yml",
            last_applied_action="migration_start_target",
        )
        planner._run_target_instance_playbook(
            plan,
            "service_status.yml",
            last_applied_action="migration_verify_target",
        )

        timeout_values = [call.kwargs["timeout"] for call in app.run_custom_inventory_playbook.call_args_list]
        self.assertEqual(timeout_values, [180, 180, 60])
