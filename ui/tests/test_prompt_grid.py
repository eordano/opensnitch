"""Verify every checkbox in the prompt dialog grid behaves correctly."""
import pytest
from unittest.mock import MagicMock
from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon

from opensnitch.dialogs.prompt.dialog import PromptDialog
from opensnitch.dialogs.prompt import constants
from opensnitch.config import Config


def _con(dst_host="www.google.com", dst_ip="142.250.80.46", dst_port=443,
         process_path="/usr/bin/curl", process_args=None, process_id=12345,
         user_id=1000, md5="d41d8cd98f00b204e9800998ecf8427e"):
    con = MagicMock()
    con.protocol = "tcp"
    con.src_ip = "192.168.1.42"
    con.src_port = 48372
    con.dst_ip = dst_ip
    con.dst_host = dst_host
    con.dst_port = dst_port
    con.user_id = user_id
    con.process_id = process_id
    con.process_path = process_path
    con.process_cwd = "/home/user"
    con.process_args = process_args if process_args is not None else [process_path, "https://www.google.com"]
    con.process_env = {}
    con.process_checksums = {
        "process.hash.md5": md5,
        "process.hash.sha1": "",
    }
    return con


class TestGridVisibility:
    """Each checkbox should be visible/hidden based on connection data."""

    @pytest.fixture(autouse=True)
    def setup(self, qapp):
        self.dialog = PromptDialog(appicon=QIcon())

    def _render(self, con):
        d = self.dialog
        d._con = con
        d._local = True
        d._peer = "unix:/tmp/osui.sock"
        d._hostname = "localhost"
        d.stackedWidget.setCurrentIndex(constants.PAGE_MAIN)
        d.reset_widgets()
        d._render_connection(con)

    def test_cmd_visible_with_args(self, qapp):
        self._render(_con(process_args=["/usr/bin/curl", "https://example.com"]))
        assert self.dialog.checkCmdline.isVisibleTo(self.dialog)
        assert self.dialog.checkArgs.isVisibleTo(self.dialog)

    def test_cmd_hidden_no_args(self, qapp):
        self._render(_con(process_args=[]))
        assert not self.dialog.checkCmdline.isVisibleTo(self.dialog)
        assert not self.dialog.checkArgs.isVisibleTo(self.dialog)

    def test_args_hidden_when_only_binary(self, qapp):
        self._render(_con(process_args=["/usr/bin/curl"]))
        assert self.dialog.checkCmdline.isVisibleTo(self.dialog)
        assert not self.dialog.checkArgs.isVisibleTo(self.dialog)

    def test_pid_visible_when_positive(self, qapp):
        self._render(_con(process_id=12345))
        assert self.dialog.checkPID.isVisibleTo(self.dialog)
        assert self.dialog.pidLabel.text() == "12345"

    def test_pid_hidden_when_negative(self, qapp):
        self._render(_con(process_id=-1))
        assert not self.dialog.checkPID.isVisibleTo(self.dialog)

    def test_host_visible_when_differs_from_ip(self, qapp):
        self._render(_con(dst_host="www.google.com", dst_ip="142.250.80.46"))
        assert self.dialog.checkDstHost.isVisibleTo(self.dialog)

    def test_host_hidden_when_same_as_ip(self, qapp):
        self._render(_con(dst_host="142.250.80.46", dst_ip="142.250.80.46"))
        assert not self.dialog.checkDstHost.isVisibleTo(self.dialog)

    def test_host_hidden_when_empty(self, qapp):
        self._render(_con(dst_host="", dst_ip="142.250.80.46"))
        assert not self.dialog.checkDstHost.isVisibleTo(self.dialog)

    def test_ip_always_visible(self, qapp):
        self._render(_con())
        assert self.dialog.checkDstIP.isVisibleTo(self.dialog)

    def test_port_visible_when_nonzero(self, qapp):
        self._render(_con(dst_port=443))
        assert self.dialog.checkDstPort.isVisibleTo(self.dialog)

    def test_port_hidden_when_zero(self, qapp):
        self._render(_con(dst_port=0))
        assert not self.dialog.checkDstPort.isVisibleTo(self.dialog)

    def test_user_always_visible(self, qapp):
        self._render(_con())
        assert self.dialog.checkUserID.isVisibleTo(self.dialog)

    def test_hash_row_visible_with_hash(self, qapp):
        self._render(_con(md5="abc123"))
        assert self.dialog.checksumLabel.isVisibleTo(self.dialog)
        assert self.dialog.checkSum.isVisibleTo(self.dialog)

    def test_hash_row_hidden_without_hash(self, qapp):
        self._render(_con(md5=""))
        assert not self.dialog.checksumLabel.isVisibleTo(self.dialog)
        assert not self.dialog.checkSum.isVisibleTo(self.dialog)

    def test_deny_always_visible(self, qapp):
        self._render(_con())
        assert self.dialog.checkDrop.isVisibleTo(self.dialog)
        assert self.dialog.checkReject.isVisibleTo(self.dialog)

    def test_rule_always_visible(self, qapp):
        self._render(_con())
        assert self.dialog.checkSaveRule.isVisibleTo(self.dialog)


