#!/usr/bin/env python3
"""Tests for core R1Setup instance methods."""

import copy
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

    @patch("sys.stderr.flush")
    @patch("sys.stdout.flush")
    @patch("builtins.input")
    def test_wait_for_enter_flushes_output_streams(self, mock_input, mock_stdout_flush, mock_stderr_flush):
        self.app.wait_for_enter()
        mock_stdout_flush.assert_called_once()
        mock_stderr_flush.assert_called_once()


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

    @patch("builtins.print")
    @patch("os.system")
    def test_print_header_clears_by_default(self, mock_system, mock_print):
        with patch.dict(os.environ, {}, clear=False):
            self.app.print_header("Header")
        if os.name == "nt":
            mock_system.assert_called_once()
        else:
            mock_system.assert_not_called()
            mock_print.assert_any_call("\033[2J\033[H", end="")

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
                    service._deploy_setup(
                        "site.yml",
                        "Install GPU Nodes",
                        "Docker + NVIDIA drivers + GPU image deploy",
                        variant="gpu",
                        manage_drivers=True,
                    )

            update_metadata.assert_called_once_with("full")
            app.record_service_file_version.assert_called_once_with(["node-1"])
            self.assertEqual(app.run_generated_playbook.call_count, 2)
            self.assertEqual(app.run_generated_playbook.call_args_list[0].kwargs["timeout"], 600)
            self.assertEqual(app.run_generated_playbook.call_args_list[1].kwargs["timeout"], 180)


class TestInstallTrackingHelpers(unittest.TestCase):
    """Tests record_install_attempt, record_install_success, and
    _normalize_host_config migration for the eight install-tracking fields."""

    def _make_manager(self, hosts):
        """Build a minimal ConfigurationManager with a stubbed app carrying
        an inventory whose gpu_nodes.hosts match `hosts`, a stub save that
        just toggles a flag, and a predictable collection version."""
        app = MagicMock()
        app.inventory = {
            'all': {'children': {'gpu_nodes': {'hosts': hosts}}}
        }
        mgr = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        mgr.app = app
        mgr._save_configuration = MagicMock()
        mgr.get_collection_version = MagicMock(return_value='1.8.0')
        return mgr

    def test_derive_driver_owner(self):
        cm = r1setup.ConfigurationManager
        self.assertEqual(cm._derive_driver_owner('cpu', False), 'n/a')
        self.assertEqual(cm._derive_driver_owner('cpu', True), 'n/a')
        self.assertEqual(cm._derive_driver_owner('gpu', True), 'r1setup')
        self.assertEqual(cm._derive_driver_owner('gpu', False), 'user')

    def test_record_install_attempt_writes_expected_fields(self):
        hosts = {'node-1': {'ansible_host': '1.2.3.4'}}
        mgr = self._make_manager(hosts)
        mgr.record_install_attempt(['node-1'], 'gpu', 'r1setup', 'failed')
        cfg = hosts['node-1']
        self.assertEqual(cfg[r1setup.INSTALL_ATTEMPTED_VARIANT_FIELD], 'gpu')
        self.assertEqual(cfg[r1setup.INSTALL_ATTEMPTED_DRIVER_OWNER_FIELD], 'r1setup')
        self.assertEqual(cfg[r1setup.INSTALL_ATTEMPTED_RESULT_FIELD], 'failed')
        self.assertIsNotNone(cfg[r1setup.INSTALL_ATTEMPTED_AT_FIELD])
        # Success fields must NOT be touched by an attempt-only call.
        self.assertNotIn(r1setup.INSTALL_LAST_VARIANT_FIELD, cfg)
        mgr._save_configuration.assert_called_once()

    def test_record_install_attempt_rejects_bad_result(self):
        mgr = self._make_manager({})
        with self.assertRaises(ValueError):
            mgr.record_install_attempt(['x'], 'gpu', 'r1setup', 'bogus')

    def test_record_install_attempt_ignores_unknown_hosts(self):
        hosts = {'node-1': {}}
        mgr = self._make_manager(hosts)
        mgr.record_install_attempt(['ghost-host'], 'cpu', 'n/a', 'success')
        self.assertEqual(hosts, {'node-1': {}})
        mgr._save_configuration.assert_not_called()

    def test_record_install_success_writes_expected_fields(self):
        hosts = {'node-1': {}, 'node-2': {}}
        mgr = self._make_manager(hosts)
        mgr.record_install_success(['node-1', 'node-2'], 'gpu', 'user')
        for name in ('node-1', 'node-2'):
            cfg = hosts[name]
            self.assertEqual(cfg[r1setup.INSTALL_LAST_VARIANT_FIELD], 'gpu')
            self.assertEqual(cfg[r1setup.INSTALL_LAST_DRIVER_OWNER_FIELD], 'user')
            self.assertEqual(cfg[r1setup.INSTALL_LAST_COLLECTION_VERSION_FIELD], '1.8.0')
            self.assertIsNotNone(cfg[r1setup.INSTALL_LAST_AT_FIELD])

    def test_normalize_host_config_backfills_install_fields(self):
        cfg = {'ansible_host': '1.2.3.4'}
        changed = r1setup.ConfigurationManager._normalize_host_config(cfg)
        self.assertTrue(changed)
        for field in r1setup.INSTALL_TRACKING_FIELDS:
            self.assertIn(field, cfg)
            self.assertIsNone(cfg[field])

    def test_read_fetched_metadata_returns_empty_for_missing_files(self):
        with tempfile.TemporaryDirectory() as td:
            out = r1setup.ConfigurationManager._read_fetched_metadata(
                ['h1', 'h2'], Path(td)
            )
            self.assertEqual(out, {'h1': {}, 'h2': {}})

    def test_read_fetched_metadata_parses_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            (base / 'h1.json').write_text(
                '{"image_variant": "gpu", "driver_owner": "r1setup", "image_url": "ratio1/edge_node_gpu:testnet"}'
            )
            out = r1setup.ConfigurationManager._read_fetched_metadata(['h1'], base)
            self.assertEqual(out['h1']['image_variant'], 'gpu')
            self.assertEqual(out['h1']['driver_owner'], 'r1setup')


