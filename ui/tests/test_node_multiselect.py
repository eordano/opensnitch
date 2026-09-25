"""Several nodes checked in the sidebar: one chip, one IN clause, one table."""
import random
from unittest.mock import patch

import pytest
from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon
from PyQt6.QtSql import QSqlQuery

import opensnitch.proto as proto
proto.import_()

from opensnitch.database import Database
from opensnitch.dialogs.events.dialog import StatsDialog
from opensnitch.dialogs.events import constants

LAPTOP = "unix:///tmp/osui.sock"
PROD = "192.168.1.10:50051"
DEV = "192.168.1.11:50051"
NODES = [(LAPTOP, "laptop", True), (PROD, "server-prod", True), (DEV, "server-dev", False)]


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
    random.seed(7)
    populate_database(Database.instance(), connection_count=150, socket_count=5)
    d = StatsDialog(db=Database.instance(), appicon=QIcon())
    d.show()
    d.resize(1280, 800)
    qapp.processEvents()
    yield d
    d.hide()


def _events_query(dialog):
    return dialog.eventsTable.model().query().lastQuery()


def _rows_of(query):
    base = query.split(" ORDER BY ")[0]
    return _count(f"SELECT count(*) FROM ({base})")


def test_two_checked_nodes_filter_with_node_in(dialog, qapp):
    dialog.set_current_tab(constants.TAB_MAIN)
    dialog.filterBar.clearAll()
    dialog.sidebar.updateNodes(NODES)
    with patch.object(dialog.firewallPanel, "select_node") as fw:
        dialog.sidebar._node_menu.actions()[3].trigger()
        fw.assert_called_once_with("")
    assert dialog.filterBar.filterValues("node") == [LAPTOP, PROD]
    query = _events_query(dialog)
    assert 'c.node IN ("{0}","{1}")'.format(LAPTOP, PROD) in query
    expected = _count("SELECT count(*) FROM connections WHERE node IN (?, ?)", (LAPTOP, PROD))
    assert expected > 0 and _rows_of(query) == expected


def test_one_checked_node_keeps_the_equality_filter(dialog):
    dialog.set_current_tab(constants.TAB_MAIN)
    dialog.sidebar.updateNodes(NODES)
    dialog.sidebar.setSelectedNodes([LAPTOP, PROD])
    with patch.object(dialog.firewallPanel, "select_node") as fw:
        dialog.sidebar._node_menu.actions()[2].trigger()
        fw.assert_called_once_with(LAPTOP)
    assert dialog.filterBar.filterValues("node") == [LAPTOP]
    query = _events_query(dialog)
    assert 'c.node="{0}"'.format(LAPTOP) in query and " IN (" not in query
    assert _rows_of(query) == _count("SELECT count(*) FROM connections WHERE node = ?", (LAPTOP,))


def test_chip_and_selector_round_trip(dialog):
    dialog.set_current_tab(constants.TAB_MAIN)
    dialog.sidebar.updateNodes(NODES)
    dialog.filterBar.setFilter("node", "{0},{1}".format(DEV, LAPTOP))
    assert dialog.sidebar.selectedNodes() == [LAPTOP, DEV]
    assert dialog.sidebar._node_btn.text() == "2 of 3 nodes"
    assert 'c.node IN ("{0}","{1}")'.format(DEV, LAPTOP) in _events_query(dialog)
    dialog.filterBar.removeFilter("node")
    assert dialog.sidebar.selectedNodes() == []
    assert dialog.sidebar._node_btn.text() == "All nodes (3)"
    assert " IN (" not in _events_query(dialog)
    dialog.sidebar._node_menu.actions()[1].trigger()
    assert dialog.filterBar.filterValues("node") == [PROD, DEV]
    dialog.filterBar.clearAll()
    assert dialog.sidebar.selectedNodes() == []
    dialog.sidebar.updateNodes([])


def test_search_parser_reads_lists_and_quoted_values(dialog):
    dialog.set_current_tab(constants.TAB_MAIN)
    q = dialog.queries
    assert q.advanced_search('conn.node IN (a,"b c") AND conn.process_args="git fetch origin main"') == \
        'c.node IN ("a","b c") AND c.process_args="git fetch origin main"'
    assert q.advanced_search('conn.dsthost=github.com') == 'c.dst_host="github.com"'
    assert q.advanced_search('conn.dsthost~"git hub"') == 'c.dst_host LIKE "%git hub%"'
    assert q.advanced_search('nothing IN (a,b)') is None
    assert q.advanced_search('conn.node IN ()') is None
