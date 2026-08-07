"""Tests for helpers/session_file.py — IP→username session mapping."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "root", "app", "heimdallr"))

from helpers import session_file


# ── load_sessions() ────────────────────────────────────────────

class TestLoadSessions:
    def test_returns_empty_for_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(session_file, "SESSION_FILE", str(tmp_path / "nonexistent.json"))
        assert session_file.load_sessions() == {}

    def test_returns_parsed_json(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        p.write_text(json.dumps({"10.13.13.2": "alice"}))
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        assert session_file.load_sessions() == {"10.13.13.2": "alice"}

    def test_returns_empty_for_corrupt_json(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        p.write_text("garbage {{{")
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        assert session_file.load_sessions() == {}


# ── save_session() ─────────────────────────────────────────────

class TestSaveSession:
    def test_saves_new_entry(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        session_file.save_session("10.13.13.2", "alice")
        assert session_file.load_sessions() == {"10.13.13.2": "alice"}

    def test_overwrites_existing_entry(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        p.write_text(json.dumps({"10.13.13.2": "alice"}))
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        session_file.save_session("10.13.13.2", "bob")
        assert session_file.load_sessions() == {"10.13.13.2": "bob"}

    def test_adds_second_entry(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        p.write_text(json.dumps({"10.13.13.2": "alice"}))
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        session_file.save_session("10.13.13.3", "bob")
        assert session_file.load_sessions() == {
            "10.13.13.2": "alice",
            "10.13.13.3": "bob",
        }

    def test_creates_file_if_missing(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        assert not p.exists()
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        session_file.save_session("10.13.13.2", "alice")
        assert p.exists()

    def test_handles_corrupt_existing_file(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        p.write_text("not json {{{")
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        # should not raise; should overwrite with fresh data
        session_file.save_session("10.13.13.2", "alice")
        assert session_file.load_sessions() == {"10.13.13.2": "alice"}


# ── remove_session() ───────────────────────────────────────────

class TestRemoveSession:
    def test_removes_existing_entry(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        p.write_text(json.dumps({"10.13.13.2": "alice", "10.13.13.3": "bob"}))
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        session_file.remove_session("10.13.13.2")
        assert session_file.load_sessions() == {"10.13.13.3": "bob"}

    def test_missing_entry_is_noop(self, tmp_path, monkeypatch):
        p = tmp_path / "sessions.json"
        p.write_text(json.dumps({"10.13.13.2": "alice"}))
        monkeypatch.setattr(session_file, "SESSION_FILE", str(p))
        session_file.remove_session("10.13.13.99")
        assert session_file.load_sessions() == {"10.13.13.2": "alice"}

    def test_missing_file_is_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr(session_file, "SESSION_FILE", str(tmp_path / "nonexistent.json"))
        # should not raise
        session_file.remove_session("10.13.13.99")
