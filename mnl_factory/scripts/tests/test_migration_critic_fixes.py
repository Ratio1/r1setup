#!/usr/bin/env python3
"""Fixes from the critic review of fix/migration-recovery: legacy rollback
plans, override visibility, abandon guidance, fail-closed preflight probes,
backup sudo stdin, early source_unit_disabled flag, private error logs."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.support import r1setup
from tests.test_migration_preflight_health import build_planner as build_preflight_planner, ok, preflight
from tests.test_migration_state_machine import TestRollbackOrder, build_app, build_plan, build_planner, last_saved


def printed(app):
    return " | ".join(str(c.args[0]) for c in app.print_colored.call_args_list if c.args)


class TestLegacyRollback(unittest.TestCase):
    """Plans written by older r1setup have no rollback_from_step."""

    _order = TestRollbackOrder._order

    def test_legacy_rollback_failed_plan_cleans_target_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="rollback_failed", last_step="rollback_failed_target_cleanup"), ["y"])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "success"}
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events, ["target_cleanup", "source_start"])

    def test_legacy_plan_with_unreachable_target_requires_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="rolling_back", last_step="rollback_started"), ["y", ""])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "error", "message": "timed out"}
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events, ["target_cleanup"])
            self.assertEqual(last_saved(app)["status"], "rollback_failed")

    def test_target_cleaned_after_source_even_when_enable_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_plan(tmp, status="failed", last_step="source_archived")
            plan["source_unit_disabled"] = True
            app = build_app(plan, ["y"])
            planner = build_planner(app)
            planner._cleanup_result = {"status": "success"}
            planner._set_source_unit_enabled = MagicMock(return_value={"status": "error", "message": "boom"})
            events = self._order(planner)

            planner.rollback_saved_migration_plan()

            self.assertEqual(events, ["source_start", "target_cleanup"])
            self.assertTrue(last_saved(app)["rollback_cleanup"]["target_volume_removed"])

    def test_review_note_matches_order(self):
        planner = r1setup.MigrationPlanner(MagicMock())
        self.assertTrue(planner._rollback_target_first({"last_step": "target_applied"}))
        self.assertTrue(planner._rollback_target_first({"last_step": "rollback_failed_target_cleanup"}))
        self.assertFalse(planner._rollback_target_first({"last_step": "archive_uploaded"}))
        self.assertFalse(planner._rollback_target_first({"last_step": "source_disabling"}))


class TestLeftoverVisibility(unittest.TestCase):

    def banner(self, plan):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        return app._migration_banner(plan)

    def test_override_leftover_keeps_red_banner(self):
        plan = {"status": "rolled_back", "instance_name": "node-1", "source_machine_id": "a", "target_machine_id": "b",
                "rollback_cleanup": {"leftovers": ["node runtime and volume on target b (timeout); may still be running"]}}
        text, color = self.banner(plan)
        self.assertEqual(color, "red")
        self.assertIn("may run on both hosts", text)

    def test_clean_terminal_plan_has_no_banner(self):
        self.assertIsNone(self.banner({"status": "finalized", "finalization_cleanup": {"leftovers": []}}))

    def test_abandoned_plan_has_no_leftover_banner(self):
        self.assertIsNone(self.banner({"status": "abandoned", "abandon_cleanup": {"leftovers": ["at abandon: x"]}}))


class TestAbandonGuidance(unittest.TestCase):

    def run_abandon(self, tmp, status, last_step, disabled=False):
        plan = build_plan(tmp, status=status, last_step=last_step)
        plan["source_unit_disabled"] = disabled
        app = build_app(plan, ["node-1"])
        planner = build_planner(app)
        planner._display_live_host_state = MagicMock(return_value=["Source a: service inactive/disabled"])
        planner.abandon_saved_migration_plan()
        return app

    def test_failed_after_target_start_warns_not_to_start_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.run_abandon(tmp, "failed", "target_started", disabled=True)
            self.assertIn("Do not start the source", printed(app))
            self.assertNotIn("start it from Operations", printed(app))

    def test_failed_before_target_start_points_to_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.run_abandon(tmp, "failed", "archive_uploaded", disabled=True)
            self.assertIn("Start it from Operations", printed(app))

    def test_executed_with_disabled_source_does_not_claim_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.run_abandon(tmp, "executed", "target_verified", disabled=True)
            self.assertNotIn("may start again", printed(app))
            self.assertIn("e2.pem", printed(app))

    def test_abandon_records_host_state_in_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = self.run_abandon(tmp, "executed", "target_verified", disabled=True)
            archived = app.archive_migration_plan.call_args.args[0]
            self.assertEqual(archived["abandon_cleanup"]["leftovers"], ["at abandon: Source a: service inactive/disabled"])


class TestFailClosedPreflight(unittest.TestCase):

    def test_failed_runtime_probe_blocks_plan(self):
        plan = build_preflight_planner(preflight(target_runtime_probe={"status": "error", "message": "sudo: a password is required"})) \
            .build_migration_plan("node-1", "machine-b")
        self.assertEqual(plan["status"], "blocked")
        self.assertTrue(any("Could not check whether the target" in e for e in plan["validation"]["errors"]))

    def test_failed_tmp_probe_blocks_plan(self):
        plan = build_preflight_planner(preflight(source_tmp_free_probe={"status": "error", "message": "timeout"})) \
            .build_migration_plan("node-1", "machine-b")
        self.assertEqual(plan["status"], "blocked")

    def test_runtime_probe_runs_as_root(self):
        app = MagicMock()
        app._run_machine_probe.return_value = ok(stdout="")
        planner = r1setup.MigrationPlanner(app)
        planner._probe_existing_target_runtime({"ansible_user": "ops"}, {"service_name": "edge_node", "volume_path": "/v"})
        self.assertTrue(str(app._run_machine_probe.call_args.args[1]).startswith("sudo -n "))


class TestBackupStreamSendsSudoPassword(unittest.TestCase):

    def test_password_goes_to_stdin(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.settings_manager = MagicMock(connection_timeout=30)
        app.migration_planner = r1setup.MigrationPlanner(app)
        host = {"ansible_host": "10.0.0.9", "ansible_user": "ops", "ansible_ssh_private_key_file": "/k",
                "ansible_become_password": "pw-S3cret"}
        proc = MagicMock(returncode=0)
        proc.communicate.return_value = (None, b"")
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(r1setup.subprocess, "Popen", return_value=proc) as popen:
            app._stream_remote_archive_to_local(host, "/v", Path(tmp) / "a.tgz")
        self.assertEqual(popen.call_args.kwargs["stdin"], r1setup.subprocess.PIPE)
        self.assertNotIn("pw-S3cret", " ".join(popen.call_args.args[0]))
        self.assertEqual(proc.communicate.call_args.kwargs["input"], b"pw-S3cret\n")


class TestExecuteDisableFlag(unittest.TestCase):

    def test_error_log_is_private_from_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = MagicMock()
            app._get_operation_log_dir.return_value = tmp
            planner = r1setup.MigrationPlanner(app)
            with patch.object(r1setup.os, "chmod") as chmod:
                path = planner._write_migration_error_log({"instance_name": "n"}, 3, "raw")
            chmod.assert_not_called()
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)


class TestDuplicateEndpointRegistration(unittest.TestCase):

    def manager(self, access):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.app.get_input = MagicMock(side_effect=["tgt-dup", "n"])
        cm.app._configure_single_node = MagicMock(return_value={})
        cm.app._extract_machine_access_config = MagicMock(return_value=access)
        fleet = {"config_schema_version": r1setup.CONFIG_SCHEMA_VERSION, "fleet": {"machines": {
            "src-1": {"machine_id": "src-1", "ansible_host": "10.0.0.1", "ansible_user": "ops", "ansible_port": 22},
        }, "instances": {}}}
        cm.get_fleet_state_copy = MagicMock(return_value=fleet)
        cm._normalize_fleet_state = MagicMock(side_effect=lambda f: f)
        cm.upsert_machine_record = MagicMock()
        return cm

    def test_same_endpoint_as_registered_machine_is_refused(self):
        cm = self.manager({"ansible_host": "10.0.0.1", "ansible_user": "ops", "ansible_port": 22})
        self.assertEqual(cm._collect_machine_registration_entries(1), [])
        cm.upsert_machine_record.assert_not_called()
        self.assertIn("already registered as machine 'src-1'", printed(cm.app))

    def test_same_host_other_port_is_allowed(self):
        cm = self.manager({"ansible_host": "10.0.0.1", "ansible_user": "ops", "ansible_port": 2222})
        self.assertEqual(cm._collect_machine_registration_entries(1), ["tgt-dup"])


if __name__ == "__main__":
    unittest.main()
