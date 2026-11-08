#!/usr/bin/env python3
"""Tests for the migration plan state machine: no dead-end statuses, retry,
rollback ordering, finalize without source, abandon, plan guard, history."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call

from tests.support import r1setup


MACHINE_A = {"machine_id": "machine-a", "ansible_host": "10.0.0.1", "ansible_user": "root"}
MACHINE_B = {"machine_id": "machine-b", "ansible_host": "10.0.0.2", "ansible_user": "root"}


def build_plan(temp_dir, *, status, last_step=None):
    plan = {
        "plan_id": "migration-node-1",
        "status": status,
        "instance_name": "node-1",
        "source_machine_id": "machine-a",
        "target_machine_id": "machine-b",
        "runtime_name_policy": "preserve",
        "source_runtime": {"service_name": "edge_node", "container_name": "edge_node",
                           "volume_path": "/var/cache/edge_node/_local_cache"},
        "target_runtime": {"service_name": "edge_node", "container_name": "edge_node",
                           "volume_path": "/var/cache/edge_node/_local_cache"},
        "transfer": {
            "source_archive_path": "/tmp/r1setup_migration_node-1.tar.gz",
            "local_temp_dir": temp_dir,
            "local_archive_path": str(Path(temp_dir) / "node-1.tar.gz"),
            "target_archive_path": "/tmp/r1setup_migration_node-1.tar.gz",
        },
        "validation": {"errors": [], "warnings": []},
    }
    if last_step:
        plan["last_step"] = last_step
    return plan


def build_app(plan, inputs):
    app = MagicMock()
    app.active_config = {"config_name": "fleet", "migration_plan_state": plan}
    app.connection_timeout = 30
    app.get_input = MagicMock(side_effect=list(inputs))
    app.get_fleet_state_copy = MagicMock(return_value={
        "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
        "fleet": {"machines": {"machine-a": dict(MACHINE_A), "machine-b": dict(MACHINE_B)},
                  "instances": {"node-1": {"assigned_machine_id": "machine-a"}}},
    })
    return app


def last_saved(app):
    return app.set_migration_plan_state.call_args_list[-1].args[0]


def build_planner(app, *, runtime_cleanup=None, start=None):
    planner = r1setup.MigrationPlanner(app)
    planner._display_migration_plan = MagicMock()
    planner._cleanup_runtime_artifacts = MagicMock(side_effect=runtime_cleanup) if callable(runtime_cleanup) or isinstance(runtime_cleanup, list) \
        else MagicMock(return_value=runtime_cleanup or {"status": "success"})
    planner._cleanup_remote_archive = MagicMock(return_value={"status": "success"})
    planner._start_source_instance_after_rollback = MagicMock(return_value=start or {"status": "success"})
    planner._verify_source_instance_after_rollback = MagicMock(return_value={"status": "error", "message": "down"})
    return planner


class TestAllowedActions(unittest.TestCase):

    def test_every_non_terminal_status_has_a_forward_action(self):
        for status, actions in r1setup.MIGRATION_STATUS_ACTIONS.items():
            forward = [a for a in actions if a not in ("abandon", "plan")]
            self.assertTrue(forward, f"status {status} has no forward action")
            self.assertIn("abandon", actions, f"status {status} cannot be abandoned")

    def test_dead_end_statuses_from_e2e_are_recoverable(self):
        cases = {
            "finalization_failed": "finalize",
            "finalizing": "finalize",
            "rollback_failed": "rollback",
            "rolling_back": "rollback",
        }
        for status, action in cases.items():
            self.assertIn(action, r1setup.migration_allowed_actions({"status": status}))

    def test_terminal_and_missing_plans_allow_only_new_plan(self):
        self.assertEqual(r1setup.migration_allowed_actions(None), ("plan",))
        for status in r1setup.MIGRATION_TERMINAL_STATUSES:
            self.assertEqual(r1setup.migration_allowed_actions({"status": status}), ("plan",))

    def test_unknown_status_can_still_be_abandoned(self):
        self.assertEqual(r1setup.migration_allowed_actions({"status": "weird"}), ("abandon",))

    def test_open_plan_does_not_allow_new_plan(self):
        for status in ("executing", "failed", "executed", "finalization_failed", "rollback_failed"):
            self.assertNotIn("plan", r1setup.migration_allowed_actions({"status": status}))


class TestFinalizeRecovery(unittest.TestCase):

    def test_finalize_retries_from_finalization_failed(self):
        for status in ("finalization_failed", "finalizing"):
            with tempfile.TemporaryDirectory() as tmp:
                plan = build_plan(tmp, status=status)
                app = build_app(plan, ["n", "y"])
                planner = build_planner(app)

                planner.finalize_saved_migration_plan()

                self.assertEqual(last_saved(app)["status"], "finalized", status)
                planner._cleanup_runtime_artifacts.assert_called_once_with(MACHINE_A, plan["source_runtime"], remove_volume=False)

    def test_finalize_refused_for_planned_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="planned"), [])
            planner = build_planner(app)

            planner.finalize_saved_migration_plan()

            app.set_migration_plan_state.assert_not_called()
            planner._cleanup_runtime_artifacts.assert_not_called()

    def test_unreachable_source_fails_then_operator_declines(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="executed"), ["n", "y", "n"])
            planner = build_planner(app, runtime_cleanup={"status": "error", "message": "Warning: Permanently added 'x'\nssh: connect to host 10.0.0.1 port 22: Connection timed out"})

            planner.finalize_saved_migration_plan()

            saved = last_saved(app)
            self.assertEqual(saved["status"], "finalization_failed")
            self.assertIn("Connection timed out", saved["last_error"])
            self.assertNotIn("Permanently added", saved["last_error"])

    def test_unreachable_source_then_operator_finalizes_without_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="executed"), ["n", "y", "y", "node-1"])
            planner = build_planner(app, runtime_cleanup={"status": "error", "message": "timed out"})

            planner.finalize_saved_migration_plan()

            saved = last_saved(app)
            self.assertEqual(saved["status"], "finalized")
            self.assertTrue(saved["finalization_cleanup"]["source_cleanup_skipped"])
            self.assertIn("e2.pem", saved["finalization_cleanup"]["leftovers"][0])
            archive_hosts = [c.args[0]["machine_id"] for c in planner._cleanup_remote_archive.call_args_list]
            self.assertEqual(archive_hosts, ["machine-b"])

    def test_finalize_without_source_never_contacts_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="finalization_failed"), ["node-1"])
            planner = build_planner(app)

            planner.finalize_saved_migration_plan(skip_source_cleanup=True)

            planner._cleanup_runtime_artifacts.assert_not_called()
            self.assertEqual(last_saved(app)["status"], "finalized")

    def test_finalize_without_source_requires_exact_typed_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="executed"), ["yes"])
            planner = build_planner(app)

            planner.finalize_saved_migration_plan(skip_source_cleanup=True)

            app.set_migration_plan_state.assert_not_called()

    def test_archive_cleanup_failure_does_not_block_finalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="executed"), ["n", "y"])
            planner = build_planner(app)
            planner._cleanup_remote_archive = MagicMock(return_value={"status": "error", "message": "unreachable"})

            planner.finalize_saved_migration_plan()

            saved = last_saved(app)
            self.assertEqual(saved["status"], "finalized")
            self.assertEqual(len(saved["finalization_cleanup"]["leftovers"]), 2)


class TestRollbackOrder(unittest.TestCase):

    def _order(self, planner):
        events = []
        planner._cleanup_runtime_artifacts.side_effect = (
            lambda *a, **k: events.append("target_cleanup") or planner._cleanup_result)
        planner._start_source_instance_after_rollback.side_effect = (
            lambda *a, **k: events.append("source_start") or {"status": "success"})
        return events

    def test_source_restarts_before_target_cleanup_when_target_never_ran(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="failed", last_step="archive_downloaded"), ["y"])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "success"}
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events, ["source_start", "target_cleanup"])
            self.assertEqual(last_saved(app)["status"], "rolled_back")

    def test_dead_target_does_not_block_source_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="failed", last_step="source_archived"), ["y"])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "error", "message": "Connection timed out during banner exchange"}
            planner._cleanup_remote_archive = MagicMock(side_effect=[
                {"status": "error", "message": "timed out"}, {"status": "success"}])
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events[0], "source_start")
            saved = last_saved(app)
            self.assertEqual(saved["status"], "rolled_back")
            self.assertFalse(saved["rollback_cleanup"]["target_volume_removed"])
            self.assertEqual(len(saved["rollback_cleanup"]["leftovers"]), 2)
            self.assertEqual(app._update_node_status.call_args_list[-1].args, ("node-1", "running"))

    def test_target_that_may_run_is_cleaned_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="failed", last_step="target_started"), ["y"])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "success"}
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events, ["target_cleanup", "source_start"])
            self.assertEqual(last_saved(app)["status"], "rolled_back")

    def test_unreachable_running_target_requires_typed_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="failed", last_step="target_started"), ["y", ""])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "error", "message": "timed out"}
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events, ["target_cleanup"])
            saved = last_saved(app)
            self.assertEqual(saved["status"], "rollback_failed")
            self.assertEqual(saved["rollback_from_step"], "target_started")

    def test_typed_override_restarts_source_and_records_leftover(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="failed", last_step="target_started"), ["y", "node-1"])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "error", "message": "timed out"}
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events, ["target_cleanup", "source_start"])
            saved = last_saved(app)
            self.assertEqual(saved["status"], "rolled_back")
            self.assertIn("may still be running", saved["rollback_cleanup"]["leftovers"][0])

    def test_rollback_retry_from_rollback_failed_keeps_original_step(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_plan(tmp, status="rollback_failed", last_step="rollback_failed_target_cleanup")
            plan["rollback_from_step"] = "target_started"
            app = build_app(plan, ["y"])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "success"}
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events, ["target_cleanup", "source_start"])
            self.assertEqual(last_saved(app)["status"], "rolled_back")

    def test_rollback_retry_from_rolling_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="rolling_back", last_step="rollback_started"), ["y"])
            planner = build_planner(app)

            planner.rollback_saved_migration_plan()

            self.assertEqual(last_saved(app)["status"], "rolled_back")

    def test_source_restart_failure_stays_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="failed", last_step="source_stopped"), ["y"])
            planner = build_planner(app, start={"status": "error", "message": "unreachable"})

            planner.rollback_saved_migration_plan()

            saved = last_saved(app)
            self.assertEqual(saved["status"], "rollback_failed")
            self.assertIn("rollback", r1setup.migration_allowed_actions(saved))
            planner._cleanup_runtime_artifacts.assert_not_called()


class TestAbandonAndGuard(unittest.TestCase):

    def test_abandon_requires_typed_name_and_archives_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="finalization_failed"), ["node-1"])
            planner = build_planner(app)

            planner.abandon_saved_migration_plan()

            archived = app.archive_migration_plan.call_args.args[0]
            self.assertEqual(archived["status"], "abandoned")
            self.assertEqual(archived["abandoned_from_status"], "finalization_failed")
            self.assertTrue(app.archive_migration_plan.call_args.kwargs["clear_current"])
            planner._cleanup_runtime_artifacts.assert_not_called()

    def test_abandon_cancelled_without_exact_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="failed"), ["y"])
            planner = build_planner(app)

            planner.abandon_saved_migration_plan()

            app.archive_migration_plan.assert_not_called()

    def test_plan_migration_refuses_over_open_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="executed"), [])
            planner = build_planner(app)
            planner._get_plannable_instances = MagicMock()

            planner.plan_instance_migration()

            planner._get_plannable_instances.assert_not_called()
            app.set_migration_plan_state.assert_not_called()

    def test_replacing_planned_plan_asks_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="planned"), ["n"])
            planner = build_planner(app)
            planner._get_plannable_instances = MagicMock()

            planner.plan_instance_migration()

            planner._get_plannable_instances.assert_not_called()

    def test_confirm_reasks_on_invalid_input(self):
        app = build_app({}, [])
        planner = r1setup.MigrationPlanner(app)
        app.get_input = MagicMock(side_effect=["maybe", "yes"])
        self.assertTrue(planner._confirm("ok? (y/N)", "N"))
        self.assertEqual(app.get_input.call_count, 2)


class TestPlanHistory(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        base = Path(self.temp_dir.name)
        self.app = MagicMock()
        self.app.config_dir = base
        self.app.configs_dir = base / "configs"
        self.app.configs_dir.mkdir(parents=True)
        self.app.config_file = base / "hosts.yml"
        self.app.vars_file = base / "group_vars" / "variables.yml"
        self.app.active_config_file = base / "active_config.json"
        self.app.inventory = {"all": {"vars": {"mnl_app_env": "mainnet"}, "children": {"gpu_nodes": {"hosts": {}}}}}
        self.cm = r1setup.ConfigurationManager(self.app)
        self.cm._save_active_config = MagicMock()
        self.cm._update_hosts_symlink = MagicMock()
        self.cm.ensure_configuration_shell("fleet", "mainnet")

    def test_history_is_bounded_and_clear_current_drops_plan(self):
        self.cm.set_migration_plan_state({"plan_id": "p-current", "status": "failed"})
        for index in range(r1setup.MIGRATION_PLAN_HISTORY_LIMIT + 3):
            self.cm.archive_migration_plan({"plan_id": f"p-{index}", "status": "finalized"})
        self.cm.archive_migration_plan({"plan_id": "p-current", "status": "abandoned"}, clear_current=True)

        metadata = json.loads((self.app.configs_dir / "fleet.json").read_text())
        history = metadata["migration_plan_history"]
        self.assertEqual(len(history), r1setup.MIGRATION_PLAN_HISTORY_LIMIT)
        self.assertEqual(history[-1]["plan_id"], "p-current")
        self.assertNotIn("migration_plan_state", metadata)
        self.assertNotIn("migration_plan_state", self.cm.active_config)


class TestInterruptHandling(unittest.TestCase):

    def test_run_migration_action_returns_to_menu_on_ctrl_c(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"migration_plan_state": {
            "status": "finalizing", "instance_name": "node-1", "last_step": "finalization_started"}}
        app.print_colored = MagicMock()
        app.wait_for_enter = MagicMock()

        def interrupted():
            raise KeyboardInterrupt

        self.assertIsNone(app.run_migration_action(interrupted))
        rendered = " ".join(c.args[0] for c in app.print_colored.call_args_list)
        self.assertIn("Finalize migration", rendered)
        self.assertFalse(app._migration_action_active)


if __name__ == "__main__":
    unittest.main()
