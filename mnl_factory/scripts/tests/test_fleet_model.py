#!/usr/bin/env python3
"""Tests for schema-aware fleet-state derivation helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestFleetStateDerivation(unittest.TestCase):
    """Tests deriving a fleet view from legacy inventory data."""

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

    def test_build_fleet_state_uses_connection_identity_grouping_for_legacy_hosts(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            },
                            "node-2": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "mnl_docker_container_name": "edge_node2",
                            },
                        }
                    }
                }
            }
        }

        fleet_state = self.cm.build_fleet_state(inventory)

        self.assertEqual(fleet_state["config_schema_version"], r1setup.CONFIG_SCHEMA_VERSION)
        machines = fleet_state["fleet"]["machines"]
        instances = fleet_state["fleet"]["instances"]

        self.assertEqual(list(machines.keys()), ["root@10.0.0.1:22"])
        self.assertEqual(machines["root@10.0.0.1:22"]["instance_names"], ["node-1", "node-2"])
        self.assertEqual(instances["node-1"]["assigned_machine_id"], "root@10.0.0.1:22")
        self.assertEqual(instances["node-2"]["runtime"]["container_name"], "edge_node2")

    def test_build_fleet_state_prefers_explicit_machine_id(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                            }
                        }
                    }
                }
            }
        }

        fleet_state = self.cm.build_fleet_state(inventory)

        self.assertIn("machine-a", fleet_state["fleet"]["machines"])
        self.assertEqual(
            fleet_state["fleet"]["instances"]["node-1"]["assigned_machine_id"],
            "machine-a",
        )

    def test_build_fleet_state_carries_machine_auth_from_host_config(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "ubuntu",
                                "ansible_port": 2222,
                                "ansible_ssh_common_args": "-o StrictHostKeyChecking=no",
                                "ansible_ssh_pass": "ssh-secret",
                                "ansible_become_password": "sudo-secret",
                            }
                        }
                    }
                }
            }
        }

        fleet_state = self.cm.build_fleet_state(inventory)
        machine = fleet_state["fleet"]["machines"]["ubuntu@10.0.0.1:2222"]

        self.assertEqual(machine["ansible_ssh_common_args"], "-o StrictHostKeyChecking=no")
        self.assertEqual(machine["ansible_ssh_pass"], "ssh-secret")
        self.assertEqual(machine["ansible_become_password"], "sudo-secret")

    def test_build_fleet_state_carries_machine_key_auth_from_host_config(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-1": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "ubuntu",
                                "ansible_ssh_private_key_file": "~/.ssh/id_ed25519",
                            }
                        }
                    }
                }
            }
        }

        fleet_state = self.cm.build_fleet_state(inventory)
        machine = fleet_state["fleet"]["machines"]["ubuntu@10.0.0.1:22"]

        self.assertEqual(machine["ansible_ssh_private_key_file"], "~/.ssh/id_ed25519")

    def test_merge_fleet_state_collapses_duplicate_machine_endpoints(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-a": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                            },
                            "node-b": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                            },
                        }
                    }
                }
            }
        }
        persisted_fleet = {
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
                        "instance_names": ["node-a"],
                    },
                    "root@10.0.0.1:22": {
                        "machine_id": "root@10.0.0.1:22",
                        "ansible_host": "10.0.0.1",
                        "ansible_user": "root",
                        "ansible_port": 22,
                        "topology_mode": "standard",
                        "deployment_state": "unknown",
                        "instance_names": ["node-b"],
                    },
                },
                "instances": {
                    "node-a": {"assigned_machine_id": "machine-a"},
                    "node-b": {"assigned_machine_id": "root@10.0.0.1:22"},
                },
            },
        }

        merged = self.cm._merge_fleet_state(persisted_fleet, inventory)

        self.assertEqual(sorted(merged["fleet"]["machines"].keys()), ["machine-a"])
        self.assertEqual(
            merged["fleet"]["machines"]["machine-a"]["instance_names"],
            ["node-a", "node-b"],
        )
        self.assertEqual(
            merged["fleet"]["instances"]["node-b"]["assigned_machine_id"],
            "machine-a",
        )

    def test_merge_fleet_state_preserves_machine_auth_from_derived_host(self):
        inventory = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {
                            "node-a": {
                                "ansible_host": "10.0.0.1",
                                "ansible_user": "root",
                                "r1setup_machine_id": "machine-a",
                                "ansible_ssh_pass": "ssh-secret",
                                "ansible_become_password": "sudo-secret",
                            },
                        }
                    }
                }
            }
        }
        persisted_fleet = {
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
                        "instance_names": ["node-a"],
                    },
                },
                "instances": {
                    "node-a": {"assigned_machine_id": "machine-a"},
                },
            },
        }

        merged = self.cm._merge_fleet_state(persisted_fleet, inventory)
        machine = merged["fleet"]["machines"]["machine-a"]

        self.assertEqual(machine["ansible_ssh_pass"], "ssh-secret")
        self.assertEqual(machine["ansible_become_password"], "sudo-secret")
