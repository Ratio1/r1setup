#!/usr/bin/env python3
"""Tests for discovery candidate inference and normalization."""

import unittest

from tests.support import r1setup


class TestDiscoveryInference(unittest.TestCase):
    """Focused tests for discovery environment precedence and candidate normalization."""

    def test_metadata_environment_takes_precedence_over_image_tag(self):
        result = r1setup.R1Setup._infer_discovery_environment({
            "metadata_app_env": "testnet",
            "image": "ratio1/edge_node:mainnet",
        })

        self.assertEqual(result["value"], "testnet")
        self.assertEqual(result["source"], "metadata")
        self.assertEqual(result["confidence"], "high")

    def test_service_environment_takes_precedence_over_image_tag(self):
        result = r1setup.R1Setup._infer_discovery_environment({
            "environment_map": {"MNL_APP_ENV": "devnet"},
            "image": "ratio1/edge_node:mainnet",
        })

        self.assertEqual(result["value"], "devnet")
        self.assertEqual(result["source"], "service_environment")

    def test_image_tag_environment_is_used_when_other_sources_missing(self):
        result = r1setup.R1Setup._infer_discovery_environment({
            "image": "ratio1/edge_node:testnet",
        })

        self.assertEqual(result["value"], "testnet")
        self.assertEqual(result["source"], "image_tag")
        self.assertEqual(result["confidence"], "medium")

    def test_unknown_environment_returns_explicit_unknown(self):
        result = r1setup.R1Setup._infer_discovery_environment({
            "image": "ratio1/edge_node:custom",
        })

        self.assertEqual(result["value"], "unknown")
        self.assertEqual(result["source"], "unknown")

    def test_normalize_discovery_candidate_prefers_live_mounts_and_preserves_names(self):
        candidate = r1setup.R1Setup._normalize_discovery_candidate(
            {
                "ansible_host": "10.0.0.2",
                "ansible_user": "vitalii",
                "ansible_port": 22,
            },
            {
                "service_name": "edge_node2",
                "service_file_path": "/etc/systemd/system/edge_node2.service",
                "service_state": "active",
                "container_name": "edge_node2",
                "container_present": True,
                "container_state": "running",
                "configured_mounts": [
                    {"source": "/var/cache/edge_node2/_local_cache", "destination": "/edge_node/_local_cache"},
                ],
                "live_mounts": [
                    {"source": "/srv/edge_node2", "destination": "/edge_node/_local_cache", "type": "bind"},
                ],
                "metadata_host_path": "/srv/edge_node2/_data/r1setup/metadata.json",
                "metadata_app_env": "mainnet",
                "service_file_version": "v3",
                "image": "ratio1/edge_node:devnet",
                "managed_by_r1setup": True,
            },
        )

        self.assertEqual(candidate["candidate_id"], "vitalii@10.0.0.2:22::edge_node2")
        self.assertEqual(candidate["service_name"], "edge_node2")
        self.assertEqual(candidate["container_name"], "edge_node2")
        self.assertEqual(candidate["environment"], "mainnet")
        self.assertEqual(candidate["environment_source"], "metadata")
        self.assertEqual(candidate["effective_mounts"][0]["source"], "/srv/edge_node2")
        self.assertEqual(candidate["service_file_version"], "v3")
        self.assertTrue(candidate["managed_by_r1setup"])
        self.assertEqual(candidate["logical_topology_hint"], "multiple_candidates_possible")

    def test_service_name_does_not_imply_expert_mode(self):
        candidate = r1setup.R1Setup._normalize_discovery_candidate(
            {
                "ansible_host": "10.0.0.3",
                "ansible_user": "root",
            },
            {
                "service_name": "edge_node3",
                "service_state": "inactive",
                "image": "ratio1/edge_node:mainnet",
            },
        )

        self.assertEqual(candidate["service_name"], "edge_node3")
        self.assertEqual(candidate["environment"], "mainnet")
        self.assertEqual(candidate["logical_topology_hint"], "multiple_candidates_possible")
