"""Create rule from several selected connections: the button names what they
share and the editor opens with only those fields."""
import random
from unittest.mock import patch

import pytest
from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon
from PyQt6.QtSql import QSqlQuery

import opensnitch.proto as proto
proto.import_()

from opensnitch.config import Config
from opensnitch.database import Database
from opensnitch.dialogs.events.dialog import StatsDialog
from opensnitch.dialogs.events import constants


@pytest.fixture(scope="module")
def dialog(qapp):
    from tests.sample_data import populate_database
    random.seed(3)
    populate_database(Database.instance(), connection_count=200, socket_count=5)
    q = QSqlQuery(Database.instance().get_db())
    for row in (
        ("2026-05-18 09:00:00", "unix:/tmp/osui.sock", "allow", "tcp", "10.0.0.1", "40000", "1.1.1.1", "one.example", "443", "1000", "11", "/opt/one", "one", "/", "r1"),
        ("2026-05-18 09:00:01", "unix:/tmp/osui.sock", "deny", "udp", "10.0.0.2", "40001", "2.2.2.2", "two.example", "53", "1001", "12", "/opt/two", "two", "/", "r2"),
        ("2026-05-18 09:00:02", "unix:/tmp/osui.sock", "allow", "tcp", "10.0.0.1", "40002", "1.1.1.1", "one.example", "443", "1000", "13", "/opt/one", "one --again", "/", "r1"),
        ("2026-05-18 09:00:03", "unix:/tmp/osui.sock", "allow", "tcp", "10.0.0.1", "40003", "1.1.1.1", "one.example", "8443", "1000", "14", "/opt/one", "one --third", "/", "r1"),
    ):
        q.prepare("INSERT OR IGNORE INTO connections (time, node, action, protocol, src_ip, src_port, dst_ip, dst_host, dst_port, uid, pid, process, process_args, process_cwd, rule) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)")
        for i, v in enumerate(row):
            q.bindValue(i, v)
        assert q.exec(), q.lastError().text()
    q.finish()
    d = StatsDialog(db=Database.instance(), appicon=QIcon())
    d.show()
    d.resize(1280, 800)
    qapp.processEvents()
    d.set_current_tab(constants.TAB_MAIN)
    d.filterBar.clearAll()
    d.refresh_active_table()
    qapp.processEvents()
    yield d
    d.hide()


def _select_times(dialog, times):
    table = dialog.eventsTable
    table.clearSelection()
    table._rows_selection = set(times)
    dialog._cb_events_selection_updated(len(times))


def _operators(rule):
    if rule.operator.type == Config.RULE_TYPE_LIST:
        return {(op.operand, op.data) for op in rule.operator.list}
    return {(rule.operator.operand, rule.operator.data)}


def test_shared_values_caption_and_editor(dialog):
    _select_times(dialog, ["2026-05-18 09:00:00", "2026-05-18 09:00:02"])
    bar = dialog.bulkActionBar
    assert bar.isVisibleTo(dialog) and bar._create_rule_btn.isEnabled()
    shared = dialog.shared_selection_fields()
    assert shared == {"process": "/opt/one", "dst_host": "one.example", "dst_ip": "1.1.1.1",
                      "dst_port": "443", "protocol": "tcp", "uid": "1000", "node": "unix:/tmp/osui.sock"}
    assert bar.createRuleCaption() == "Create rule to /opt/one one.example 1.1.1.1 …"
    assert "443" in bar._create_rule_btn.toolTip() and "'" not in bar._create_rule_btn.toolTip()

    editor = dialog._rules_dialog
    with patch.object(editor, "show") as shown:
        dialog._cb_bulk_create_rule()
        shown.assert_called_once()
    assert editor.procCheck.isChecked() and editor.procLine.text() == "/opt/one"
    assert editor.dstHostCheck.isChecked() and editor.dstHostLine.text() == "one.example"
    assert editor.dstPortCheck.isChecked() and editor.dstPortLine.text() == "443"
    assert editor.dstIPCheck.isChecked() and editor.dstIPCombo.currentText() == "1.1.1.1"
    assert editor.protoCheck.isChecked() and editor.protoCombo.currentText() == "TCP"
    assert editor.uidCheck.isChecked() and editor.uidCombo.currentText() == "1000"
    assert not editor.cmdlineCheck.isChecked() and not editor.pidCheck.isChecked() and not editor.srcIPCheck.isChecked()
    ok, err = editor.save_rule()
    assert ok, err
    ops = _operators(editor.rule)
    assert (Config.OPERAND_PROCESS_PATH, "/opt/one") in ops
    assert (Config.OPERAND_DEST_HOST, "one.example") in ops
    assert (Config.OPERAND_DEST_PORT, "443") in ops
    assert not any(op[0] in (Config.OPERAND_PROCESS_COMMAND, Config.OPERAND_PROCESS_ID) for op in ops)


def test_partly_shared_rows_keep_only_the_common_fields(dialog):
    _select_times(dialog, ["2026-05-18 09:00:00", "2026-05-18 09:00:02", "2026-05-18 09:00:03"])
    shared = dialog.shared_selection_fields()
    assert "dst_port" not in shared and shared["process"] == "/opt/one"
    editor = dialog._rules_dialog
    with patch.object(editor, "show"):
        dialog._cb_bulk_create_rule()
    assert editor.procCheck.isChecked() and not editor.dstPortCheck.isChecked()
    ok, err = editor.save_rule()
    assert ok, err
    assert not any(op[0] == Config.OPERAND_DEST_PORT for op in _operators(editor.rule))


def test_nothing_shared_keeps_the_plain_caption_disabled(dialog):
    _select_times(dialog, ["2026-05-18 09:00:00", "2026-05-18 09:00:01"])
    bar = dialog.bulkActionBar
    assert dialog.shared_selection_fields() == {"node": "unix:/tmp/osui.sock"}
    assert bar.createRuleCaption() == "Create rule..."
    assert not bar._create_rule_btn.isEnabled()


def test_one_row_keeps_todays_behaviour(dialog):
    _select_times(dialog, ["2026-05-18 09:00:00"])
    bar = dialog.bulkActionBar
    assert bar.createRuleCaption() == "Create rule..." and bar._create_rule_btn.isEnabled()
    editor = dialog._rules_dialog
    with patch.object(editor, "show"), patch.object(editor, "new_rule_from_connection", return_value=True) as one:
        dialog.detailPanel.showConnection({"time": "2026-05-18 09:00:00"})
        dialog._cb_bulk_create_rule()
        one.assert_called_once_with("2026-05-18 09:00:00")
    _select_times(dialog, [])
    assert not bar.isVisibleTo(dialog)
