#!/usr/bin/env python3
"""Tests for runtime naming and collision helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from tests.support import r1setup


class TestRuntimeNaming(unittest.TestCase):
    """Tests deterministic runtime-name resolution."""

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

    def test_standard_normalize_to_target_uses_single_node_defaults(self):
        runtime = self.cm.resolve_runtime_names(
            "node-1",
            topology_mode="standard",
            runtime_name_policy="normalize_to_target",
        )

        self.assertEqual(runtime["service_name"], "edge_node")
        self.assertEqual(runtime["container_name"], "edge_node")
        self.assertEqual(runtime["volume_path"], "/var/cache/edge_node/_local_cache")
        self.assertEqual(runtime["exit_status_path"], "/tmp/edge_node.exit")

    def test_expert_normalize_to_target_is_deterministic(self):
        runtime = self.cm.resolve_runtime_names(
            "Node 1 / Canary",
            topology_mode="expert",
            runtime_name_policy="normalize_to_target",
        )

        self.assertEqual(runtime["service_name"], "edge_node_node_1_canary")
        self.assertEqual(runtime["container_name"], "edge_node_node_1_canary")
        self.assertEqual(runtime["volume_path"], "/var/cache/edge_node_node_1_canary/_local_cache")
        self.assertEqual(runtime["exit_status_path"], "/tmp/edge_node_node_1_canary.exit")

    def test_preserve_policy_uses_existing_runtime(self):
        runtime = self.cm.resolve_runtime_names(
            "node-1",
            topology_mode="expert",
            runtime_name_policy="preserve",
            existing_runtime={
                "service_name": "edge_node7",
                "container_name": "edge_node7",
                "volume_path": "/var/cache/edge_node7/_local_cache",
                "metadata_path": "/var/cache/edge_node7/_local_cache/_data/r1setup/metadata.json",
                "exit_status_path": "/tmp/edge_node7.exit",
            },
        )

        self.assertEqual(runtime["service_name"], "edge_node7")
        self.assertEqual(runtime["exit_status_path"], "/tmp/edge_node7.exit")

    def test_detect_runtime_collisions_finds_conflicting_fields(self):
        fleet_state = {
            "fleet": {
                "instances": {
                    "node-1": {
                        "assigned_machine_id": "machine-a",
                        "runtime": {
                            "service_name": "edge_node_node_1",
                            "container_name": "edge_node_node_1",
                            "volume_path": "/var/cache/edge_node_node_1/_local_cache",
                            "metadata_path": "/var/cache/edge_node_node_1/_local_cache/_data/r1setup/metadata.json",
                            "exit_status_path": "/tmp/edge_node_node_1.exit",
                        },
                    }
                }
            }
        }
        proposed = {
            "service_name": "edge_node_node_1",
            "container_name": "edge_node_node_2",
            "volume_path": "/var/cache/edge_node_node_1/_local_cache",
            "metadata_path": "/var/cache/edge_node_node_2/_local_cache/_data/r1setup/metadata.json",
            "exit_status_path": "/tmp/edge_node_node_2.exit",
        }

        collisions = self.cm.detect_runtime_collisions("machine-a", proposed, fleet_state)

        self.assertEqual(collisions["service_name"], ["node-1"])
        self.assertEqual(collisions["volume_path"], ["node-1"])
        self.assertNotIn("container_name", collisions)