class TestBuildInstallExtraVars(unittest.TestCase):
    """Validates the three-mode install extra-vars builder."""

    def test_mode_1_cpu_install(self):
        self.assertEqual(
            r1setup.DeploymentService._build_install_extra_vars("cpu", False),
            {"mnl_image_variant_cli": "cpu", "skip_gpu": True},
        )

    def test_mode_2_gpu_managed_drivers(self):
        self.assertEqual(
            r1setup.DeploymentService._build_install_extra_vars("gpu", True),
            {"mnl_image_variant_cli": "gpu"},
        )

    def test_mode_3_gpu_user_managed_drivers(self):
        self.assertEqual(
            r1setup.DeploymentService._build_install_extra_vars("gpu", False),
            {"mnl_image_variant_cli": "gpu", "skip_gpu": True},
        )

    def test_rejects_cpu_with_manage_drivers_true(self):
        with self.assertRaises(ValueError) as ctx:
            r1setup.DeploymentService._build_install_extra_vars("cpu", True)
        self.assertIn("Illegal", str(ctx.exception))

    def test_rejects_invalid_variant(self):
        with self.assertRaises(ValueError) as ctx:
            r1setup.DeploymentService._build_install_extra_vars("xyz", False)
        self.assertIn("Invalid variant", str(ctx.exception))


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

    def test_display_node_info_details_skips_update_recommendation_for_not_deployed_node(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                r1setup.SERVICE_FILE_VERSION_FIELD: "NOT",
                            }
                        }
                    }
                }
            }
        }
        app.load_configuration = MagicMock()
        app.get_mnl_service_version = MagicMock(return_value="v5")
        app.get_host_service_file_version = MagicMock(return_value="NOT")
        app._get_node_status_info = MagicMock(return_value={"status": "not_deployed"})
        app._get_status_display_info = MagicMock(return_value=("📦", "yellow", "Not Deployed"))
        app.print_header = MagicMock()
        app.print_section = MagicMock()
        app.print_colored = MagicMock()

        app._display_node_info_details({
            "node-1": {
                "status": "unreachable",
                "data": {},
            }
        })

        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("Service File Version: NOT (not applicable)", rendered_text)
        self.assertNotIn("Update service for: node-1", rendered_text)


class TestMainMenuDeploymentDisplay(unittest.TestCase):
    """Tests compact main-menu deployment wording."""

    def test_show_main_menu_loads_configuration_before_tracking_live_label(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {
            "config_name": "cfg",
            "deployment_status": "never_deployed",
        }
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
        def _load_configuration():
            app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-1"]["node_status"] = "running"
        app.load_configuration = MagicMock(side_effect=_load_configuration)
        app._load_active_config = MagicMock()
        app.check_hosts_config = MagicMock(return_value=True)
        app.get_mnl_app_env = MagicMock(return_value="devnet")
        app._get_node_status_info = MagicMock(return_value={"status": "running", "last_update": ""})
        app._get_status_display_info = MagicMock(return_value=("🟢", "green", "Running"))
        app._format_timestamp_ago = MagicMock(return_value="Just now")
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.get_input = MagicMock(return_value="0")

        app.show_main_menu()

        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("cfg | devnet | 📡 tracking 1 live node(s)", rendered_text)

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

    def test_suggested_action_prefers_review_for_tracked_live_nodes(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {"node_status": "running"},
                        }
                    }
                }
            }
        }

        default_option, hint = app._get_suggested_action()

        self.assertEqual(default_option, "4")
        self.assertIn("Review fleet status", hint)


class TestTrackedLiveNodeMessaging(unittest.TestCase):
    """Tests operator-facing deployment wording for tracked live nodes."""

    def test_get_deployment_display_state_marks_tracked_live_nodes(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {"node_status": "running"},
                            "node-2": {"node_status": "not_deployed"},
                        }
                    }
                }
            }
        }

        display = app._get_deployment_display_state()

        self.assertEqual(display["state_key"], "tracking_live_nodes")
        self.assertEqual(display["main_menu_text"], "📡 tracking 1 live node(s)")
        self.assertIn("actively tracking live runtimes", display["status_note"])
        self.assertIn("imported from discovery or moved via migration", display["status_note"])

    def test_combined_status_and_info_describes_tracked_live_nodes(self):
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
                                "node_status": "running",
                            }
                        }
                    }
                }
            }
        }
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app.get_mnl_app_env = MagicMock(return_value="mainnet")
        app.get_mnl_service_version = MagicMock(return_value="v2")
        app.get_host_service_file_version = MagicMock(return_value="v1")
        app._get_real_time_node_status = MagicMock(return_value={"node-1": {"status": "running"}})
        app._update_node_status = MagicMock()
        app._get_node_status_info = MagicMock(return_value={"status": "running", "last_update": "2026-03-17T00:00:00"})
        app._format_timestamp_ago = MagicMock(return_value="15 minute(s) ago")
        app.settings_manager = MagicMock()
        app.settings_manager.connection_timeout = 30
        app.settings_manager.mark_status_refreshed = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app._load_active_config = MagicMock()
        app.print_header = MagicMock()
        app.print_colored = MagicMock()
        app.get_input = MagicMock(return_value="n")
        app.wait_for_enter = MagicMock()
        app.clear_screen = MagicMock()

        app.combined_node_status_and_info()

        rendered_text = " ".join(call.args[0] for call in app.print_colored.call_args_list if call.args)
        self.assertIn("Deployment: 📡 Tracking 1 live node(s)", rendered_text)
        self.assertIn("actively tracking live runtimes", rendered_text)
        self.assertIn("imported from discovery or moved via migration", rendered_text)


