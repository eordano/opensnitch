"""Continuous scrolling of the history views, split-by columns and GeoIP lookups.

Run with:
    cd ui && QT_QPA_PLATFORM=offscreen PYTHONPATH=.:opensnitch:opensnitch/proto \
        python3 -m pytest tests/test_paging_split.py -v
"""

import os
import pytest
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtTest import QTest

TAB_MAIN = 0
TAB_HOSTS = 3
TAB_ADDRS = 5
EXTRA_HOSTS = 300


@pytest.fixture(scope="module")
def populated_db(qapp):
    from opensnitch.database import Database
    from tests.sample_data import populate_database
    db = Database.instance()
    populate_database(db, connection_count=400, socket_count=5)
    for i in range(EXTRA_HOSTS):
        db.insert("hosts", "(what, hits)", (f"host{i:03d}.example.net", 1000 - i))
    db.commit()
    return db


@pytest.fixture(scope="module")
def dialog(qapp, populated_db):
    from opensnitch.dialogs.events.dialog import StatsDialog
    dlg = StatsDialog(db=populated_db, appicon=QtGui.QIcon())
    dlg.show()
    dlg.resize(1200, 700)
    QtWidgets.QApplication.processEvents()
    yield dlg
    dlg.close()
    dlg.deleteLater()
    QtWidgets.QApplication.processEvents()


def _view(dlg, idx):
    dlg.set_current_tab(idx)
    dlg.update_split_control()
    dlg.refresh_active_table()
    QtWidgets.QApplication.processEvents()
    return dlg.TABLES[idx]['view']


def _no_limit(dlg):
    from opensnitch.dialogs.events import constants
    dlg.limitCombo.setCurrentIndex(len(constants.LIMITS) - 1)
    QtWidgets.QApplication.processEvents()


def _no_split(dlg, idx):
    dlg.set_split_by(idx, [])


class TestContinuousScrolling:
    def test_scrollbar_spans_every_row(self, dialog):
        _no_limit(dialog)
        _no_split(dialog, TAB_HOSTS)
        view = _view(dialog, TAB_HOSTS)
        model = view.model()
        assert model.totalRowCount > EXTRA_HOSTS
        assert view.vScrollBar.maximum() == model.totalRowCount - view.maxRowsInViewport

    def test_scrolling_to_the_end_shows_the_last_rows(self, dialog):
        _no_limit(dialog)
        _no_split(dialog, TAB_HOSTS)
        view = _view(dialog, TAB_HOSTS)
        model = view.model()
        view.vScrollBar.setValue(view.vScrollBar.maximum())
        QtWidgets.QApplication.processEvents()
        assert model.rowCount() == view.maxRowsInViewport
        last_label = model.headerData(model.rowCount() - 1, QtCore.Qt.Orientation.Vertical)
        assert int(last_label) == model.totalRowCount
        # stepping past the end must never leave an empty viewport
        view.vScrollBar.setValue(view.vScrollBar.maximum() + 50)
        QtWidgets.QApplication.processEvents()
        assert model.rowCount() == view.maxRowsInViewport

    def test_end_and_home_keys(self, dialog):
        _no_limit(dialog)
        _no_split(dialog, TAB_HOSTS)
        view = _view(dialog, TAB_HOSTS)
        view.setFocus()
        QTest.keyClick(view, QtCore.Qt.Key.Key_End)
        QtWidgets.QApplication.processEvents()
        assert view.vScrollBar.value() == view.vScrollBar.maximum()
        QTest.keyClick(view, QtCore.Qt.Key.Key_Home)
        QtWidgets.QApplication.processEvents()
        assert view.vScrollBar.value() == 0
        assert view.model().items[0][0] == "host000.example.net"

    def test_limit_caps_the_rows(self, dialog):
        _no_split(dialog, TAB_HOSTS)
        view = _view(dialog, TAB_HOSTS)
        dialog.limitCombo.setCurrentIndex(0)
        QtWidgets.QApplication.processEvents()
        assert view.model().totalRowCount == 50
        assert view.vScrollBar.maximum() == 50 - view.maxRowsInViewport

    def test_refresh_keeps_the_scroll_position(self, dialog):
        _no_limit(dialog)
        _no_split(dialog, TAB_HOSTS)
        view = _view(dialog, TAB_HOSTS)
        view.vScrollBar.setValue(77)
        QtWidgets.QApplication.processEvents()
        dialog.refresh_active_table()
        QtWidgets.QApplication.processEvents()
        assert view.vScrollBar.value() == 77
        assert view.model().items[0][0] == "host077.example.net"

    def test_click_selects_the_absolute_row(self, dialog):
        _no_limit(dialog)
        _no_split(dialog, TAB_HOSTS)
        view = _view(dialog, TAB_HOSTS)
        view.vScrollBar.setValue(100)
        QtWidgets.QApplication.processEvents()
        y = view.rowViewportPosition(3) + 5
        QTest.mouseClick(view.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=QtCore.QPoint(60, y))
        QtWidgets.QApplication.processEvents()
        assert [r[0] for r in view.selectedRows()] == ["host103.example.net"]


