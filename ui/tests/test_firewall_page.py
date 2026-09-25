"""The system firewall lives on a page of the main window."""
import pytest
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtGui import QIcon

import opensnitch.proto as proto
proto.import_()

from opensnitch.database import Database
from opensnitch.nodes import Nodes
from opensnitch.dialogs.events.dialog import StatsDialog
from opensnitch.dialogs.events import constants
from opensnitch.dialogs.firewall import FirewallPanel


@pytest.fixture(scope="module")
def dialog(qapp):
    d = StatsDialog(db=Database.instance(), appicon=QIcon())
    d.show()
    d.resize(1280, 800)
    qapp.processEvents()
    yield d
    d.hide()


def _layout_holding(root, widget):
    for i in range(root.count()):
        item = root.itemAt(i)
        if item.layout() is not None and item.layout().indexOf(widget) != -1:
            return item.layout()
    return None


def test_firewall_page_holds_panel_and_rules_table(dialog):
    page = dialog.stackedWidget.widget(constants.TAB_FIREWALL)
    assert isinstance(dialog.firewallPanel, FirewallPanel)
    assert dialog.firewallPanel.parentWidget() is page
    assert dialog.fwTable.parentWidget() is page
    assert dialog.rulesTreePanel.topLevelItem(constants.RULES_TREE_FIREWALL).isHidden()


def test_open_firewall_switches_page(dialog):
    dialog.set_current_tab(constants.TAB_MAIN)
    dialog.open_firewall()
    assert dialog.get_current_view_idx() == constants.TAB_FIREWALL
    assert dialog.sidebar.currentItem() == constants.TAB_FIREWALL
    assert dialog.fw_view_active()
    assert dialog.get_active_table() is dialog.fwTable


def test_panel_controls_are_reachable_targets(dialog):
    p = dialog.firewallPanel
    for w in (p.cmdNewRule, p.cmdAllowINService, p.cmdAllowOUTService):
        assert w.minimumHeight() >= 34
        assert w.toolTip()
    assert p.comboInput.count() == 2 and p.comboOutput.count() == 2
    assert p.chkEnabled.text().startswith("Apply")
    assert not p.comboNodes.isVisibleTo(p)  # one node at most in tests


def test_policies_share_the_header_line_left_of_the_wiki_button(dialog):
    p = dialog.firewallPanel
    root = p.layout()
    header = _layout_holding(root, p.cmdHelp)
    assert header is not None
    assert header.indexOf(p.policiesBox) != -1
    assert header.indexOf(p.policiesBox) < header.indexOf(p.cmdHelp)
    assert root.indexOf(p.policiesBox) == -1
    assert p.chkEnabled.parentWidget() is p.policiesBox
    assert p.comboInput.parentWidget() is p.policiesBox and p.comboOutput.parentWidget() is p.policiesBox
    dialog.set_current_tab(constants.TAB_FIREWALL)
    QtWidgets.QApplication.processEvents()
    assert p.policiesBox.geometry().right() <= p.cmdHelp.geometry().left()
    assert abs(p.policiesBox.geometry().center().y() - p.cmdHelp.geometry().center().y()) <= 4


def test_empty_state_is_centred_in_the_rules_table(dialog, qapp):
    p = dialog.firewallPanel
    assert p.lblFwStatus.parentWidget() is dialog.fwTable.viewport()
    assert p.lblFwStatus.alignment() & QtCore.Qt.AlignmentFlag.AlignHCenter
    assert p.lblFwStatus.alignment() & QtCore.Qt.AlignmentFlag.AlignVCenter
    nodes = Nodes.instance()
    saved = dict(nodes._nodes)
    nodes._nodes.clear()
    try:
        dialog.set_current_tab(constants.TAB_FIREWALL)
        p.load_fw_policies()
        qapp.processEvents()
        assert p.lblFwStatus.isVisibleTo(dialog)
        assert p.lblFwStatus.text() == "There are no nodes connected, so there is no firewall to configure."
        assert p.lblFwStatus.geometry() == dialog.fwTable.viewport().rect()
        dialog.resize(1100, 700)
        qapp.processEvents()
        assert p.lblFwStatus.geometry() == dialog.fwTable.viewport().rect()
    finally:
        nodes._nodes.update(saved)
        p.load_fw_policies()
    assert not p.lblFwStatus.isVisibleTo(dialog)


