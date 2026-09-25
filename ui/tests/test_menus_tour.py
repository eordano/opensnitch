"""Rules context menu wording, Group by descriptions, status card, settings tour."""
import pytest
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtGui import QIcon

import opensnitch.utils  # breaks the database <-> views import cycle
import opensnitch.proto as proto
proto.import_()

from opensnitch.database import Database
from opensnitch.dialogs.events.dialog import StatsDialog
from opensnitch.dialogs.events import constants
from opensnitch.dialogs.preferences.dialog import PreferencesDialog
from opensnitch.dialogs.preferences.tour import SettingsTour
from opensnitch.customwidgets.filterbar import FilterBarWidget
from opensnitch.customwidgets.sidebar import SidebarWidget


@pytest.fixture(scope="module")
def dialog(qapp):
    from tests.sample_data import populate_database
    db = Database.instance()
    populate_database(db, connection_count=60, socket_count=0)
    db.commit()
    d = StatsDialog(db=db, appicon=QIcon())
    d.show()
    qapp.processEvents()
    yield d
    d.hide()


def _rule_row(action="allow", enabled="True", duration="always"):
    row = [""] * 12
    row[constants.COL_R_ENABLED] = enabled
    row[constants.COL_R_ACTION] = action
    row[constants.COL_R_DURATION] = duration
    row[constants.COL_R_NAME] = "some-rule"
    return row


def _texts(menu):
    return ["|" if a.isSeparator() else a.text() for a in menu.actions()]


def test_rules_menu_names_what_each_entry_does(dialog):
    dialog.set_current_tab(constants.TAB_RULES)
    menu, handlers = dialog.build_rules_menu([_rule_row("allow", "True")])
    assert _texts(menu) == [
        "Change action to drop", "Change action to reject", "Change expiration", "|",
        "Disable rule", "Duplicate", "Edit", "Delete", "|", "Copy", "Save as...",
    ]
    assert all(a in handlers for a in menu.actions() if not a.isSeparator() and a.menu() is None)
    menu, _ = dialog.build_rules_menu([_rule_row("deny", "False")])
    texts = _texts(menu)
    assert texts[:2] == ["Change action to allow", "Change action to reject"]
    assert "Enable rule" in texts
    expiration = [a for a in menu.actions() if a.text() == "Change expiration"][0].menu()
    assert [a.text() for a in expiration.actions()][:2] == ["Never (always)", "Until reboot"]
    menu, _ = dialog.build_rules_menu([_rule_row("allow", "True", "always")])
    expiration = [a for a in menu.actions() if a.text() == "Change expiration"][0].menu()
    assert not expiration.actions()[0].isEnabled() and expiration.actions()[1].isEnabled()


def test_group_by_menu_says_what_each_choice_would_do(qapp):
    bar = FilterBarWidget()
    bar.setSplitOptions([("ip", "IP"), ("port", "Port"), ("node", "Node")], ["port"])
    bar.setSplitStatsProvider(lambda: {"ip": (4, 4, ""), "port": (24, 12, ""), "node": (24, 1, "unix:///tmp/osui.sock")})
    bar._describe_split_choices()
    texts = ["|" if a.isSeparator() else a.text() for a in bar._split_menu.actions()]
    assert texts[:2] == ["Drill down by...", "|"]
    assert bar._split_actions["ip"].text() == "IP  (4 rows)" and bar._split_actions["ip"].isEnabled()
    assert bar._split_actions["port"].text() == "Port  (24 rows without it)"
    assert bar._split_actions["node"].text() == "Node: unix:///tmp/osui.sock" and not bar._split_actions["node"].isEnabled()


def test_split_stats_come_from_the_current_view(dialog):
    dialog.set_split_by(constants.TAB_HOSTS, [])
    dialog.set_current_tab(constants.TAB_HOSTS)
    dialog.update_split_control()
    dialog.refresh_active_table()
    stats = dialog.split_dimension_stats()
    assert "ip" in stats and "host" not in stats
    rows, distinct, sample = stats["ip"]
    assert rows is not None and rows > 0 and distinct is not None and distinct > 1
    dialog.set_current_tab(constants.TAB_MAIN)
    assert dialog.split_dimension_stats() == {}


