#!/usr/bin/env python3
"""Tests for grouped machine/instance fleet views and display helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestMachineGroupViews(unittest.TestCase):
    """Tests for ConfigurationManager.build_machine_group_views()."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base_path = Path(self.temp_dir.name)

        self.app = MagicMock()
        self.app.config_dir = self.base_path
        self.app.config_file = self.base_path / "hosts.yml"
        self.app.vars_file = self.base_path / "group_vars" / "variables.yml"
        self.app.inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}
        self.app.print_debug = MagicMock()
        self.app.print_colored = MagicMock()

        self.cm = r1setup.ConfigurationManager(self.app)

    def test_build_machine_group_views_includes_empty_machine_and_mixed_expert_machine(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                                "r1setup_topology_mode": "expert",
                                "edge_node_service_name": "edge_node2",
                                "mnl_docker_container_name": "edge_node2",
                                "mnl_docker_volume_path": "/var/cache/edge_node2/_local_cache",
                            },
                            "node-2": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                                "r1setup_topology_mode": "expert",
                                "edge_node_service_name": "edge_node3",
                                "mnl_docker_container_name": "edge_node3",
                                "mnl_docker_volume_path": "/var/cache/edge_node3/_local_cache",
                            },
                        }
                    }
                }
            }
        }

        fleet_state = self.cm.build_fleet_state(inventory)
        fleet_state["fleet"]["machines"]["machine-a"]["machine_specs"] = {
            "cpu_total": 16,
            "memory_gb_total": 64,
        }
        fleet_state["fleet"]["machines"]["machine-b"] = {
            "machine_id": "machine-b",
            "ansible_host": "10.0.0.2",
            "ansible_user": "root",
            "ansible_port": 22,
            "topology_mode": "standard",
            "deployment_state": "empty",
            "instance_names": [],
            "machine_specs": {
                "cpu_total": 8,
                "memory_gb_total": 32,
            },
        }

        views = self.cm.build_machine_group_views(
            inventory=inventory,
            fleet_state=fleet_state,
            node_status_data={
                "node-1": {"status": "running"},
                "node-2": {"status": "stopped"},
            },
        )

        self.assertEqual([view["machine_id"] for view in views], ["machine-a", "machine-b"])

        expert_view = views[0]
        self.assertEqual(expert_view["display_label"], "machine-a")
        self.assertEqual(expert_view["topology_mode"], "expert")
        self.assertEqual(expert_view["instance_count"], 2)
        self.assertEqual(expert_view["group_status"], "Mixed States")
        self.assertEqual(expert_view["machine_specs_summary"], "16 CPU / 64 GiB RAM")
        self.assertEqual(
            [instance["instance_name"] for instance in expert_view["instances"]],
            ["node-1", "node-2"],
        )
        self.assertEqual(
            [instance["status"] for instance in expert_view["instances"]],
            ["running", "stopped"],
        )

        empty_view = views[1]
        self.assertEqual(empty_view["display_label"], "machine-b")
        self.assertEqual(empty_view["topology_mode"], "standard")
        self.assertEqual(empty_view["instance_count"], 0)
        self.assertEqual(empty_view["group_status"], "No Instances")
        self.assertEqual(empty_view["machine_specs_summary"], "8 CPU / 32 GiB RAM")

    def test_service_name_suffix_does_not_force_expert_topology(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-solo": {
                                "ansible_host": "10.0.0.9",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-solo",
                                "r1setup_topology_mode": "standard",
                                "edge_node_service_name": "edge_node2",
                                "mnl_docker_container_name": "edge_node2",
                                "mnl_docker_volume_path": "/var/cache/edge_node2/_local_cache",
                            }
                        }
                    }
                }
            }
        }

        views = self.cm.build_machine_group_views(
            inventory=inventory,
            fleet_state=self.cm.build_fleet_state(inventory),
            node_status_data={"node-solo": {"status": "running"}},
        )

        self.assertEqual(len(views), 1)
        view = views[0]
        self.assertEqual(view["topology_mode"], "standard")
        self.assertEqual(view["instance_count"], 1)
        self.assertEqual(view["group_status"], "Running")
        self.assertEqual(view["instances"][0]["runtime"]["service_name"], "edge_node2")

    def test_build_machine_group_views_includes_untracked_discovered_candidates(self):
        inventory = {"all": {"children": {"gpu_nodes": {"hosts": {}}}}}
        fleet_state = self.cm._default_fleet_state()
        fleet_state["fleet"]["machines"]["machine-discovery"] = {
            "machine_id": "machine-discovery",
            "ansible_host": "10.0.0.20",
            "ansible_user": "root",
            "ansible_port": 22,
            "topology_mode": "standard",
            "deployment_state": "empty",
            "instance_names": [],
            "discovery": {
                "last_scanned_at": "2026-03-20T10:00:00",
                "candidates": [
                    {
                        "service_name": "edge_node_devnet",
                        "service_state": "active",
                        "environment": "devnet",
                        "environment_source": "metadata",
                    }
                ],
            },
        }

        views = self.cm.build_machine_group_views(inventory=inventory, fleet_state=fleet_state)

        self.assertEqual(len(views), 1)
        self.assertEqual(len(views[0]["instances"]), 0)
        self.assertEqual(len(views[0]["untracked_discovered_candidates"]), 1)
        self.assertEqual(views[0]["untracked_discovered_candidates"][0]["service_name"], "edge_node_devnet")

    def test_derived_machine_id_uses_hostname_as_display_label(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-solo": {
                                "ansible_host": "10.0.0.9",
                                "ansible_user": "root",
                            }
                        }
                    }
                }
            }
        }
        fleet_state = self.cm.build_fleet_state(inventory)
        derived_machine_id = "root@10.0.0.9:22"
        fleet_state["fleet"]["machines"][derived_machine_id]["machine_specs"] = {
            "hostname": "host-solo",
            "cpu_total": 4,
            "memory_gb_total": 15.6,
        }

        views = self.cm.build_machine_group_views(inventory=inventory, fleet_state=fleet_state)

        self.assertEqual(views[0]["display_label"], "host-solo")


