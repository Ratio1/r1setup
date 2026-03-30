#!/usr/bin/env python3
"""Tests for machine-spec probing and resource messaging."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.support import r1setup


class TestMachineSpecs(unittest.TestCase):
    """Focused tests for machine spec parsing and capacity messaging."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        self.app.settings_manager = MagicMock()
        self.app.settings_manager.connection_timeout = 30
        self.app.settings_manager.ssh_connect_timeout = 10

    def test_probe_machine_specs_parses_float_memory_gib(self):
        completed = MagicMock(returncode=0, stdout="host-a\n4\n15.6\n", stderr="")

        with patch.object(r1setup.subprocess, "run", return_value=completed):
            result = self.app._probe_machine_specs({
                "ansible_host": "10.0.0.1",
                "ansible_user": "root",
            })

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["cpu_total"], 4)
        self.assertEqual(result["memory_gb_total"], 15.6)

    def test_probe_machine_specs_rejects_implausible_memory_values(self):
        completed = MagicMock(returncode=0, stdout="host-a\n4\n20000\n", stderr="")

        with patch.object(r1setup.subprocess, "run", return_value=completed):
            result = self.app._probe_machine_specs({
                "ansible_host": "10.0.0.1",
                "ansible_user": "root",
            })

        self.assertEqual(result["status"], "error")
        self.assertIn("Unable to parse", result["message"])

    def test_format_machine_specs_summary_uses_gib_display(self):
        summary = r1setup.ConfigurationManager._format_machine_specs_summary({
            "cpu_total": 4,
            "memory_gb_total": 15.6,
        })

        self.assertEqual(summary, "4 CPU / 15.6 GiB RAM")

    def test_assess_machine_resource_recommendation_marks_near_boundary_as_tolerated(self):
        assessment = r1setup.ConfigurationManager.assess_machine_resource_recommendation({
            "cpu_total": 4,
            "memory_gb_total": 15.4,
        })

        self.assertEqual(assessment["status"], "tolerated_near_boundary")

    def test_assess_machine_resource_recommendation_marks_insufficient_multi_instance_capacity(self):
        assessment = r1setup.ConfigurationManager.assess_machine_resource_recommendation({
            "cpu_total": 4,
            "memory_gb_total": 15.6,
        }, planned_instances=2)

        self.assertEqual(assessment["status"], "below_recommendation")


class TestMachineRegistrationSpecMessaging(unittest.TestCase):
    """Tests registration messaging around probed machine specs."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_path = Path(self.temp_dir.name)

        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app.inventory = {
            "all": {
                "vars": {"mnl_app_env": "mainnet"},
                "children": {"gpu_nodes": {"hosts": {}}},
            }
        }
        app.config_dir = self.base_path
        app.configs_dir = self.base_path / "configs"
        app.configs_dir.mkdir(parents=True, exist_ok=True)
        app.config_file = self.base_path / "hosts.yml"
        app.vars_file = self.base_path / "group_vars" / "variables.yml"
        app.active_config_file = self.base_path / "active_config.json"
        app.print_colored = MagicMock()
        app.print_debug = MagicMock()
        app.wait_for_enter = MagicMock()
        app._extract_machine_access_config = MagicMock(return_value={
            "ansible_host": "10.0.0.2",
            "ansible_user": "root",
        })
        app._configure_single_node = MagicMock(return_value={
            "ansible_host": "10.0.0.2",
            "ansible_user": "root",
        })
        app._probe_machine_specs = MagicMock(return_value={
            "status": "success",
            "hostname": "host-b",
            "cpu_total": 4,
            "memory_gb_total": 15.6,
            "last_checked_at": "2026-03-20T00:00:00",
        })
        app.get_input = MagicMock(side_effect=["machine-b", "y", "n"])
        app.config_manager = r1setup.ConfigurationManager(app)
        app.config_manager._save_active_config = MagicMock()
        app.config_manager._update_hosts_symlink = MagicMock()
        app.config_manager.active_config["config_name"] = "demo"
        app.config_manager.active_config["environment"] = "mainnet"
        self.app = app

    def test_register_machine_surfaces_tolerated_boundary_message(self):
        self.app.register_machine_without_deployment()

        rendered_text = " ".join(call.args[0] for call in self.app.print_colored.call_args_list if call.args)
        self.assertIn("15.6 GiB RAM", rendered_text)
        self.assertIn("tolerated near-16 GiB boundary", rendered_text)