def test_status_card_keeps_uptime_on_one_line(qapp):
    sidebar = SidebarWidget()
    sidebar.updateShield(True, "0:00:45 uptime")
    assert not sidebar._shield_sub.wordWrap()
    grid = sidebar._shield.layout()
    assert isinstance(grid, QtWidgets.QGridLayout)
    assert grid.itemAtPosition(1, 0).widget() is sidebar._shield_sub
    assert grid.itemAtPosition(1, 1).widget() is sidebar._shield_sub
    assert sidebar._shield_sub.alignment() & QtCore.Qt.AlignmentFlag.AlignHCenter


def test_tour_is_a_panel_beside_the_row(qapp):
    prefs = PreferencesDialog(appicon=QIcon())
    prefs.resize(1100, 720)
    prefs.show()
    qapp.processEvents()
    from opensnitch.dialogs.preferences import design
    prefs.stackedWidget.setCurrentIndex(design.PAGE_EVENTS)
    qapp.processEvents()
    tour = SettingsTour(prefs)
    assert not tour.isWindow() and tour.parentWidget() is prefs
    assert [b.text() for b in (tour.back, tour.end_button, tour.next)] == ["Back", "End tour", "Next"]
    page = prefs.stackedWidget.currentWidget()
    assert len(tour.steps) < len([e for e in page.entries if any(w.isVisibleTo(page) for w in e.widgets)])
    grouped = [s for s in tour.steps if s.section]
    assert grouped and len(grouped[0].widgets) > 3
    assert grouped[0].title and "Tick the ones" in tour._describe(grouped[0])
    # one step per section, every row explained with its value
    assert [s.title for s in tour.steps] == ["Updates", "Columns"]
    assert "Refresh every" in tour._describe(tour.steps[0]) and "reloads" in tour._describe(tour.steps[0])
    prefs.stackedWidget.setCurrentIndex(design.PAGE_SERVER)
    qapp.processEvents()
    server = SettingsTour(prefs)
    assert [s.title for s in server.steps] == ["Incoming connections", "GUI log", "Limits"]
    text = server._describe(server.steps[2])
    assert "Largest message" in text and "memory" in text and "Ping nodes every" in text
    server.start()
    server.advance(1); server.advance(1)
    qapp.processEvents()
    assert prefs.rect().contains(server.geometry())
    assert server.body_scroll.widget() is server.body
    server.close()
    tour.start()
    qapp.processEvents()
    target = QtCore.QRect(page.viewport().mapTo(prefs, tour.target_rect().topLeft()), tour.target_rect().size())
    assert prefs.rect().contains(tour.geometry())
    assert not tour.geometry().intersects(target)
    tour.close()
    prefs.close()


def test_history_rows_have_a_menu(dialog):
    dialog.set_split_by(constants.TAB_HOSTS, ["ip"])
    dialog.set_current_tab(constants.TAB_HOSTS)
    dialog.update_split_control()
    dialog.refresh_active_table()
    QtWidgets.QApplication.processEvents()
    view = dialog.TABLES[constants.TAB_HOSTS]['view']
    assert view.model().rowCount() > 0
    menu, handlers = dialog.build_history_menu(constants.TAB_HOSTS, 0)
    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts[0].startswith("Show events for Host ") and " IP " in texts[0]
    assert texts[1] == "Drill down by" and texts[2:] == ["Copy row", "Export CSV..."]
    drill = [a for a in menu.actions() if a.text() == "Drill down by"][0].menu()
    assert any("rows" in a.text() for a in drill.actions())
    host = view.model().index(0, 0).data()
    # the row's counts are its own, smaller than the view's
    view_stats = dialog.split_dimension_stats()
    row_stats = dialog.split_dimension_stats([("host", host)])
    assert row_stats["port"][0] <= view_stats["port"][0]
    assert row_stats["host"] if "host" in row_stats else True
    single = [a for a in drill.actions() if not a.isEnabled()]
    assert all(":" in a.text() for a in single)
    handlers[menu.actions()[0]]()
    assert dialog.get_current_view_idx() == constants.TAB_MAIN
    assert dialog.filterBar.filterValue("host") == host
    dialog.filterBar.clearAll()
    dialog.set_split_by(constants.TAB_HOSTS, [])