class TestGridMutualExclusion:
    """Mutually exclusive checkboxes should uncheck each other."""

    @pytest.fixture(autouse=True)
    def setup(self, qapp):
        self.dialog = PromptDialog(appicon=QIcon())
        self.dialog._con = _con()
        self.dialog._local = True
        self.dialog._peer = "unix:/tmp/osui.sock"
        self.dialog._hostname = "localhost"
        self.dialog.stackedWidget.setCurrentIndex(constants.PAGE_MAIN)
        self.dialog.reset_widgets()
        self.dialog._render_connection(self.dialog._con)

    def test_host_unchecks_ip(self, qapp):
        self.dialog.checkDstIP.setChecked(True)
        self.dialog.checkDstHost.setChecked(True)
        assert self.dialog.checkDstHost.isChecked()
        assert not self.dialog.checkDstIP.isChecked()

    def test_ip_unchecks_host(self, qapp):
        self.dialog.checkDstHost.setChecked(True)
        self.dialog.checkDstIP.setChecked(True)
        assert self.dialog.checkDstIP.isChecked()
        assert not self.dialog.checkDstHost.isChecked()

    def test_drop_unchecks_reject(self, qapp):
        self.dialog.checkReject.setChecked(True)
        self.dialog.checkDrop.setChecked(True)
        assert self.dialog.checkDrop.isChecked()
        assert not self.dialog.checkReject.isChecked()

    def test_reject_unchecks_drop(self, qapp):
        self.dialog.checkDrop.setChecked(True)
        self.dialog.checkReject.setChecked(True)
        assert self.dialog.checkReject.isChecked()
        assert not self.dialog.checkDrop.isChecked()

    def test_cannot_uncheck_both_deny(self, qapp):
        """Unchecking one should force the other on."""
        self.dialog.checkDrop.setChecked(True)
        self.dialog.checkDrop.setChecked(False)
        assert self.dialog.checkDrop.isChecked() or self.dialog.checkReject.isChecked()


class TestGridRuleEffect:
    """Checking a box should produce the correct constraint in the rule."""

    @pytest.fixture(autouse=True)
    def setup(self, qapp):
        self.dialog = PromptDialog(appicon=QIcon())
        self.dialog._con = _con()
        self.dialog._local = True
        self.dialog._peer = "unix:/tmp/osui.sock"
        self.dialog._hostname = "localhost"
        self.dialog.stackedWidget.setCurrentIndex(constants.PAGE_MAIN)
        self.dialog.reset_widgets()
        self.dialog._render_connection(self.dialog._con)

    def test_rule_unchecked_forces_once(self, qapp):
        self.dialog.checkSaveRule.setChecked(False)
        assert not self.dialog.durationCombo.isVisibleTo(self.dialog)

    def test_rule_checked_shows_duration(self, qapp):
        self.dialog.checkSaveRule.setChecked(True)
        assert self.dialog.durationCombo.isVisibleTo(self.dialog)

    def test_host_combo_shows_wildcard_options(self, qapp):
        self.dialog.checkDstHost.setChecked(True)
        assert self.dialog.hostCombo.count() >= 2
        assert self.dialog.hostCombo.itemText(0) == "www.google.com"
        assert "*.google.com" in self.dialog.hostCombo.itemText(1)

    def test_host_combo_visible_when_checked(self, qapp):
        self.dialog.checkDstHost.setChecked(True)
        assert self.dialog.hostCombo.isVisibleTo(self.dialog)
        assert not self.dialog.dstHostLabel.isVisibleTo(self.dialog)

    def test_host_label_visible_when_unchecked(self, qapp):
        self.dialog.checkDstHost.setChecked(False)
        assert not self.dialog.hostCombo.isVisibleTo(self.dialog)

    def test_ip_combo_shows_wildcard_and_cidr(self, qapp):
        self.dialog.checkDstIP.setChecked(True)
        combo = self.dialog.ipCombo
        assert combo.count() >= 4
        assert combo.itemText(0) == "142.250.80.46"
        texts = [combo.itemText(i) for i in range(combo.count())]
        assert any("*" in t for t in texts)
        assert any("/" in t for t in texts)

    def test_ip_combo_visible_when_checked(self, qapp):
        self.dialog.checkDstIP.setChecked(True)
        assert self.dialog.ipCombo.isVisibleTo(self.dialog)

    def test_ip_label_visible_when_unchecked(self, qapp):
        self.dialog.checkDstIP.setChecked(False)
        assert not self.dialog.ipCombo.isVisibleTo(self.dialog)

    def test_drop_sets_action(self, qapp):
        self.dialog.checkDrop.setChecked(True)
        assert self.dialog._default_action == Config.ACTION_DROP_IDX

    def test_reject_sets_action(self, qapp):
        self.dialog.checkReject.setChecked(True)
        assert self.dialog._default_action == Config.ACTION_REJECT_IDX

    def test_preview_updates_on_host_check(self, qapp):
        self.dialog.checkDstHost.setChecked(True)
        text = self.dialog._preview_label.text()
        assert "www.google.com" in text

    def test_preview_updates_on_port_check(self, qapp):
        self.dialog.checkDstPort.setChecked(True)
        text = self.dialog._preview_label.text()
        assert "443" in text

    def test_preview_updates_on_no_rule(self, qapp):
        self.dialog.checkSaveRule.setChecked(False)
        text = self.dialog._preview_label.text()
        assert "no rule saved" in text

    def test_preview_updates_on_cmdline_check(self, qapp):
        self.dialog.checkCmdline.setChecked(True)
        text = self.dialog._preview_label.text()
        assert "curl" in text.lower()

    def test_preview_updates_on_args_check(self, qapp):
        self.dialog.checkArgs.setChecked(True)
        text = self.dialog._preview_label.text()
        assert "arguments" in text.lower()
