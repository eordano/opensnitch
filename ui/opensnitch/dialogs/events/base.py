
import sys
import os

from PyQt6.QtCore import QCoreApplication as QC
from PyQt6 import QtCore, QtGui, uic, QtWidgets

from opensnitch.customwidgets.sidebar import SidebarWidget
from opensnitch.customwidgets.filterbar import FilterBarWidget
from opensnitch.customwidgets.detailpanel import ConnectionDetailPanel
from opensnitch.customwidgets.bulkbar import BulkActionBar
from . import (
    constants
)

DIALOG_UI_PATH = "%s/../../res/stats.ui" % os.path.dirname(sys.modules[__name__].__file__)
class EventsBase(QtWidgets.QDialog, uic.loadUiType(DIALOG_UI_PATH)[0]):
    def __init__(self, parent=None):
        super(EventsBase, self).__init__(parent)
        self.setupUi(self)
        self._setup_sidebar()

    def _setup_sidebar(self):
        self.sidebar = SidebarWidget(self.sidebarContainer)
        layout = QtWidgets.QVBoxLayout(self.sidebarContainer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.sidebar)
        # the .ui pinned the container between 180 and 240 px; the sidebar's
        # own layout knows how wide its widest row is, and the splitter
        # honours that minimum. Let them size it.
        self.sidebarContainer.setMinimumSize(0, 0)
        self.sidebarContainer.setMaximumSize(QtWidgets.QWIDGETSIZE_MAX, QtWidgets.QWIDGETSIZE_MAX)
        self.mainSplitter.setCollapsible(0, False)
        self.mainSplitter.setStretchFactor(0, 0)
        self.mainSplitter.setStretchFactor(1, 1)
        self.sidebar.navigationChanged.connect(self.set_current_tab)
        self.sidebar.setCurrentItem(0)

        self._setup_filter_bar()
        self._setup_detail_panel()
        self._setup_bulk_bar()
        self._setup_firewall_page()
        self._setup_status_line()

    def _setup_filter_bar(self):
        self.filterBar = FilterBarWidget(self)
        content_layout = self.contentContainer.layout()
        content_layout.insertWidget(0, self.filterBar)

    def _setup_detail_panel(self):
        """the events table above, the connection details below, with a
        handle between them"""
        self.detailPanel = ConnectionDetailPanel(self)
        self.detailPanel.setVisible(False)
        events_layout = self.eventsTable.parent().layout()
        if events_layout is None:
            return
        row = None
        for i in range(events_layout.count()):
            item = events_layout.itemAt(i)
            if item.layout() is not None and item.layout().indexOf(self.eventsTable) != -1:
                row = item.layout()
        host = QtWidgets.QWidget()
        hl = QtWidgets.QHBoxLayout(host)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        if row is not None:
            widgets = []
            while row.count():
                it = row.takeAt(0)
                if it.widget() is not None:
                    widgets.append(it.widget())
            events_layout.removeItem(row)
            # the emptied layout stays a child of the tab; keep the wrapper so
            # Python never frees what Qt still owns
            self._retired_events_row = row
            for w in widgets:
                hl.addWidget(w, 1 if w is self.eventsTable else 0)
        else:
            hl.addWidget(self.eventsTable, 1)
        self.eventsSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.eventsSplitter.setChildrenCollapsible(False)
        self.eventsSplitter.setHandleWidth(6)
        self.eventsSplitter.addWidget(host)
        self.eventsSplitter.addWidget(self.detailPanel)
        self.eventsSplitter.setStretchFactor(0, 3)
        self.eventsSplitter.setStretchFactor(1, 2)
        events_layout.addWidget(self.eventsSplitter, 1)
        self.detailPanel.installEventFilter(self)
        self._events_splitter_sized = False

    def eventFilter(self, source, event):
        if source is getattr(self, "detailPanel", None) and event.type() == QtCore.QEvent.Type.Show \
                and not self._events_splitter_sized:
            self._events_splitter_sized = True
            total = self.eventsSplitter.height()
            if total > 200:
                self.eventsSplitter.setSizes([int(total * 0.55), int(total * 0.45)])
        return super().eventFilter(source, event)

    def _setup_firewall_page(self):
        """the system firewall gets its own page: the policy panel on top, the
        rules table (declared in the .ui inside the Rules page) below it"""
        from opensnitch.dialogs.firewall import FirewallPanel
        from opensnitch.dialogs.events import constants
        page = QtWidgets.QWidget()
        page.setObjectName("firewallPage")
        vl = QtWidgets.QVBoxLayout(page)
        vl.setContentsMargins(6, 6, 6, 6)
        vl.setSpacing(8)
        self.firewallPanel = FirewallPanel(page, appicon=getattr(self, "appicon", None))
        vl.addWidget(self.firewallPanel)
        vl.addWidget(self.fwTable, 1)
        self.firewallPanel.attach_table(self.fwTable)
        self.fwTable.setVisible(True)
        idx = self.stackedWidget.addWidget(page)
        assert idx == constants.TAB_FIREWALL, idx

    def _setup_status_line(self):
        """the .ui shows the daemon figures as ten labels with dashes; they
        stay as the store the update code writes to, hidden, and one line
        renders them"""
        from opensnitch.customwidgets.statusline import StatusLine
        for name in ("label_5", "consLabel", "label_7", "droppedLabel", "label",
                     "uptimeLabel", "label_3", "rulesLabel", "rxtxLabel", "label_6", "daemonVerLabel"):
            w = getattr(self, name, None)
            if w is not None:
                w.setVisible(False)
        self.statusLine = StatusLine(self)
        self.horizontalLayout_9.insertWidget(0, self.statusLine, 1)

    def _setup_bulk_bar(self):
        self.bulkActionBar = BulkActionBar(self)
        content_layout = self.contentContainer.layout()
        content_layout.addWidget(self.bulkActionBar)
        # the Sockets refresh interval lives in the bar, with a label saying
        # what the "5s" is
        self.netstatIntervalLabel = QtWidgets.QLabel(QC.translate("stats", "Refresh every"))
        self.netstatIntervalLabel.setStyleSheet("color: palette(placeholder-text);")
        self.netstatIntervalLabel.setBuddy(self.comboNetstatInterval)
        self.comboNetstatInterval.setParent(self.filterBar)
        self.comboNetstatInterval.setToolTip(QC.translate(
            "stats", "How often the node is asked for its open sockets. Stop pauses the updates."))
        self.comboNetstatInterval.setMinimumHeight(30)
        self.filterBar.layout().addWidget(self.netstatIntervalLabel)
        self.filterBar.layout().addWidget(self.comboNetstatInterval)
        self.netstatIntervalLabel.hide()
        self.comboNetstatInterval.hide()
        def _show_interval(idx):
            self.netstatIntervalLabel.setVisible(idx == constants.TAB_NETSTAT)
            self.comboNetstatInterval.setVisible(idx == constants.TAB_NETSTAT)
        self.stackedWidget.currentChanged.connect(_show_interval)
        # the pages start right under the bar; their status text lines up
        # with the bar's magnifier
        for i in range(self.stackedWidget.count()):
            lay = self.stackedWidget.widget(i).layout()
            if lay is not None:
                m = lay.contentsMargins()
                lay.setContentsMargins(m.left(), 4, m.right(), m.bottom())
        self.netstatLabel.setIndent(12)

    def add_tab(self, widget, icon, label):
        self.stackedWidget.addWidget(widget)

    def set_current_tab(self, idx, block_events=False):
        if block_events:
            self.stackedWidget.blockSignals(True)
        self.stackedWidget.setCurrentIndex(idx)
        self.sidebar.setCurrentItem(idx)
        if block_events:
            self.stackedWidget.blockSignals(False)

    def get_tab_index_by_name(self, name):
        for i in range(0, self.stackedWidget.count()):
            w = self.stackedWidget.widget(i)
            if w is not None:
                if w.objectName() == name:
                    return i
        return None

    def add_toolbar_button(self, widget):
        self.horizontalLayout_10.addWidget(widget)

    def insert_toolbar_button(self, pos, widget):
        self.horizontalLayout_10.insertWidget(pos, widget)

    def add_tree_items(self, level, labels, clean=True):
        """adds new items to the panel.
         - level: index under the items will be added.
         - labels: tuple with the labels of columns 0 and 1.
         - clean: if the existing items must be deleted.
        """
        item = self.rulesTreePanel.topLevelItem(level)
        if clean:
            item.takeChildren()

        for k, v in labels:
            item.addChild(
                QtWidgets.QTreeWidgetItem([k, v])
            )
        item.setExpanded(True)

    def get_tree_item(self, idx):
        try:
            return self.rulesTreePanel.topLevelItem(idx)
        except Exception:
            return None

    def find_tree_items(self, idx, data):
        item = self.rulesTreePanel.topLevelItem(idx)
        it = QtWidgets.QTreeWidgetItemIterator(item)
        items = []
        while it.value():
            x = it.value()
            if x.data(0, QtCore.Qt.ItemDataRole.UserRole) == data:
                items.append(x)
            it+=1

        return items

    def get_tree_selected_items(self, tree_idx):
        expanded = list()
        selected = None
        item = self.rulesTreePanel.topLevelItem(tree_idx)
        it = QtWidgets.QTreeWidgetItemIterator(item)
        # save tree selected rows
        try:
            while it.value():
                v = it.value()
                if v.isExpanded():
                    expanded.append(v)
                if v.isSelected():
                    selected = v
                it += 1
        except Exception:
            pass

        return selected, expanded

    def set_tree_selected_items(self, selected, expanded):
        try:
            for item in expanded:
                items = self.rulesTreePanel.findItems(item.text(0), QtCore.Qt.MatchRecursive)
                for it in items:
                    it.setExpanded(True)
                    if selected is not None and selected.text(0) == it.text(0):
                        it.setSelected(True)
        except:
            pass

    def get_current_view_idx(self):
        return self.stackedWidget.currentIndex()

    def get_central_widget(self):
        return self.stackedWidget

    def get_data_view(self, idx):
        return self.eventsTable

    def get_search_widget(self):
        return self.filterLine

    def get_search_text(self):
        return self.filterLine.text()

    def set_search_text(self, text):
        return self.filterLine.setText(text)
