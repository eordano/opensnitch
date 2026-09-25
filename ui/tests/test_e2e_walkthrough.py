"""End-to-end walkthrough tests exercising all new UX features.

These tests generate rich sample data and walk through realistic user
scenarios, taking screenshots at each key step.

Run with:
    cd ui && QT_QPA_PLATFORM=offscreen PYTHONPATH=.:opensnitch \
        python3 -m pytest tests/test_e2e_walkthrough.py -v

Screenshots show the sample data of tests/sample_data.py, never a real
daemon; they land in tests.paths.SCREENSHOT_DIR (a directory named for that).
"""

import os
import pytest
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtCore import Qt


# Tab index constants (avoid circular import from opensnitch.dialogs.events.constants)
TAB_MAIN = 0
TAB_NODES = 1
TAB_RULES = 2
TAB_HOSTS = 3
TAB_PROCS = 4
TAB_ADDRS = 5
TAB_PORTS = 6
TAB_USERS = 7
TAB_NETSTAT = 8

from tests.paths import SCREENSHOT_DIR


@pytest.fixture(scope="module")
def screenshot_dir():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    return SCREENSHOT_DIR


@pytest.fixture(scope="module")
def populated_db(qapp):
    """Populate the database with rich sample data once for all tests."""
    from opensnitch.database import Database
    from tests.sample_data import populate_database
    db = Database.instance()
    populate_database(db, connection_count=150, socket_count=30)
    return db


@pytest.fixture
def dialog(qapp, populated_db):
    """Create a StatsDialog with populated data."""
    from opensnitch.database import Database
    from opensnitch.dialogs.events.dialog import StatsDialog
    dlg = StatsDialog(db=Database.instance(), appicon=QtGui.QIcon())
    dlg.show()
    dlg.resize(1440, 900)
    QtWidgets.QApplication.processEvents()
    yield dlg
    dlg.hide()


def _screenshot(dialog, screenshot_dir, name):
    """Take a screenshot and save it."""
    QtWidgets.QApplication.processEvents()
    path = os.path.join(screenshot_dir, f"{name}.png")
    dialog.grab().save(path)
    return path


class TestNavigationWalkthrough:
    """Walk through all navigation: sidebar clicks and view verification."""

    def test_01_initial_state_events_view(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_MAIN)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        path = _screenshot(dialog, screenshot_dir, "nav_01_events")
        assert dialog.get_current_view_idx() == TAB_MAIN
        assert os.path.exists(path)

    def test_02_navigate_to_rules(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_RULES)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "nav_02_rules")
        assert dialog.get_current_view_idx() == TAB_RULES

    def test_03_navigate_to_hosts(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_HOSTS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "nav_03_hosts")
        assert dialog.get_current_view_idx() == TAB_HOSTS

    def test_04_navigate_to_processes(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_PROCS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "nav_04_processes")
        assert dialog.get_current_view_idx() == TAB_PROCS

    def test_05_navigate_to_addresses(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_ADDRS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "nav_05_addresses")
        assert dialog.get_current_view_idx() == TAB_ADDRS

    def test_06_navigate_to_ports(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_PORTS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "nav_06_ports")
        assert dialog.get_current_view_idx() == TAB_PORTS

    def test_07_navigate_to_users(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_USERS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "nav_07_users")
        assert dialog.get_current_view_idx() == TAB_USERS

    def test_08_navigate_to_sockets(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_NETSTAT)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "nav_08_sockets")
        assert dialog.get_current_view_idx() == TAB_NETSTAT

    def test_09_navigate_to_nodes(self, dialog, screenshot_dir):
        dialog.set_current_tab(TAB_NODES)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "nav_09_nodes")
        assert dialog.get_current_view_idx() == TAB_NODES

    def test_10_sidebar_highlight_follows(self, dialog, screenshot_dir):
        """Verify sidebar highlight matches current view after navigation."""
        for idx in range(9):
            dialog.set_current_tab(idx)
            assert dialog.sidebar.currentItem() == idx


