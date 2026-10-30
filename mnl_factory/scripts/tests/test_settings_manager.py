#!/usr/bin/env python3
"""Tests for SettingsManager timeout behavior."""

import unittest
from unittest.mock import MagicMock

from tests.support import r1setup


class TestConnectionTimeout(unittest.TestCase):
    """Tests for SettingsManager connection_timeout / ssh_connect_timeout."""

    def _make_settings_manager(self, **overrides):
        sm = r1setup.SettingsManager.__new__(r1setup.SettingsManager)
        sm.app = MagicMock()
        sm.settings = dict(r1setup.SettingsManager.DEFAULT_SETTINGS)
        sm.settings.update(overrides)
        return sm

    def test_default_value(self):
        sm = self._make_settings_manager()
        self.assertEqual(sm.connection_timeout, 30)

    def test_custom_value(self):
        sm = self._make_settings_manager(connection_timeout=120)
        self.assertEqual(sm.connection_timeout, 120)

    def test_clamp_below_minimum(self):
        sm = self._make_settings_manager(connection_timeout=5)
        self.assertEqual(sm.connection_timeout, 30)

    def test_clamp_above_maximum(self):
        sm = self._make_settings_manager(connection_timeout=999)
        self.assertEqual(sm.connection_timeout, 600)

    def test_boundary_min(self):
        sm = self._make_settings_manager(connection_timeout=30)
        self.assertEqual(sm.connection_timeout, 30)

    def test_boundary_max(self):
        sm = self._make_settings_manager(connection_timeout=600)
        self.assertEqual(sm.connection_timeout, 600)

    def test_non_integer_string(self):
        sm = self._make_settings_manager(connection_timeout="abc")
        self.assertEqual(sm.connection_timeout, 30)

    def test_none_value(self):
        sm = self._make_settings_manager(connection_timeout=None)
        self.assertEqual(sm.connection_timeout, 30)

    def test_string_number(self):
        sm = self._make_settings_manager(connection_timeout="120")
        self.assertEqual(sm.connection_timeout, 120)

    def test_ssh_default(self):
        sm = self._make_settings_manager(connection_timeout=30)
        self.assertEqual(sm.ssh_connect_timeout, 10)

    def test_ssh_60(self):
        sm = self._make_settings_manager(connection_timeout=60)
        self.assertEqual(sm.ssh_connect_timeout, 20)

    def test_ssh_120(self):
        sm = self._make_settings_manager(connection_timeout=120)
        self.assertEqual(sm.ssh_connect_timeout, 40)

    def test_ssh_600(self):
        sm = self._make_settings_manager(connection_timeout=600)
        self.assertEqual(sm.ssh_connect_timeout, 200)

    def test_ssh_floor_10(self):
        sm = self._make_settings_manager(connection_timeout=30)
        self.assertGreaterEqual(sm.ssh_connect_timeout, 10)

    def test_missing_key_gets_default(self):
        sm = self._make_settings_manager()
        del sm.settings["connection_timeout"]
        self.assertEqual(sm.connection_timeout, 30)


class TestPlaybookTimeout(unittest.TestCase):
    """Tests for SettingsManager playbook_timeout."""

    def _make_settings_manager(self, **overrides):
        sm = r1setup.SettingsManager.__new__(r1setup.SettingsManager)
        sm.app = MagicMock()
        sm.settings = dict(r1setup.SettingsManager.DEFAULT_SETTINGS)
        sm.settings.update(overrides)
        return sm

    def test_default_value(self):
        sm = self._make_settings_manager()
        self.assertEqual(sm.playbook_timeout, 1800)

    def test_allows_long_values_for_slow_hosts(self):
        sm = self._make_settings_manager(playbook_timeout=43200)
        self.assertEqual(sm.playbook_timeout, 43200)

    def test_clamp_above_maximum(self):
        sm = self._make_settings_manager(playbook_timeout=999999)
        self.assertEqual(sm.playbook_timeout, 86400)

    def test_clamp_below_minimum(self):
        sm = self._make_settings_manager(playbook_timeout=10)
        self.assertEqual(sm.playbook_timeout, 300)

    def test_settings_menu_sets_playbook_timeout(self):
        sm = self._make_settings_manager()
        sm.set = MagicMock(side_effect=lambda key, value: sm.settings.__setitem__(key, value))
        sm.app.get_input = MagicMock(side_effect=["3", "21600", "0"])

        sm.settings_menu()

        sm.set.assert_called_once_with('playbook_timeout', 21600)
        self.assertEqual(sm.playbook_timeout, 21600)
