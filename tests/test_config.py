"""Tests for config.py — defaults, timeout derivation, and boolean parsing."""

import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "root", "app", "heimdallr"))

import config as _cfg_module


def _reload():
    importlib.reload(_cfg_module)
    return _cfg_module


class TestDefaults:
    """Default values when no environment variables are set."""

    def test_listen_port_defaults_to_8080(self):
        assert _reload().LISTEN_PORT == 8080

    def test_idle_timeout_defaults_to_60(self):
        assert _reload().IDLE_TIMEOUT == 60

    def test_wg_interface_defaults_to_wg0(self):
        assert _reload().WG_INTERFACE == "wg0"

    def test_issuer_name_defaults_to_wireguard_vpn(self):
        assert _reload().ISSUER_NAME == "WireGuard VPN"

    def test_allow_http_defaults_to_false(self):
        assert _reload().ALLOW_HTTP is False

    def test_telegram_disabled_by_default(self):
        cfg = _reload()
        assert cfg.TG_TOKEN == ""
        assert cfg.TG_CHAT_ID == ""


class TestIdleTimeoutDerivation:
    """POLL_INTERVAL and GRACE_POLLS are derived from IDLE_TIMEOUT."""

    def test_timeout_60_derives_poll_20_grace_3(self):
        os.environ["IDLE_TIMEOUT"] = "60"
        cfg = _reload()
        assert cfg.POLL_INTERVAL == 20       # 60 // 3
        assert cfg.GRACE_POLLS == 3          # ceil(60 / 20)

    def test_timeout_10_clamps_poll_to_5(self):
        os.environ["IDLE_TIMEOUT"] = "10"
        cfg = _reload()
        assert cfg.POLL_INTERVAL == 5        # clamped to minimum
        assert cfg.GRACE_POLLS == 2          # ceil(10 / 5)

    def test_timeout_300_clamps_poll_to_30(self):
        os.environ["IDLE_TIMEOUT"] = "300"
        cfg = _reload()
        assert cfg.POLL_INTERVAL == 30       # clamped to maximum
        assert cfg.GRACE_POLLS >= 2

    def test_poll_override_respected(self):
        os.environ["IDLE_TIMEOUT"] = "60"
        os.environ["POLL_INTERVAL"] = "7"
        cfg = _reload()
        assert cfg.POLL_INTERVAL == 7        # explicit override
        assert cfg.GRACE_POLLS >= 2

    def test_grace_minimum_is_two(self):
        os.environ["IDLE_TIMEOUT"] = "2"
        os.environ["POLL_INTERVAL"] = "1"
        cfg = _reload()
        assert cfg.GRACE_POLLS == 2          # never below 2


class TestAllowHttpParsing:
    """ALLOW_HTTP is a tri‑state boolean: unset -> false, else truthy."""

    @pytest.mark.parametrize("val", ["1", "true", "yes"])
    def test_truthy_values(self, val):
        os.environ["ALLOW_HTTP"] = val
        cfg = _reload()
        assert cfg.ALLOW_HTTP is True

    @pytest.mark.parametrize("val", ["0", "false", "no", ""])
    def test_falsey_values_stay_false(self, val):
        os.environ["ALLOW_HTTP"] = val
        cfg = _reload()
        assert cfg.ALLOW_HTTP is False