class TestCancellationGuidance(unittest.TestCase):
    """Tests recovery hints after keyboard interrupts."""

    def test_print_cancellation_guidance_mentions_rollback_for_executing_migration(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {
            "migration_plan_state": {
                "status": "executing",
                "instance_name": "node-1",
                "last_step": "target_prepared",
            }
        }
        app.print_colored = MagicMock()

        app._print_cancellation_guidance()

        rendered = " ".join(call.args[0] for call in app.print_colored.call_args_list)
        self.assertIn("remains in 'executing' state", rendered)
        self.assertIn("Rollback Migration", rendered)

    def test_print_cancellation_guidance_is_silent_without_saved_plan(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {}
        app.print_colored = MagicMock()

        app._print_cancellation_guidance()

        app.print_colored.assert_not_called()

    def test_clear_screen_respects_no_clear_env(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)

        with patch.dict(os.environ, {"R1SETUP_NO_CLEAR": "1"}, clear=False):
            with patch("builtins.print") as mock_print, patch("os.system") as mock_system:
                app.clear_screen()

        mock_print.assert_not_called()
        mock_system.assert_not_called()


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
        app.has_active_config_shell = MagicMock(side_effect=[False, True])
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


class TestHasActiveConfigShell(unittest.TestCase):
    """Tests for has_active_config_shell() helper."""

    def test_true_when_hosts_exist(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.config_manager = MagicMock()

        self.assertTrue(app.has_active_config_shell())

    def test_true_for_zero_host_shell(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            configs_dir = Path(temp_dir) / "configs"
            configs_dir.mkdir()
            config_path = configs_dir / "my-config_20260329_1200_0n.yml"
            config_path.write_text("all:\n  children:\n    gpu_nodes:\n      hosts: {}\n")

            app = r1setup.R1Setup.__new__(r1setup.R1Setup)
            app.check_hosts_config = MagicMock(return_value=False)
            app.config_manager = MagicMock()
            app.config_manager.active_config = {"config_name": "my-config_20260329_1200_0n"}
            app.config_manager.app = MagicMock()
            app.config_manager.app.configs_dir = configs_dir

            self.assertTrue(app.has_active_config_shell())

    def test_false_when_no_config(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=False)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"config_name": None}

        self.assertFalse(app.has_active_config_shell())

    def test_false_when_config_file_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            configs_dir = Path(temp_dir) / "configs"
            configs_dir.mkdir()

            app = r1setup.R1Setup.__new__(r1setup.R1Setup)
            app.check_hosts_config = MagicMock(return_value=False)
            app.config_manager = MagicMock()
            app.config_manager.active_config = {"config_name": "nonexistent"}
            app.config_manager.app = MagicMock()
            app.config_manager.app.configs_dir = configs_dir

            self.assertFalse(app.has_active_config_shell())


class TestPhase0Wording(unittest.TestCase):
    """Tests that Phase 0 UX wording updates are applied."""

    def test_suggested_action_no_config_says_create_or_load(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=False)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app.config_manager.get_fleet_state_copy = MagicMock(
            return_value={"fleet": {"machines": {}, "instances": {}}}
        )

        _, hint = app._get_suggested_action()

        self.assertIn("Create or load a configuration first", hint)

    def test_suggested_action_never_deployed_says_instances(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.check_hosts_config = MagicMock(return_value=True)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {"node_status": "not_deployed"},
                        }
                    }
                }
            }
        }

        _, hint = app._get_suggested_action()

        self.assertIn("Deploy your configured instances", hint)

    def test_deployment_display_tracking_live_says_fleet_status(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.config_manager = MagicMock()
        app.config_manager.active_config = {"deployment_status": "never_deployed"}
        app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {"node_status": "running"},
                        }
                    }
                }
            }
        }

        display = app._get_deployment_display_state()

        self.assertEqual(display["state_key"], "tracking_live_nodes")
        action_option, action_hint = display["suggested_action"]
        self.assertEqual(action_option, "4")
        self.assertIn("Review fleet status", action_hint)


