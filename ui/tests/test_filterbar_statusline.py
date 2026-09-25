"""Filter bar discoverability, node chip helpers, status line."""
import pytest
from PyQt6 import QtWidgets, QtCore, QtTest

import opensnitch.proto as proto
proto.import_()

from opensnitch.customwidgets.filterbar import FilterBarWidget
from opensnitch.customwidgets.statusline import StatusLine


@pytest.fixture
def bar(qapp):
    w = FilterBarWidget()
    w.show()
    yield w
    w.close()


def test_focus_offers_fields_and_tab_takes_one(bar, qapp):
    inp = bar._input
    inp.setFocus()
    qapp.processEvents()
    inp._offer()
    assert inp.offersFields()
    assert inp.completionKeys()[0] == "dst"
    QtTest.QTest.keyClick(inp._completer.popup(), QtCore.Qt.Key.Key_Tab)
    assert inp.text() == "dst:"
    assert not inp.offersFields()
    inp.setText("dst:github.com a")
    inp.setCursorPosition(len(inp.text()))
    inp._offer()
    assert inp.completionKeys() == ["action"]
    QtTest.QTest.keyClick(inp._completer.popup(), QtCore.Qt.Key.Key_Return)
    assert inp.text() == "dst:github.com action:"
    QtTest.QTest.keyClick(inp, QtCore.Qt.Key.Key_Escape)
    assert inp.text() == ""
    assert "Enter" in inp.placeholderText()


def test_values_are_offered_after_the_field(bar, qapp):
    inp = bar._input
    bar.setValueProvider(lambda key, prefix: ["140.82.121.3", "140.82.121.6"] if key == "ip" and prefix == "1" else [])
    inp.setText("ip:1")
    inp.setCursorPosition(4)
    inp._offer()
    assert inp.completionValues() == ["140.82.121.3", "140.82.121.6"]
    QtTest.QTest.keyClick(inp._completer.popup(), QtCore.Qt.Key.Key_Down)
    QtTest.QTest.keyClick(inp._completer.popup(), QtCore.Qt.Key.Key_Tab)
    assert inp.text() == "ip:140.82.121.6"
    inp.setText("ip:9"); inp.setCursorPosition(4); inp._offer()
    assert not inp.offersFields()
    inp.clear()


def test_one_chip_per_key(bar):
    changed = []
    bar.filterChanged.connect(changed.append)
    bar.setFilter("node", "a")
    bar.setFilter("node", "b")
    assert [c.key for c in bar._chips] == ["node"]
    assert bar.filterValue("node") == "b"
    assert changed[-1] == "conn.node=b"
    assert bar.removeFilter("node", emit=False)
    assert bar.filterValue("node") is None
    assert not bar.removeFilter("node")


def test_status_line_hides_missing_figures(qapp):
    line = StatusLine()
    line.show()
    assert line._empty.isVisibleTo(line)
    line.set(connections="1 234", dropped=0, uptime="0:00:45", rules=30, version="1.6.7")
    assert line.values() == {"connections": "1 234", "dropped": "0", "uptime": "0:00:45", "rules": "30", "version": "1.6.7"}
    assert not line._empty.isVisibleTo(line)
    line.set(nodes=3, version="1.6.7")
    assert line.values() == {"nodes": "3", "version": "1.6.7"}
    line.clear()
    assert line.values() == {} and line._empty.isVisibleTo(line)


def test_backspace_on_empty_box_removes_the_last_chip(bar):
    bar.setFilter("dst", "a", emit=False)
    bar.setFilter("ip", "b", emit=False)
    bar._input.clear()
    QtTest.QTest.keyClick(bar._input, QtCore.Qt.Key.Key_Backspace)
    assert [c.key for c in bar._chips] == ["dst"]
    bar._input.setText("x")
    QtTest.QTest.keyClick(bar._input, QtCore.Qt.Key.Key_Backspace)
    assert [c.key for c in bar._chips] == ["dst"] and bar._input.text() == ""
    QtTest.QTest.keyClick(bar._input, QtCore.Qt.Key.Key_Backspace)
    assert bar._chips == []


def test_bar_actions_are_push_buttons(bar):
    bar.setActions([("Export CSV...", "tip", lambda: None)])
    assert all(isinstance(b, QtWidgets.QPushButton) and b.minimumHeight() >= 30 for b in bar._action_buttons)
