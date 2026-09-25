"""The Nodes page says what it lists, and a node that no longer connects can
be forgotten."""
from unittest.mock import patch

import pytest
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtGui import QIcon
from PyQt6.QtSql import QSqlQuery

import opensnitch.proto as proto
proto.import_()

from opensnitch.database import Database
from opensnitch.dialogs.events.dialog import StatsDialog
from opensnitch.dialogs.events import constants

OLD = "ipv4:10.9.9.9:50051"
LIVE = "unix:/tmp/osui.sock"


def _sql(sql, binds=()):
    q = QSqlQuery(Database.instance().get_db())
    q.prepare(sql)
    for i, b in enumerate(binds):
        q.bindValue(i, b)
    assert q.exec(), q.lastError().text()
    return q


def _count(sql, binds=()):
    q = _sql(sql, binds)
    q.next()
    return q.value(0)


def _insert_node(addr, hostname, status):
    _sql("INSERT OR REPLACE INTO nodes (addr, hostname, daemon_version, daemon_uptime, daemon_rules, cons, cons_dropped, version, status, last_connection) "
         "VALUES (?, ?, '1.6.6', '1h', '1', '1', '0', '1.6.6', ?, '2026-05-17 11:30:00')", (addr, hostname, status))
    _sql("INSERT OR IGNORE INTO connections (time, node, action, protocol, src_ip, src_port, dst_ip, dst_host, dst_port, uid, pid, process, process_args, process_cwd, rule) "
         "VALUES ('2026-05-17 11:31:00', ?, 'allow', 'tcp', '10.0.0.5', '1', '1.1.1.1', 'x', '443', '1000', '1', '/bin/x', 'x', '/', 'r')", (addr,))


@pytest.fixture(scope="module")
def dialog(qapp):
    d = StatsDialog(db=Database.instance(), appicon=QIcon())
    d.show()
    d.resize(1280, 800)
    qapp.processEvents()
    yield d
    d.hide()


def _row_of(dialog, addr):
    model = dialog.nodesTable.model()
    for r in range(model.rowCount()):
        if model.index(r, constants.COL_NODE).data() == addr:
            return model.index(r, constants.COL_NODE)
    return None


def test_nodes_page_says_what_it_lists(dialog, qapp):
    dialog.set_current_tab(constants.TAB_NODES)
    qapp.processEvents()
    lbl = dialog.nodesDescription
    assert lbl.text() == "Every daemon that has connected to this interface, with its version and settings."
    assert lbl.isVisibleTo(dialog)
    page = dialog.stackedWidget.widget(constants.TAB_NODES)
    assert lbl.parentWidget() is page
    assert lbl.y() < dialog.nodesTable.mapTo(page, QtCore.QPoint(0, 0)).y()


def test_forget_node_asks_and_removes_an_offline_node(dialog, qapp):
    _insert_node(OLD, "old-box", "offline")
    dialog.set_current_tab(constants.TAB_NODES)
    dialog.refresh_active_table()
    qapp.processEvents()
    assert _row_of(dialog, OLD) is not None
    cancel = QtWidgets.QMessageBox.StandardButton.Cancel
    yes = QtWidgets.QMessageBox.StandardButton.Yes
    with patch("opensnitch.utils.Message.yes_no", return_value=cancel) as ask:
        assert dialog.forget_node(OLD) is False
        assert "'" not in ask.call_args.args[0] + ask.call_args.args[1]
    assert _count("SELECT count(*) FROM nodes WHERE addr = ?", (OLD,)) == 1
    with patch("opensnitch.utils.Message.yes_no", return_value=yes):
        assert dialog.forget_node(OLD) is True
    assert _count("SELECT count(*) FROM nodes WHERE addr = ?", (OLD,)) == 0
    assert _count("SELECT count(*) FROM connections WHERE node = ?", (OLD,)) == 0
    qapp.processEvents()
    assert _row_of(dialog, OLD) is None


def test_a_connected_node_cannot_be_forgotten(dialog):
    with patch("opensnitch.utils.Message.yes_no", return_value=QtWidgets.QMessageBox.StandardButton.Yes) as ask:
        assert dialog.forget_node(LIVE) is False
        ask.assert_not_called()


def test_context_menu_offers_forget_on_offline_rows_only(dialog, qapp):
    _insert_node(OLD, "old-box", "offline")
    _insert_node(LIVE, "live-box", "online")
    dialog.set_current_tab(constants.TAB_NODES)
    dialog.refresh_active_table()
    qapp.processEvents()
    seen = {}

    def fake_exec(menu, pos):
        seen["actions"] = [(a.text(), a.isEnabled()) for a in menu.actions()]

    with patch.object(QtWidgets.QMenu, "exec", fake_exec):
        dialog._cb_nodes_table_context_menu(dialog.nodesTable.visualRect(_row_of(dialog, OLD)).center())
        assert seen["actions"] == [("Forget node old-box", True)]
        dialog._cb_nodes_table_context_menu(dialog.nodesTable.visualRect(_row_of(dialog, LIVE)).center())
        assert seen["actions"] == [("Forget node (it is connected)", False)]
        seen.clear()
        dialog._cb_nodes_table_context_menu(QtCore.QPoint(5, dialog.nodesTable.viewport().height() - 2))
        assert seen == {}
    with patch("opensnitch.utils.Message.yes_no", return_value=QtWidgets.QMessageBox.StandardButton.Yes):
        dialog.forget_node(OLD)
    _sql("DELETE FROM nodes WHERE addr = ?", (LIVE,))
