"""Tests for helpers/nft.py — nftables set manipulation."""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "root", "app", "heimdallr"))

from helpers import nft


# ── Sample nft output ─────────────────────────────────────────

NFT_SET = (
    "table inet vpn {\n"
    "\tset allowed_clients {\n"
    "\t\ttype ipv4_addr\n"
    "\t\telements = { 10.13.13.2, 10.13.13.5 }\n"
    "\t}\n"
    "}\n"
)

NFT_SET_EMPTY = (
    "table inet vpn {\n"
    "\tset allowed_clients {\n"
    "\t\ttype ipv4_addr\n"
    "\t}\n"
    "}\n"
)


# ── add_ip() ───────────────────────────────────────────────────

class TestAddIp:
    def test_successful_add_returns_true(self, mock_run):
        mock_run.return_value.returncode = 0
        ok = nft.add_ip("10.13.13.2")
        assert ok is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "add" in args
        assert "element" in args
        assert "10.13.13.2" in args[-1]

    def test_failed_add_returns_false(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "nft", stderr="error")
        ok = nft.add_ip("10.13.13.99")
        assert ok is False


# ── remove_ip() ────────────────────────────────────────────────

class TestRemoveIp:
    def test_successful_remove_returns_true(self, mock_run):
        mock_run.return_value.returncode = 0
        ok = nft.remove_ip("10.13.13.2")
        assert ok is True

    def test_failed_remove_returns_false(self, mock_run):
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "No such element"
        ok = nft.remove_ip("10.13.13.99")
        assert ok is False


# ── is_authenticated() ─────────────────────────────────────────

class TestIsAuthenticated:
    def test_ip_found_in_set(self, mock_run):
        mock_run.return_value.stdout = NFT_SET
        assert nft.is_authenticated("10.13.13.2") is True

    def test_ip_not_found(self, mock_run):
        mock_run.return_value.stdout = NFT_SET
        assert nft.is_authenticated("10.13.13.99") is False

    def test_empty_set(self, mock_run):
        mock_run.return_value.stdout = NFT_SET_EMPTY
        assert nft.is_authenticated("10.13.13.2") is False

    def test_command_failure_returns_false(self, mock_run):
        mock_run.side_effect = Exception("nft not found")
        assert nft.is_authenticated("10.13.13.2") is False


# ── allowed_ips() ──────────────────────────────────────────────

class TestAllowedIps:
    def test_extracts_ips(self, mock_run):
        mock_run.return_value.stdout = NFT_SET
        result = nft.allowed_ips()
        assert result == {"10.13.13.2", "10.13.13.5"}

    def test_empty_set(self, mock_run):
        mock_run.return_value.stdout = NFT_SET_EMPTY
        result = nft.allowed_ips()
        assert result == set()

    def test_command_failure(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, "nft")
        result = nft.allowed_ips()
        assert result == set()

    def test_single_element(self, mock_run):
        output = (
            "table inet vpn {\n"
            "\tset allowed_clients {\n"
            "\t\ttype ipv4_addr\n"
            "\t\telements = { 10.0.0.2 }\n"
            "\t}\n"
            "}\n"
        )
        mock_run.return_value.stdout = output
        result = nft.allowed_ips()
        assert result == {"10.0.0.2"}
