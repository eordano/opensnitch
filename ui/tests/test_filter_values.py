"""After `field:` the filter box offers the values that column holds in the
connections the current chips leave."""
import random

import pytest
from PyQt6 import QtWidgets, QtCore, QtTest
from PyQt6.QtGui import QIcon
from PyQt6.QtSql import QSqlQuery

import opensnitch.proto as proto
proto.import_()

from opensnitch.database import Database
from opensnitch.dialogs.events.dialog import StatsDialog
from opensnitch.dialogs.events import constants


def _count(sql, binds=()):
    q = QSqlQuery(Database.instance().get_db())
    q.prepare(sql)
    for i, b in enumerate(binds):
        q.bindValue(i, b)
    assert q.exec(), q.lastError().text()
    q.next()
    return q.value(0)


@pytest.fixture(scope="module")
def dialog(qapp):
    from tests.sample_data import populate_database
    random.seed(11)
    populate_database(Database.instance(), connection_count=200, socket_count=5)
    d = StatsDialog(db=Database.instance(), appicon=QIcon())
    d.show()
    d.resize(1280, 800)
    qapp.processEvents()
    d.set_current_tab(constants.TAB_MAIN)
    d.filterBar.clearAll()
    yield d
    d.hide()


def test_values_come_from_the_column_prefix_filtered_case_insensitively(dialog):
    actions = dialog.filter_values("action", "")
    assert "deny" in actions and "allow" in actions and set(actions) <= {"allow", "deny", "reject"}
    assert dialog.filter_values("action", "D") == ["deny"]
    assert dialog.filter_values("action", "de") == ["deny"]
    assert dialog.filter_values("process", "/USR/BIN/F") == ["/usr/bin/firefox"]
    assert dialog.filter_values("cmd", "git ") == ["git fetch origin main"]
    assert dialog.filter_values("nope", "") == []
    hosts = dialog.filter_values("dst", "")
    assert hosts == sorted(hosts) and 0 < len(hosts) <= dialog.FILTER_VALUES_LIMIT
    assert dialog.filter_values("dst", "zzz-no-such-host") == []


def test_values_respect_the_applied_chips(dialog):
    dialog.filterBar.setFilter("action", "deny")
    try:
        hosts = dialog.filter_values("dst", "")
        assert hosts
        for host in hosts:
            assert _count("SELECT count(*) FROM connections WHERE dst_host = ? AND action = 'deny'", (host,)) > 0
        every_host = set(dialog.filter_values("dst", "")) | {"github.com", "api.github.com"}
        dialog.filterBar.clearAll()
        assert every_host <= set(dialog.filter_values("dst", ""))
    finally:
        dialog.filterBar.clearAll()


def test_the_node_chip_does_not_hide_the_other_nodes(dialog):
    nodes = dialog.filter_values("node", "")
    assert len(nodes) >= 2
    dialog.filterBar.setFilter("node", nodes[0])
    try:
        assert dialog.filter_values("node", "") == nodes
    finally:
        dialog.filterBar.clearAll()


def test_taking_a_value_with_spaces_quotes_it_and_applies(dialog, qapp):
    inp = dialog.filterBar._input
    inp.setFocus()
    qapp.processEvents()
    inp.setText("cmd:git")
    inp.setCursorPosition(len(inp.text()))
    inp._offer()
    assert inp.offersValues() and inp.completionValues() == ["git fetch origin main"]
    QtTest.QTest.keyClick(inp._completer.popup(), QtCore.Qt.Key.Key_Tab)
    assert inp.text() == 'cmd:"git fetch origin main"'
    dialog.filterBar._on_enter()
    assert dialog.filterBar.filterValue("cmd") == "git fetch origin main"
    query = dialog.eventsTable.model().query().lastQuery()
    assert 'c.process_args="git fetch origin main"' in query
    base = query.split(" ORDER BY ")[0]
    assert _count(f"SELECT count(*) FROM ({base})") == \
        _count("SELECT count(*) FROM connections WHERE process_args = 'git fetch origin main'")
    dialog.filterBar.clearAll()
