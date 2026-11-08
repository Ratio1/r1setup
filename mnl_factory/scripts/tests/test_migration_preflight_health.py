#!/usr/bin/env python3
"""Preflight blocks (source/target /tmp space, existing runtime on target) and
the fresh node-info health check."""

import copy
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.support import r1setup

GIB = 1024 ** 3

FLEET = {
    "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
    "fleet": {
        "machines": {
            "machine-a": {"machine_id": "machine-a", "ansible_host": "10.0.0.1", "ansible_user": "root",
                          "topology_mode": "standard", "deployment_state": "active", "instance_names": ["node-1"]},
            "machine-b": {"machine_id": "machine-b", "ansible_host": "10.0.0.2", "ansible_user": "root",
                          "topology_mode": "standard", "deployment_state": "prepared", "instance_names": []},
        },
        "instances": {
            "node-1": {"logical_name": "node-1", "assigned_machine_id": "machine-a",
                       "runtime": {"service_name": "edge_node", "container_name": "edge_node",
                                   "volume_path": "/var/cache/edge_node/_local_cache"}},
        },
    },
}


def ok(**extra):
    probe = {"status": "success"}
    probe.update(extra)
    return probe


def preflight(**overrides):
    data = {
        "local_temp_dir": "/tmp/r1setup-migration",
        "source_reachability": ok(),
        "target_reachability": ok(),
        "source_volume_probe": ok(bytes=10 * GIB),
        "local_free_probe": ok(bytes=100 * GIB),
        "target_free_probe": ok(bytes=100 * GIB, mount_point="/"),
        "source_tmp_free_probe": ok(bytes=100 * GIB, mount_point="/"),
        "target_tmp_free_probe": ok(bytes=100 * GIB, mount_point="/"),
        "target_runtime_probe": ok(found=[]),
    }
    data.update(overrides)
    return data


def build_planner(preflight_data):
    app = MagicMock()
    app.get_fleet_state_copy.return_value = copy.deepcopy(FLEET)
    app._default_migration_temp_dir.return_value = Path("/tmp/r1setup-migration")
    app.config_manager._normalize_fleet_state.side_effect = lambda fleet: fleet
    app.config_manager.resolve_runtime_names.side_effect = (
        lambda logical_name, **kwargs: r1setup.ConfigurationManager.resolve_runtime_names(logical_name, **kwargs))
    app.config_manager._sanitize_runtime_suffix.side_effect = r1setup.ConfigurationManager._sanitize_runtime_suffix
    app.config_manager.detect_runtime_collisions.return_value = {}
    planner = r1setup.MigrationPlanner(app)
    planner._collect_preflight = MagicMock(return_value=preflight_data)
    return planner


class TestPreflightBlocks(unittest.TestCase):

    def plan(self, **overrides):
        return build_planner(preflight(**overrides)).build_migration_plan("node-1", "machine-b")

    def test_enough_space_and_empty_target_is_planned(self):
        plan = self.plan()
        self.assertEqual(plan["status"], "planned", plan["validation"]["errors"])

    def test_low_source_tmp_blocks_plan(self):
        plan = self.plan(source_tmp_free_probe=ok(bytes=1 * GIB, mount_point="/"))
        self.assertEqual(plan["status"], "blocked")
        self.assertTrue(any("Source /tmp" in error for error in plan["validation"]["errors"]))

    def test_target_tmp_on_same_filesystem_needs_archive_plus_volume(self):
        plan = self.plan(
            target_free_probe=ok(bytes=15 * GIB, mount_point="/"),
            target_tmp_free_probe=ok(bytes=15 * GIB, mount_point="/"),
        )
        self.assertEqual(plan["status"], "blocked")
        self.assertTrue(any("Target /tmp" in error for error in plan["validation"]["errors"]))

    def test_target_tmp_on_separate_filesystem_needs_archive_only(self):
        plan = self.plan(
            target_free_probe=ok(bytes=15 * GIB, mount_point="/var"),
            target_tmp_free_probe=ok(bytes=15 * GIB, mount_point="/tmp"),
        )
        self.assertEqual(plan["status"], "planned", plan["validation"]["errors"])

    def test_existing_runtime_on_target_blocks_plan_with_hint(self):
        plan = self.plan(target_runtime_probe=ok(found=["unit", "volume"]))
        self.assertEqual(plan["status"], "blocked")
        self.assertTrue(any("already has a service unit edge_node and volume" in e for e in plan["validation"]["errors"]))
        self.assertTrue(any("rm -rf /var/cache/edge_node/_local_cache" in h for h in plan["validation"]["hints"]))

    def test_old_preflight_without_new_probes_still_plans(self):
        data = preflight()
        for key in ("source_tmp_free_probe", "target_tmp_free_probe", "target_runtime_probe"):
            data.pop(key)
        plan = build_planner(data).build_migration_plan("node-1", "machine-b")
        self.assertEqual(plan["status"], "planned")

    def test_free_space_probe_reads_mount_point(self):
        app = MagicMock()
        app._run_machine_probe.return_value = {"status": "success", "stdout": "123456 /var\n"}
        result = r1setup.MigrationPlanner(app)._probe_remote_free_space({}, "/var/cache/edge_node")
        self.assertEqual((result["bytes"], result["mount_point"]), (123456, "/var"))

    def test_existing_runtime_probe_parses_found_items(self):
        app = MagicMock()
        app._run_machine_probe.return_value = {"status": "success", "stdout": "volume\n"}
        result = r1setup.MigrationPlanner(app)._probe_existing_target_runtime(
            {}, {"service_name": "edge_node", "volume_path": "/v"})
        self.assertEqual(result["found"], ["volume"])


class TestFreshNodeInfo(unittest.TestCase):

    def planner_with_mtimes(self, mtimes):
        app = MagicMock(connection_timeout=30)
        planner = r1setup.MigrationPlanner(app)
        planner._run_machine_command = MagicMock(side_effect=[
            {"status": "success", "stdout": f"{value}\n"} for value in mtimes])
        return planner

    @patch.object(r1setup.time, "sleep")
    def test_stale_then_fresh_file_is_accepted(self, _sleep):
        planner = self.planner_with_mtimes([900, 900, 1500])
        self.assertTrue(planner._wait_for_fresh_node_info({"ansible_user": "root"}, {}, 1000,
                                                          window_secs=60, interval_secs=10))
        self.assertEqual(planner._run_machine_command.call_count, 3)

    @patch.object(r1setup.time, "sleep")
    def test_file_never_refreshed_times_out(self, _sleep):
        planner = self.planner_with_mtimes([900] * 20)
        with patch.object(r1setup.time, "monotonic", side_effect=[0, 0, 5, 15, 25, 35]):
            self.assertFalse(planner._wait_for_fresh_node_info({"ansible_user": "root"}, {}, 1000,
                                                               window_secs=30, interval_secs=10))

    def test_health_reports_unverified_without_fresh_info(self):
        app = MagicMock()
        app.status_tracker._parse_ansible_status_lines.return_value = {"node-1": {"status": "running"}}
        planner = r1setup.MigrationPlanner(app)
        planner._run_target_instance_playbook = MagicMock(return_value=(True, "status-output"))
        planner._run_with_spinner = MagicMock(return_value=False)
        plan = {"instance_name": "node-1", "target_machine_id": "machine-b", "target_start_epoch": 1000,
                "target_runtime": {}}

        result = planner._verify_target_migration_health(plan)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["app_health_status"], "unverified")
        self.assertEqual(planner._run_target_instance_playbook.call_count, 1)


if __name__ == "__main__":
    unittest.main()
