#!/usr/bin/env python3
"""Tests for VersionManager behavior."""

import unittest
from unittest.mock import MagicMock, patch

from tests.support import r1setup


class TestAutoUpdateCheck(unittest.TestCase):
    """Tests for VersionManager._auto_update_check()."""

    def test_skip_auto_update_via_environment(self):
        app = MagicMock()
        manager = r1setup.VersionManager(app)
        manager._check_latest_version = MagicMock()
        manager._check_ansible_collection_version = MagicMock()

        with patch.dict("os.environ", {"R1SETUP_SKIP_AUTO_UPDATE": "1"}, clear=False):
            manager._auto_update_check()

        manager._check_latest_version.assert_not_called()
        manager._check_ansible_collection_version.assert_not_called()



class TestCompareVersions(unittest.TestCase):
    """Tests for VersionManager._compare_versions()."""

    def _cmp(self, v1, v2):
        return r1setup.VersionManager._compare_versions(v1, v2)

    def test_equal(self):
        self.assertEqual(self._cmp("1.0.0", "1.0.0"), 0)

    def test_greater(self):
        self.assertEqual(self._cmp("2.0.0", "1.0.0"), 1)

    def test_lesser(self):
        self.assertEqual(self._cmp("1.0.0", "2.0.0"), -1)

    def test_patch_difference(self):
        self.assertEqual(self._cmp("1.0.1", "1.0.0"), 1)
        self.assertEqual(self._cmp("1.0.0", "1.0.1"), -1)

    def test_minor_difference(self):
        self.assertEqual(self._cmp("1.2.0", "1.1.0"), 1)

    def test_different_lengths(self):
        self.assertEqual(self._cmp("1.0", "1.0.0"), 0)
        self.assertEqual(self._cmp("1.0.0.1", "1.0.0"), 1)

    def test_prerelease_stripped(self):
        self.assertEqual(self._cmp("1.0.0-beta", "1.0.0"), 0)
        self.assertEqual(self._cmp("1.0.1-rc1", "1.0.0"), 1)

    def test_non_numeric_part(self):
        self.assertEqual(self._cmp("1.abc.0", "1.0.0"), 0)
