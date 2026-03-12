#!/usr/bin/env python3
"""Tests for SSH key management helpers."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from tests.support import r1setup


def make_inventory(hosts):
    """Build a minimal inventory structure for tests."""
    return {
        "all": {
            "vars": {},
            "children": {
                "gpu_nodes": {
                    "hosts": hosts,
                }
            },
        }
    }


class TestSSHKeyManagerMigration(unittest.TestCase):
    """Tests for legacy SSH metadata migration."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base_path = Path(self.tempdir.name)
        self.app = MagicMock()
        self.app.configs_dir = self.base_path / "configs"
        self.app.configs_dir.mkdir()
        self.app.print_debug = MagicMock()
        self.app.print_colored = MagicMock()
        self.manager = r1setup.SSHKeyManager(self.app)

    def test_migrate_legacy_ssh_metadata_adds_schema_and_host_states(self):
        config_path = self.app.configs_dir / "legacy.yml"
        config_data = make_inventory(
            {
                "pw-node": {
                    "ansible_host": "10.0.0.10",
                    "ansible_user": "root",
                    "ansible_ssh_pass": "secret",
                },
                "key-node": {
                    "ansible_host": "10.0.0.11",
                    "ansible_user": "ubuntu",
                    "ansible_ssh_private_key_file": "~/.ssh/id_ed25519",
                },
            }
        )
        config_path.write_text(yaml.safe_dump(config_data))

        self.manager.migrate_legacy_ssh_metadata()

        migrated = yaml.safe_load(config_path.read_text())
        vars_section = migrated["all"]["vars"]
        hosts = migrated["all"]["children"]["gpu_nodes"]["hosts"]

        self.assertEqual(vars_section["r1setup_schema_version"], r1setup.SSH_SCHEMA_VERSION)
        self.assertEqual(hosts["pw-node"]["r1setup_ssh_auth_mode"], r1setup.SSH_AUTH_MODE_PASSWORD_ONLY)
        self.assertFalse(hosts["pw-node"]["r1setup_ssh_requires_revalidation"])
        self.assertEqual(hosts["key-node"]["r1setup_ssh_auth_mode"], r1setup.SSH_AUTH_MODE_KEY_CONFIGURED_LEGACY)
        self.assertTrue(hosts["key-node"]["r1setup_ssh_requires_revalidation"])
        self.assertEqual(hosts["key-node"]["r1setup_ssh_primary_key_path"], "~/.ssh/id_ed25519")

    def test_migrate_legacy_ssh_metadata_is_additive(self):
        config_path = self.app.configs_dir / "already_migrated.yml"
        config_data = make_inventory(
            {
                "node": {
                    "ansible_host": "10.0.0.12",
                    "ansible_user": "root",
                    "ansible_ssh_private_key_file": "~/.ssh/id_ed25519",
                    "r1setup_ssh_auth_mode": r1setup.SSH_AUTH_MODE_KEY_VERIFIED,
                    "r1setup_ssh_key_auth_verified_at": "2026-03-12T09:00:00",
                }
            }
        )
        config_data["all"]["vars"]["r1setup_schema_version"] = r1setup.SSH_SCHEMA_VERSION
        config_path.write_text(yaml.safe_dump(config_data))

        self.manager.migrate_legacy_ssh_metadata()

        migrated = yaml.safe_load(config_path.read_text())
        host = migrated["all"]["children"]["gpu_nodes"]["hosts"]["node"]

        self.assertEqual(host["r1setup_ssh_auth_mode"], r1setup.SSH_AUTH_MODE_KEY_VERIFIED)
        self.assertEqual(host["r1setup_ssh_key_auth_verified_at"], "2026-03-12T09:00:00")


