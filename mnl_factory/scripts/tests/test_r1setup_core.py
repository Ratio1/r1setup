#!/usr/bin/env python3
"""Tests for core R1Setup instance methods."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.support import r1setup


class TestValidateIp(unittest.TestCase):
    """Tests for R1Setup.validate_ip()."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)

    def test_valid_ip(self):
        self.assertTrue(self.app.validate_ip("192.168.1.1"))

    def test_valid_ip_zeros(self):
        self.assertTrue(self.app.validate_ip("0.0.0.0"))

    def test_valid_ip_max(self):
        self.assertTrue(self.app.validate_ip("255.255.255.255"))

    def test_octet_too_high(self):
        self.assertFalse(self.app.validate_ip("256.0.0.1"))

    def test_too_few_octets(self):
        self.assertFalse(self.app.validate_ip("192.168.1"))

    def test_too_many_octets(self):
        self.assertFalse(self.app.validate_ip("192.168.1.1.1"))

    def test_letters(self):
        self.assertFalse(self.app.validate_ip("abc.def.ghi.jkl"))

    def test_empty_string(self):
        self.assertFalse(self.app.validate_ip(""))

    def test_localhost(self):
        self.assertTrue(self.app.validate_ip("127.0.0.1"))

    def test_negative_octet(self):
        self.assertFalse(self.app.validate_ip("-1.0.0.1"))


class TestFormatTimestampAgo(unittest.TestCase):
    """Tests for R1Setup._format_timestamp_ago()."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        self.app.print_debug = MagicMock()

    def test_empty_returns_never(self):
        self.assertEqual(self.app._format_timestamp_ago(""), "Never")

    def test_none_returns_never(self):
        self.assertEqual(self.app._format_timestamp_ago(None), "Never")

    def test_invalid_returns_unknown(self):
        self.assertEqual(self.app._format_timestamp_ago("not-a-date"), "Unknown")

    def test_recent_timestamp(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.app._format_timestamp_ago(now)
        self.assertEqual(result, "Just now")

    def test_hours_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = self.app._format_timestamp_ago(ts)
        self.assertIn("hour(s) ago", result)

    def test_days_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        result = self.app._format_timestamp_ago(ts)
        self.assertIn("5 day(s) ago", result)

    def test_minutes_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        result = self.app._format_timestamp_ago(ts)
        self.assertIn("minute(s) ago", result)


class TestWaitForEnter(unittest.TestCase):
    """Tests for R1Setup.wait_for_enter()."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)

    @patch("builtins.input")
    def test_default_message(self, mock_input):
        self.app.wait_for_enter()
        mock_input.assert_called_once_with("\nPress Enter to continue...")

    @patch("builtins.input")
    def test_custom_message(self, mock_input):
        self.app.wait_for_enter("Press Enter to start streaming logs...")
        mock_input.assert_called_once_with("\nPress Enter to start streaming logs...")

    @patch("builtins.input")
    def test_newline_always_prefixed(self, mock_input):
        self.app.wait_for_enter("whatever")
        arg = mock_input.call_args[0][0]
        self.assertTrue(arg.startswith("\n"))


class TestServiceVersionTracking(unittest.TestCase):
    """Tests for service-template version persistence helpers."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_path = Path(self.temp_dir.name)

        self.app = MagicMock()
        self.app.config_dir = self.base_path
        self.app.config_file = self.base_path / "hosts.yml"
        self.app.vars_file = self.base_path / "group_vars" / "variables.yml"
        self.app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {}
                    }
                }
            }
        }
        self.app.print_debug = MagicMock()
        self.app.print_colored = MagicMock()

        self.cm = r1setup.ConfigurationManager(self.app)

    def test_get_host_service_file_version_defaults_to_v0(self):
        self.assertEqual(
            self.cm.get_host_service_file_version({}),
            r1setup.DEFAULT_SERVICE_FILE_VERSION,
        )

    def test_load_configuration_backfills_missing_service_version(self):
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.app.config_file.write_text(
            "all:\n"
            "  children:\n"
            "    gpu_nodes:\n"
            "      hosts:\n"
            "        node-1:\n"
            "          ansible_host: 10.0.0.1\n"
            "          ansible_user: root\n"
        )
        self.cm._save_configuration = MagicMock()

        loaded = self.cm.load_configuration()

        self.assertTrue(loaded)
        host = self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-1"]
        self.assertEqual(host[r1setup.SERVICE_FILE_VERSION_FIELD], "v0")
        self.cm._save_configuration.assert_called_once()

    def test_record_service_file_version_updates_selected_hosts(self):
        group_vars_dir = self.base_path / "group_vars"
        group_vars_dir.mkdir(parents=True, exist_ok=True)
        (group_vars_dir / "mnl.yml").write_text('mnl_service_version: "v7"\n')
        self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"] = {
            "node-1": {},
            "node-2": {r1setup.SERVICE_FILE_VERSION_FIELD: "v3"},
        }
        self.cm._save_configuration = MagicMock()

        self.cm.record_service_file_version(["node-1"])

        hosts = self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]
        self.assertEqual(hosts["node-1"][r1setup.SERVICE_FILE_VERSION_FIELD], "v7")
        self.assertEqual(hosts["node-2"][r1setup.SERVICE_FILE_VERSION_FIELD], "v3")
        self.cm._save_configuration.assert_called_once()


class TestDeploymentServiceVersionStamping(unittest.TestCase):
    """Tests deployment success stamps selected hosts with the current service version."""

    def test_successful_deploy_records_service_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            playbooks_dir = base_path / "playbooks"
            playbooks_dir.mkdir(parents=True, exist_ok=True)
            (playbooks_dir / "site.yml").write_text("---\n")

            app = MagicMock()
            app.check_hosts_config.return_value = True
            app.load_configuration.return_value = True
            app.inventory = {
                "all": {
                    "children": {
                        "gpu_nodes": {
                            "hosts": {
                                "node-1": {"ansible_host": "10.0.0.1", "ansible_user": "root"}
                            }
                        }
                    }
                }
            }
            app.get_mnl_app_env.return_value = "mainnet"
            app.select_hosts.return_value = ["node-1"]
            app._get_node_status_info.return_value = {"status": "never_deployed"}
            app._get_status_display_info.return_value = ("?", "yellow", "Never deployed")
            app.get_input.return_value = "y"
            app.config_dir = base_path
            app.config_file = base_path / "hosts.yml"
            app.active_config = {"deployment_status": "never_deployed"}
            app.run_command.return_value = (True, "")
            app.print_colored = MagicMock()
            app.print_header = MagicMock()
            app.wait_for_enter = MagicMock()
            app._update_node_status = MagicMock()
            app._display_node_status = MagicMock()
            app._display_copy_friendly_addresses = MagicMock()
            app.record_service_file_version = MagicMock()

            service = r1setup.DeploymentService(app)

            with patch.dict(os.environ, {
                "ANSIBLE_CONFIG": "ansible.cfg",
                "ANSIBLE_COLLECTIONS_PATH": "collections",
                "ANSIBLE_HOME": "ansible-home",
            }, clear=False):
                with patch.object(service, "_update_deployment_metadata") as update_metadata:
                    service._deploy_setup("site.yml", "Full Deployment", "Docker + NVIDIA drivers + GPU setup")

            update_metadata.assert_called_once_with("full")
            app.record_service_file_version.assert_called_once_with(["node-1"])