class TestMachineGroupDisplayLines(unittest.TestCase):
    """Tests for grouped machine display formatting."""

    def test_build_machine_group_display_lines_includes_specs_versions_and_empty_machine(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app._format_timestamp_ago = MagicMock(return_value="2 hour(s) ago")

        machine_views = [
            {
                "machine_id": "machine-a",
                "connection_display": "root@10.0.0.1",
                "topology_mode": "expert",
                "deployment_state": "active",
                "group_status": "Mixed States",
                "group_status_color": "yellow",
                "group_status_emoji": "🟡",
                "machine_specs_summary": "16 CPU / 64 GB RAM",
                "instances": [
                    {
                        "instance_name": "node-1",
                        "status_emoji": "🟢",
                        "status_label": "Running",
                        "status_color": "green",
                        "runtime": {
                            "service_name": "edge_node2",
                            "container_name": "edge_node2",
                        },
                        "service_file_version": "v1",
                        "last_update": "2026-03-17T22:00:00+02:00",
                        "ssh_auth_mode": "key_only",
                    },
                    {
                        "instance_name": "node-2",
                        "status_emoji": "🔴",
                        "status_label": "Stopped",
                        "status_color": "red",
                        "runtime": {
                            "service_name": "edge_node3",
                            "container_name": "edge_node3",
                        },
                        "service_file_version": "v2",
                        "last_update": "2026-03-17T22:10:00+02:00",
                        "ssh_auth_mode": "password_only",
                    },
                ],
            },
            {
                "machine_id": "machine-b",
                "connection_display": "root@10.0.0.2",
                "topology_mode": "standard",
                "deployment_state": "empty",
                "group_status": "No Instances",
                "group_status_color": "yellow",
                "group_status_emoji": "📭",
                "machine_specs_summary": "8 CPU / 32 GB RAM",
                "instances": [],
            },
        ]

        lines, outdated = app._build_machine_group_display_lines(
            machine_views,
            target_service_version="v2",
            include_last_update=True,
        )

        texts = [text for text, _ in lines]
        self.assertIn(
            "  • machine-a: root@10.0.0.1 | mode=expert | state=active | 🟡 Mixed States",
            texts,
        )
        self.assertIn("      specs: 16 CPU / 64 GB RAM", texts)
        self.assertIn(
            "      - 🟢 node-1 [RUNNING] service=edge_node2 container=edge_node2 | service v1 / target v2 [UPDATE]",
            texts,
        )
        self.assertIn(
            "      - 🔴 node-2 [STOPPED] service=edge_node3 container=edge_node3 | service v2 / target v2 [OK]",
            texts,
        )
        self.assertIn("          last update 2 hour(s) ago | ssh auth key_only", texts)
        self.assertIn("  • machine-b: root@10.0.0.2 | mode=standard | state=empty | 📭 No Instances", texts)
        self.assertIn("      no assigned instances in this config", texts)
        self.assertEqual(outdated, ["node-1"])

    def test_build_machine_group_display_lines_notes_single_instance_expert_mode_retention(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app._format_timestamp_ago = MagicMock(return_value="Just now")

        machine_views = [
            {
                "machine_id": "machine-a",
                "display_label": "machine-a",
                "connection_display": "root@10.0.0.1",
                "topology_mode": "expert",
                "deployment_state": "active",
                "group_status": "Running",
                "group_status_color": "green",
                "group_status_emoji": "🟢",
                "machine_specs_summary": "",
                "instances": [
                    {
                        "instance_name": "node-1",
                        "status_emoji": "🟢",
                        "status_label": "Running",
                        "status_color": "green",
                        "runtime": {
                            "service_name": "edge_node",
                            "container_name": "edge_node",
                        },
                        "service_file_version": "v1",
                        "last_update": "",
                        "ssh_auth_mode": "key_only",
                    }
                ],
            }
        ]

        lines, _ = app._build_machine_group_display_lines(machine_views, target_service_version="v1")

        texts = [text for text, _ in lines]
        self.assertIn(
            "      expert mode retained with 1 instance; normalize back to standard only via an explicit future action",
            texts,
        )

    def test_build_machine_group_display_lines_skips_update_flag_for_not_deployed_instance(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app._format_timestamp_ago = MagicMock(return_value="Just now")

        machine_views = [
            {
                "machine_id": "machine-a",
                "display_label": "machine-a",
                "connection_display": "root@10.0.0.1",
                "topology_mode": "expert",
                "deployment_state": "active",
                "group_status": "Mixed States",
                "group_status_color": "yellow",
                "group_status_emoji": "🟡",
                "machine_specs_summary": "",
                "instances": [
                    {
                        "instance_name": "node-1",
                        "status": "running",
                        "status_emoji": "🟢",
                        "status_label": "Running",
                        "status_color": "green",
                        "runtime": {
                            "service_name": "edge_node",
                            "container_name": "edge_node",
                        },
                        "service_file_version": "v1",
                        "last_update": "",
                        "ssh_auth_mode": "key_only",
                    },
                    {
                        "instance_name": "node-2",
                        "status": "not_deployed",
                        "status_emoji": "📦",
                        "status_label": "Not Deployed",
                        "status_color": "yellow",
                        "runtime": {
                            "service_name": "edge_node_node2",
                            "container_name": "edge_node_node2",
                        },
                        "service_file_version": "NOT",
                        "last_update": "",
                        "ssh_auth_mode": "key_only",
                    },
                ],
            }
        ]

        lines, outdated = app._build_machine_group_display_lines(machine_views, target_service_version="v1")

        texts = [text for text, _ in lines]
        self.assertIn(
            "      - 📦 node-2 [NOT DEPLOYED] service=edge_node_node2 container=edge_node_node2 | service NOT / target v1 [N/A]",
            texts,
        )
        self.assertEqual(outdated, [])

    def test_build_machine_group_display_lines_show_discovered_untracked_candidates(self):
        app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        app._format_timestamp_ago = MagicMock(return_value="Just now")

        machine_views = [
            {
                "machine_id": "machine-discovery",
                "display_label": "machine-discovery",
                "connection_display": "root@10.0.0.20",
                "topology_mode": "standard",
                "deployment_state": "empty",
                "group_status": "No Instances",
                "group_status_color": "yellow",
                "group_status_emoji": "📭",
                "machine_specs_summary": "",
                "instances": [],
                "last_discovery_scan_at": "2026-03-20T11:00:00+02:00",
                "untracked_discovered_candidates": [
                    {
                        "service_name": "edge_node_devnet",
                        "service_state": "active",
                        "environment": "devnet",
                        "environment_source": "metadata",
                    }
                ],
            }
        ]

        lines, _ = app._build_machine_group_display_lines(machine_views)
        texts = [text for text, _ in lines]
        self.assertIn(
            "      cached discovery results not imported into this config (last scan Just now; refresh via Configuration -> Discover Services):",
            texts,
        )
        self.assertIn(
            "        ~ edge_node_devnet [DISCOVERED] state=active env=devnet (metadata)",
            texts,
        )
