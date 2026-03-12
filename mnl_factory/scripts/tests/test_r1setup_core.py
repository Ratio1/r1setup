#!/usr/bin/env python3
"""Tests for core R1Setup instance methods."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from tests.support import r1setup


class TestValidateIp(unittest.TestCase):
    """Tests for R1Setup.validate_ip()."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)

    def test_valid_ip(self):
        self.assertTrue(self.app.validate_ip("192.168.1.1"))

    def test_valid_ip_zeros(self):
        self.assertTrue(self.app.validate_ip("0.0.0.0"))

    def test_valid_ip_max(self):
        self.assertTrue(self.app.validate_ip("255.255.255.255"))

    def test_octet_too_high(self):
        self.assertFalse(self.app.validate_ip("256.0.0.1"))

    def test_too_few_octets(self):
        self.assertFalse(self.app.validate_ip("192.168.1"))

    def test_too_many_octets(self):
        self.assertFalse(self.app.validate_ip("192.168.1.1.1"))

    def test_letters(self):
        self.assertFalse(self.app.validate_ip("abc.def.ghi.jkl"))

    def test_empty_string(self):
        self.assertFalse(self.app.validate_ip(""))

    def test_localhost(self):
        self.assertTrue(self.app.validate_ip("127.0.0.1"))

    def test_negative_octet(self):
        self.assertFalse(self.app.validate_ip("-1.0.0.1"))


class TestFormatTimestampAgo(unittest.TestCase):
    """Tests for R1Setup._format_timestamp_ago()."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)
        self.app.print_debug = MagicMock()

    def test_empty_returns_never(self):
        self.assertEqual(self.app._format_timestamp_ago(""), "Never")

    def test_none_returns_never(self):
        self.assertEqual(self.app._format_timestamp_ago(None), "Never")

    def test_invalid_returns_unknown(self):
        self.assertEqual(self.app._format_timestamp_ago("not-a-date"), "Unknown")

    def test_recent_timestamp(self):
        now = datetime.now(timezone.utc).isoformat()
        result = self.app._format_timestamp_ago(now)
        self.assertEqual(result, "Just now")

    def test_hours_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        result = self.app._format_timestamp_ago(ts)
        self.assertIn("hour(s) ago", result)

    def test_days_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        result = self.app._format_timestamp_ago(ts)
        self.assertIn("5 day(s) ago", result)

    def test_minutes_ago(self):
        ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        result = self.app._format_timestamp_ago(ts)
        self.assertIn("minute(s) ago", result)


class TestWaitForEnter(unittest.TestCase):
    """Tests for R1Setup.wait_for_enter()."""

    def setUp(self):
        self.app = r1setup.R1Setup.__new__(r1setup.R1Setup)

    @patch("builtins.input")
    def test_default_message(self, mock_input):
        self.app.wait_for_enter()
        mock_input.assert_called_once_with("\nPress Enter to continue...")

    @patch("builtins.input")
    def test_custom_message(self, mock_input):
        self.app.wait_for_enter("Press Enter to start streaming logs...")
        mock_input.assert_called_once_with("\nPress Enter to start streaming logs...")

    @patch("builtins.input")
    def test_newline_always_prefixed(self, mock_input):
        self.app.wait_for_enter("whatever")
        arg = mock_input.call_args[0][0]
        self.assertTrue(arg.startswith("\n"))
