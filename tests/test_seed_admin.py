"""Tests for seed_admin.py — single-user account seeding."""

import json
import os
import string
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "root", "app", "heimdallr"))

import seed_admin

from config import USERNAME as DEFAULT_USERNAME


class TestPasswordGeneration:
    """generate_password() produces usable random passwords."""

    def test_random_password_is_sixteen_characters(self):
        pw = seed_admin.generate_password()
        assert len(pw) == 16

    def test_password_contains_all_character_classes(self):
        pw = seed_admin.generate_password()
        assert any(c.islower() for c in pw)
        assert any(c.isupper() for c in pw)
        assert any(c.isdigit() for c in pw)
        assert any(c in string.punctuation for c in pw)

    def test_consecutive_calls_produce_different_passwords(self):
        p1 = seed_admin.generate_password()
        p2 = seed_admin.generate_password()
        assert p1 != p2


class TestSeeding:
    """main() creates or skips the account."""

    def test_creates_secrets_if_file_missing(self, tmp_path, monkeypatch):
        """File doesn't exist -> create it with generated credentials."""
        secrets_file = tmp_path / "subdir" / "secrets.json"
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "admin")
        monkeypatch.setattr(seed_admin, "PASSWORD", "")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "")

        seed_admin.main()

        assert secrets_file.exists()
        data = json.loads(secrets_file.read_text())
        assert "admin" in data
        assert "password" in data["admin"]
        assert "totp" in data["admin"]

    def test_creates_secrets_if_file_is_empty_json(self, tmp_path, monkeypatch):
        """Empty JSON file -> same as missing, create account."""
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text("{}")
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "admin")
        monkeypatch.setattr(seed_admin, "PASSWORD", "")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "")

        seed_admin.main()

        data = json.loads(secrets_file.read_text())
        assert "admin" in data

    def test_skips_if_stored_has_valid_credentials(self, tmp_path, monkeypatch):
        """Stored file has password + totp -> leave it alone."""
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(
            '{"alice": {"password": "some-hash", "totp": "BASE32SECRET"}}'
        )
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "alice")
        monkeypatch.setattr(seed_admin, "PASSWORD", "")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "")

        seed_admin.main()

        data = json.loads(secrets_file.read_text())
        assert data == {"alice": {"password": "some-hash", "totp": "BASE32SECRET"}}

    def test_updates_if_username_changed_via_env(self, tmp_path, monkeypatch):
        """Stored has 'alice', env says 'bob' -> update account."""
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(
            '{"alice": {"password": "old-hash", "totp": "OLDKEY"}}'
        )
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "bob")
        monkeypatch.setattr(seed_admin, "PASSWORD", "")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "")

        seed_admin.main()

        data = json.loads(secrets_file.read_text())
        assert "bob" in data
        assert "alice" not in data
        # Should have kept old TOTP from stored
        assert data["bob"]["totp"] == "OLDKEY"

    def test_uses_env_password_when_set(self, tmp_path, monkeypatch):
        """Explicit PASSWORD env var -> hash it and store."""
        secrets_file = tmp_path / "secrets.json"
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "root")
        monkeypatch.setattr(seed_admin, "PASSWORD", "my-password")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "MYTOTPSECRET")

        seed_admin.main()

        data = json.loads(secrets_file.read_text())
        assert "root" in data
        assert data["root"]["totp"] == "MYTOTPSECRET"
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        ph.verify(data["root"]["password"], "my-password")

    def test_generates_random_password_when_env_empty(self, tmp_path, monkeypatch):
        """No PASSWORD env var -> generate one, store the hash."""
        secrets_file = tmp_path / "secrets.json"
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "admin")
        monkeypatch.setattr(seed_admin, "PASSWORD", "")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "")

        seed_admin.main()

        data = json.loads(secrets_file.read_text())
        # Argon2 hash is long
        assert len(data["admin"]["password"]) > 20

    def test_handles_corrupt_secrets_file(self, tmp_path, monkeypatch):
        """Corrupt JSON -> treat as missing, create new account."""
        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text("not valid json {{{")
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "admin")
        monkeypatch.setattr(seed_admin, "PASSWORD", "")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "")

        seed_admin.main()

        data = json.loads(secrets_file.read_text())
        assert "admin" in data

    def test_updates_if_password_changed_via_env(self, tmp_path, monkeypatch):
        """Stored has hash of 'oldpass', env says 'newpass' -> update."""
        from argon2 import PasswordHasher
        ph = PasswordHasher()
        old_hash = ph.hash("oldpass")

        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(
            '{{"alice": {{"password": "{}", "totp": "KEY"}}}}'.format(old_hash)
        )
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "alice")
        monkeypatch.setattr(seed_admin, "PASSWORD", "newpass")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "")

        seed_admin.main()

        data = json.loads(secrets_file.read_text())
        assert "alice" in data
        # Old password should no longer verify
        with pytest.raises(Exception):
            ph.verify(data["alice"]["password"], "oldpass")
        # New password should verify
        ph.verify(data["alice"]["password"], "newpass")
        # TOTP should be unchanged
        assert data["alice"]["totp"] == "KEY"

    def test_updates_if_totp_changed_via_env(self, tmp_path, monkeypatch):
        """Stored has 'OLDKEY', env says 'NEWKEY' -> update."""
        from argon2 import PasswordHasher
        ph = PasswordHasher()

        secrets_file = tmp_path / "secrets.json"
        secrets_file.write_text(
            '{{"alice": {{"password": "{}", "totp": "OLDKEY"}}}}'
                .format(ph.hash("password"))
        )
        monkeypatch.setattr(seed_admin.secrets, "SECRETS_FILE", str(secrets_file))
        monkeypatch.setattr(seed_admin, "USERNAME", "alice")
        monkeypatch.setattr(seed_admin, "PASSWORD", "")
        monkeypatch.setattr(seed_admin, "TOTP_SECRET", "NEWKEY")

        seed_admin.main()

        data = json.loads(secrets_file.read_text())
        assert data["alice"]["totp"] == "NEWKEY"
        # Password should be unchanged
        ph.verify(data["alice"]["password"], "password")
