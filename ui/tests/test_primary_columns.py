import sqlite3
from types import SimpleNamespace
from PyQt6 import QtCore, QtGui, QtWidgets
from opensnitch.customwidgets.generictableview import PrimaryColumnHeader
import opensnitch.utils  # breaks the database <-> views import cycle
from opensnitch.dialogs.events.views import ViewsManager
from opensnitch.dialogs.events import constants


def test_primary_column_survives_moves_and_saved_layout(qapp):
    table = QtWidgets.QTableView()
    model = QtGui.QStandardItemModel(1, 4)
    table.setModel(model)
    old = table.horizontalHeader()
    old.moveSection(0, 2)
    saved = old.saveState()
    header = PrimaryColumnHeader(table)
    table.setHorizontalHeader(header)
    header.setSectionsMovable(True)
    header.moveSection(0, 2)
    assert header.visualIndex(0) == 0
    header.moveSection(2, 0)
    assert header.visualIndex(0) == 0
    header.blockSignals(True)
    assert header.restoreState(saved)
    header.blockSignals(False)
    assert header.visualIndex(0) == 0
    header.moveSection(1, 3)
    assert header.visualIndex(1) == 3


def test_secondary_sort_keeps_port_rows_consecutive(qapp):
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE traffic (port INTEGER, host TEXT)')
    db.executemany('INSERT INTO traffic VALUES (?, ?)', [(443, 'a'), (3000, 'b'), (443, 'c')])
    for direction in (constants.SORT_ASC, constants.SORT_DESC):
        view = SimpleNamespace(
            get_current_view_idx=lambda: constants.TAB_PORTS,
            get_split_by=lambda idx: ['host'],
            TABLES={constants.TAB_PORTS: {'last_order_by': 2, 'last_order_to': direction}})
        order = ViewsManager.get_view_order(view)
        rows = db.execute('SELECT port, host FROM traffic' + order).fetchall()
        assert [r[0] for r in rows] == [443, 443, 3000]
        assert [r[1] for r in rows[:2]] == (['a', 'c'] if direction == constants.SORT_ASC else ['c', 'a'])
    db.close()


def test_primary_header_remains_clickable_for_sorting(qapp):
    from PyQt6.QtTest import QTest
    table = QtWidgets.QTableView()
    table.setModel(QtGui.QStandardItemModel(2, 3))
    header = PrimaryColumnHeader(table)
    table.setHorizontalHeader(header)
    table.setSortingEnabled(True)
    table.show()
    qapp.processEvents()
    header.setSortIndicator(0, QtCore.Qt.SortOrder.AscendingOrder)
    point = QtCore.QPoint(header.sectionViewportPosition(0) + header.sectionSize(0) // 2, header.height() // 2)
    QTest.mouseClick(header.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert header.sortIndicatorSection() == 0
    assert header.sortIndicatorOrder() == QtCore.Qt.SortOrder.DescendingOrder
    QTest.mouseClick(header.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
    assert header.sortIndicatorOrder() == QtCore.Qt.SortOrder.AscendingOrder
    table.close()