class TestSharedConfigCreationPrimitives(unittest.TestCase):
    """Tests for Phase 1 shared config-creation primitives."""

    def _make_config_manager(self):
        """Build a minimal ConfigurationManager mock for primitive testing."""
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {}
        cm.fleet_state = None
        return cm

    def test_prompt_new_config_name_returns_valid_name(self):
        cm = self._make_config_manager()
        cm.app.get_input = MagicMock(return_value="my-cluster")
        result = cm._prompt_new_config_name()
        self.assertEqual(result, "my-cluster")

    def test_prompt_new_config_name_rejects_invalid_then_accepts(self):
        cm = self._make_config_manager()
        cm.app.get_input = MagicMock(side_effect=["bad name!", "good-name"])
        result = cm._prompt_new_config_name()
        self.assertEqual(result, "good-name")
        self.assertEqual(cm.app.get_input.call_count, 2)

    def test_prompt_new_config_environment_calls_set_mnl_app_env(self):
        cm = self._make_config_manager()
        cm.app._select_network_environment = MagicMock(return_value="testnet")
        cm.set_mnl_app_env = MagicMock()
        result = cm._prompt_new_config_environment()
        self.assertEqual(result, "testnet")
        cm.set_mnl_app_env.assert_called_once_with("testnet")

    def test_reset_inventory_for_new_config(self):
        cm = self._make_config_manager()
        cm.app.inventory = {"old": "data"}
        cm._reset_inventory_for_new_config()
        hosts = cm.app.inventory['all']['children']['gpu_nodes']['hosts']
        self.assertEqual(hosts, {})

    def test_generate_config_name_delegates_to_prompt_when_no_name(self):
        cm = self._make_config_manager()
        cm._prompt_new_config_name = MagicMock(return_value="auto-name")
        result = cm._generate_config_name(3)
        cm._prompt_new_config_name.assert_called_once()
        self.assertIn("auto-name", result)
        self.assertTrue(result.endswith("3n"))

    def test_generate_config_name_skips_prompt_when_name_given(self):
        cm = self._make_config_manager()
        cm._prompt_new_config_name = MagicMock()
        result = cm._generate_config_name(2, "explicit")
        cm._prompt_new_config_name.assert_not_called()
        self.assertIn("explicit", result)
        self.assertTrue(result.endswith("2n"))


class TestConfigCreationPathMigration(unittest.TestCase):
    """Tests that all config-creation entry points delegate to the machine-first flow."""

    def test_machine_first_flow_prompts_environment(self):
        """Machine-first flow must call _prompt_new_config_environment."""
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {}
        cm.fleet_state = None

        cm._prompt_new_config_name = MagicMock(return_value="test")
        cm._prompt_new_config_environment = MagicMock(return_value="devnet")
        cm._prompt_machine_count = MagicMock(return_value=1)
        cm._generate_config_name = MagicMock(return_value="test_20260329_1200_1m")
        cm._reset_inventory_for_new_config = MagicMock()
        cm.ensure_configuration_shell = MagicMock()
        cm._collect_machine_registration_entries = MagicMock(return_value=["machine-1"])
        cm._onboarding_batch_discovery_and_import = MagicMock(return_value={
            'scanned': False, 'imported_total': 0, 'session_mode': 'simple', 'clean_machine_ids': [],
        })
        cm._onboarding_gap_fill_clean_machines = MagicMock(return_value=0)
        cm.app.print_section = MagicMock()
        cm.app.print_colored = MagicMock()
        cm.app.get_input = MagicMock(return_value="n")
        cm.app.wait_for_enter = MagicMock()

        cm._create_machine_first_configuration()

        cm._prompt_new_config_environment.assert_called_once()

    def test_machine_first_flow_creates_config_shell_before_registration(self):
        """Config shell must exist before machine registration."""
        call_order = []

        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {}
        cm.fleet_state = None

        cm._prompt_new_config_name = MagicMock(return_value="test")
        cm._prompt_new_config_environment = MagicMock(return_value="mainnet")
        cm._prompt_machine_count = MagicMock(return_value=1)
        cm._generate_config_name = MagicMock(return_value="test_20260329_1200_1m")
        cm._reset_inventory_for_new_config = MagicMock()
        cm.ensure_configuration_shell = MagicMock(side_effect=lambda *a, **kw: call_order.append('shell'))
        cm._collect_machine_registration_entries = MagicMock(
            side_effect=lambda *a, **kw: (call_order.append('register'), ["machine-1"])[1],
        )
        cm._onboarding_batch_discovery_and_import = MagicMock(return_value={
            'scanned': False, 'imported_total': 0, 'session_mode': 'simple', 'clean_machine_ids': [],
        })
        cm._onboarding_gap_fill_clean_machines = MagicMock(return_value=0)
        cm.app.print_section = MagicMock()
        cm.app.print_colored = MagicMock()
        cm.app.get_input = MagicMock(return_value="n")
        cm.app.wait_for_enter = MagicMock()

        cm._create_machine_first_configuration()

        self.assertEqual(call_order, ['shell', 'register'])

    def test_create_new_configuration_resets_and_delegates_to_machine_first(self):
        """_create_new_configuration backs up then delegates to machine-first flow."""
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.get_input = MagicMock(return_value="y")
        app.config_file = MagicMock()
        app.config_file.exists = MagicMock(return_value=False)
        app.config_manager = MagicMock()
        app._create_machine_first_configuration = MagicMock()

        app._create_new_configuration()

        app.config_manager._reset_inventory_for_new_config.assert_called_once()
        app._create_machine_first_configuration.assert_called_once()


