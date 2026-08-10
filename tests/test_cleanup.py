"""Tests for cleanup.py — wg dump parsing and revocation."""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "root", "app", "heimdallr"))

import cleanup
from helpers import session_file


# ── Sample data ────────────────────────────────────────────────
# `wg show wg0 dump` output — header line + three peers
WG_DUMP = (
    "wg0\tkey1\t51820\n"                                          # interface line
    "peer1\tpsk1\t1.2.3.4:51820\t10.13.13.2/32\t1752\t50000\t8000\t0\n"
    "peer2\tpsk2\t5.6.7.8:51820\t10.13.13.3/32,fd00::2/128\t1753\t0\t12000\t5\n"
    "peer3\tpsk3\t9.10.11.12:51820\t10.13.13.4/32\t0\t99999\t500\t0\n"
)

# ── rx_data() tests ────────────────────────────────────────────

class TestRxData:
    """Parsing of `wg show wg0 dump` into {ip: rx_bytes}."""

    def test_extracts_ip_and_rx(self, mock_run):
        mock_run.return_value.stdout = WG_DUMP
        result = cleanup.rx_data()
        assert result == {
            "10.13.13.2": 50000,
            "10.13.13.3": 0,
            "10.13.13.4": 99999,
        }

    def test_handles_empty_dump(self, mock_run):
        mock_run.return_value.stdout = "wg0\tkey1\t51820\n"
        result = cleanup.rx_data()
        assert result == {}

    def test_handles_command_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "wg")
        result = cleanup.rx_data()
        assert result == {}

    def test_skips_peer_without_ipv4(self, mock_run):
        """A peer with only IPv6 should be skipped."""
        dump = (
            "wg0\tkey1\t51820\n"
            "peer1\tpsk\t1.2.3.4:51820\tfd00::2/128\t1752\t500\t800\t0\n"
        )
        mock_run.return_value.stdout = dump
        result = cleanup.rx_data()
        assert result == {}

    def test_malformed_line_skipped(self, mock_run):
        """A line with too few columns is ignored."""
        dump = "wg0\tkey1\t51820\npeer1\tpsk\n"
        mock_run.return_value.stdout = dump
        result = cleanup.rx_data()
        assert result == {}


# ── revoke() tests ─────────────────────────────────────────────

class TestRevoke:
    """Revocation removes the IP from nftables and cleans state."""

    def test_removes_ip_from_nft(self, mock_run, mock_popen, tmp_path, monkeypatch):
        mock_run.return_value.returncode = 0
        monkeypatch.setattr(session_file, "SESSION_FILE", str(tmp_path / "sessions.json"))

        cleanup.prev["10.13.13.2"] = 50000
        cleanup.idle["10.13.13.2"] = 3

        cleanup.revoke("10.13.13.2", "frozen")
        assert "10.13.13.2" not in cleanup.prev
        assert "10.13.13.2" not in cleanup.idle

    def test_nft_failure_preserves_state(self, mock_run, mock_popen):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "error"
        cleanup.prev["10.13.13.2"] = 50000
        cleanup.revoke("10.13.13.2", "frozen")
        assert "10.13.13.2" in cleanup.prev  # state preserved

    def test_skip_nft_skips_delete(self, mock_run, mock_popen, tmp_path, monkeypatch):
        monkeypatch.setattr(session_file, "SESSION_FILE", str(tmp_path / "sessions.json"))
        cleanup.prev["10.13.13.2"] = 50000
        cleanup.revoke("10.13.13.2", "logout", skip_nft=True)
        mock_run.assert_not_called()  # nft delete was never attempted
