#!/usr/bin/env python3
"""Tests for Advanced Menu -> Reset Node Key (e2.pem regeneration)."""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.support import r1setup


OLD_PEM = "-----BEGIN PRIVATE KEY-----\nOLDKEY\n-----END PRIVATE KEY-----\n"


def info(**addresses):
    """Node-info results keyed by instance: info(nodea=("0xai_A", "0xA"))."""
    return {
        name: {"status": "success", "data": {"address": addr, "eth_address": eth}}
        for name, (addr, eth) in addresses.items()
    }


OLD_INFO = info(nodea=("0xai_oldA", "0xOLDA"), nodeb=("0xai_oldB", "0xOLDB"))
NEW_INFO = info(nodea=("0xai_newA", "0xNEWA"), nodeb=("0xai_newB", "0xNEWB"))


class TestResetNodeKey(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_path = Path(self.temp_dir.name)
        self.backup_dir = self.base_path / "backups"

        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "nodea": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "mnl_docker_volume_path": "/var/cache/edge_node/_local_cache",
                            },
                            "nodeb": {
                                "ansible_host": "10.0.0.2",
                                "ansible_user": "ubuntu",
                                "mnl_docker_volume_path": "/var/cache/edge_node_nodeb/_local_cache",
                            },
                        }
                    }
                }
            }
        }
        app.config_dir = self.base_path
        (self.base_path / "playbooks").mkdir()
        (self.base_path / "playbooks" / "reset_node_key.yml").write_text("---\n")
        app.r1_setup_dir = self.base_path / "r1_setup"
        app.settings_manager = MagicMock(playbook_timeout=60)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.print_colored = MagicMock()
        app.print_header = MagicMock()
        app.print_section = MagicMock()
        app.wait_for_enter = MagicMock()
        app.select_hosts = MagicMock(return_value=["nodea", "nodeb"])
        app.run_generated_playbook = MagicMock(return_value=(True, "", [], {}))
        app.migration_planner = MagicMock()
        app.migration_planner._run_machine_command = MagicMock(
            return_value={"status": "success", "stdout": OLD_PEM, "stderr": ""}
        )
        app.migration_planner._build_remote_root_shell_command = MagicMock(
            side_effect=lambda record, cmd: f"ROOT[{cmd}]"
        )
        app._fetch_node_info_results = MagicMock(side_effect=[OLD_INFO, NEW_INFO])
        self.app = app
        sleep_patch = patch("time.sleep")
        self.sleep = sleep_patch.start()
        self.addCleanup(sleep_patch.stop)

    def _printed(self):
        return "\n".join(str(c.args[0]) for c in self.app.print_colored.call_args_list if c.args)

    def _inputs(self, *answers):
        self.app.get_input = MagicMock(side_effect=list(answers))

    def _reset_playbook_targets(self):
        calls = self.app.run_generated_playbook.call_args_list
        return [list(c.args[1]) for c in calls if Path(c.args[0]).name == "reset_node_key.yml"]

    def test_backs_up_old_key_with_owner_only_permissions_then_resets(self):
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        saved = sorted(self.backup_dir.glob("*e2.pem"))
        self.assertEqual(2, len(saved))
        self.assertTrue(saved[0].name.startswith("nodea-"))
        self.assertTrue(saved[1].name.startswith("nodeb-"))
        for path in saved:
            self.assertEqual(OLD_PEM, path.read_text())
            self.assertEqual(0o600, stat.S_IMODE(os.stat(path).st_mode))
        self.assertEqual([["nodea", "nodeb"]], self._reset_playbook_targets())

    def test_reads_key_from_each_instance_volume_as_root(self):
        self.app.select_hosts.return_value = ["nodeb"]
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        record, command = self.app.migration_planner._run_machine_command.call_args.args
        self.assertEqual("10.0.0.2", record["ansible_host"])
        self.assertEqual("ROOT[cat /var/cache/edge_node_nodeb/_local_cache/_data/e2.pem]", command)

    def test_node_whose_backup_fails_is_not_reset(self):
        self.app.migration_planner._run_machine_command.side_effect = [
            {"status": "error", "message": "Permission denied"},
            {"status": "success", "stdout": OLD_PEM, "stderr": ""},
        ]
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        self.assertEqual([["nodeb"]], self._reset_playbook_targets())
        self.assertEqual(["nodeb"], [p.name.split("-")[0] for p in self.backup_dir.glob("*e2.pem")])

    def test_empty_key_file_counts_as_failed_backup(self):
        self.app.select_hosts.return_value = ["nodea"]
        self.app.migration_planner._run_machine_command.return_value = {
            "status": "success", "stdout": "  \n", "stderr": ""
        }
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        self.assertEqual([], self._reset_playbook_targets())

    def test_declining_backup_resets_without_reading_keys(self):
        self._inputs("n", "RESET")

        self.app.reset_node_keys()

        self.app.migration_planner._run_machine_command.assert_not_called()
        self.assertEqual([["nodea", "nodeb"]], self._reset_playbook_targets())

    def test_wrong_confirmation_changes_nothing(self):
        self._inputs("y", str(self.backup_dir), "yes")

        self.app.reset_node_keys()

        self.app.migration_planner._run_machine_command.assert_not_called()
        self.assertEqual([], self._reset_playbook_targets())

    def test_empty_selection_changes_nothing(self):
        self.app.select_hosts.return_value = []
        self.app.get_input = MagicMock()

        self.app.reset_node_keys()

        self.app.get_input.assert_not_called()
        self.assertEqual([], self._reset_playbook_targets())

    def _reset_log_events(self):
        log_path = self.base_path / "r1_setup" / "logs" / "operations.log"
        if not log_path.exists():
            return []
        events = [json.loads(line) for line in log_path.read_text().splitlines()]
        return [e for e in events if e["operation_type"] == "reset_node_key"]

    def test_new_backup_directory_is_owner_only(self):
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        self.assertEqual(0o700, stat.S_IMODE(os.stat(self.backup_dir).st_mode))

    def test_existing_backup_directory_permissions_are_left_alone(self):
        self.backup_dir.mkdir()
        os.chmod(self.backup_dir, 0o755)
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        self.assertEqual(0o755, stat.S_IMODE(os.stat(self.backup_dir).st_mode))

    def test_logs_one_event_per_node_with_backup_path_and_outcome(self):
        self.app.migration_planner._run_machine_command.side_effect = [
            {"status": "error", "message": "Permission denied"},
            {"status": "success", "stdout": OLD_PEM, "stderr": ""},
        ]
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        events = {e["details"]["instance"]: e for e in self._reset_log_events()}
        self.assertEqual({"nodea", "nodeb"}, set(events))
        self.assertEqual("skipped_backup_failed", events["nodea"]["status"])
        self.assertIsNone(events["nodea"]["details"]["backup_path"])
        self.assertEqual("success", events["nodeb"]["status"])
        self.assertEqual("10.0.0.2", events["nodeb"]["details"]["ansible_host"])
        self.assertEqual(
            "/var/cache/edge_node_nodeb/_local_cache/_data/e2.pem",
            events["nodeb"]["details"]["key_path"],
        )
        self.assertTrue(Path(events["nodeb"]["details"]["backup_path"]).exists())

    def test_failed_playbook_is_logged_as_failed_without_backup_when_declined(self):
        self.app.run_generated_playbook.return_value = (False, "", [], {})
        self._inputs("n", "RESET")

        self.app.reset_node_keys()

        events = self._reset_log_events()
        self.assertEqual(["failed", "failed"], [e["status"] for e in events])
        self.assertEqual([None, None], [e["details"]["backup_path"] for e in events])

    def test_cancelled_reset_writes_no_log(self):
        self._inputs("y", str(self.backup_dir), "no")

        self.app.reset_node_keys()

        self.assertEqual([], self._reset_log_events())

    def test_shows_old_and_new_address_for_each_reset_node(self):
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        printed = self._printed()
        for expected in ("0xai_oldA", "0xai_newA", "0xNEWA", "0xai_oldB", "0xai_newB", "0xNEWB"):
            self.assertIn(expected, printed)

    def test_new_addresses_are_recorded_in_the_audit_log(self):
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        events = {e["details"]["instance"]: e["details"] for e in self._reset_log_events()}
        self.assertEqual("0xai_oldA", events["nodea"]["old_address"])
        self.assertEqual("0xai_newA", events["nodea"]["new_address"])
        self.assertEqual("0xNEWB", events["nodeb"]["new_eth_address"])

    def test_keeps_polling_while_a_node_still_reports_its_old_address(self):
        stale = info(nodea=("0xai_oldA", "0xOLDA"), nodeb=("0xai_newB", "0xNEWB"))
        self.app._fetch_node_info_results.side_effect = [OLD_INFO, stale, NEW_INFO]
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        events = {e["details"]["instance"]: e["details"] for e in self._reset_log_events()}
        self.assertEqual("0xai_newA", events["nodea"]["new_address"])
        self.assertEqual(3, self.app._fetch_node_info_results.call_count)

    def test_address_still_unchanged_after_polling_is_reported_not_claimed_new(self):
        self.app.select_hosts.return_value = ["nodea"]
        self.app._fetch_node_info_results.side_effect = None
        self.app._fetch_node_info_results.return_value = info(nodea=("0xai_oldA", "0xOLDA"))
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        events = self._reset_log_events()
        self.assertIsNone(events[0]["details"]["new_address"])
        self.assertIn("Node Status & Info", self._printed())

    def test_node_info_unavailable_before_reset_does_not_block_reset(self):
        self.app._fetch_node_info_results.side_effect = [None, NEW_INFO]
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        self.assertEqual([["nodea", "nodeb"]], self._reset_playbook_targets())
        self.assertIn("0xai_newA", self._printed())

    def test_address_lookup_only_targets_reset_nodes(self):
        self.app.migration_planner._run_machine_command.side_effect = [
            {"status": "error", "message": "Permission denied"},
            {"status": "success", "stdout": OLD_PEM, "stderr": ""},
        ]
        self._inputs("y", str(self.backup_dir), "RESET")

        self.app.reset_node_keys()

        for call in self.app._fetch_node_info_results.call_args_list[1:]:
            self.assertEqual(["nodeb"], call.kwargs["host_names"])

    def test_advanced_menu_option_8_opens_reset_node_key(self):
        self.app.has_fleet_machines = MagicMock(return_value=False)
        self.app.reset_node_keys = MagicMock()
        self._inputs("8", "0")

        self.app.advanced_menu()

        self.app.reset_node_keys.assert_called_once_with()


class TestResetNodeKeyPlaybook(unittest.TestCase):
    def test_playbook_deletes_instance_key_restarts_and_waits_for_new_key(self):
        playbook = (
            Path(r1setup.__file__).resolve().parent.parent / "playbooks" / "reset_node_key.yml"
        ).read_text()

        self.assertIn('{{ mnl_docker_volume_path }}/_data/e2.pem', playbook)
        self.assertIn("state: absent", playbook)
        self.assertIn("state: stopped", playbook)
        self.assertIn("state: started", playbook)
        self.assertIn("ansible.builtin.wait_for", playbook)
        self.assertLess(playbook.index("state: stopped"), playbook.index("state: absent"))
        self.assertLess(playbook.index("state: absent"), playbook.index("state: started"))


if __name__ == "__main__":
    unittest.main()