class TestSplitBy:
    def test_hosts_are_split_by_ip_by_default(self, dialog):
        dialog.cfg.settings.remove(dialog._split_setting(TAB_HOSTS, dialog.cfg.STATS_SPLIT_BY))
        view = _view(dialog, TAB_HOSTS)
        model = view.model()
        headers = [model.headerData(c, QtCore.Qt.Orientation.Horizontal) for c in range(model.columnCount())]
        assert headers[:3] == ["Host", "Hits", "IP"]
        assert "GROUP BY c.dst_host, c.dst_ip" in model.baseQueryStr
        assert dialog.filterBar._split_btn.isVisible()
        assert dialog.filterBar._split_btn.text().startswith("Group by: IP")

    def test_two_hosts_on_one_ip_stay_apart(self, dialog):
        dialog.set_split_by(TAB_HOSTS, ["ip"])
        view = _view(dialog, TAB_HOSTS)
        rows = view.model().dumpRows(nolimits=True)
        shared = [r for r in rows if r[2] == "34.120.115.102"]
        assert sorted(r[0] for r in shared) == ["incoming.telemetry.mozilla.org", "telemetry.mozilla.org"]

    def test_toggling_a_dimension_updates_query_and_settings(self, dialog):
        dialog.set_split_by(TAB_HOSTS, ["ip"])
        view = _view(dialog, TAB_HOSTS)
        dialog.filterBar._split_actions["port"].setChecked(True)
        QtWidgets.QApplication.processEvents()
        model = view.model()
        headers = [model.headerData(c, QtCore.Qt.Orientation.Horizontal) for c in range(model.columnCount())]
        assert headers[:4] == ["Host", "Hits", "IP", "Port"]
        assert dialog.get_split_by(TAB_HOSTS) == ["ip", "port"]
        dialog.filterBar._split_actions["ip"].setChecked(False)
        dialog.filterBar._split_actions["port"].setChecked(False)
        QtWidgets.QApplication.processEvents()
        assert dialog.get_split_by(TAB_HOSTS) == []
        assert "FROM hosts" in view.model().baseQueryStr

    def test_split_button_hidden_in_detail_view_and_on_events(self, dialog):
        _view(dialog, TAB_MAIN)
        assert not dialog.filterBar._split_btn.isVisible()
        events = dialog.TABLES[TAB_MAIN]['view']
        from opensnitch.dialogs.events import constants
        dialog._cb_main_table_double_clicked(events.model().index(0, constants.COL_DSTHOST))
        QtWidgets.QApplication.processEvents()
        assert dialog.get_current_view_idx() == TAB_HOSTS
        assert dialog.in_detail_view(TAB_HOSTS)
        assert not dialog.filterBar._split_btn.isVisible()
        dialog.TABLES[TAB_HOSTS]['cmd'].click()
        QtWidgets.QApplication.processEvents()
        assert dialog.filterBar._split_btn.isVisible()

    def test_double_click_filters_events_by_every_column(self, dialog):
        dialog.set_split_by(TAB_HOSTS, ["ip"])
        view = _view(dialog, TAB_HOSTS)
        first = view.model().items[0]
        dialog._cb_table_double_clicked(view.model().index(0, 0))
        QtWidgets.QApplication.processEvents()
        # grouped rows filter the view they are in; one chip per column
        assert dialog.get_current_view_idx() == TAB_HOSTS
        assert [(c.key, c.value) for c in dialog.filterBar._chips] == [("host", first[0]), ("ip", first[2])]
        dialog.filterBar.clearAll()

    def test_filter_bar_keys_are_known_connection_fields(self):
        from opensnitch.customwidgets.filterbar import FilterBarWidget
        from opensnitch.proto.enums import ConnFields
        known = {f.value for f in ConnFields}
        conn_fields = {v for v in FilterBarWidget.FIELD_MAP.values() if v.startswith("conn.")}
        assert conn_fields <= known


