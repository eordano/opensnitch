"""The sidebar: node selector on top, status card + play/pause, footer buttons."""
import pytest
from PyQt6 import QtWidgets, QtCore, QtTest

import opensnitch.proto as proto
proto.import_()

from opensnitch.customwidgets.sidebar import SidebarWidget


@pytest.fixture
def sidebar(qapp):
    w = SidebarWidget()
    w.show()
    qapp.processEvents()
    yield w
    w.close()


def _menu_texts(sidebar):
    return [a.text() for a in sidebar._node_menu.actions() if not a.isSeparator()]


def _checks(sidebar):
    return [a.isChecked() for a in sidebar._node_menu.actions() if a.isCheckable()]


def test_node_selector_lists_nodes_and_the_nodes_page_entry(sidebar):
    sidebar.updateNodes([])
    assert sidebar._node_btn.text() == "No nodes connected"
    assert _menu_texts(sidebar) == ["All nodes", "No nodes connected", "Show the Nodes page"]
    sidebar.updateNodes([("unix:///tmp/osui.sock", "mars", True), ("ipv4:10.0.0.2:50051", "robin", False)])
    assert sidebar._node_btn.text() == "All nodes (2)"
    assert _menu_texts(sidebar) == ["All nodes", "mars  osui.sock", "robin  ipv4:10.0.0.2:50051  (offline)", "Show the Nodes page"]
    assert _checks(sidebar) == [True, True, True]
    assert all(a.icon().isNull() for a in sidebar._node_menu.actions())
    assert sidebar._node_btn.minimumHeight() >= 36


def test_single_node_is_named_on_the_button(sidebar):
    sidebar.updateNodes([("unix:///tmp/osui.sock", "mars", True)])
    assert sidebar._node_btn.text() == "mars  osui.sock"


def test_nodes_toggle_independently(sidebar):
    sidebar.updateNodes([("a", "alpha", True), ("b", "beta", True), ("c", "gamma", False)])
    got = []
    sidebar.nodeSelected.connect(got.append)
    acts = sidebar._node_menu.actions()
    acts[3].trigger()
    assert got == [["a", "b"]]
    assert sidebar.selectedNodes() == ["a", "b"]
    assert sidebar._node_btn.text() == "2 of 3 nodes"
    assert _checks(sidebar) == [False, True, True, False]
    acts[2].trigger()
    assert got[-1] == ["a"]
    assert sidebar._node_btn.text() == "alpha  a"
    acts[3].trigger()
    assert got[-1] == ["a", "c"]
    assert sidebar._node_btn.text() == "2 of 3 nodes"
    acts[2].trigger()
    assert got[-1] == []
    assert _checks(sidebar) == [True, True, True, True]
    assert sidebar._node_btn.text() == "All nodes (3)"


def test_all_nodes_resets_and_unchecking_the_last_node_shows_all(sidebar):
    sidebar.updateNodes([("a", "alpha", True), ("b", "beta", True)])
    got = []
    sidebar.nodeSelected.connect(got.append)
    acts = sidebar._node_menu.actions()
    acts[1].trigger()
    assert got[-1] == ["b"]
    acts[2].trigger()
    assert got[-1] == []
    assert _checks(sidebar) == [True, True, True]
    acts[1].trigger()
    assert got[-1] == ["b"]
    acts[0].trigger()
    assert got[-1] == []
    assert _checks(sidebar) == [True, True, True]
    acts[0].trigger()
    assert got[-1] == [] and len(got) == 4
    assert _checks(sidebar) == [True, True, True]


