#!/usr/bin/env python3
"""Tests for VersionManager behavior."""

import unittest

from tests.support import r1setup


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