class TestSSHKeyManagerValidation(unittest.TestCase):
    """Tests for key validation helpers."""

    def setUp(self):
        self.app = MagicMock()
        self.manager = r1setup.SSHKeyManager(self.app)

    @patch.object(r1setup.SSHKeyManager, "_derive_public_key")
    @patch.object(r1setup.SSHKeyManager, "_validate_public_key_file")
    def test_validate_keypair_accepts_derived_public_key_when_pub_missing(self, mock_validate_public, mock_derive):
        with tempfile.TemporaryDirectory() as tmp:
            private_key = Path(tmp) / "id_ed25519"
            private_key.write_text("private-key")

            mock_derive.return_value = {
                "valid": True,
                "content": "ssh-ed25519 AAAATEST derived@example",
                "fingerprint": "SHA256:derived",
            }
            mock_validate_public.return_value = {"valid": False, "error": "should not be called"}

            result = self.manager._validate_keypair(str(private_key))

            self.assertTrue(result["valid"])
            self.assertEqual(result["private_key_path"], str(private_key.resolve()))
            self.assertEqual(result["public_key"], "ssh-ed25519 AAAATEST derived@example")
            self.assertEqual(result["fingerprint"], "SHA256:derived")
            self.assertEqual(result["public_key_path"], "")
            mock_validate_public.assert_not_called()

    @patch.object(r1setup.SSHKeyManager, "_derive_public_key")
    @patch.object(r1setup.SSHKeyManager, "_validate_public_key_file")
    def test_validate_keypair_rejects_mismatched_public_key(self, mock_validate_public, mock_derive):
        with tempfile.TemporaryDirectory() as tmp:
            private_key = Path(tmp) / "id_ed25519"
            private_key.write_text("private-key")

            mock_derive.return_value = {
                "valid": True,
                "content": "ssh-ed25519 AAAATEST derived@example",
                "fingerprint": "SHA256:derived",
            }
            mock_validate_public.return_value = {
                "valid": True,
                "content": "ssh-ed25519 BBBBTEST wrong@example",
                "fingerprint": "SHA256:wrong",
                "path": str((Path(tmp) / "id_ed25519.pub").resolve()),
            }

            result = self.manager._validate_keypair(str(private_key), str(Path(tmp) / "id_ed25519.pub"))

            self.assertFalse(result["valid"])
            self.assertIn("does not match", result["error"])