def test_connection_details_is_a_dialog_with_fields(dialog):
    from opensnitch.dialogs.conndetails import ConnDetails
    dialog.set_current_tab(constants.TAB_MAIN)
    dialog.refresh_active_table()
    QtWidgets.QApplication.processEvents()
    model = dialog.eventsTable.model()
    coltime = model.index(0, constants.COL_TIME).data()
    details = ConnDetails(dialog)
    assert details.showByField("time", coltime)
    assert details.windowTitle() == "Connection details"
    assert details.panel.isVisibleTo(details)
    assert details.panel.currentData()["time"] == str(coltime)
    assert "dst host:" in details.details_text()
    assert [b.text() for b in (details.copy_button, details.rule_button, details.close_button)] == ["Copy details", "Create rule...", "Close"]
    QtWidgets.QApplication.processEvents()
    scroll = details.panel.findChild(QtWidgets.QScrollArea)
    content = details.content_height()
    assert content - 2 <= scroll.height() <= content + 24
    details.close()


def test_summary_views_are_named_from_the_start(qapp):
    """the first query of a summary view already aliases its columns"""
    d = StatsDialog(db=Database.instance(), appicon=QIcon())
    try:
        for idx, label in ((constants.TAB_ADDRS, "IP"), (constants.TAB_HOSTS, "Host"), (constants.TAB_USERS, "User")):
            model = d.TABLES[idx]['view'].model()
            headers = [model.headerData(c, QtCore.Qt.Orientation.Horizontal) for c in range(2)]
            assert headers == [label, "Hits"], (idx, headers)
    finally:
        d.close()


def test_drill_down_from_a_row_regroups_the_view(dialog, monkeypatch):
    dialog.set_split_by(constants.TAB_HOSTS, [])
    dialog.set_current_tab(constants.TAB_HOSTS)
    dialog.update_split_control()
    dialog.refresh_active_table()
    QtWidgets.QApplication.processEvents()
    view = dialog.TABLES[constants.TAB_HOSTS]['view']
    before = view.model().columnCount()

    def fake_exec(menu, *args, **kwargs):
        drill = [a for a in menu.actions() if a.text() == "Drill down by"][0].menu()
        port = [a for a in drill.actions() if a.text().startswith("Port")][0]
        return port
    monkeypatch.setattr(QtWidgets.QMenu, "exec", fake_exec)
    # a host that has connections (the sample stats table also lists hosts
    # without any), so the regrouped view can keep it in sight
    from PyQt6 import QtSql
    q = QtSql.QSqlQuery(dialog._db_sqlite)
    q.exec("SELECT DISTINCT dst_host FROM connections")
    known = set()
    while q.next():
        known.add(str(q.value(0)))
    row = next(r for r in range(view.model().rowCount()) if str(view.model().index(r, 0).data()) in known)
    host = str(view.model().index(row, 0).data())
    pos = view.visualRect(view.model().index(row, 0)).center()
    dialog.configure_history_contextual_menu(pos)
    QtWidgets.QApplication.processEvents()
    assert dialog.get_split_by(constants.TAB_HOSTS) == ["port"]
    assert view.model().columnCount() > before
    assert not dialog.is_context_menu_active()
    # the clicked host stays selected after the regroup
    QtWidgets.QApplication.processEvents()
    assert view._rows_selection == {host}
    assert host in [str(view.model().index(r, 0).data()) for r in range(view.model().rowCount())]
    dialog.set_split_by(constants.TAB_HOSTS, [])
    dialog.refresh_active_table()
