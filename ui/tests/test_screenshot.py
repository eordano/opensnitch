"""Take screenshots of the real PromptDialog exercising the real render path."""
import pytest
from unittest.mock import MagicMock
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtGui import QIcon

from opensnitch.dialogs.prompt.dialog import PromptDialog
from opensnitch.dialogs.prompt import constants
from tests.paths import screenshot_path


def _con(dst_host="www.google.com", dst_ip="142.250.80.46", dst_port=443,
         process_path="/nix/store/sm2nq18jjqp4x0sxpl6lrvwl9rx6mvj2-curl-8.19.0-bin/bin/curl",
         process_args=None, process_id=12345, md5="d41d8cd98f00b204e9800998ecf8427e"):
    con = MagicMock()
    con.protocol = "tcp"
    con.src_ip = "192.168.1.42"
    con.src_port = 48372
    con.dst_ip = dst_ip
    con.dst_host = dst_host
    con.dst_port = dst_port
    con.user_id = 1000
    con.process_id = process_id
    con.process_path = process_path
    con.process_cwd = "/home/user"
    con.process_args = process_args if process_args is not None else [process_path, "https://www.google.com"]
    con.process_env = {}
    con.process_checksums = {"process.hash.md5": md5, "process.hash.sha1": ""}
    return con


def _save(dialog, name):
    dialog.show()
    dialog.resize(700, 500)
    QtWidgets.QApplication.processEvents()
    path = screenshot_path(f"prompt_{name}")
    dialog.grab().save(path)
    dialog.hide()


class TestScreenshots:
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
        d._update_preview()

    def test_screenshot_host_port(self, qapp):
        """Typical web rule: HOST + PORT checked."""
        self._render(_con())
        self.dialog.checkDstHost.setChecked(True)
        self.dialog.checkDstPort.setChecked(True)
        self.dialog._update_preview()
        _save(self.dialog, "host_port")

    def test_screenshot_ip_cidr(self, qapp):
        """IP checked with CIDR subnet selected."""
        self._render(_con())
        self.dialog.checkDstIP.setChecked(True)
        if self.dialog.ipCombo.count() > 4:
            self.dialog.ipCombo.setCurrentIndex(4)
        self.dialog.checkDstPort.setChecked(True)
        self.dialog._update_preview()
        _save(self.dialog, "ip_cidr")

    def test_screenshot_no_rule(self, qapp):
        """ADD RULE unchecked -- once, no rule saved."""
        self._render(_con())
        self.dialog.checkSaveRule.setChecked(False)
        _save(self.dialog, "no_rule")

    def test_screenshot_cmdline_wildcard_host(self, qapp):
        """CMD + ARGS + wildcard HOST."""
        self._render(_con())
        self.dialog.checkCmdline.setChecked(True)
        self.dialog.checkArgs.setChecked(True)
        self.dialog.checkDstHost.setChecked(True)
        if self.dialog.hostCombo.count() > 1:
            self.dialog.hostCombo.setCurrentIndex(1)
        self.dialog._update_preview()
        _save(self.dialog, "cmdline_wildcard")

    def test_screenshot_no_hash(self, qapp):
        """Connection without MD5 hash -- HASH row hidden."""
        self._render(_con(md5=""))
        self.dialog.checkDstHost.setChecked(True)
        self.dialog.checkDstPort.setChecked(True)
        self.dialog._update_preview()
        _save(self.dialog, "no_hash")

    def test_screenshot_no_hostname(self, qapp):
        """Direct IP connection -- HOST row hidden."""
        self._render(_con(dst_host="8.8.8.8", dst_ip="8.8.8.8", dst_port=53))
        self.dialog.checkDstIP.setChecked(True)
        self.dialog.checkDstPort.setChecked(True)
        self.dialog._update_preview()
        _save(self.dialog, "no_hostname")