def test_menu_stays_open_while_toggling_by_mouse_and_keyboard(sidebar, qapp):
    sidebar.updateNodes([("a", "alpha", True), ("b", "beta", True)])
    menu = sidebar._node_menu
    menu.popup(sidebar.mapToGlobal(QtCore.QPoint(10, 10)))
    qapp.processEvents()
    assert menu.isVisible()
    acts = menu.actions()
    QtTest.QTest.mouseClick(menu, QtCore.Qt.MouseButton.LeftButton, pos=menu.actionGeometry(acts[2]).center())
    qapp.processEvents()
    assert menu.isVisible()
    assert sidebar.selectedNodes() == ["a"]
    menu.setActiveAction(acts[2])
    QtTest.QTest.keyClick(menu, QtCore.Qt.Key.Key_Space)
    qapp.processEvents()
    assert menu.isVisible()
    assert sidebar.selectedNodes() == [] and _checks(sidebar) == [True, True, True]
    menu.setActiveAction(acts[1])
    QtTest.QTest.keyClick(menu, QtCore.Qt.Key.Key_Return)
    assert menu.isVisible() and sidebar.selectedNodes() == ["b"]
    QtTest.QTest.keyClick(menu, QtCore.Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not menu.isVisible()


def test_external_changes_are_followed_without_emitting(sidebar):
    sidebar.updateNodes([("a", "alpha", True), ("b", "beta", True), ("c", "gamma", True)])
    got = []
    sidebar.nodeSelected.connect(got.append)
    sidebar.setSelectedNodes(["b"])
    assert got == [] and sidebar._node_btn.text() == "beta  b"
    sidebar.setSelectedNodes(["c", "a"])
    assert sidebar.selectedNodes() == ["a", "c"] and sidebar._node_btn.text() == "2 of 3 nodes"
    sidebar.setSelectedNodes(["zzz"])
    assert sidebar.selectedNodes() == [] and sidebar._node_btn.text() == "All nodes (3)"
    sidebar.setSelectedNodes(["a", "b", "c"])
    assert sidebar.selectedNodes() == []
    sidebar.setSelectedNodes(["a"])
    sidebar.updateNodes([("b", "beta", True), ("c", "gamma", True)])
    assert sidebar.selectedNodes() == [] and sidebar._node_btn.text() == "All nodes (2)"
    assert got == []


def test_nodes_page_entry_opens_the_nodes_view(sidebar):
    got = []
    sidebar.navigationChanged.connect(got.append)
    entry = sidebar._node_menu.actions()[-1]
    assert entry.text() == "Show the Nodes page"
    assert "daemon" in entry.toolTip() and "'" not in entry.toolTip()
    entry.trigger()
    assert got == [1]
    sidebar.setCurrentItem(1)
    assert sidebar._node_btn.property("selected")


def test_status_is_informational_and_play_pause_is_the_control(sidebar):
    holder = sidebar.findChild(QtWidgets.QWidget, "nodeSelectorHolder")
    assert sidebar._shield.parentWidget() is holder and sidebar._toggle_btn.parentWidget() is holder
    assert sidebar._shield.minimumHeight() >= 48
    assert sidebar._toggle_btn.width() >= 48 and sidebar._toggle_btn.height() >= 48
    sidebar.updateShield(True, "0:00:45 uptime")
    sidebar.show()
    QtWidgets.QApplication.processEvents()
    assert sidebar._toggle_btn.height() == sidebar._shield.height()
    assert sidebar._shield_label.text() == "Filtering"
    assert sidebar._shield_sub.text() == "0:00:45 uptime"
    assert "Pause" in sidebar._toggle_btn.toolTip()
    sidebar.updateShield(False, "0:00:45 uptime")
    assert sidebar._shield_label.text() == "Paused"
    assert "Resume" in sidebar._toggle_btn.toolTip()
    toggled = []
    sidebar.interceptToggled.connect(lambda: toggled.append(1))
    sidebar._toggle_btn.click()
    assert toggled == [1]
    nav = []
    sidebar.navigationChanged.connect(nav.append)
    assert isinstance(sidebar._shield, QtWidgets.QFrame)
    assert sidebar._shield.focusPolicy() == QtCore.Qt.FocusPolicy.NoFocus
    assert nav == []


def test_footer_buttons_have_full_height_targets_and_tooltips(sidebar):
    footer = sidebar.findChild(QtWidgets.QWidget, "sidebarFooter")
    buttons = [b for b in footer.findChildren(QtWidgets.QPushButton)
               if b not in (sidebar._shield, sidebar._toggle_btn)]
    assert [b.text() for b in buttons] == ["Settings"]
    assert all(b.minimumHeight() >= 36 for b in buttons)
    assert all(b.toolTip() for b in buttons)


def test_firewall_is_a_navigation_entry(sidebar):
    assert sidebar._buttons[9].text() == "Firewall"
    got = []
    sidebar.navigationChanged.connect(got.append)
    sidebar._buttons[9].click()
    assert got == [9]



def test_empty_status_description_is_hidden(sidebar):
    sidebar.updateShield(True, "")
    assert sidebar._shield_sub.isHidden()


def test_sidebar_width_follows_its_content(sidebar):
    # no hard-coded width: the layout derives the minimum from the widest row
    assert sidebar.minimumWidth() == sidebar.minimumSizeHint().width()
    assert sidebar.minimumSizeHint().width() >= sidebar._toggle_btn.width() + 100