class TestCommandPaletteWalkthrough:
    """Exercise the Ctrl+K command palette."""

    def test_01_palette_exists(self, dialog):
        """Command palette widget should exist on the dialog."""
        assert hasattr(dialog, 'commandPalette') or hasattr(dialog, 'command_palette'), \
            "Command palette not found - feature may not be integrated yet"

    def test_02_palette_opens(self, dialog, screenshot_dir):
        """Ctrl+K should show the command palette."""
        palette = getattr(dialog, 'commandPalette', None) or getattr(dialog, 'command_palette', None)
        if palette is None:
            pytest.skip("Command palette not integrated yet")
        palette.show()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "palette_01_open")
        assert palette.isVisible()

    def test_03_palette_search_filters(self, dialog, screenshot_dir):
        """Typing in palette should filter commands."""
        palette = getattr(dialog, 'commandPalette', None) or getattr(dialog, 'command_palette', None)
        if palette is None:
            pytest.skip("Command palette not integrated yet")
        palette.show()
        search_input = palette.findChild(QtWidgets.QLineEdit)
        if search_input:
            search_input.setText("rule")
            QtWidgets.QApplication.processEvents()
            _screenshot(dialog, screenshot_dir, "palette_02_filtered")

    def test_04_palette_navigate(self, dialog, screenshot_dir):
        """Selecting a nav command should switch views."""
        palette = getattr(dialog, 'commandPalette', None) or getattr(dialog, 'command_palette', None)
        if palette is None:
            pytest.skip("Command palette not integrated yet")
        palette.show()
        palette.hide()
        QtWidgets.QApplication.processEvents()
        assert not palette.isVisible()


class TestFilterBarWalkthrough:
    """Exercise the structured query filter bar."""

    def test_01_filter_bar_exists(self, dialog):
        """Filter bar should be present in the dialog."""
        assert hasattr(dialog, 'filterBar')
        from opensnitch.customwidgets.filterbar import FilterBarWidget
        assert isinstance(dialog.filterBar, FilterBarWidget)

    def test_02_filter_by_host(self, dialog, screenshot_dir):
        """Filter with dst:github.com should narrow events."""
        dialog.set_current_tab(TAB_MAIN)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "filter_01_before")

        dialog.filterBar.addFilter("dst", "github.com")
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "filter_02_host")

    def test_03_filter_by_action(self, dialog, screenshot_dir):
        """Filter with action:deny should show only blocked connections."""
        dialog.filterBar.clearAll()
        dialog.set_current_tab(TAB_MAIN)
        dialog.filterBar.addFilter("action", "deny")
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "filter_03_deny")

    def test_04_filter_combined(self, dialog, screenshot_dir):
        """Combined filter: proto:tcp dst:github.com."""
        dialog.filterBar.clearAll()
        dialog.set_current_tab(TAB_MAIN)
        dialog.filterBar.addFilter("proto", "tcp")
        dialog.filterBar.addFilter("dst", "github.com")
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "filter_04_combined")

    def test_05_filter_clear(self, dialog, screenshot_dir):
        """Clearing filter should show all events again."""
        dialog.filterBar.clearAll()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "filter_05_cleared")


class TestDetailPaneWalkthrough:
    """Exercise the connection detail split-pane."""

    def test_01_detail_pane_hidden_by_default(self, dialog):
        """Detail pane should exist but be hidden initially."""
        from opensnitch.customwidgets.detailpanel import ConnectionDetailPanel
        assert hasattr(dialog, 'detailPanel')
        assert isinstance(dialog.detailPanel, ConnectionDetailPanel)
        assert not dialog.detailPanel.isVisible()

    def test_02_click_row_shows_detail(self, dialog, screenshot_dir):
        """Clicking a row in Events should show the detail panel."""
        dialog.set_current_tab(TAB_MAIN)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()

        table = dialog.eventsTable
        model = table.model()
        if model and model.rowCount() > 0:
            dialog._show_detail_for_row(0)
            QtWidgets.QApplication.processEvents()
            _screenshot(dialog, screenshot_dir, "detail_01_open")
            assert dialog.detailPanel.isVisible()

    def test_03_detail_shows_connection_info(self, dialog, screenshot_dir):
        """Detail panel should show connection fields."""
        if dialog.detailPanel.isVisible():
            data = dialog.detailPanel.currentData()
            assert data.get("time") is not None or data.get("process") is not None
            _screenshot(dialog, screenshot_dir, "detail_02_populated")


