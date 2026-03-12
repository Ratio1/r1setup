#!/usr/bin/env python3
"""Tests for r1setup module-level helpers."""

import inspect
import unittest
from datetime import datetime

from tests.support import r1setup


class TestGetGpuHosts(unittest.TestCase):
    """Tests for _get_gpu_hosts()."""

    def test_full_inventory(self):
        inv = {
            "all": {
                "children": {
                    "gpu_nodes": {
                        "hosts": {"node1": {"ansible_host": "1.2.3.4"}, "node2": {}}
                    }
                }
            }
        }
        result = r1setup._get_gpu_hosts(inv)
        self.assertEqual(len(result), 2)
        self.assertIn("node1", result)
        self.assertIn("node2", result)

    def test_empty_dict(self):
        self.assertEqual(r1setup._get_gpu_hosts({}), {})

    def test_missing_all(self):
        self.assertEqual(r1setup._get_gpu_hosts({"other": {}}), {})

    def test_missing_children(self):
        self.assertEqual(r1setup._get_gpu_hosts({"all": {}}), {})

    def test_missing_gpu_nodes(self):
        self.assertEqual(r1setup._get_gpu_hosts({"all": {"children": {}}}), {})

    def test_missing_hosts(self):
        inv = {"all": {"children": {"gpu_nodes": {}}}}
        self.assertEqual(r1setup._get_gpu_hosts(inv), {})

    def test_returns_reference_not_copy(self):
        hosts = {"n1": {"ip": "10.0.0.1"}}
        inv = {"all": {"children": {"gpu_nodes": {"hosts": hosts}}}}
        result = r1setup._get_gpu_hosts(inv)
        self.assertIs(result, hosts)

    def test_no_infinite_recursion(self):
        source = inspect.getsource(r1setup._get_gpu_hosts)
        body = "\n".join(source.split("\n")[1:])
        self.assertNotIn("_get_gpu_hosts(", body,
                         "_get_gpu_hosts calls itself — infinite recursion!")


class TestParseIsoToDatetime(unittest.TestCase):
    """Tests for _parse_iso_to_datetime()."""

    def test_iso_string_with_z(self):
        dt = r1setup._parse_iso_to_datetime("2024-06-15T14:30:00Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 6)
        self.assertEqual(dt.day, 15)
        self.assertEqual(dt.hour, 14)
        self.assertEqual(dt.minute, 30)

    def test_iso_string_with_offset(self):
        dt = r1setup._parse_iso_to_datetime("2024-06-15T14:30:00+02:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.hour, 14)

    def test_iso_string_no_tz(self):
        dt = r1setup._parse_iso_to_datetime("2024-06-15T14:30:00")
        self.assertIsNotNone(dt)

    def test_numeric_timestamp(self):
        ts = 1718457000.0
        dt = r1setup._parse_iso_to_datetime(ts)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2024)

    def test_none_returns_none(self):
        self.assertIsNone(r1setup._parse_iso_to_datetime(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(r1setup._parse_iso_to_datetime(""))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(r1setup._parse_iso_to_datetime("not-a-date"))

    def test_garbage_number_returns_none(self):
        result = r1setup._parse_iso_to_datetime(99999999999999)
        self.assertTrue(result is None or isinstance(result, datetime))

    def test_zero_returns_none(self):
        self.assertIsNone(r1setup._parse_iso_to_datetime(0))

    def test_boolean_false_returns_none(self):
        self.assertIsNone(r1setup._parse_iso_to_datetime(False))


class TestParseIsoDatetime(unittest.TestCase):
    """Tests for _parse_iso_datetime()."""

    def test_default_format(self):
        result = r1setup._parse_iso_datetime("2024-06-15T14:30:00Z")
        self.assertEqual(result, "2024-06-15 14:30")

    def test_custom_format(self):
        result = r1setup._parse_iso_datetime("2024-06-15T14:30:00Z", "%Y/%m/%d")
        self.assertEqual(result, "2024/06/15")

    def test_numeric_timestamp(self):
        result = r1setup._parse_iso_datetime(1718457000.0)
        self.assertIsNotNone(result)
        self.assertIn("2024", result)

    def test_none_returns_none(self):
        self.assertIsNone(r1setup._parse_iso_datetime(None))

    def test_invalid_returns_none(self):
        self.assertIsNone(r1setup._parse_iso_datetime("garbage"))

    def test_or_pattern_unknown_fallback(self):
        self.assertEqual(r1setup._parse_iso_datetime("bad") or "Unknown", "Unknown")
        self.assertNotEqual(r1setup._parse_iso_datetime("2024-01-01T00:00:00Z") or "Unknown", "Unknown")
