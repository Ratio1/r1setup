#!/usr/bin/env python3
"""Tests for helper-mode resolution and dispatcher command routing."""

import unittest
from unittest.mock import MagicMock

from tests.support import r1setup


class TestDispatcherHelpers(unittest.TestCase):
    """Verify helper-mode behavior for standard and expert nodes."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        self.app.config_manager = MagicMock()
        self.app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {}
                    }
                }
            }
        }
        self.app.print_colored = MagicMock()

        self.config_app = MagicMock()
        self.config_app.inventory = self.app.inventory
        self.config_app.print_debug = MagicMock()
        self.cm = r1setup.ConfigurationManager(self.config_app)

    def test_build_helper_runtime_standard_mode_uses_global_helpers(self):
        helper_runtime = self.cm.build_helper_runtime("node-a", {
            "edge_node_service_name": "edge_node",
            "mnl_docker_container_name": "edge_node",
        })

        self.assertEqual(helper_runtime["helper_mode"], r1setup.HELPER_MODE_STANDARD)
        self.assertEqual(helper_runtime["helper_registry_path"], "/var/lib/ratio1/r1setup/helpers/edge_node.env")
        self.assertEqual(helper_runtime["remote_commands"]["logs"], "get_logs")
        self.assertEqual(helper_runtime["remote_commands"]["info"], "get_node_info")

    def test_build_helper_runtime_expert_mode_uses_dispatcher(self):
        helper_runtime = self.cm.build_helper_runtime("node-b", {
            "r1setup_topology_mode": "expert",
            "edge_node_service_name": "edge_node2",
            "mnl_docker_container_name": "edge_node2",
        })

        self.assertEqual(helper_runtime["helper_mode"], r1setup.HELPER_MODE_EXPERT)
        self.assertEqual(helper_runtime["helper_registry_path"], "/var/lib/ratio1/r1setup/helpers/edge_node2.env")
        self.assertEqual(helper_runtime["remote_commands"]["logs"], "r1service edge_node2 logs")
        self.assertEqual(helper_runtime["remote_commands"]["info"], "r1service edge_node2 info")
        self.assertEqual(helper_runtime["remote_commands"]["restart"], "r1service edge_node2 restart")

    def test_detect_helper_mode_conflicts_same_machine(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-a": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_topology_mode": "standard",
                            },
                            "node-b": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_topology_mode": "expert",
                            },
                        }
                    }
                }
            }
        }

        conflicts = self.cm.detect_helper_mode_conflicts(inventory, selected_host_names=["node-b"])
        self.assertIn("root@10.0.0.1:22", conflicts)
        detail = conflicts["root@10.0.0.1:22"]
        self.assertEqual(sorted(detail["selected_hosts"]), ["node-b"])
        self.assertEqual(sorted(detail["helper_modes"].keys()), [r1setup.HELPER_MODE_EXPERT, r1setup.HELPER_MODE_STANDARD])

    def test_build_remote_helper_command_adds_arguments(self):
        host_config = {
            "r1setup_topology_mode": "expert",
            "edge_node_service_name": "edge_node2",
            "mnl_docker_container_name": "edge_node2",
        }
        self.app.config_manager.build_helper_runtime.return_value = self.cm.build_helper_runtime("node-b", host_config)

        command = self.app._build_remote_helper_command("node-b", host_config, "logs", "-n", "50")

        self.assertEqual(command, "r1service edge_node2 logs -n 50")

    def test_build_node_ssh_command_uses_sshpass_when_password_present(self):
        command = self.app._build_node_ssh_command("node-a", {
            "ansible_host": "10.0.0.2",
            "ansible_user": "root",
            "ansible_port": 2222,
            "ansible_ssh_pass": "secret",
        }, "get_logs -f")

        self.assertEqual(command[:3], ["sshpass", "-p", "secret"])
        self.assertEqual(command[3:8], ["ssh", "-p", "2222", "root@10.0.0.2", "get_logs -f"])

    def test_ensure_helper_mode_supported_for_hosts_rejects_mixed_machine(self):
        self.app.detect_helper_mode_conflicts = MagicMock(return_value={
            "root@10.0.0.1:22": {
                "helper_modes": {
                    r1setup.HELPER_MODE_STANDARD: ["node-a"],
                    r1setup.HELPER_MODE_EXPERT: ["node-b"],
                }
            }
        })

        allowed = self.app._ensure_helper_mode_supported_for_hosts(["node-b"], action_label="deploy selected nodes")

        self.assertFalse(allowed)
        self.app.print_colored.assert_called()
