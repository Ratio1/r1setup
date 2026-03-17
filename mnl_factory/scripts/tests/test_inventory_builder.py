#!/usr/bin/env python3
"""Tests for generated execution inventory and playbook runner helpers."""

import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.support import r1setup


class TestInventoryBuilder(unittest.TestCase):
    """Verify generated execution inventory behavior."""

    def setUp(self):
        self.app = MagicMock()
        self.app.inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_topology_mode": "standard",
                            },
                            "node-2": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_topology_mode": "expert",
                                "edge_node_service_name": "edge_node2",
                                "mnl_docker_container_name": "edge_node2",
                                "mnl_docker_volume_path": "/var/cache/edge_node2/_local_cache",
                            },
                            "node-3": {
                                "ansible_host": "10.0.0.2",
                                "ansible_user": "ubuntu",
                            },
                        }
                    }
                }
            }
        }
        self.app.print_debug = MagicMock()
        self.cm = r1setup.ConfigurationManager(self.app)

    def test_build_execution_inventory_instance_scope_enriches_runtime_fields(self):
        inventory = self.cm.build_execution_inventory(["node-2"])
        hosts = inventory["all"]["children"]["gpu_nodes"]["hosts"]

        self.assertEqual(list(hosts.keys()), ["node-2"])
        node = hosts["node-2"]
        self.assertEqual(node["edge_node_service_name"], "edge_node2")
        self.assertEqual(node["mnl_docker_container_name"], "edge_node2")
        self.assertEqual(node["r1setup_execution_scope"], "instance")
        self.assertEqual(node["r1setup_helper_mode"], r1setup.HELPER_MODE_EXPERT)
        self.assertEqual(node["r1setup_remote_get_logs_command"], "r1service edge_node2 logs")

    def test_build_execution_inventory_machine_scope_dedupes_machine_hosts(self):
        inventory = self.cm.build_execution_inventory(["node-1", "node-2", "node-3"], dedupe_by_machine=True)
        hosts = inventory["all"]["children"]["gpu_nodes"]["hosts"]

        self.assertEqual(sorted(hosts.keys()), ["node-1", "node-3"])
        node_1 = hosts["node-1"]
        self.assertEqual(node_1["r1setup_execution_scope"], "machine")
        self.assertEqual(sorted(node_1["r1setup_selected_instance_hosts"]), ["node-1", "node-2"])
        self.assertEqual(node_1["r1setup_machine_id"], "root@10.0.0.1:22")


class TestGeneratedPlaybookRunner(unittest.TestCase):
    """Verify generated playbook runner builds and cleans temporary inventory."""

    def test_run_generated_playbook_writes_and_removes_temp_inventory(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
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
        app.config_manager = r1setup.ConfigurationManager(MagicMock(inventory=app.inventory, print_debug=MagicMock()))
        app.get_collection_version = MagicMock(return_value="1.3.30")
        app.run_command = MagicMock(return_value=(True, "ok"))

        with tempfile.TemporaryDirectory() as temp_dir:
            playbook_path = Path(temp_dir) / "service_status.yml"
            playbook_path.write_text("---\n")

            with patch.dict(os.environ, {
                "ANSIBLE_CONFIG": "ansible.cfg",
                "ANSIBLE_COLLECTIONS_PATH": "collections",
                "ANSIBLE_HOME": "ansible-home",
            }, clear=False):
                success, output, host_names, _ = app.run_generated_playbook(
                    playbook_path,
                    ["node-1"],
                    machine_scope=False,
                    last_applied_action="status_check",
                    show_output=False,
                    timeout=30,
                )

        self.assertTrue(success)
        self.assertEqual(output, "ok")
        self.assertEqual(host_names, ["node-1"])
        cmd = app.run_command.call_args[0][0]
        self.assertIn("ansible-playbook -i ", cmd)
        self.assertIn(str(playbook_path), cmd)
        inventory_arg = cmd.split("ansible-playbook -i ", 1)[1].split(" ", 1)[0]
        self.assertFalse(Path(inventory_arg).exists())