class TestGeoDB:
    def test_private_and_bogus_addresses_are_not_looked_up(self, tmp_path, monkeypatch):
        from opensnitch.utils import GeoDB
        monkeypatch.setenv("OPENSNITCH_MMDB_DIR", str(tmp_path))
        geo = GeoDB()
        assert geo.country("192.168.1.10") == ""
        assert geo.asn("not-an-ip") == ""
        assert geo.country("8.8.8.8") == ""
        assert not geo.has_country()
        assert GeoDB.is_public("8.8.8.8")
        assert not GeoDB.is_public("10.0.0.1")
        assert not GeoDB.is_public("::1")

    def test_lookup_when_databases_are_present(self):
        from opensnitch.utils import GeoDB
        geo = GeoDB()
        if not geo.has_country():
            pytest.skip("no .mmdb database available")
        assert geo.country("8.8.8.8").split(" ")[0] == "US"
        if geo.has_asn():
            assert geo.asn("8.8.8.8").startswith("AS15169")


class TestSplitKeepsPlace:
    def test_users_key_reads_the_same_grouped_or_not(self, dialog):
        from opensnitch.dialogs.events.constants import TAB_USERS
        dialog.set_split_by(TAB_USERS, [])
        view = _view(dialog, TAB_USERS)
        plain = {str(view.model().index(r, 0).data()) for r in range(view.model().rowCount())}
        dialog.set_split_by(TAB_USERS, ["host"])
        view = _view(dialog, TAB_USERS)
        grouped = {str(view.model().index(r, 0).data()) for r in range(view.model().rowCount())}
        assert grouped and grouped <= plain
        dialog.set_split_by(TAB_USERS, [])

    def test_toggling_group_by_keeps_sort_and_anchor(self, dialog):
        dialog.set_split_by(TAB_HOSTS, [])
        view = _view(dialog, TAB_HOSTS)
        _no_limit(dialog)
        header = view.horizontalHeader()
        header.setSortIndicator(0, QtCore.Qt.SortOrder.DescendingOrder)
        dialog.on_table_header_clicked(0, QtCore.Qt.SortOrder.DescendingOrder)
        QtWidgets.QApplication.processEvents()
        assert dialog.TABLES[TAB_HOSTS]['last_order_by'] == 1
        # look at the 6th host
        # the window must be short enough for the list to scroll
        dialog.resize(1200, 360)
        QtWidgets.QApplication.processEvents()
        view.calculateRowsInViewport()
        view.onRowCountChanged()
        view.vScrollBar.setValue(5)
        QtWidgets.QApplication.processEvents()
        anchor = str(view.model().index(0, 0).data())
        dialog.filterBar._split_actions["ip"].setChecked(True)
        QtWidgets.QApplication.processEvents()
        assert dialog.get_split_by(TAB_HOSTS) == ["ip"]
        assert dialog.TABLES[TAB_HOSTS]['last_order_by'] == 1
        assert header.sortIndicatorSection() == 0
        # the anchor stays on screen, around the middle of the viewport, selected
        keys = [str(view.model().index(r, 0).data()) for r in range(view.model().rowCount())]
        assert anchor in keys
        assert 0 < keys.index(anchor) <= view.maxRowsInViewport // 2 + 1
        assert view.vScrollBar.value() == view.model().viewOffset > 0
        assert view._rows_selection == {anchor}
        dialog.filterBar._split_actions["ip"].setChecked(False)
        QtWidgets.QApplication.processEvents()
        keys = [str(view.model().index(r, 0).data()) for r in range(view.model().rowCount())]
        assert anchor in keys
        dialog.resize(1200, 700)

    def test_sort_on_a_removed_grouping_column_falls_back_to_the_key(self, dialog):
        dialog.set_split_by(TAB_HOSTS, ["ip", "port"])
        view = _view(dialog, TAB_HOSTS)
        view.horizontalHeader().setSortIndicator(3, QtCore.Qt.SortOrder.AscendingOrder)
        dialog.on_table_header_clicked(3, QtCore.Qt.SortOrder.AscendingOrder)
        QtWidgets.QApplication.processEvents()
        assert dialog.TABLES[TAB_HOSTS]['last_order_by'] == 4
        dialog.filterBar._split_actions["port"].setChecked(False)
        QtWidgets.QApplication.processEvents()
        assert dialog.TABLES[TAB_HOSTS]['last_order_by'] == "1"
        assert view.horizontalHeader().sortIndicatorSection() == 0
        assert view.model().columnCount() >= 3
        dialog.set_split_by(TAB_HOSTS, ["ip"])


def test_summary_headers_are_named_after_grouping_is_removed(dialog):
    from opensnitch.dialogs.events.constants import TAB_USERS
    dialog.set_split_by(TAB_USERS, ["host"])
    view = _view(dialog, TAB_USERS)
    dialog.set_split_by(TAB_USERS, [])
    view = _view(dialog, TAB_USERS)
    model = view.model()
    headers = [model.headerData(c, QtCore.Qt.Orientation.Horizontal) for c in range(model.columnCount())]
    assert headers[:2] == ["User", "Hits"]
    assert view.horizontalHeader().defaultAlignment() & QtCore.Qt.AlignmentFlag.AlignLeft
