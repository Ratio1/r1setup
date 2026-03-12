#!/usr/bin/env python3
"""Tests for NodeStatusTracker pure logic and parsing helpers."""

import unittest
from unittest.mock import MagicMock

from tests.support import r1setup


class TestResolveNodeStatus(unittest.TestCase):
    """Tests for NodeStatusTracker._resolve_node_status()."""

    def _resolve(self, svc, ctr):
        return r1setup.NodeStatusTracker._resolve_node_status(svc, ctr)

    def test_container_running(self):
        status, result, overwrite = self._resolve(None, "RUNNING")
        self.assertEqual(status, "running")
        self.assertTrue(overwrite)

    def test_container_running_ignores_service(self):
        for svc in ("ACTIVE", "INACTIVE", "FAILED", "NOT_FOUND", None):
            status, _, _ = self._resolve(svc, "RUNNING")
            self.assertEqual(status, "running", f"Failed for service_status={svc}")

    def test_container_not_running_service_active(self):
        status, _, overwrite = self._resolve("ACTIVE", "NOT_RUNNING")
        self.assertEqual(status, "stopped")
        self.assertTrue(overwrite)

    def test_container_not_running_service_not_found(self):
        status, _, _ = self._resolve("NOT_FOUND", "NOT_RUNNING")
        self.assertEqual(status, "not_deployed")

    def test_container_not_running_service_none(self):
        status, _, _ = self._resolve(None, "NOT_RUNNING")
        self.assertEqual(status, "stopped")

    def test_service_active_no_container(self):
        status, _, overwrite = self._resolve("ACTIVE", None)
        self.assertEqual(status, "running")
        self.assertFalse(overwrite)

    def test_service_inactive(self):
        status, _, _ = self._resolve("INACTIVE", None)
        self.assertEqual(status, "stopped")

    def test_service_failed(self):
        status, _, _ = self._resolve("FAILED", None)
        self.assertEqual(status, "stopped")

    def test_service_not_found_no_container(self):
        status, _, _ = self._resolve("NOT_FOUND", None)
        self.assertEqual(status, "not_deployed")

    def test_both_none(self):
        self.assertIsNone(self._resolve(None, None))


class TestParseStatusFields(unittest.TestCase):
    """Tests for NodeStatusTracker._parse_status_fields()."""

    def setUp(self):
        self.tracker = r1setup.NodeStatusTracker.__new__(r1setup.NodeStatusTracker)

    def test_active_running(self):
        text = "Service Status: ACTIVE\nContainer Status: RUNNING"
        svc, ctr = self.tracker._parse_status_fields(text)
        self.assertEqual(svc, "ACTIVE")
        self.assertEqual(ctr, "RUNNING")

    def test_inactive_not_running(self):
        text = "Service Status: INACTIVE\nContainer Status: NOT RUNNING"
        svc, ctr = self.tracker._parse_status_fields(text)
        self.assertEqual(svc, "INACTIVE")
        self.assertEqual(ctr, "NOT_RUNNING")

    def test_failed(self):
        text = "Service Status: FAILED"
        svc, ctr = self.tracker._parse_status_fields(text)
        self.assertEqual(svc, "FAILED")
        self.assertIsNone(ctr)

    def test_not_found(self):
        text = "Service Status: NOT FOUND"
        svc, ctr = self.tracker._parse_status_fields(text)
        self.assertEqual(svc, "NOT_FOUND")

    def test_empty_text(self):
        svc, ctr = self.tracker._parse_status_fields("")
        self.assertIsNone(svc)
        self.assertIsNone(ctr)

    def test_inactive_failed_variant(self):
        text = "Service Status: INACTIVE/FAILED"
        svc, _ = self.tracker._parse_status_fields(text)
        self.assertEqual(svc, "INACTIVE")


class TestDetermineUpdatedStatus(unittest.TestCase):
    """Tests for NodeStatusTracker._determine_updated_status()."""

    def setUp(self):
        self.tracker = r1setup.NodeStatusTracker.__new__(r1setup.NodeStatusTracker)
        self.tracker.app = MagicMock()

    def test_running(self):
        self.assertEqual(self.tracker._determine_updated_status("unknown", "running"), "running")

    def test_stopped(self):
        self.assertEqual(self.tracker._determine_updated_status("running", "stopped"), "stopped")

    def test_service_missing(self):
        self.assertEqual(self.tracker._determine_updated_status("unknown", "service_missing"), "never_deployed")

    def test_connection_failed(self):
        self.assertEqual(self.tracker._determine_updated_status("running", "connection_failed"), "error")

    def test_pending_restart_stopped(self):
        self.assertEqual(self.tracker._determine_updated_status("pending_restart", "stopped"), "stopped")

    def test_pending_restart_service_missing(self):
        self.assertEqual(self.tracker._determine_updated_status("pending_restart", "service_missing"), "never_deployed")

    def test_pending_restart_running(self):
        self.assertEqual(self.tracker._determine_updated_status("pending_restart", "running"), "pending_restart")

    def test_unknown_actual(self):
        self.assertEqual(self.tracker._determine_updated_status("running", "unknown"), "unknown")

    def test_unexpected_actual(self):
        self.assertEqual(self.tracker._determine_updated_status("running", "some_garbage"), "unknown")
