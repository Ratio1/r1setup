#!/usr/bin/env python3
"""Migration UX: failure summary, live host state, receipt, prompts, target registration."""

import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tests.support import r1setup
from tests.test_migration_state_machine import build_app, build_plan, build_planner, last_saved

ANSIBLE_OUTPUT = """PLAY [Apply] ****
TASK [Start service] ****
fatal: [node-1]: FAILED! => {"changed": false, "msg": "Unable to start service edge_node: Job failed"}
PLAY RECAP ****
node-1 : ok=3 changed=1 unreachable=0 failed=1"""


def printed(app):
    return " | ".join(str(c.args[0]) for c in app.print_colored.call_args_list if c.args)


class TestFailureSummary(unittest.TestCase):

    def test_summarize_error_extracts_ansible_msg(self):
        self.assertEqual(r1setup.MigrationPlanner._summarize_error(ANSIBLE_OUTPUT),
                         "Unable to start service edge_node: Job failed")

    def test_summarize_error_skips_ssh_noise(self):
        raw = "Warning: Permanently added '10.0.0.2' (ED25519) to the list of known hosts.\r\nConnection timed out during banner exchange"
        self.assertEqual(r1setup.MigrationPlanner._summarize_error(raw), "Connection timed out during banner exchange")

    def test_fail_step_records_short_error_and_prints_next_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_plan(tmp, status="executing")
            app = build_app(plan, [])
            app._get_operation_log_dir = MagicMock(return_value=tmp)
            planner = r1setup.MigrationPlanner(app)

            planner._fail_step(plan, 8, "Apply and start target runtime", "target", ANSIBLE_OUTPUT)

            saved = last_saved(app)
            self.assertEqual(saved["status"], "failed")
            self.assertEqual(saved["last_error"],
                             "Step 8/9 Apply and start target runtime failed on target machine-b: "
                             "Unable to start service edge_node: Job failed")
            text = printed(app)
            self.assertIn("Roll back migration", text)
            self.assertIn("the node may be running", text)
            self.assertIn("Full output:", text)
            self.assertNotIn("PLAY RECAP", text)


class TestLiveHostState(unittest.TestCase):

    def test_probe_parses_key_values(self):
        planner = r1setup.MigrationPlanner(MagicMock(connection_timeout=30))
        planner._run_machine_command = MagicMock(return_value={"status": "success", "stdout": (
            "active=inactive\nenabled=disabled\ncontainer=absent\nvolume=present\narchive=absent\nkey=21eb017f0a1b\n")})
        state = planner._probe_host_runtime_state({"ansible_user": "root"}, {}, "/tmp/a.tgz")
        text, color = planner._format_host_runtime_state(state)
        self.assertIn("service inactive/disabled", text)
        self.assertIn("node key 21eb017f0a1b", text)
        self.assertEqual(color, "white")

    def test_running_and_unreachable_are_highlighted(self):
        fmt = r1setup.MigrationPlanner._format_host_runtime_state
        self.assertEqual(fmt({"status": "success", "active": "active"})[1], "yellow")
        text, color = fmt({"status": "error", "message": "timed out"})
        self.assertEqual((text, color), ("unreachable (timed out)", "red"))

    def test_finalization_review_hides_planning_preflight(self):
        plan = build_plan("/tmp", status="executed")
        plan["preflight"] = {"target_deployment_state": "empty", "requires_target_preparation": True}
        app = build_app(plan, [])
        planner = r1setup.MigrationPlanner(app)
        planner._display_migration_plan(plan, context="finalization")
        self.assertNotIn("Target deployment state", printed(app))


class TestReceiptAndHelpers(unittest.TestCase):

    def test_helpers_kept_when_other_instance_remains_on_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="executed"), ["n", "y"])
            fleet = app.get_fleet_state_copy.return_value
            fleet["fleet"]["machines"]["machine-a"]["instance_names"] = ["node-2"]
            planner = build_planner(app)

            planner.finalize_saved_migration_plan()

            self.assertNotIn("remove_global_helpers", planner._cleanup_runtime_artifacts.call_args.kwargs)

    def test_receipt_mentions_kept_node_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            app = build_app(build_plan(tmp, status="executed"), ["n", "y"])
            planner = build_planner(app)

            planner.finalize_saved_migration_plan()

            text = printed(app)
            self.assertIn("runs on target machine-b", text)
            self.assertIn("holds the node key (e2.pem)", text)


class TestPromptsAndTargetSelection(unittest.TestCase):

    def test_only_candidate_target_is_default(self):
        app = MagicMock()
        app.get_input = MagicMock(return_value="1")
        planner = r1setup.MigrationPlanner(app)
        fleet = {"fleet": {"machines": {"a": {}, "b": {}}}}
        self.assertEqual(planner._select_migration_target_machine(fleet, "a"), "b")
        self.assertEqual(app.get_input.call_args.args[1], "1")

    def test_no_target_offers_inline_registration(self):
        app = MagicMock()
        app.get_input = MagicMock(return_value="y")
        app.config_manager._collect_machine_registration_entries.return_value = ["new-host"]
        planner = r1setup.MigrationPlanner(app)
        self.assertEqual(planner._select_migration_target_machine({"fleet": {"machines": {"a": {}}}}, "a"), "new-host")

    def test_blocked_plan_save_defaults_to_no(self):
        app = MagicMock()
        app.active_config = {"config_name": "fleet"}
        app.get_input = MagicMock(side_effect=lambda prompt, default='': default)
        planner = r1setup.MigrationPlanner(app)
        planner._get_plannable_instances = MagicMock(return_value={"node-1": {"assigned_machine_id": "a"}})
        planner._select_migration_source_instance = MagicMock(return_value="node-1")
        planner._confirm_source_machine = MagicMock(return_value=True)
        planner._select_migration_target_machine = MagicMock(return_value="b")
        planner._select_runtime_name_policy = MagicMock(return_value="preserve")
        planner.build_migration_plan = MagicMock(return_value={"status": "blocked", "validation": {"errors": ["x"]}})
        planner._display_migration_plan = MagicMock()

        planner.plan_instance_migration()

        app.set_migration_plan_state.assert_not_called()

    def test_format_duration(self):
        fmt = r1setup.MigrationPlanner._format_duration
        self.assertEqual([fmt(5), fmt(65), fmt(3725)], ["5s", "1m05s", "1h02m"])


class TestBlockedPlanGrouping(unittest.TestCase):

    def test_occupied_standard_target_reports_one_cause(self):
        from tests.test_migration_preflight_health import FLEET, build_planner as build_plan_builder, preflight
        import copy
        planner = build_plan_builder(preflight())
        fleet = copy.deepcopy(FLEET)
        fleet["fleet"]["machines"]["machine-b"]["instance_names"] = ["placeholder"]
        fleet["fleet"]["instances"]["placeholder"] = {"assigned_machine_id": "machine-b", "runtime": {}}
        planner.app.get_fleet_state_copy.return_value = fleet
        planner.app.config_manager.detect_runtime_collisions.return_value = {
            "service_name": ["placeholder"], "container_name": ["placeholder"], "volume_path": ["placeholder"]}

        plan = planner.build_migration_plan("node-1", "machine-b")

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(len(plan["validation"]["errors"]), 1)
        self.assertIn("already has assigned instance(s): placeholder", plan["validation"]["errors"][0])


if __name__ == "__main__":
    unittest.main()
