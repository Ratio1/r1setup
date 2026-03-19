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


class TestPrintHeader(unittest.TestCase):
    """Tests for R1Setup.print_header()."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        self.app.colors = {
            'cyan': '',
            'white': '',
            'yellow': '',
            'red': '',
            'green': '',
            'blue': '',
            'end': '',
        }

    @patch("os.system")
    def test_print_header_clears_by_default(self, mock_system):
        with patch.dict(os.environ, {}, clear=False):
            self.app.print_header("Header")
        mock_system.assert_called_once()

    @patch("os.system")
    def test_print_header_skips_clear_when_requested(self, mock_system):
        with patch.dict(os.environ, {"R1SETUP_NO_CLEAR": "1"}, clear=False):
            self.app.print_header("Header")
        mock_system.assert_not_called()


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
            (playbooks_dir / "prepare_machine.yml").write_text("---\n")
            (playbooks_dir / "apply_instance.yml").write_text("---\n")

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
            app.connection_timeout = 30
            app.print_colored = MagicMock()
            app.print_header = MagicMock()
            app.wait_for_enter = MagicMock()
            app._update_node_status = MagicMock()
            app._display_node_status = MagicMock()
            app._display_copy_friendly_addresses = MagicMock()
            app.record_service_file_version = MagicMock()
            app.group_host_names_by_machine.return_value = {
                "root@10.0.0.1:22": {
                    "representative_host": "node-1",
                    "host_names": ["node-1"],
                }
            }
            app.config_manager = MagicMock()
            app.config_manager._derive_machine_id.side_effect = lambda host_name, host_config: f"{host_config.get('ansible_user', 'root')}@{host_config['ansible_host']}:22"
            app._parse_ansible_play_recap.return_value = {
                "node-1": {"status": "connected"}
            }
            app.run_generated_playbook.side_effect = [
                (True, "machine phase", ["node-1"], {"all": {"children": {"gpu_nodes": {"hosts": {"node-1": {}}}}}}),
                (True, "instance phase", ["node-1"], {"all": {"children": {"gpu_nodes": {"hosts": {"node-1": {}}}}}}),
            ]

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
            self.assertEqual(app.run_generated_playbook.call_count, 2)
            self.assertEqual(app.run_generated_playbook.call_args_list[0].kwargs["timeout"], 600)
            self.assertEqual(app.run_generated_playbook.call_args_list[1].kwargs["timeout"], 180)


class TestAddNodeExpertModeFlow(unittest.TestCase):
    """Tests same-machine add-node expert-mode gating."""

    def _make_app(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "nodea": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                            }
                        }
                    }
                }
            }
        }
        app.print_section = MagicMock()
        app.print_colored = MagicMock()
        app._save_configuration = MagicMock()
        app._get_valid_hostname = MagicMock(return_value="nodeb")
        app._configure_single_node = MagicMock(return_value={
            "ansible_host": "10.0.0.1",
            "ansible_user": "root",
        })
        app.config_manager = MagicMock()
        app.config_manager.bind_host_to_existing_machine.return_value = {
            "ansible_host": "10.0.0.1",
            "ansible_user": "root",
            "r1setup_machine_id": "machine-a",
        }
        app.config_manager.get_fleet_state_copy.return_value = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {
                "machines": {
                    "machine-a": {
                        "machine_id": "machine-a",
                        "ansible_host": "10.0.0.1",
                        "ansible_user": "root",
                        "ansible_port": 22,
                        "topology_mode": "standard",
                        "deployment_state": "active",
                        "instance_names": ["nodea"],
                    }
                },
                "instances": {
                    "nodea": {"assigned_machine_id": "machine-a"},
                },
            },
        }
        app.config_manager._normalize_fleet_state.side_effect = lambda fleet_state: fleet_state
        app.config_manager._format_machine_connection_display.return_value = "root@10.0.0.1"
        app.config_manager.promote_machine_to_expert.return_value = {
            "machine_id": "machine-a",
            "topology_mode": "expert",
            "deployment_state": "active",
            "instance_names": ["nodea"],
        }
        return app

    def test_add_node_cancels_when_expert_mode_declined(self):
        app = self._make_app()
        app.get_input = MagicMock(return_value="n")

        app._add_node()

        hosts = app.inventory["all"]["children"]["gpu_nodes"]["hosts"]
        self.assertEqual(sorted(hosts.keys()), ["nodea"])
        app._save_configuration.assert_not_called()
        app.config_manager.promote_machine_to_expert.assert_not_called()

    def test_add_node_promotes_machine_when_expert_mode_accepted(self):
        app = self._make_app()
        app.get_input = MagicMock(return_value="y")
        app.config_manager.apply_runtime_snapshot_to_host_config.side_effect = lambda host_name, host_config: host_config.update({
            "edge_node_service_name": "edge_node_nodeb",
            "mnl_docker_container_name": "edge_node_nodeb",
            "mnl_docker_volume_path": "/var/cache/edge_node_nodeb/_local_cache",
            "mnl_r1setup_metadata_host_path": "/var/cache/edge_node_nodeb/_local_cache/_data/r1setup/metadata.json",
            "r1setup_runtime_exit_status_path": "/tmp/edge_node_nodeb.exit",
        }) or True

        app._add_node()

        hosts = app.inventory["all"]["children"]["gpu_nodes"]["hosts"]
        self.assertIn("nodeb", hosts)
        self.assertEqual(hosts["nodeb"]["r1setup_topology_mode"], "expert")
        self.assertEqual(hosts["nodeb"]["r1setup_runtime_name_policy"], "normalize_to_target")
        self.assertEqual(hosts["nodeb"]["edge_node_service_name"], "edge_node_nodeb")
        self.assertEqual(hosts["nodeb"]["mnl_docker_container_name"], "edge_node_nodeb")
        app.config_manager.promote_machine_to_expert.assert_called_once_with("machine-a", app.inventory)
        app.config_manager.apply_runtime_snapshot_to_host_config.assert_called_once_with("nodeb", hosts["nodeb"])
        app._save_configuration.assert_called_once()


class TestNodeInfoDetails(unittest.TestCase):
    """Tests the optional detailed node info display."""

    def test_display_node_info_details_shows_service_versions(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v3",
                            }
                        }
                    }
                }
            }
        }
        app.load_configuration = MagicMock()
        app.get_mnl_service_version = MagicMock(return_value="v5")
        app.get_host_service_file_version = MagicMock(return_value="v3")
        app._get_node_status_info = MagicMock(return_value={"status": "running"})
        app._get_status_display_info = MagicMock(return_value=("🟢", "green", "Running"))
        app.print_header = MagicMock()
        app.print_section = MagicMock()
        app.print_colored = MagicMock()

        app._display_node_info_details({
            "node-1": {
                "status": "success",
                "data": {
                    "alias": "node-alpha",
                    "eth_address": "0x123",
                    "address": "addr-1",
                },
            }
        })

        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("Target Service Template Version: v5", rendered_text)
        self.assertIn("Service File Version: v3 (update recommended)", rendered_text)
        self.assertIn("alias: node-alpha", rendered_text)
        matching_calls = [call for call in app.print_colored.call_args_list if "Service File Version: v3" in call.args[0]]
        self.assertTrue(matching_calls)
        self.assertEqual(matching_calls[0].args[1], "red")

    def test_combined_status_and_info_shows_inline_details(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            }
                        }
                    }
                }
            }
        }
        app.get_mnl_app_env = MagicMock(return_value="mainnet")
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(return_value="v1")
        app._get_real_time_node_status = MagicMock(return_value={"node-1": {"status": "running"}})
        app._update_node_status = MagicMock()
        app._get_node_status_info = MagicMock(return_value={"status": "running", "last_update": "2026-03-17T00:00:00"})
        app._format_timestamp_ago = MagicMock(return_value="15 minute(s) ago")
        app.settings_manager = MagicMock()
        app.settings_manager.connection_timeout = 30
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app._load_active_config = MagicMock()
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.get_input = MagicMock(return_value="n")
        app.wait_for_enter = MagicMock()

        app.combined_node_status_and_info()

        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("service v1 / target v2 [UPDATE]", rendered_text)
        self.assertIn("last update 15 minute(s) ago | ssh auth unknown", rendered_text)

    def test_combined_status_and_info_shows_outdated_service_actions(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            }
                        }
                    }
                }
            }
        }
        app.get_mnl_app_env = MagicMock(return_value="mainnet")
        app.get_mnl_service_version = MagicMock(return_value="v3")
        app.get_host_service_file_version = MagicMock(return_value="v1")
        app._get_real_time_node_status = MagicMock(return_value={"node-1": {"status": "running"}})
        app._update_node_status = MagicMock()
        app._get_node_status_info = MagicMock(return_value={"status": "running", "last_update": "2026-03-17T00:00:00"})
        app._format_timestamp_ago = MagicMock(return_value="15 minute(s) ago")
        app.settings_manager = MagicMock()
        app.settings_manager.connection_timeout = 30
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app._load_active_config = MagicMock()
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.get_input = MagicMock(return_value="n")
        app.wait_for_enter = MagicMock()

        app.combined_node_status_and_info()

        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("Update service for: node-1", rendered_text)
        self.assertIn("Operations Menu -> Update Service File", rendered_text)

    def test_combined_status_and_info_can_open_detailed_view_after_short_info(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            }
                        }
                    }
                }
            }
        }
        app.get_mnl_app_env = MagicMock(return_value="mainnet")
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(return_value="v1")
        app._get_real_time_node_status = MagicMock(return_value={"node-1": {"status": "running"}})
        app._update_node_status = MagicMock()
        app._get_node_status_info = MagicMock(return_value={"status": "running", "last_update": "2026-03-17T00:00:00"})
        app._format_timestamp_ago = MagicMock(return_value="15 minute(s) ago")
        app.settings_manager = MagicMock()
        app.settings_manager.connection_timeout = 30
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app._load_active_config = MagicMock()
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.get_input = MagicMock(return_value="y")
        app._fetch_node_info_results = MagicMock(return_value={"node-1": {"status": "success", "data": {}}})
        app._display_node_info_details = MagicMock()
        app.wait_for_enter = MagicMock()

        app.combined_node_status_and_info()

        app._fetch_node_info_results.assert_called_once_with("Retrieving detailed per-node info...")
        app._display_node_info_details.assert_called_once()


class TestServiceFileUpdateFlow(unittest.TestCase):
    """Tests the operator-facing service file update workflow."""

    def test_update_service_file_preselects_outdated_nodes(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v1",
                            },
                            "node-2": {
                                "ansible_host": "10.0.0.2",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v3",
                            },
                        }
                    }
                }
            }
        }
        app.get_mnl_service_version = MagicMock(return_value="v3")
        app.get_host_service_file_version = MagicMock(
            side_effect=lambda config: config.get(r1setup.SERVICE_FILE_VERSION_FIELD, "v0")
        )
        app._get_node_status_info = MagicMock(return_value={"status": "running"})
        app._get_service_overrides = MagicMock(return_value={})
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.select_hosts = MagicMock(return_value=["node-1"])
        app.get_input = MagicMock(return_value="y")
        app._apply_service_template_to_hosts = MagicMock(return_value=True)
        app.wait_for_enter = MagicMock()

        app.update_service_file()

        app.select_hosts.assert_called_once()
        self.assertEqual(app.select_hosts.call_args.kwargs["initial_selection"], {"node-1"})
        self.assertEqual(
            app.select_hosts.call_args.kwargs["preselection_label"],
            "nodes that need a service update",
        )
        app._apply_service_template_to_hosts.assert_called_once_with(
            ["node-1"],
            overrides=None,
            last_applied_action="update_service_file",
            progress_message="Applying service file update...",
            success_message="Service file update applied on 1 node(s).",
            failure_message="Service file update encountered errors. Check the output above.",
        )

    def test_update_service_file_all_current_can_cancel_before_selection(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v3",
                            }
                        }
                    }
                }
            }
        }
        app.get_mnl_service_version = MagicMock(return_value="v3")
        app.get_host_service_file_version = MagicMock(
            side_effect=lambda config: config.get(r1setup.SERVICE_FILE_VERSION_FIELD, "v0")
        )
        app._get_node_status_info = MagicMock(return_value={"status": "running"})
        app._get_service_overrides = MagicMock(return_value={})
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.get_input = MagicMock(return_value="n")
        app.select_hosts = MagicMock()
        app._apply_service_template_to_hosts = MagicMock()
        app.wait_for_enter = MagicMock()

        app.update_service_file()

        app.select_hosts.assert_not_called()
        app._apply_service_template_to_hosts.assert_not_called()
        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("All nodes already have the current service file version.", rendered_text)

    def test_update_service_file_skips_undeployed_nodes(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v1",
                            },
                            "node-2": {
                                "ansible_host": "10.0.0.2",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v0",
                            },
                        }
                    }
                }
            }
        }
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(
            side_effect=lambda config: config.get(r1setup.SERVICE_FILE_VERSION_FIELD, "v0")
        )
        app._get_node_status_info = MagicMock(side_effect=[
            {"status": "running"},
            {"status": "never_deployed"},
        ])
        app._get_service_overrides = MagicMock(return_value={})
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.select_hosts = MagicMock(return_value=["node-1"])
        app.get_input = MagicMock(return_value="y")
        app._apply_service_template_to_hosts = MagicMock(return_value=True)
        app.wait_for_enter = MagicMock()

        app.update_service_file()

        eligible_hosts = app.select_hosts.call_args.args[0]
        self.assertEqual(set(eligible_hosts.keys()), {"node-1"})
        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("Skipping nodes without a deployed service: node-2", rendered_text)


class TestStartupServiceUpdatePrompt(unittest.TestCase):
    """Tests startup guidance for outdated service files."""

    def test_offer_startup_service_update_applies_outdated_nodes_when_confirmed(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v1",
                            },
                            "node-2": {
                                "ansible_host": "10.0.0.2",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v2",
                            },
                        }
                    }
                }
            }
        }
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(
            side_effect=lambda config: config.get(r1setup.SERVICE_FILE_VERSION_FIELD, "v0")
        )
        app._get_node_status_info = MagicMock(side_effect=[
            {"status": "running"},
            {"status": "running"},
        ])
        app._get_service_overrides = MagicMock(return_value={})
        app.print_colored = MagicMock()
        app.get_input = MagicMock(return_value="y")
        app._apply_service_template_to_hosts = MagicMock(return_value=True)
        app.wait_for_enter = MagicMock()

        app._offer_startup_service_update()

        app._apply_service_template_to_hosts.assert_called_once_with(
            ["node-1"],
            overrides=None,
            last_applied_action="update_service_file",
            progress_message="Applying service file update...",
            success_message="Service file update applied on 1 node(s).",
            failure_message="Service file update encountered errors. Check the output above.",
        )
        app.wait_for_enter.assert_called_once()
        first_prompt = app.get_input.call_args_list[0]
        self.assertEqual(first_prompt.args[0], "Update outdated service files now? (Y/n)")
        self.assertEqual(first_prompt.args[1], "Y")

    def test_offer_startup_service_update_can_skip_after_second_confirmation(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v1",
                            }
                        }
                    }
                }
            }
        }
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(
            side_effect=lambda config: config.get(r1setup.SERVICE_FILE_VERSION_FIELD, "v0")
        )
        app._get_node_status_info = MagicMock(return_value={"status": "running"})
        app._get_service_overrides = MagicMock(return_value={})
        app.print_colored = MagicMock()
        app.get_input = MagicMock(side_effect=["n", "y"])
        app._apply_service_template_to_hosts = MagicMock()
        app.wait_for_enter = MagicMock()

        app._offer_startup_service_update()

        self.assertEqual(app.get_input.call_count, 2)
        self.assertEqual(
            app.get_input.call_args_list[1].args[0],
            "Service updates are recommended to keep nodes aligned. Skip for now anyway? (y/N)",
        )
        app._apply_service_template_to_hosts.assert_not_called()
        app.wait_for_enter.assert_not_called()

    def test_offer_startup_service_update_proceeds_when_skip_not_confirmed(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v1",
                            }
                        }
                    }
                }
            }
        }
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(
            side_effect=lambda config: config.get(r1setup.SERVICE_FILE_VERSION_FIELD, "v0")
        )
        app._get_node_status_info = MagicMock(return_value={"status": "running"})
        app._get_service_overrides = MagicMock(return_value={})
        app.print_colored = MagicMock()
        app.get_input = MagicMock(side_effect=["n", "n"])
        app._apply_service_template_to_hosts = MagicMock(return_value=True)
        app.wait_for_enter = MagicMock()

        app._offer_startup_service_update()

        app._apply_service_template_to_hosts.assert_called_once()
        app.wait_for_enter.assert_called_once()

    def test_offer_startup_service_update_skips_when_no_eligible_drift(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.load_configuration = MagicMock()
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "v0",
                            }
                        }
                    }
                }
            }
        }
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(
            side_effect=lambda config: config.get(r1setup.SERVICE_FILE_VERSION_FIELD, "v0")
        )
        app._get_node_status_info = MagicMock(return_value={"status": "never_deployed"})
        app._get_service_overrides = MagicMock(return_value={})
        app.print_colored = MagicMock()
        app.get_input = MagicMock()
        app._apply_service_template_to_hosts = MagicMock()

        app._offer_startup_service_update()

        app.get_input.assert_not_called()
        app._apply_service_template_to_hosts.assert_not_called()


class TestSuggestedActions(unittest.TestCase):
    """Tests main-menu suggested actions."""

    def test_suggested_action_prefers_service_update_when_versions_drift(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {r1setup.SERVICE_FILE_VERSION_FIELD: "v1"},
                        }
                    }
                }
            }
        }
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(return_value="v1")
        app._get_node_status_info = MagicMock(return_value={"status": "running"})

        default_option, hint = app._get_suggested_action()

        self.assertEqual(default_option, "3")
        self.assertIn("Update service file on 1 node(s)", hint)


class TestRuntimeMetadataHelpers(unittest.TestCase):
    """Tests CLI helpers that attach runtime metadata to ansible commands."""

    def test_get_collection_version_reads_galaxy_yml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = MagicMock()
            app.config_dir = Path(temp_dir)
            app.print_debug = MagicMock()
            (Path(temp_dir) / "galaxy.yml").write_text('version: "1.3.30"\n')

            cm = r1setup.ConfigurationManager(app)

            self.assertEqual(cm.get_collection_version(), "1.3.30")

    def test_build_runtime_metadata_extra_vars_merges_existing_payload(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.get_collection_version = MagicMock(return_value="1.3.30")

        payload = app._build_runtime_metadata_extra_vars("customize_service", {"skip_gpu": True})

        self.assertEqual(payload["skip_gpu"], True)
        self.assertEqual(payload["r1setup_collection_version"], "1.3.30")
        self.assertEqual(payload["r1setup_last_applied_action"], "customize_service")
        self.assertEqual(payload["r1setup_cli_version"], r1setup.CLI_VERSION)

    def test_get_collection_version_prefers_version_manager_result(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.version_manager = MagicMock()
        app.version_manager._get_current_collection_version.return_value = "1.3.34"
        app.config_manager = MagicMock()
        app.config_manager.get_collection_version.return_value = "unknown"
        app.print_debug = MagicMock()

        self.assertEqual(app.get_collection_version(), "1.3.34")
        app.config_manager.get_collection_version.assert_not_called()


class TestActiveConfigurationRecovery(unittest.TestCase):
    """Tests automatic restoration of the previously active configuration."""

    def test_restore_active_configuration_if_possible_relinks_previous_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = r1setup.R1Setup.__new__(r1setup.R1Setup)
            app.configs_dir = Path(temp_dir) / "configs"
            app.configs_dir.mkdir(parents=True, exist_ok=True)
            (app.configs_dir / "prod.yml").write_text("all:\n  children:\n    gpu_nodes:\n      hosts: {}\n")
            app._load_active_config = MagicMock()
            app.config_manager = MagicMock()
            app.config_manager.active_config = {"config_name": "prod"}
            app._load_config_by_name = MagicMock(return_value=True)
            app.print_colored = MagicMock()
            app.print_debug = MagicMock()

            restored = app._restore_active_configuration_if_possible()

            self.assertTrue(restored)
            app._load_config_by_name.assert_called_once_with("prod")
            app.print_colored.assert_called_once_with("Restored active configuration: prod", 'green')

    def test_ensure_active_configuration_restores_before_prompting(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(side_effect=[False, True])
        app._restore_active_configuration_if_possible = MagicMock(return_value=True)
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app._list_available_configs = MagicMock()

        ensured = app.ensure_active_configuration()

        self.assertTrue(ensured)
        app._restore_active_configuration_if_possible.assert_called_once()
        app.print_header.assert_not_called()

    def test_restore_active_configuration_if_possible_returns_false_when_saved_config_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = r1setup.R1Setup.__new__(r1setup.R1Setup)
            app.configs_dir = Path(temp_dir) / "configs"
            app.configs_dir.mkdir(parents=True, exist_ok=True)
            app._load_active_config = MagicMock()
            app.config_manager = MagicMock()
            app.config_manager.active_config = {"config_name": "prod"}
            app._load_config_by_name = MagicMock()
            app.print_colored = MagicMock()
            app.print_debug = MagicMock()

            restored = app._restore_active_configuration_if_possible()

            self.assertFalse(restored)
            app._load_config_by_name.assert_not_called()