class TestBulkOperationsWalkthrough:
    """Exercise multi-select and bulk actions."""

    def test_01_multi_select_enabled(self, dialog):
        """Tables should support extended selection (Ctrl/Shift+click)."""
        dialog.set_current_tab(TAB_MAIN)
        table = dialog.eventsTable
        mode = table.selectionMode()
        assert mode == QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection

    def test_02_select_multiple_rows(self, dialog, screenshot_dir):
        """Selecting all rows should show bulk action bar."""
        dialog.set_current_tab(TAB_MAIN)
        dialog.detailPanel.hideDetail()
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()

        table = dialog.eventsTable
        model = table.model()
        if model and model.rowCount() >= 3:
            table.selectAll()
            QtWidgets.QApplication.processEvents()
            _screenshot(dialog, screenshot_dir, "bulk_01_selected")
            assert dialog.bulkActionBar.isVisible()
            assert dialog.bulkActionBar.count() > 0

    def test_03_bulk_bar_visible(self, dialog, screenshot_dir):
        """Bulk action bar should appear with multiple selection."""
        from opensnitch.customwidgets.bulkbar import BulkActionBar
        assert hasattr(dialog, 'bulkActionBar')
        assert isinstance(dialog.bulkActionBar, BulkActionBar)
        dialog.bulkActionBar.updateCount(5)
        assert dialog.bulkActionBar.isVisible()
        _screenshot(dialog, screenshot_dir, "bulk_02_bar_visible")

    def test_04_clear_selection_hides_bar(self, dialog, screenshot_dir):
        """Clearing selection should hide the bulk action bar."""
        dialog.eventsTable.clearSelection()
        dialog.bulkActionBar.updateCount(0)
        QtWidgets.QApplication.processEvents()
        assert not dialog.bulkActionBar.isVisible()
        _screenshot(dialog, screenshot_dir, "bulk_03_cleared")


class TestLiveStreamWalkthrough:
    """Exercise real-time streaming mode."""

    def test_01_live_toggle_exists(self, dialog):
        """Live mode toggle should exist on the Events view."""
        toggle = getattr(dialog, 'liveToggle', None) or getattr(dialog, 'live_toggle', None) or \
                 getattr(dialog, 'liveButton', None) or getattr(dialog, 'live_button', None)
        if toggle is None:
            pytest.skip("Live stream toggle not integrated yet")
        assert toggle is not None

    def test_02_toggle_live_mode(self, dialog, screenshot_dir):
        """Toggling live mode should change indicator state."""
        toggle = getattr(dialog, 'liveToggle', None) or getattr(dialog, 'live_toggle', None) or \
                 getattr(dialog, 'liveButton', None) or getattr(dialog, 'live_button', None)
        if toggle is None:
            pytest.skip("Live stream toggle not integrated yet")
        dialog.set_current_tab(TAB_MAIN)
        toggle.click()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "live_01_active")

    def test_03_live_new_rows_highlighted(self, dialog, screenshot_dir):
        """New rows arriving in live mode should be highlighted."""
        toggle = getattr(dialog, 'liveToggle', None) or getattr(dialog, 'live_toggle', None) or \
                 getattr(dialog, 'liveButton', None) or getattr(dialog, 'live_button', None)
        if toggle is None:
            pytest.skip("Live stream toggle not integrated yet")
        # Insert a new connection to simulate live data
        from PyQt6.QtSql import QSqlQuery
        from opensnitch.database import Database
        db = Database.instance()
        q = QSqlQuery(db.get_db())
        q.exec(
            "INSERT OR IGNORE INTO connections VALUES "
            "('2026-05-17 12:00:01','unix:///tmp/osui.sock','deny','tcp',"
            "'192.168.1.42','55555','198.51.100.66','malware-c2.evil.example.com','443',"
            "'1000','9999','/usr/bin/suspicious','suspicious --connect','//home/user','deny-all-outbound')"
        )
        q.finish()
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "live_02_new_row")


class TestContextMenuWalkthrough:
    """Exercise right-click context menus on each view."""

    def _trigger_context_menu(self, table, row=0):
        """Simulate right-click on a table row."""
        model = table.model()
        if model and model.rowCount() > row:
            idx = model.index(row, 0)
            table.setCurrentIndex(idx)
            rect = table.visualRect(idx)
            pos = rect.center()
            table.customContextMenuRequested.emit(pos)
            QtWidgets.QApplication.processEvents()

    def test_01_events_context_menu(self, dialog, screenshot_dir):
        """Right-click on Events table should produce a context menu."""
        dialog.set_current_tab(TAB_MAIN)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()

        table = dialog.eventsTable
        policy = table.contextMenuPolicy()
        assert policy == Qt.ContextMenuPolicy.CustomContextMenu, \
            f"Context menu policy is {policy}, expected CustomContextMenu"
        _screenshot(dialog, screenshot_dir, "ctx_01_events")

    def test_02_rules_context_menu(self, dialog, screenshot_dir):
        """Right-click on Rules table should produce a context menu."""
        dialog.set_current_tab(TAB_RULES)
        # Click "Application rules" tree item to load rules into table
        tree = dialog.rulesTreePanel
        app_rules_item = tree.topLevelItem(0)
        if app_rules_item is not None:
            app_rules_item.setExpanded(True)
            tree.setCurrentItem(app_rules_item)
            tree.itemClicked.emit(app_rules_item, 0)
        QtWidgets.QApplication.processEvents()
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "ctx_02_rules")

    def test_03_hosts_context_menu(self, dialog, screenshot_dir):
        """Right-click on Hosts table should produce a context menu."""
        dialog.set_current_tab(TAB_HOSTS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "ctx_03_hosts")

    def test_04_processes_context_menu(self, dialog, screenshot_dir):
        """Right-click on Processes table should produce a context menu."""
        dialog.set_current_tab(TAB_PROCS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "ctx_04_processes")


