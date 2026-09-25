"""Security tests: process.command rules always include process.path.

The prompt dialog's base operator is always process.path. When the
checkArgs checkbox adds a process.command constraint, both operands
must appear in the rule data. This prevents argv[0] spoofing via execve().
"""
import json
from unittest.mock import MagicMock, patch
import threading

from PyQt6 import QtCore

import opensnitch.proto as proto
proto.import_()

from opensnitch.config import Config
from opensnitch.dialogs.prompt import utils, constants


def _make_dialog_with_args(process_args, process_path="/usr/bin/real_binary"):
    from opensnitch.dialogs.prompt.dialog import PromptDialog

    con = MagicMock()
    con.process_args = process_args
    con.process_path = process_path
    con.process_id = 1234
    con.process_cwd = "/tmp"
    con.dst_ip = "127.0.0.1"
    con.dst_host = "localhost"
    con.dst_port = "443"
    con.src_ip = "127.0.0.1"
    con.user_id = 1000
    con.protocol = "tcp"
    con.process_checksums = {"process.hash.md5": "", "process.hash.sha1": ""}

    dialog = MagicMock(spec=PromptDialog)
    dialog.logger = MagicMock()
    dialog._cfg = MagicMock()
    dialog._con = con
    dialog._rules = MagicMock()
    dialog._rules.exists.return_value = False
    dialog._rules.new_unique_name.side_effect = lambda name, peer, s: name
    dialog._peer = "unix:/tmp/osui.sock"
    dialog._done = threading.Event()
    dialog._default_action = Config.ACTION_ALLOW_IDX

    ui_pb2, _ = proto.import_()
    dialog._rule = ui_pb2.Rule(name="user.choice")

    dialog.durationCombo = MagicMock()
    dialog.durationCombo.currentIndex.return_value = 0

    dialog.checkDstIP = MagicMock(); dialog.checkDstIP.isChecked.return_value = False
    dialog.checkDstPort = MagicMock(); dialog.checkDstPort.isChecked.return_value = False
    dialog.checkUserID = MagicMock(); dialog.checkUserID.isChecked.return_value = False
    dialog.checkDstHost = MagicMock(); dialog.checkDstHost.isChecked.return_value = False
    dialog.checkCmdline = MagicMock(); dialog.checkCmdline.isChecked.return_value = False
    dialog.checkPID = MagicMock(); dialog.checkPID.isChecked.return_value = False
    dialog.checkSaveRule = MagicMock(); dialog.checkSaveRule.isChecked.return_value = True

    dialog.checkArgs = MagicMock(); dialog.checkArgs.isChecked.return_value = True
    dialog.checkSum = MagicMock(); dialog.checkSum.isChecked.return_value = False
    dialog.checksumLabel = MagicMock(); dialog.checksumLabel.text.return_value = ""
    dialog._is_list_rule.return_value = True
    dialog.hostCombo = MagicMock(); dialog.hostCombo.isVisible.return_value = False
    dialog.ipCombo = MagicMock(); dialog.ipCombo.isVisible.return_value = False

    dialog.saveGeometry.return_value = QtCore.QByteArray()

    with patch.object(utils, 'get_duration', return_value=Config.DURATION_ONCE), \
         patch.object(utils, 'get_rule_name', return_value="test-rule"):
        PromptDialog._send_rule(dialog)

    return dialog


class TestPromptCommandPathPairing:

    def test_absolute_path_argv0_includes_process_path(self, qapp):
        dialog = _make_dialog_with_args(
            ["/usr/bin/wget", "http://example.com"],
            process_path="/usr/bin/wget"
        )
        rule = dialog._rule
        assert rule.operator.type == Config.RULE_TYPE_LIST
        data = json.loads(rule.operator.data)
        operands = [e["operand"] for e in data]
        assert Config.OPERAND_PROCESS_PATH in operands
        assert Config.OPERAND_PROCESS_COMMAND in operands

    def test_spoofed_absolute_argv0_includes_process_path(self, qapp):
        dialog = _make_dialog_with_args(
            ["/usr/bin/wget", "http://example.com"],
            process_path="/tmp/malware"
        )
        data = json.loads(dialog._rule.operator.data)
        path_entries = [e for e in data if e["operand"] == Config.OPERAND_PROCESS_PATH]
        assert any(e["data"] == "/tmp/malware" for e in path_entries)

    def test_relative_argv0_includes_process_path(self, qapp):
        dialog = _make_dialog_with_args(
            ["wget", "http://example.com"],
            process_path="/usr/bin/wget"
        )
        rule = dialog._rule
        assert rule.operator.type == Config.RULE_TYPE_LIST
        data = json.loads(rule.operator.data)
        operands = [e["operand"] for e in data]
        assert Config.OPERAND_PROCESS_PATH in operands

    def test_proc_path_argv0_includes_process_path(self, qapp):
        dialog = _make_dialog_with_args(
            ["/proc/self/fd/3", "--flag"],
            process_path="/usr/bin/actual"
        )
        data = json.loads(dialog._rule.operator.data)
        operands = [e["operand"] for e in data]
        assert Config.OPERAND_PROCESS_PATH in operands

    def test_process_path_entry_type_is_simple(self, qapp):
        dialog = _make_dialog_with_args(
            ["/usr/bin/wget", "http://example.com"],
            process_path="/usr/bin/wget"
        )
        data = json.loads(dialog._rule.operator.data)
        path_entries = [e for e in data if e["operand"] == Config.OPERAND_PROCESS_PATH]
        assert all(e["type"] == Config.RULE_TYPE_SIMPLE for e in path_entries)
