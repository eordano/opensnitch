"""Verify sidebar navigation replaces tab widget correctly."""
import pytest
from PyQt6 import QtWidgets
from PyQt6.QtGui import QIcon

import opensnitch.proto as proto
proto.import_()

from opensnitch.database import Database
from opensnitch.dialogs.events.dialog import StatsDialog
from opensnitch.dialogs.events import constants
from opensnitch.customwidgets.sidebar import SidebarWidget
from tests.paths import screenshot_path


class TestSidebarNavigation:
    @pytest.fixture(autouse=True)
    def setup(self, qapp):
        self.dialog = StatsDialog(db=Database.instance(), appicon=QIcon())

    def test_sidebar_exists(self, qapp):
        assert hasattr(self.dialog, 'sidebar')
        assert isinstance(self.dialog.sidebar, SidebarWidget)

    def test_stacked_widget_exists(self, qapp):
        assert hasattr(self.dialog, 'stackedWidget')
        assert isinstance(self.dialog.stackedWidget, QtWidgets.QStackedWidget)

    def test_main_splitter_exists(self, qapp):
        assert hasattr(self.dialog, 'mainSplitter')
        assert isinstance(self.dialog.mainSplitter, QtWidgets.QSplitter)

    def test_stacked_widget_has_10_pages(self, qapp):
        assert self.dialog.stackedWidget.count() == 10

    def test_all_views_reachable(self, qapp):
        for idx in range(10):
            self.dialog.set_current_tab(idx)
            assert self.dialog.get_current_view_idx() == idx

    def test_sidebar_highlight_syncs_with_set_current_tab(self, qapp):
        for idx in range(10):
            self.dialog.set_current_tab(idx)
            assert self.dialog.sidebar.currentItem() == idx

    def test_get_central_widget_returns_stacked(self, qapp):
        assert self.dialog.get_central_widget() is self.dialog.stackedWidget

    def test_set_current_tab_with_block_events(self, qapp):
        self.dialog.set_current_tab(3, block_events=True)
        assert self.dialog.get_current_view_idx() == 3
        assert self.dialog.sidebar.currentItem() == 3

    def test_tab_constants_match_views(self, qapp):
        mapping = {
            constants.TAB_MAIN: 0,
            constants.TAB_NODES: 1,
            constants.TAB_RULES: 2,
            constants.TAB_HOSTS: 3,
            constants.TAB_PROCS: 4,
            constants.TAB_ADDRS: 5,
            constants.TAB_PORTS: 6,
            constants.TAB_USERS: 7,
            constants.TAB_NETSTAT: 8,
            constants.TAB_FIREWALL: 9,
        }
        for const_val, expected_idx in mapping.items():
            self.dialog.set_current_tab(const_val)
            assert self.dialog.get_current_view_idx() == expected_idx

    def test_screenshot_each_view(self, qapp):
        names = ['events', 'nodes', 'rules', 'hosts', 'procs', 'addrs', 'ports', 'users', 'netstat', 'firewall']
        self.dialog.show()
        self.dialog.resize(1280, 820)
        for idx, name in enumerate(names):
            self.dialog.set_current_tab(idx)
            QtWidgets.QApplication.processEvents()
            path = screenshot_path(f"sidebar_{name}")
            self.dialog.grab().save(path)
        self.dialog.hide()