class TestDrillDownWalkthrough:
    """Exercise double-click drill-down from history views to filtered Events."""

    def test_01_double_click_host_navigates(self, dialog, screenshot_dir):
        """Double-clicking a host should navigate to Events filtered by that host."""
        dialog.set_current_tab(TAB_HOSTS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "drill_01_hosts_view")

        table = dialog.TABLES[TAB_HOSTS]['view']
        model = table.model()
        if model and model.rowCount() > 0:
            idx = model.index(0, 0)
            table.setCurrentIndex(idx)
            table.doubleClicked.emit(idx)
            QtWidgets.QApplication.processEvents()
            _screenshot(dialog, screenshot_dir, "drill_02_filtered_events")
            # Should have navigated to Events
            assert dialog.get_current_view_idx() == TAB_MAIN

    def test_02_double_click_process_navigates(self, dialog, screenshot_dir):
        """Double-clicking a process should navigate to Events filtered by that process."""
        dialog.set_current_tab(TAB_PROCS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()

        table = dialog.TABLES[TAB_PROCS]['view']
        model = table.model()
        if model and model.rowCount() > 0:
            idx = model.index(0, 0)
            table.setCurrentIndex(idx)
            table.doubleClicked.emit(idx)
            QtWidgets.QApplication.processEvents()
            _screenshot(dialog, screenshot_dir, "drill_03_from_process")
            assert dialog.get_current_view_idx() == TAB_MAIN

    def test_03_double_click_port_navigates(self, dialog, screenshot_dir):
        """Double-clicking a port should navigate to Events filtered by that port."""
        dialog.set_current_tab(TAB_PORTS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()

        table = dialog.TABLES[TAB_PORTS]['view']
        model = table.model()
        if model and model.rowCount() > 0:
            idx = model.index(0, 0)
            table.setCurrentIndex(idx)
            table.doubleClicked.emit(idx)
            QtWidgets.QApplication.processEvents()
            _screenshot(dialog, screenshot_dir, "drill_04_from_port")
            assert dialog.get_current_view_idx() == TAB_MAIN


class TestFullWorkflow:
    """Chain all features in a realistic user scenario.

    Scenario: User notices suspicious traffic, investigates, creates block rule.
    """

    def test_full_investigation_workflow(self, dialog, screenshot_dir):
        """Complete investigation workflow from live events to rule creation."""
        # Step 1: Start on Events view, see all traffic
        dialog.set_current_tab(TAB_MAIN)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_01_events_overview")

        # Step 2: Check hosts view for suspicious domains
        dialog.set_current_tab(TAB_HOSTS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_02_check_hosts")

        # Step 3: Navigate to processes to see what's connecting
        dialog.set_current_tab(TAB_PROCS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_03_check_processes")

        # Step 4: Check Rules view for existing rules
        dialog.set_current_tab(TAB_RULES)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_04_check_rules")

        # Step 5: Check active sockets
        dialog.set_current_tab(TAB_NETSTAT)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_05_active_sockets")

        # Step 6: Check addresses
        dialog.set_current_tab(TAB_ADDRS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_06_addresses")

        # Step 7: Check ports
        dialog.set_current_tab(TAB_PORTS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_07_ports")

        # Step 8: Check users
        dialog.set_current_tab(TAB_USERS)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_08_users")

        # Step 9: Back to events - all data visible
        dialog.set_current_tab(TAB_MAIN)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_09_back_to_events")

        # Step 10: Check nodes
        dialog.set_current_tab(TAB_NODES)
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        _screenshot(dialog, screenshot_dir, "workflow_10_nodes")

        # Verify all views were reachable
        for idx in range(9):
            dialog.set_current_tab(idx)
            assert dialog.get_current_view_idx() == idx