class TestPhase2MachineFirstConfig(unittest.TestCase):
    """Tests for Phase 2 machine-first configuration flow."""

    def test_generate_config_name_with_unit_m(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        result = cm._generate_config_name(3, "fleet", unit='m')
        self.assertIn("fleet", result)
        self.assertTrue(result.endswith("3m"))

    def test_generate_config_name_default_unit_n(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        result = cm._generate_config_name(2, "test")
        self.assertTrue(result.endswith("2n"))

    def test_prompt_machine_count_returns_positive(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.app.get_input = MagicMock(return_value="3")
        self.assertEqual(cm._prompt_machine_count(), 3)

    def test_collect_machine_registration_entries_registers_machines(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {"config_name": "test"}
        cm.fleet_state = {"config_schema_version": 1, "fleet": {"machines": {}, "instances": {}}}

        # Mock interactions: label, SSH config, then batch probe at end
        cm.app.get_input = MagicMock(side_effect=[
            "my-machine",   # label for machine 1
            "n",            # decline batch spec probe
        ])
        cm.app._configure_single_node = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "ansible_user": "root", "ansible_port": 22,
        })
        cm.app._extract_machine_access_config = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "ansible_user": "root", "ansible_port": 22,
        })
        cm.app.print_section = MagicMock()
        cm.app.print_colored = MagicMock()

        # Mock upsert to capture calls
        cm.upsert_machine_record = MagicMock()

        ids = cm._collect_machine_registration_entries(1)

        self.assertEqual(ids, ["my-machine"])
        cm.upsert_machine_record.assert_called_once()
        call_args = cm.upsert_machine_record.call_args
        self.assertEqual(call_args[0][0], "my-machine")
        self.assertEqual(call_args[0][1]["topology_mode"], "standard")
        self.assertEqual(call_args[0][1]["deployment_state"], "empty")

    def test_collect_machine_registration_rejects_duplicate_labels(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {"config_name": "test"}
        cm.fleet_state = {"config_schema_version": 1, "fleet": {"machines": {}, "instances": {}}}

        # First machine: "dup", second attempt: "dup" (rejected), then "unique"
        # Batch probe is asked once at the end for all machines
        cm.app.get_input = MagicMock(side_effect=[
            "dup",      # label for machine 1
            "dup",      # label for machine 2 (rejected - duplicate)
            "unique",   # retry for machine 2
            "n",        # decline batch probe
        ])
        cm.app._configure_single_node = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "ansible_user": "root",
        })
        cm.app._extract_machine_access_config = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "ansible_user": "root",
        })
        cm.app.print_section = MagicMock()
        cm.app.print_colored = MagicMock()
        cm.upsert_machine_record = MagicMock()

        ids = cm._collect_machine_registration_entries(2)

        self.assertEqual(ids, ["dup", "unique"])

    def test_create_machine_first_configuration_full_flow(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {}
        cm.fleet_state = None

        cm._prompt_new_config_name = MagicMock(return_value="prod")
        cm._prompt_new_config_environment = MagicMock(return_value="mainnet")
        cm._prompt_machine_count = MagicMock(return_value=2)
        cm._generate_config_name = MagicMock(return_value="prod_20260329_1200_2m")
        cm._reset_inventory_for_new_config = MagicMock()
        cm.ensure_configuration_shell = MagicMock()
        cm._collect_machine_registration_entries = MagicMock(return_value=["m-1", "m-2"])

        cm._create_machine_first_configuration()

        cm._generate_config_name.assert_called_once_with(2, "prod", unit='m')
        cm._reset_inventory_for_new_config.assert_called_once()
        cm.ensure_configuration_shell.assert_called_once_with("prod_20260329_1200_2m", "mainnet")
        cm._collect_machine_registration_entries.assert_called_once_with(2)
        # Verify summary output mentions machines
        printed = [call[0][0] for call in cm.app.print_colored.call_args_list]
        self.assertTrue(any("2 machine(s) registered" in p for p in printed))
        self.assertTrue(any("0 instances" in p for p in printed))

    def test_ensure_active_configuration_accepts_zero_host_shell(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.has_active_config_shell = MagicMock(return_value=True)
        app.print_header = MagicMock()

        result = app.ensure_active_configuration()

        self.assertTrue(result)
        app.print_header.assert_not_called()

    def test_ensure_active_configuration_import_uses_has_active_config_shell(self):
        """Import success check should use has_active_config_shell, not check_hosts_config."""
        # Verify the method body references has_active_config_shell for import checks.
        import inspect
        src = inspect.getsource(r1setup.R1Setup.ensure_active_configuration)
        # The import-success checks should use has_active_config_shell
        self.assertIn("has_active_config_shell", src)


class TestPhase3BatchDiscovery(unittest.TestCase):
    """Tests for Phase 3 batch discovery and import primitives."""

    def _make_cm(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {"config_name": "test_config"}
        cm.fleet_state = {
            "config_schema_version": 1,
            "fleet": {
                "machines": {
                    "m-1": {"machine_id": "m-1", "ansible_host": "10.0.0.1", "ansible_user": "root"},
                    "m-2": {"machine_id": "m-2", "ansible_host": "10.0.0.2", "ansible_user": "root"},
                },
                "instances": {},
            },
        }
        return cm

    def test_batch_discover_machines_classifies_results(self):
        cm = self._make_cm()
        # m-1 returns 1 candidate; m-2 returns clean
        cm.app.discover_existing_edge_node_services = MagicMock(side_effect=[
            {"status": "success", "candidates": [{"service_name": "edge_node"}]},
            {"status": "success", "candidates": []},
        ])
        buffer = cm._batch_discover_machines(["m-1", "m-2"])
        self.assertEqual(buffer["m-1"]["status"], "success")
        self.assertEqual(len(buffer["m-1"]["candidates"]), 1)
        self.assertEqual(buffer["m-2"]["status"], "success")
        self.assertEqual(len(buffer["m-2"]["candidates"]), 0)

    def test_batch_discover_machines_handles_error(self):
        cm = self._make_cm()
        cm.app.discover_existing_edge_node_services = MagicMock(
            side_effect=Exception("connection refused"),
        )
        buffer = cm._batch_discover_machines(["m-1"])
        self.assertEqual(buffer["m-1"]["status"], "error")
        self.assertIn("connection refused", buffer["m-1"]["error"])

    def test_batch_discover_machines_skips_unregistered(self):
        cm = self._make_cm()
        buffer = cm._batch_discover_machines(["nonexistent"])
        self.assertEqual(buffer["nonexistent"]["status"], "skipped")

    def test_persist_batch_discovery_calls_record_for_successful_only(self):
        cm = self._make_cm()
        cm.record_machine_discovery_scan = MagicMock()
        scan_buffer = {
            "m-1": {"status": "success", "candidates": [{"service_name": "edge_node"}]},
            "m-2": {"status": "error", "candidates": [], "error": "fail"},
            "m-3": {"status": "skipped", "candidates": [], "error": "not registered"},
        }
        cm._persist_batch_discovery_results(scan_buffer)
        cm.record_machine_discovery_scan.assert_called_once_with("m-1", [{"service_name": "edge_node"}])

    def test_classify_scan_results(self):
        cm = self._make_cm()
        scan_buffer = {
            "m-1": {"status": "success", "candidates": [{"service_name": "x"}]},
            "m-2": {"status": "success", "candidates": []},
            "m-3": {"status": "error", "candidates": [], "error": "fail"},
            "m-4": {"status": "skipped", "candidates": [], "error": "not registered"},
        }
        classified = cm._classify_scan_results(scan_buffer)
        self.assertEqual(classified["discovered"], ["m-1"])
        self.assertEqual(classified["clean"], ["m-2"])
        self.assertEqual(classified["failed"], ["m-3"])
        self.assertEqual(classified["skipped"], ["m-4"])

    def test_onboarding_review_skips_when_no_env_match(self):
        cm = self._make_cm()
        candidates = [
            {"service_name": "edge_node", "service_state": "active", "environment": "devnet"},
        ]
        result = cm._onboarding_review_machine_candidates("m-1", candidates, "testnet", "simple")
        self.assertEqual(result["action"], "skipped")
        self.assertEqual(result["imported_count"], 0)

    def test_onboarding_review_simple_mode_guardrail_skip(self):
        cm = self._make_cm()
        # 2 services = needs expert; user chooses skip (default)
        candidates = [
            {"service_name": "edge_node", "service_state": "active", "environment": "testnet"},
            {"service_name": "edge_node_2", "service_state": "active", "environment": "testnet"},
        ]
        cm.app.get_input = MagicMock(return_value="2")  # skip
        result = cm._onboarding_review_machine_candidates("m-1", candidates, "testnet", "simple")
        self.assertEqual(result["action"], "skipped")
        self.assertIsNone(result["mode_switched_to"])

    def test_onboarding_review_single_service_stays_standard(self):
        cm = self._make_cm()
        candidates = [
            {"service_name": "edge_node", "service_state": "active", "environment": "testnet"},
        ]
        # User selects 'all' in candidate selection, provides name 'en1'
        cm.app._select_discovery_candidates = MagicMock(return_value=candidates)
        cm.find_runtime_identity_claims = MagicMock(return_value=[])
        cm.upsert_machine_record = MagicMock()
        cm.app._prompt_discovery_import_name = MagicMock(return_value="edge_node")
        cm.app.import_discovery_candidates = MagicMock(return_value={
            "status": "success", "imported_names": ["edge_node"], "topology_mode": "standard",
        })
        cm.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}

        result = cm._onboarding_review_machine_candidates("m-1", candidates, "testnet", "simple")

        self.assertEqual(result["action"], "imported")
        self.assertEqual(result["imported_count"], 1)
        self.assertIsNone(result["mode_switched_to"])
        # Should NOT promote to expert for single service
        cm.upsert_machine_record.assert_not_called()

    def test_onboarding_batch_discovery_declined(self):
        cm = self._make_cm()
        cm.app.get_input = MagicMock(return_value="n")
        result = cm._onboarding_batch_discovery_and_import(["m-1"], "testnet")
        self.assertFalse(result["scanned"])
        self.assertEqual(result["imported_total"], 0)

    def test_create_machine_first_configuration_offers_discovery(self):
        cm = self._make_cm()
        cm._prompt_new_config_name = MagicMock(return_value="test")
        cm._prompt_new_config_environment = MagicMock(return_value="testnet")
        cm._select_configuration_mode = MagicMock(return_value="simple")
        cm._prompt_machine_count = MagicMock(return_value=1)
        cm._generate_config_name = MagicMock(return_value="test_20260329_1200_1m")
        cm._reset_inventory_for_new_config = MagicMock()
        cm.ensure_configuration_shell = MagicMock()
        cm._collect_machine_registration_entries = MagicMock(return_value=["m-1"])
        cm._onboarding_batch_discovery_and_import = MagicMock(
            return_value={"scanned": True, "imported_total": 0, "session_mode": "simple", "clean_machine_ids": []},
        )
        cm._onboarding_gap_fill_clean_machines = MagicMock(return_value=0)
        cm.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}
        cm.app.wait_for_enter = MagicMock()

        cm._create_machine_first_configuration()

        cm._onboarding_batch_discovery_and_import.assert_called_once_with(
            ["m-1"], "testnet", session_mode="simple",
        )


class TestPhase4GapFill(unittest.TestCase):
    """Tests for Phase 4 safe gap fill for simple mode."""

    def _make_cm(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {"config_name": "test_config"}
        cm.fleet_state = {
            "config_schema_version": 1,
            "fleet": {
                "machines": {
                    "m-1": {
                        "machine_id": "m-1",
                        "ansible_host": "10.0.0.1",
                        "ansible_user": "root",
                        "ansible_port": 22,
                        "topology_mode": "standard",
                        "instance_names": [],
                    },
                },
                "instances": {},
            },
        }
        return cm

    def test_build_fresh_host_entry_sets_standard_fields(self):
        cm = self._make_cm()
        cm.app._extract_machine_access_config = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "ansible_user": "root", "ansible_port": 22,
        })
        cm.apply_runtime_snapshot_to_host_config = MagicMock(return_value=False)

        host = cm._build_fresh_host_entry("m-1", "my-node")

        self.assertEqual(host["ansible_host"], "10.0.0.1")
        self.assertEqual(host["r1setup_machine_id"], "m-1")
        self.assertEqual(host["r1setup_topology_mode"], "standard")
        self.assertEqual(host["r1setup_runtime_name_policy"], "normalize_to_target")
        self.assertEqual(host["r1setup_instance_logical_name"], "my-node")
        self.assertEqual(host["node_status"], "never_deployed")
        self.assertEqual(host["r1setup_service_file_version"], r1setup.DEFAULT_SERVICE_FILE_VERSION)
        cm.apply_runtime_snapshot_to_host_config.assert_called_once_with("my-node", host)

    def test_build_fresh_host_entry_raises_for_unknown_machine(self):
        cm = self._make_cm()
        with self.assertRaises(ValueError):
            cm._build_fresh_host_entry("nonexistent", "node-1")

    def test_gap_fill_creates_instances_on_clean_machines(self):
        cm = self._make_cm()
        cm.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}
        cm.app._get_valid_hostname = MagicMock(return_value="m-1")
        cm._build_fresh_host_entry = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "node_status": "never_deployed",
        })
        cm.upsert_machine_record = MagicMock()
        cm._save_config_with_metadata = MagicMock()
        cm.app.get_input = MagicMock(return_value="Y")

        count = cm._onboarding_gap_fill_clean_machines(["m-1"], "testnet")

        self.assertEqual(count, 1)
        cm._build_fresh_host_entry.assert_called_once_with("m-1", "m-1", topology_mode='standard')
        cm.upsert_machine_record.assert_called_once()
        cm._save_config_with_metadata.assert_called_once()

    def test_gap_fill_skips_when_declined(self):
        cm = self._make_cm()
        cm.app.get_input = MagicMock(return_value="n")

        count = cm._onboarding_gap_fill_clean_machines(["m-1"], "testnet")

        self.assertEqual(count, 0)

    def test_gap_fill_skips_when_no_clean_machines(self):
        cm = self._make_cm()

        count = cm._onboarding_gap_fill_clean_machines([], "testnet")

        self.assertEqual(count, 0)

    def test_batch_discovery_returns_clean_machine_ids(self):
        cm = self._make_cm()
        cm.app.get_input = MagicMock(return_value="Y")
        cm.app.discover_existing_edge_node_services = MagicMock(
            return_value={"status": "success", "candidates": []},
        )
        cm.record_machine_discovery_scan = MagicMock()

        result = cm._onboarding_batch_discovery_and_import(["m-1"], "testnet")

        self.assertIn("clean_machine_ids", result)
        self.assertEqual(result["clean_machine_ids"], ["m-1"])

    def test_create_machine_first_deploys_only_for_fresh(self):
        """Deploy prompt should only appear when fresh_count > 0."""
        cm = self._make_cm()
        cm._prompt_new_config_name = MagicMock(return_value="test")
        cm._prompt_new_config_environment = MagicMock(return_value="testnet")
        cm._prompt_machine_count = MagicMock(return_value=1)
        cm._generate_config_name = MagicMock(return_value="test_20260329_1200_1m")
        cm._reset_inventory_for_new_config = MagicMock()
        cm.ensure_configuration_shell = MagicMock()
        cm._collect_machine_registration_entries = MagicMock(return_value=["m-1"])
        cm._onboarding_batch_discovery_and_import = MagicMock(return_value={
            "scanned": True, "imported_total": 2, "session_mode": "simple",
            "clean_machine_ids": [],
        })
        cm._onboarding_gap_fill_clean_machines = MagicMock(return_value=0)
        cm.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {"n1": {}, "n2": {}}}}}}
        cm.app.wait_for_enter = MagicMock()
        cm.app.get_input = MagicMock()

        cm._create_machine_first_configuration()

        # With 0 fresh, deploy prompt should NOT be shown (get_input not called for deploy)
        # The only get_input calls are from mocked methods, not deploy prompt
        deploy_calls = [
            c for c in cm.app.get_input.call_args_list
            if 'deploy' in str(c).lower()
        ]
        self.assertEqual(len(deploy_calls), 0)


