"""Tests for helpers/secrets.py — credential file I/O."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "root", "app", "heimdallr"))

from helpers import secrets as secrets_file


# ── load() ─────────────────────────────────────────────────────

class TestLoad:
    def test_returns_parsed_dict(self, tmp_path, monkeypatch):
        p = tmp_path / "secrets.json"
        payload = {"alice": {"password": "hash", "totp": "secret"}}
        p.write_text(json.dumps(payload))
        monkeypatch.setattr(secrets_file, "SECRETS_FILE", str(p))
        assert secrets_file.load() == payload

    def test_returns_empty_for_missing_file(self, monkeypatch):
        monkeypatch.setattr(secrets_file, "SECRETS_FILE", "/nonexistent/path.json")
        assert secrets_file.load() == {}

    def test_returns_empty_for_empty_json_object(self, tmp_path, monkeypatch):
        p = tmp_path / "secrets.json"
        p.write_text("{}")
        monkeypatch.setattr(secrets_file, "SECRETS_FILE", str(p))
        assert secrets_file.load() == {}

    def test_returns_empty_for_corrupt_json(self, tmp_path, monkeypatch):
        p = tmp_path / "secrets.json"
        p.write_text("not valid json {{{")
        monkeypatch.setattr(secrets_file, "SECRETS_FILE", str(p))
        assert secrets_file.load() == {}

    def test_returns_empty_for_empty_file(self, tmp_path, monkeypatch):
        p = tmp_path / "secrets.json"
        p.write_text("")
        monkeypatch.setattr(secrets_file, "SECRETS_FILE", str(p))
        assert secrets_file.load() == {}


# ── save() ─────────────────────────────────────────────────────

class TestSave:
    def test_writes_correct_json(self, tmp_path, monkeypatch):
        p = tmp_path / "sub" / "secrets.json"
        monkeypatch.setattr(secrets_file, "SECRETS_FILE", str(p))
        data = {"bob": {"password": "hash123", "totp": "TOTPSECRET"}}
        secrets_file.save(data)
        assert json.loads(p.read_text()) == data

    def test_creates_parent_directories(self, tmp_path, monkeypatch):
        p = tmp_path / "deep" / "nested" / "secrets.json"
        monkeypatch.setattr(secrets_file, "SECRETS_FILE", str(p))
        secrets_file.save({"u": {"password": "h", "totp": "t"}})
        assert p.exists()

    def test_output_is_readable_by_load(self, tmp_path, monkeypatch):
        p = tmp_path / "secrets.json"
        monkeypatch.setattr(secrets_file, "SECRETS_FILE", str(p))
        data = {"c": {"password": "h", "totp": "t"}}
        secrets_file.save(data)
        reloaded = secrets_file.load()
        assert reloaded == data
