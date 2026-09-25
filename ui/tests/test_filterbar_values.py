"""The filter box offers values after the colon; values with spaces are quoted;
a node chip can list several nodes."""
import pytest
from PyQt6 import QtCore, QtTest

import opensnitch.proto as proto
proto.import_()

from PyQt6 import QtWidgets
from opensnitch.customwidgets.filterbar import FilterBarWidget, FilterChip, quote_value


@pytest.fixture
def bar(qapp):
    w = FilterBarWidget()
    w.show()
    yield w
    w.close()


def test_values_are_offered_after_the_colon(bar, qapp):
    seen = []

    def provider(key, prefix):
        seen.append((key, prefix))
        return [v for v in ["deny", "allow", "curl -sL https://x"] if v.lower().startswith(prefix.lower())]

    bar.setValueProvider(provider)
    inp = bar._input
    inp.setFocus()
    qapp.processEvents()
    inp.setText("action:")
    inp.setCursorPosition(len(inp.text()))
    inp._offer()
    assert seen[-1] == ("action", "")
    assert inp.offersValues() and not inp.offersFields()
    assert inp.completionValues() == ["deny", "allow", "curl -sL https://x"]
    inp.setText("action:DE")
    inp.setCursorPosition(len(inp.text()))
    inp._offer()
    assert seen[-1] == ("action", "DE")
    assert inp.completionValues() == ["deny"]
    QtTest.QTest.keyClick(inp._completer.popup(), QtCore.Qt.Key.Key_Tab)
    assert inp.text() == "action:deny"
    assert not inp.offersValues()
    inp.setText("cmd:cu")
    inp.setCursorPosition(len(inp.text()))
    inp._offer()
    QtTest.QTest.keyClick(inp._completer.popup(), QtCore.Qt.Key.Key_Return)
    assert inp.text() == 'cmd:"curl -sL https://x"'
    inp.setText("ac")
    inp.setCursorPosition(2)
    inp._offer()
    assert inp.offersFields() and inp.completionKeys() == ["action"]


def test_no_provider_offers_nothing_after_the_colon(bar):
    inp = bar._input
    inp.setText("action:")
    inp.setCursorPosition(len(inp.text()))
    inp._offer()
    assert not inp.offersValues() and not inp.offersFields()


def test_quote_value():
    assert quote_value("deny") == "deny"
    assert quote_value("unix:///tmp/osui.sock") == "unix:///tmp/osui.sock"
    assert quote_value("git fetch origin main") == '"git fetch origin main"'
    assert quote_value('say "hi"') == '"say ""hi"""'


def test_quoted_values_and_node_lists(bar):
    changed = []
    bar.filterChanged.connect(changed.append)
    bar._input.setText('cmd:"curl -sL https://x" action:deny')
    bar._on_enter()
    assert [(c.key, c.value) for c in bar._chips] == [("cmd", "curl -sL https://x"), ("action", "deny")]
    assert changed[-1] == 'conn.process_args="curl -sL https://x" AND conn.action=deny'
    bar.setFilter("node", "unix:///tmp/a.sock,ipv4:10.0.0.2:50051")
    assert bar.filterValues("node") == ["unix:///tmp/a.sock", "ipv4:10.0.0.2:50051"]
    assert changed[-1].endswith("conn.node IN (unix:///tmp/a.sock,ipv4:10.0.0.2:50051)")
    bar.setFilter("node", "unix:///tmp/a.sock")
    assert bar.filterValues("node") == ["unix:///tmp/a.sock"]
    assert changed[-1].endswith("conn.node=unix:///tmp/a.sock")
    assert bar.filterValues("dst") == []
    assert bar.chipsFilterText() == changed[-1]
    bar.clearAll()
    assert bar.chipsFilterText() == ""


def _visible_chips(bar):
    return [c for c in bar.findChildren(QtWidgets.QFrame) if c.objectName() == "filterChip" and c.isVisible()]


def _disjoint(chips):
    return all(not a.geometry().intersects(b.geometry()) for i, a in enumerate(chips) for b in chips[i + 1:])


def test_chips_never_overlap_and_long_values_are_elided(bar, qapp):
    """removed chips leave at once (not on the next event-loop pass), long
    values are elided in the middle with the full text in the tooltip"""
    bar.resize(900, 40)
    qapp.processEvents()
    long_node = "unix:///tmp/osui.sock,192.168.1.10:50051,192.168.1.11:50051,192.168.1.12:50051"
    bar.setFilter("node", long_node)
    bar.setFilter("process", "/usr/bin/firefox")
    bar.setFilter("action", "deny")
    qapp.processEvents()
    chips = _visible_chips(bar)
    assert [c.key for c in chips] == ["node", "process", "action"]
    assert _disjoint(chips)
    node_label = chips[0].findChild(QtWidgets.QLabel)
    assert "\u2026" in node_label.text() and chips[0].width() <= FilterChip.MAX_TEXT_WIDTH + 40
    assert chips[0].toolTip() == "node:" + long_node
    bar.setFilter("node", "unix:///tmp/osui.sock")
    bar.removeFilter("process")
    qapp.processEvents()
    chips = _visible_chips(bar)
    assert sorted(c.key for c in chips) == ["action", "node"] and _disjoint(chips)
    bar.clearAll()
    assert _visible_chips(bar) == []
    bar.setFilter("dst", "github.com")
    bar.setFilters([("node", "a"), ("port", "443")])
    qapp.processEvents()
    chips = _visible_chips(bar)
    assert [c.key for c in chips] == ["node", "port"] and _disjoint(chips)
    chips[0].removed.emit(chips[0])
    qapp.processEvents()
    assert [c.key for c in _visible_chips(bar)] == ["port"]