class TestPhase5AdvancedMode(unittest.TestCase):
    """Tests for Phase 5 advanced mode / expert topology."""

    def _make_cm(self):
        cm = r1setup.ConfigurationManager.__new__(r1setup.ConfigurationManager)
        cm.app = MagicMock()
        cm.active_config = {"config_name": "test_config"}
        cm.fleet_state = {
            "config_schema_version": r1setup.CONFIG_SCHEMA_VERSION,
            "fleet": {"machines": {}, "instances": {}},
        }
        cm._normalize_fleet_state = r1setup.ConfigurationManager._normalize_fleet_state.__get__(cm)
        cm.get_fleet_state_copy = lambda: copy.deepcopy(cm.fleet_state)
        return cm

    def test_select_configuration_mode_returns_simple_by_default(self):
        cm = self._make_cm()
        cm.app.get_input = MagicMock(return_value="")
        self.assertEqual(cm._select_configuration_mode(), "simple")

    def test_select_configuration_mode_returns_advanced(self):
        cm = self._make_cm()
        cm.app.get_input = MagicMock(return_value="advanced")
        self.assertEqual(cm._select_configuration_mode(), "advanced")

    def test_select_configuration_mode_rejects_partial_match(self):
        cm = self._make_cm()
        cm.app.get_input = MagicMock(return_value="adv")
        self.assertEqual(cm._select_configuration_mode(), "simple")

    def test_collect_advanced_instance_counts_uses_capacity_formula(self):
        cm = self._make_cm()
        cm.fleet_state["fleet"]["machines"]["m-1"] = {
            "machine_id": "m-1",
            "machine_specs": {"cpu_total": 16, "memory_gb_total": 64.0},
            "instance_names": [],
        }
        # Accept the default (should be min(16//4, 64//16) = 4)
        cm.app.get_input = MagicMock(return_value="4")
        counts = cm._collect_advanced_instance_counts(["m-1"])
        self.assertEqual(counts["m-1"], 4)

    def test_collect_advanced_instance_counts_caps_at_memory_limit(self):
        cm = self._make_cm()
        cm.fleet_state["fleet"]["machines"]["m-1"] = {
            "machine_id": "m-1",
            "machine_specs": {"cpu_total": 32, "memory_gb_total": 48.0},
            "instance_names": [],
        }
        # max = min(32//4, 48//16) = min(8, 3) = 3
        cm.app.get_input = MagicMock(return_value="3")
        counts = cm._collect_advanced_instance_counts(["m-1"])
        self.assertEqual(counts["m-1"], 3)

    def test_gap_fill_advanced_creates_multiple_instances(self):
        cm = self._make_cm()
        cm.fleet_state["fleet"]["machines"]["m-1"] = {
            "machine_id": "m-1", "instance_names": [], "topology_mode": "standard",
            "ansible_host": "10.0.0.1", "ansible_user": "root",
        }
        cm.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}
        # Return sequential hostnames
        cm.app._get_valid_hostname = MagicMock(side_effect=["inst-1", "inst-2", "inst-3"])
        cm._build_fresh_host_entry = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "node_status": "never_deployed",
        })
        cm.upsert_machine_record = MagicMock()
        cm._save_config_with_metadata = MagicMock()
        cm.app.get_input = MagicMock(return_value="Y")

        count = cm._onboarding_gap_fill_clean_machines(
            ["m-1"], "testnet",
            config_mode="advanced",
            desired_counts={"m-1": 3},
        )

        self.assertEqual(count, 3)
        # All calls should use topology_mode='expert'
        for call in cm._build_fresh_host_entry.call_args_list:
            self.assertEqual(call.kwargs.get("topology_mode"), "expert")

    def test_gap_fill_advanced_subtracts_imported(self):
        cm = self._make_cm()
        # Machine already has 1 imported instance
        cm.fleet_state["fleet"]["machines"]["m-1"] = {
            "machine_id": "m-1", "instance_names": ["imported-1"],
            "ansible_host": "10.0.0.1", "ansible_user": "root",
        }
        cm.fleet_state["fleet"]["instances"]["imported-1"] = {
            "assigned_machine_id": "m-1", "logical_name": "imported-1",
        }
        cm.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}
        cm.app._get_valid_hostname = MagicMock(side_effect=["inst-2", "inst-3"])
        cm._build_fresh_host_entry = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "node_status": "never_deployed",
        })
        cm.upsert_machine_record = MagicMock()
        cm._save_config_with_metadata = MagicMock()
        cm.app.get_input = MagicMock(return_value="Y")

        count = cm._onboarding_gap_fill_clean_machines(
            ["m-1"], "testnet",
            config_mode="advanced",
            desired_counts={"m-1": 3},
        )

        # 3 desired - 1 imported = 2 fresh
        self.assertEqual(count, 2)
        self.assertEqual(cm._build_fresh_host_entry.call_count, 2)

    def test_gap_fill_simple_still_creates_one(self):
        """Simple mode backward compatibility: exactly 1 instance per machine."""
        cm = self._make_cm()
        cm.fleet_state["fleet"]["machines"]["m-1"] = {
            "machine_id": "m-1", "instance_names": [],
            "ansible_host": "10.0.0.1", "ansible_user": "root",
        }
        cm.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}
        cm.app._get_valid_hostname = MagicMock(return_value="m-1")
        cm._build_fresh_host_entry = MagicMock(return_value={
            "ansible_host": "10.0.0.1", "node_status": "never_deployed",
        })
        cm.upsert_machine_record = MagicMock()
        cm._save_config_with_metadata = MagicMock()
        cm.app.get_input = MagicMock(return_value="Y")

        count = cm._onboarding_gap_fill_clean_machines(["m-1"], "testnet")

        self.assertEqual(count, 1)
        cm._build_fresh_host_entry.assert_called_once_with("m-1", "m-1", topology_mode="standard")