class TestSSHKeyManagerCapabilities(unittest.TestCase):
    """Tests for feature capability checks."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base_path = Path(self.tempdir.name)
        self.app = MagicMock()
        self.app.config_dir = self.base_path
        self.manager = r1setup.SSHKeyManager(self.app)

    @patch("tests.support.r1setup.shutil.which")
    def test_check_feature_capabilities_reports_missing_playbook(self, mock_which):
        mock_which.return_value = "/usr/bin/fake"
        (self.base_path / "playbooks").mkdir()
        (self.base_path / "playbooks/ssh_install_key.yml").write_text("---\n")

        ok, issues = self.manager.check_feature_capabilities()

        self.assertFalse(ok)
        self.assertTrue(any("missing playbook:" in issue for issue in issues))


class TestSSHKeyManagerInventoryUpdates(unittest.TestCase):
    """Tests for in-memory inventory updates after verification."""

    def setUp(self):
        self.app = MagicMock()
        self.app.inventory = make_inventory(
            {
                "node-1": {
                    "ansible_host": "10.0.0.20",
                    "ansible_user": "root",
                    "ansible_ssh_pass": "secret",
                    "r1setup_ssh_auth_mode": r1setup.SSH_AUTH_MODE_PASSWORD_ONLY,
                }
            }
        )
        self.manager = r1setup.SSHKeyManager(self.app)

    def test_apply_successful_key_migration_switches_inventory_auth(self):
        self.manager._apply_successful_key_migration(
            "node-1",
            "/home/test/.ssh/r1setup_ed25519",
            "SHA256:testfingerprint",
        )

        host = self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-1"]
        self.assertNotIn("ansible_ssh_pass", host)
        self.assertEqual(host["ansible_ssh_private_key_file"], "/home/test/.ssh/r1setup_ed25519")
        self.assertEqual(host["r1setup_ssh_auth_mode"], r1setup.SSH_AUTH_MODE_KEY_VERIFIED)
        self.assertEqual(host["r1setup_ssh_primary_key_fingerprint"], "SHA256:testfingerprint")
        self.assertEqual(host["r1setup_ssh_last_verified_fingerprint"], "SHA256:testfingerprint")
        self.assertEqual(host["r1setup_ssh_last_verification_status"], "success")
        self.assertFalse(host["r1setup_ssh_requires_revalidation"])

    def test_apply_failed_key_verification_keeps_existing_auth(self):
        self.manager._apply_failed_key_verification(
            "node-1",
            "/home/test/.ssh/r1setup_ed25519",
            "SHA256:testfingerprint",
        )

        host = self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-1"]
        self.assertIn("ansible_ssh_pass", host)
        self.assertEqual(host["r1setup_ssh_auth_mode"], r1setup.SSH_AUTH_MODE_VERIFICATION_FAILED)
        self.assertEqual(host["r1setup_ssh_primary_key_path"], "/home/test/.ssh/r1setup_ed25519")
        self.assertEqual(host["r1setup_ssh_primary_key_fingerprint"], "SHA256:testfingerprint")
        self.assertEqual(host["r1setup_ssh_last_verification_status"], "failed")
        self.assertTrue(host["r1setup_ssh_requires_revalidation"])

    def test_get_hosts_ready_for_password_disable_filters_on_verified_fingerprint(self):
        self.app.inventory = make_inventory(
            {
                "ready-node": {
                    "ansible_host": "10.0.0.21",
                    "ansible_user": "root",
                    "ansible_ssh_private_key_file": "/tmp/key1",
                    "r1setup_ssh_auth_mode": r1setup.SSH_AUTH_MODE_KEY_VERIFIED,
                    "r1setup_ssh_primary_key_fingerprint": "SHA256:ready",
                    "r1setup_ssh_last_verified_fingerprint": "SHA256:ready",
                    "r1setup_ssh_requires_revalidation": False,
                },
                "stale-node": {
                    "ansible_host": "10.0.0.22",
                    "ansible_user": "root",
                    "ansible_ssh_private_key_file": "/tmp/key2",
                    "r1setup_ssh_auth_mode": r1setup.SSH_AUTH_MODE_KEY_VERIFIED,
                    "r1setup_ssh_primary_key_fingerprint": "SHA256:new",
                    "r1setup_ssh_last_verified_fingerprint": "SHA256:old",
                    "r1setup_ssh_requires_revalidation": False,
                },
                "needs-revalidation": {
                    "ansible_host": "10.0.0.23",
                    "ansible_user": "root",
                    "ansible_ssh_private_key_file": "/tmp/key3",
                    "r1setup_ssh_auth_mode": r1setup.SSH_AUTH_MODE_KEY_VERIFIED,
                    "r1setup_ssh_primary_key_fingerprint": "SHA256:same",
                    "r1setup_ssh_last_verified_fingerprint": "SHA256:same",
                    "r1setup_ssh_requires_revalidation": True,
                },
            }
        )

        ready = self.manager._get_hosts_ready_for_password_disable()

        self.assertEqual(list(ready.keys()), ["ready-node"])

    def test_apply_successful_password_hardening_sets_password_disabled_state(self):
        self.manager._apply_successful_password_hardening("node-1")

        host = self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-1"]
        self.assertEqual(host["r1setup_ssh_auth_mode"], r1setup.SSH_AUTH_MODE_PASSWORD_DISABLED)
        self.assertTrue(host["r1setup_password_auth_disabled"])
        self.assertEqual(host["r1setup_ssh_last_verification_status"], "success")
        self.assertFalse(host["r1setup_ssh_requires_revalidation"])
        self.assertIn("r1setup_ssh_hardening_applied_at", host)

    def test_apply_failed_password_hardening_marks_host_for_revalidation(self):
        self.manager._apply_failed_password_hardening("node-1")

        host = self.app.inventory["all"]["children"]["gpu_nodes"]["hosts"]["node-1"]
        self.assertEqual(host["r1setup_ssh_auth_mode"], r1setup.SSH_AUTH_MODE_VERIFICATION_FAILED)
        self.assertFalse(host["r1setup_password_auth_disabled"])
        self.assertEqual(host["r1setup_ssh_last_verification_status"], "failed")
        self.assertTrue(host["r1setup_ssh_requires_revalidation"])


if __name__ == "__main__":
    unittest.main()
