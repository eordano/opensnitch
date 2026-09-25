import opensnitch.utils  # breaks the database <-> views import cycle
import sqlite3
import pytest
from PyQt6 import QtGui, QtCore
from opensnitch.customwidgets.filterexpression import compile_filter, FilterError
from opensnitch.database import Database
from opensnitch.dialogs.events.dialog import StatsDialog
from opensnitch.dialogs.events import constants


def test_boolean_precedence_ranges_negation_and_escaping():
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE rows(port INTEGER, proto TEXT, host TEXT)')
    db.executemany('INSERT INTO rows VALUES(?,?,?)', [(80,'tcp','a'),(443,'tcp',"O'Reilly"),(443,'udp','b'),(3000,'tcp','c')])
    columns = {'port':'port','proto':'proto','host':'host'}
    cases = [
        ('(port=80 OR port=443) AND !proto:udp', [80,443]),
        ('port>=443 AND port<3000 AND proto!=udp', [443]),
        ('port<>443 AND port<=3000 AND port>80', [3000]),
        ('host:"O\'Reilly"', [443]),
        ('port=80 OR port=443 AND proto=udp', [80,443]),
    ]
    for text, expected in cases:
        sql=compile_filter(text,columns)
        assert [r[0] for r in db.execute('SELECT port FROM rows WHERE '+sql)] == expected
    for text in ('port>', '(port=80', 'port=80 OR', 'unknown=1', 'port=80; DROP TABLE rows', 'port<abc'):
        with pytest.raises(FilterError): compile_filter(text, columns)


def test_filtering_stays_in_hosts_and_sockets(qapp, qtbot):
    from tests.sample_data import populate_database
    db=Database.instance();populate_database(db,connection_count=50,socket_count=10)
    dialog=StatsDialog(db=db,appicon=QtGui.QIcon());qtbot.addWidget(dialog);dialog.show()
    dialog.set_current_tab(constants.TAB_HOSTS)
    dialog.filterBar.setFilter('port','443')
    assert dialog.get_current_view_idx()==constants.TAB_HOSTS
    query=dialog.get_active_table().model().query().lastQuery()
    assert 'FROM connections AS c' in query and 'c.dst_port="443"' in query
    dialog.filterBar.clearAll()
    dialog.set_current_tab(constants.TAB_NETSTAT)
    dialog.filterBar._input.setText('proto:tcp AND (port=443 OR port=80)')
    dialog.filterBar._on_enter()
    assert dialog.get_current_view_idx()==constants.TAB_NETSTAT
    query=dialog.get_active_table().model().query().lastQuery()
    assert 'FROM sockets AS c' in query and "c.proto='6'" in query
    assert ' OR ' in query
    assert dialog.netstatFilterRow.isHidden()
    assert not dialog.comboNetstatInterval.isHidden()
    old=query
    dialog.filterBar._input.setText('port>')
    dialog.filterBar._on_enter()
    assert dialog.get_active_table().model().query().lastQuery()==old


def test_rule_port_and_metadata_are_visible(qapp, qtbot):
    import re, socket
    from opensnitch.dialogs.ruleseditor import RulesEditorDialog
    editor=RulesEditorDialog(appicon=QtGui.QIcon());qtbot.addWidget(editor)
    editor.new_rule_from_shared({'dst_port':'123'})
    assert editor.dstPortCheck.isChecked() and editor.dstPortLine.text()=='123'
    assert editor.tabWidget.currentWidget().isAncestorOf(editor.dstPortLine)
    assert '123' in editor.ruleNameEdit.text()
    assert re.fullmatch(r'Created from '+re.escape(socket.gethostname())+r' UI at \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC',editor.ruleDescEdit.toPlainText())
    assert editor.ruleFlagsLayout.indexOf(editor.enableCheck)>=0
    assert editor.ruleFlagsLayout.indexOf(editor.precedenceCheck)>=0


def test_view_filters_restore_and_empty_controls_hide(qapp, qtbot):
    from tests.sample_data import populate_database
    db=Database.instance();populate_database(db,connection_count=30,socket_count=4)
    dialog=StatsDialog(db=db,appicon=QtGui.QIcon());qtbot.addWidget(dialog);dialog.show()
    dialog.set_current_tab(constants.TAB_HOSTS)
    dialog.filterBar.setFilter('port','443')
    dialog.set_current_tab(constants.TAB_NETSTAT)
    assert dialog.filterBar.filterValue('port') is None
    dialog.set_current_tab(constants.TAB_HOSTS)
    assert dialog.filterBar.filterValue('port')=='443'
    dialog.filterBar.setFilter('port','999999')
    dialog.update_view_actions()
    assert dialog.get_active_table().model().totalRowCount==0
    assert not dialog.filterBar._input.isHidden()
    assert 'Export CSV...' not in dialog.filterBar.actionTexts()
    dialog.filterBar.clearAll()
    dialog.set_current_tab(constants.TAB_NETSTAT)
    db.clean('sockets');dialog.netstat.apply_filter();dialog.update_view_actions()
    assert dialog.filterBar._input.isHidden()
    assert 'Export CSV...' not in dialog.filterBar.actionTexts()


def test_socket_snapshot_replaces_only_its_node(qapp, qtbot):
    import json
    from PyQt6.QtSql import QSqlQuery
    from tests.sample_data import populate_database
    db=Database.instance();populate_database(db,connection_count=2,socket_count=4)
    query=QSqlQuery(db.get_db())
    assert query.exec("UPDATE sockets SET node=CASE WHEN id % 2 = 0 THEN 'a' ELSE 'b' END")
    dialog=StatsDialog(db=db,appicon=QtGui.QIcon());qtbot.addWidget(dialog)
    dialog.netstat.update_node('a', json.dumps({'Table': [], 'Processes': {}}))
    assert query.exec("SELECT node, count(*) FROM sockets GROUP BY node")
    assert query.next() and query.value(0)=='b' and query.value(1)==2
    assert not query.next()
