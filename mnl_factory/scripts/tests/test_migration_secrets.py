#!/usr/bin/env python3
"""Secrets never reach argv; migration SSH honours keepalive and ssh_common_args;
the source unit is disabled during migration and re-enabled on rollback."""

import tempfile
import unittest
from unittest.mock import MagicMock, patch

from tests.support import r1setup
from tests.test_migration_state_machine import build_app, build_plan, build_planner, last_saved

SSH_PASSWORD = "ssh-S3cret!"
SUDO_PASSWORD = "sudo-S3cret!"


def password_machine(**extra):
    record = {
        "machine_id": "machine-p",
        "ansible_host": "10.0.0.9",
        "ansible_user": "ops",
        "ansible_ssh_pass": SSH_PASSWORD,
        "ansible_become_password": SUDO_PASSWORD,
    }
    record.update(extra)
    return record


def real_app():
    app = r1setup.R1Setup.__new__(r1setup.R1Setup)
    app.settings_manager = MagicMock(connection_timeout=30)
    return app


class TestNoSecretsInArgv(unittest.TestCase):

    def test_machine_ssh_command_uses_sshpass_env(self):
        cmd = real_app()._build_machine_ssh_command(password_machine(), "true")
        self.assertEqual(list(cmd[:2]), ["sshpass", "-e"])
        self.assertNotIn(SSH_PASSWORD, " ".join(cmd))
        self.assertEqual(r1setup.ssh_subprocess_env(cmd)["SSHPASS"], SSH_PASSWORD)

    def test_scp_command_uses_sshpass_env(self):
        planner = r1setup.MigrationPlanner(MagicMock())
        cmd = planner._build_scp_command(password_machine(), "/local/a", "/remote/a", download=False)
        self.assertEqual(list(cmd[:2]), ["sshpass", "-e"])
        self.assertNotIn(SSH_PASSWORD, " ".join(cmd))

    def test_sudo_password_goes_to_stdin_not_command(self):
        planner = r1setup.MigrationPlanner(MagicMock())
        command = planner._build_remote_root_shell_command(password_machine(), "tar -czf /tmp/a.tgz .")
        self.assertNotIn(SUDO_PASSWORD, str(command))
        self.assertTrue(str(command).startswith("sudo -S -p ''"))
        self.assertEqual(command.stdin_data, SUDO_PASSWORD + "\n")

    def test_run_machine_command_sends_password_on_stdin_and_env(self):
        app = real_app()
        planner = r1setup.MigrationPlanner(app)
        command = planner._build_remote_root_shell_command(password_machine(), "true")
        completed = MagicMock(returncode=0, stdout="", stderr="")
        with patch.object(r1setup.subprocess, "run", return_value=completed) as run:
            result = planner._run_machine_command(password_machine(), command)

        self.assertEqual(result["status"], "success")
        argv = run.call_args.args[0]
        self.assertNotIn(SSH_PASSWORD, " ".join(argv))
        self.assertNotIn(SUDO_PASSWORD, " ".join(argv))
        self.assertEqual(run.call_args.kwargs["input"], SUDO_PASSWORD + "\n")
        self.assertEqual(run.call_args.kwargs["env"]["SSHPASS"], SSH_PASSWORD)

    def test_passwordless_sudo_and_key_auth_unchanged(self):
        record = {"ansible_host": "10.0.0.9", "ansible_user": "ops", "ansible_ssh_private_key_file": "/k"}
        planner = r1setup.MigrationPlanner(MagicMock())
        command = planner._build_remote_root_shell_command(record, "true")
        self.assertTrue(command.startswith("sudo -n "))
        self.assertIsNone(getattr(command, "stdin_data", None))
        cmd = real_app()._build_machine_ssh_command(record, command)
        self.assertEqual(cmd[0], "ssh")
        self.assertIsNone(r1setup.ssh_subprocess_env(cmd))


class TestSshOptions(unittest.TestCase):

    def test_keepalive_and_common_args_reach_ssh_and_scp(self):
        record = password_machine(ansible_ssh_common_args="-o ProxyJump=bastion@1.2.3.4")
        ssh_cmd = real_app()._build_machine_ssh_command(record, "true")
        scp_cmd = r1setup.MigrationPlanner(MagicMock())._build_scp_command(record, "/a", "/b", download=True)
        for cmd in (ssh_cmd, scp_cmd):
            joined = " ".join(cmd)
            self.assertIn("ServerAliveInterval=15", joined)
            self.assertIn("ProxyJump=bastion@1.2.3.4", joined)
        self.assertLess(ssh_cmd.index("ProxyJump=bastion@1.2.3.4"), ssh_cmd.index("ops@10.0.0.9"))


class TestSourceUnitDisabled(unittest.TestCase):

    def test_rollback_reenables_disabled_source_unit_before_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_plan(tmp, status="failed", last_step="source_archived")
            plan["source_unit_disabled"] = True
            app = build_app(plan, ["y"])
            planner = build_planner(app)
            events = []
            planner._set_source_unit_enabled = MagicMock(
                side_effect=lambda *a, **k: events.append(("enable", a[2])) or {"status": "success"})
            planner._start_source_instance_after_rollback.side_effect = (
                lambda *a, **k: events.append(("start",)) or {"status": "success"})

            planner.rollback_saved_migration_plan()

            self.assertEqual(events[:2], [("enable", True), ("start",)])
            self.assertFalse(last_saved(app)["source_unit_disabled"])

    def test_rollback_records_leftover_when_reenable_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = build_plan(tmp, status="failed", last_step="source_archived")
            plan["source_unit_disabled"] = True
            app = build_app(plan, ["y"])
            planner = build_planner(app)
            planner._set_source_unit_enabled = MagicMock(return_value={"status": "error", "message": "boom"})

            planner.rollback_saved_migration_plan()

            saved = last_saved(app)
            self.assertEqual(saved["status"], "rolled_back")
            self.assertIn("not enabled at boot", saved["rollback_cleanup"]["leftovers"][0])

    def test_set_source_unit_enabled_builds_systemctl_command(self):
        planner = r1setup.MigrationPlanner(MagicMock(connection_timeout=30))
        planner._run_machine_command = MagicMock(return_value={"status": "success"})
        planner._set_source_unit_enabled({"ansible_user": "root"}, {"service_name": "edge_node"}, False)
        self.assertIn("systemctl disable edge_node", planner._run_machine_command.call_args.args[1])


if __name__ == "__main__":
    unittest.main()
