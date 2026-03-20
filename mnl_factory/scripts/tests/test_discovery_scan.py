#!/usr/bin/env python3
"""Tests for discovery scan execution and result handling."""

import unittest
from unittest.mock import MagicMock

from tests.support import r1setup


class TestDiscoveryScan(unittest.TestCase):
    """Tests the machine-level discovery scan wrapper."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        self.app.print_debug = MagicMock()

    def test_discovery_scan_returns_normalized_candidates(self):
        self.app._run_machine_probe = MagicMock(return_value={
            "status": "success",
            "stdout": """
            {
              "services": [
                {
                  "service_name": "edge_node",
                  "service_file_path": "/etc/systemd/system/edge_node.service",
                  "service_state": "active",
                  "container_name": "edge_node",
                  "container_present": true,
                  "container_state": "running",
                  "configured_mounts": [
                    {"source": "/var/cache/edge_node/_local_cache", "destination": "/edge_node/_local_cache"}
                  ],
                  "live_mounts": [],
                  "metadata_host_path": "/var/cache/edge_node/_local_cache/_data/r1setup/metadata.json",
                  "metadata_app_env": "mainnet",
                  "service_file_version": "v2",
                  "image": "ratio1/edge_node:mainnet",
                  "managed_by_r1setup": true
                }
              ]
            }
            """,
        })

        result = self.app.discover_existing_edge_node_services({
            "ansible_host": "35.228.69.214",
            "ansible_user": "vitalii",
        })

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["candidate_count"], 1)
        candidate = result["candidates"][0]
        self.assertEqual(candidate["service_name"], "edge_node")
        self.assertEqual(candidate["environment"], "mainnet")
        self.assertEqual(candidate["container_state"], "running")

    def test_discovery_scan_rejects_invalid_json(self):
        self.app._run_machine_probe = MagicMock(return_value={
            "status": "success",
            "stdout": "not-json",
        })

        result = self.app.discover_existing_edge_node_services({
            "ansible_host": "35.228.69.214",
            "ansible_user": "vitalii",
        })

        self.assertEqual(result["status"], "error")
        self.assertIn("invalid JSON", result["message"])

    def test_discovery_scan_propagates_probe_error(self):
        self.app._run_machine_probe = MagicMock(return_value={
            "status": "error",
            "message": "Probe timed out after 30 seconds",
        })

        result = self.app.discover_existing_edge_node_services({
            "ansible_host": "35.228.69.214",
            "ansible_user": "vitalii",
        })

        self.assertEqual(result["status"], "error")
        self.assertIn("timed out", result["message"])
