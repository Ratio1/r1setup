#!/usr/bin/env python3
"""UX critic fixes: leftover target cleanup action, Ctrl-C after a finished
action, honest spinner verbs, unreachable-host warnings, status wording."""

import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tests.support import r1setup
from tests.test_migration_state_machine import build_app, build_plan, build_planner, last_saved

DUP = "node runtime and volume on target machine-b (timed out); may still be running"


def printed(app):
    return " | ".join(str(c.args[0]) for c in app.print_colored.call_args_list if c.args)


class TestCleanupTargetAction(unittest.TestCase):

    def plan(self, tmp):
        plan = build_plan(tmp, status="rolled_back", last_step="rollback_completed")
        plan["rollback_cleanup"] = {"leftovers": [DUP, "transfer archive on source"]}
        return plan

    def test_offered_only_when_override_left_a_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(r1setup.migration_allowed_actions(self.plan(tmp))[0], "cleanup_target")
            self.assertEqual(r1setup.migration_allowed_actions({"status": "rolled_back"}), ("plan",))

    def test_cleanup_removes_duplicate_leftover_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(self.plan(tmp), ["y"])
            planner = build_planner(app)
            planner._run_with_spinner = lambda label, func, *a, **k: func(*a, **k)

            planner.cleanup_target_leftovers()

            planner._cleanup_runtime_artifacts.assert_called_once()
            self.assertEqual(last_saved(app)["rollback_cleanup"]["leftovers"], ["transfer archive on source"])
            planner._cleanup_remote_archive.assert_called_once()

    def test_cleanup_also_clears_target_archive_leftover(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = self.plan(tmp)
            plan["rollback_cleanup"]["leftovers"].append(
                "archive /tmp/r1setup_migration_node-1.tar.gz on machine-b (Connection timed out)")
            app = build_app(plan, ["y"])
            planner = build_planner(app)
            planner._run_with_spinner = lambda label, func, *a, **k: func(*a, **k)

            planner.cleanup_target_leftovers()

            self.assertEqual(last_saved(app)["rollback_cleanup"]["leftovers"], ["transfer archive on source"])
            self.assertEqual(r1setup.migration_allowed_actions(last_saved(app)), ("plan",))

    def test_failed_cleanup_keeps_leftover(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(self.plan(tmp), ["y"])
            planner = build_planner(app, runtime_cleanup={"status": "error", "message": "timed out"})
            planner._run_with_spinner = lambda label, func, *a, **k: func(*a, **k)

            planner.cleanup_target_leftovers()

            app.set_migration_plan_state.assert_not_called()
            self.assertIn("Could not clean target", printed(app))


class TestCtrlCAfterFinishedAction(unittest.TestCase):

    def app(self, before):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"migration_plan_state": {"status": before}}
        app.print_colored = MagicMock()
        app.wait_for_enter = MagicMock()
        app._print_cancellation_guidance = MagicMock()
        return app

    def test_ctrl_c_at_final_pause_is_not_reported_as_interrupt(self):
        app = self.app("executed")

        def finalize():
            app.active_config["migration_plan_state"] = {"status": "finalized"}
            raise KeyboardInterrupt

        app.run_migration_action(finalize)
        self.assertIn("had already finished", printed(app))
        app._print_cancellation_guidance.assert_not_called()

    def test_real_interrupt_still_reported(self):
        app = self.app("executed")

        def finalize():
            app.active_config["migration_plan_state"] = {"status": "finalizing"}
            raise KeyboardInterrupt

        app.run_migration_action(finalize)
        self.assertIn("Migration action interrupted", printed(app))


class TestSpinnerVerb(unittest.TestCase):

    def run_spinner(self, result):
        app = MagicMock()
        planner = r1setup.MigrationPlanner(app)
        with patch.object(r1setup.time, "monotonic", side_effect=[0] + [10] * 50), \
                patch.object(r1setup.sys, "stdout"):
            planner._run_with_spinner("Uploading archive...", lambda: result)
        return printed(app)

    def test_failed_phase_says_stopped(self):
        self.assertIn("stopped after", self.run_spinner({"status": "error"}))
        self.assertIn("stopped after", self.run_spinner(False))

    def test_successful_phase_says_finished(self):
        self.assertIn("finished in", self.run_spinner({"status": "success"}))


class TestUnreachableWarnings(unittest.TestCase):

    def test_finalize_warns_when_source_unreachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="executed", last_step="target_verified"), ["n", "n"])
            planner = build_planner(app)
            planner._display_live_host_state = MagicMock(return_value=["Source machine-a: unreachable (timeout)"])
            planner.finalize_saved_migration_plan()
            self.assertIn("The source is unreachable", printed(app))

    def test_rollback_warns_when_running_target_unreachable(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="failed", last_step="target_started"), ["n"])
            planner = build_planner(app)
            planner._display_live_host_state = MagicMock(return_value=["Target machine-b: unreachable (timeout)"])
            planner.rollback_saved_migration_plan()
            self.assertIn("The target is unreachable", printed(app))


class TestStatusWording(unittest.TestCase):

    def status_text(self, plan):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.print_colored = MagicMock()
        app.print_section = MagicMock()
        app._print_migration_status(plan)
        return printed(app)

    def test_interrupted_execute_after_source_stop_is_stated_plainly(self):
        text = self.status_text({"status": "executing", "last_step": "archive_downloaded", "source_unit_disabled": True})
        self.assertIn("executing (interrupted)", text)
        self.assertIn("last completed step: archive_downloaded", text)
        self.assertIn("interrupted after the source was stopped", text)
        self.assertNotIn("may be stopped", text)


if __name__ == "__main__":
    unittest.main()
