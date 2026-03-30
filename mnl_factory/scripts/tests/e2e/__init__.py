"""E2E tests requiring real SSH access to remote machines.

These tests are excluded from the default ``python3 -m unittest discover tests``
run via the ``load_tests`` protocol below.  Run them explicitly with::

    python3 -m unittest tests.e2e.test_machine_first_onboarding -v
"""


def load_tests(loader, tests, pattern):
    """Return an empty suite so ``discover`` does not recurse into this package."""
    import unittest
    return unittest.TestSuite()