def test_filter_bar_actions_follow_the_view(dialog):
    dialog.set_current_tab(constants.TAB_RULES)
    # CSV export only appears when the view has rows
    assert dialog.filterBar.actionTexts()[:3] == ["New rule...", "Import rules...", "Export rules..."]
    dialog.set_current_tab(constants.TAB_HOSTS)
    assert dialog.filterBar.actionTexts() in ([], ["Export CSV..."])
    dialog.set_current_tab(constants.TAB_FIREWALL)
    assert dialog.filterBar.actionTexts() == []


def test_selection_bar_stays_on_events(dialog):
    dialog.set_current_tab(constants.TAB_MAIN)
    dialog.bulkActionBar.updateCount(3)
    assert dialog.bulkActionBar.isVisibleTo(dialog)
    dialog.set_current_tab(constants.TAB_FIREWALL)
    assert not dialog.bulkActionBar.isVisibleTo(dialog)
    dialog.set_current_tab(constants.TAB_MAIN)
    assert dialog.bulkActionBar.isVisibleTo(dialog)
    dialog.bulkActionBar.updateCount(0)


def test_node_selector_drives_the_events_chip_and_firewall_page(dialog):
    dialog.set_current_tab(constants.TAB_MAIN)
    dialog.sidebar.updateNodes([("unix:///tmp/a.sock", "alpha", True), ("unix:///tmp/b.sock", "beta", True)])
    dialog.sidebar._node_menu.actions()[2].trigger()
    assert dialog.filterBar.filterValue("node") == "unix:///tmp/a.sock"
    assert dialog.sidebar.selectedNodes() == ["unix:///tmp/a.sock"]
    dialog.filterBar.removeFilter("node")
    assert dialog.sidebar.selectedNodes() == []
    dialog.sidebar.updateNodes([])


def test_rules_tree_is_flat_and_fully_open(dialog):
    tree = dialog.rulesTreePanel
    assert not tree.rootIsDecorated() and not tree.itemsExpandable()
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        if item.childCount():
            assert item.isExpanded()


def test_filter_values_come_from_the_connections_table(dialog):
    from tests.sample_data import populate_database
    populate_database(Database.instance(), connection_count=40, socket_count=0)
    Database.instance().commit()
    values = dialog.filter_values("action", "")
    assert set(values) <= {"allow", "deny", "reject"} and values
    assert dialog.filter_values("ip", "zzz") == []
    assert dialog.filter_values("nonsense", "") == []


def test_sockets_message_names_the_node(dialog):
    from unittest.mock import patch
    with patch.object(dialog._nodes, 'get_nodes', return_value={}), patch.object(dialog.sidebar, 'selectedNodes', return_value=[]):
        dialog.netstat.monitor_node()
        assert dialog.netstatLabel.text().startswith("No selected node is connected")


def test_sockets_interval_has_a_label_in_the_bar(dialog):
    dialog.set_current_tab(constants.TAB_NETSTAT)
    assert dialog.netstatIntervalLabel.isVisibleTo(dialog.filterBar)
    assert dialog.netstatIntervalLabel.text() == "Refresh every"
    dialog.set_current_tab(constants.TAB_MAIN)
    assert not dialog.netstatIntervalLabel.isVisibleTo(dialog.filterBar)
    assert dialog.netstatLabel.indent() == 12


def test_sidebar_container_is_not_capped(dialog):
    from PyQt6 import QtWidgets
    assert dialog.sidebarContainer.maximumWidth() == QtWidgets.QWIDGETSIZE_MAX
    assert dialog.sidebarContainer.minimumWidth() == 0
    assert not dialog.mainSplitter.isCollapsible(0)
    QtWidgets.QApplication.processEvents()
    assert dialog.mainSplitter.sizes()[0] >= dialog.sidebar.minimumSizeHint().width()


def test_rules_tree_never_scrolls_sideways(dialog):
    tree = dialog.rulesTreePanel
    assert tree.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert tree.header().stretchLastSection()
    dialog.show()
    QtWidgets.QApplication.processEvents()
    assert tree.header().length() <= tree.viewport().width()
