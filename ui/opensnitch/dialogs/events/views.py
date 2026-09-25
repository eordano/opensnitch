import csv
import io
import os
import threading
import datetime

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC

from opensnitch.customwidgets.colorizeddelegate import ColorizedDelegate
from opensnitch.customwidgets.addresstablemodel import AddressTableModel
from opensnitch.utils import AsnDB, GeoDB
from opensnitch.utils import (
    Message
)
from opensnitch.config import Config
from opensnitch.utils.themes import Themes
from .tasks import (
    nodemon
)
from . import (
    base,
    constants,
    config,
    nodes,
    queries
)

class ViewsManager(config.ConfigManager, nodes.NodesManager, base.EventsBase):
    def __init__(self, parent):
        super(ViewsManager, self).__init__(parent)
        self._lock = threading.RLock()

        self.cfg = Config.get()
        self.node_mon = nodemon.Nodemon(self)
        self.queries = queries.Queries(self)

        self._last_update = datetime.datetime.now()
        self.TABLES = self.default_views_config()

        # restore scrollbar position when going back from a detail view
        self.LAST_SCROLL_VALUE = None

        # try to restore last selections
        self.LAST_SELECTED_ITEM = ""
        self.LAST_TAB = 0
        self.LAST_NETSTAT_NODE = None

        # if the user clicks on an item of a table, it'll enter into the detail
        # view. From there, deny further clicks on the items.
        self.IN_DETAIL_VIEW = {
            constants.TAB_MAIN: False,
            constants.TAB_NODES: False,
            constants.TAB_RULES: False,
            constants.TAB_HOSTS: False,
            constants.TAB_PROCS: False,
            constants.TAB_ADDRS: False,
            constants.TAB_PORTS: False,
            constants.TAB_USERS: False,
            constants.TAB_NETSTAT: False,
            constants.TAB_FIREWALL: False,
            constants.TAB_ALERTS: False
        }
        # used to skip updates while the user is moving the scrollbar
        self.scrollbar_active = False

        # skip table updates if a contextual menu is active
        self._context_menu_active = False

    def view_setup(
        self,
        tableWidget,
        table_name,
        fields="*",
        group_by="",
        order_by="2",
        sort_direction=constants.SORT_ORDER[constants.SORT_DESC],
        limit="",
        resize_cols=(),
        model=None,
        delegate=None,
        verticalScrollBar=None,
        tracking_column=constants.COL_TIME,
        widget=QtWidgets.QTableView
    ):

        tableWidget.setSortingEnabled(True)
        tableWidget.setAlternatingRowColors(True)
        tableWidget.setStyleSheet(
            "QTableView {"
            "  gridline-color: palette(midlight);"
            "  selection-background-color: rgba(0, 120, 215, 90);"
            "  selection-color: palette(text);"
            "}"
            "QTableView::item {"
            "  padding: 2px 6px;"
            "}"
            "QTableView::item:hover {"
            "  background-color: rgba(0, 120, 215, 25);"
            "}"
            "QTableCornerButton::section { background: palette(window); border: none; border-bottom: 2px solid palette(mid); }"
            "QTableView QHeaderView::section {"
            "  background-color: palette(window);"
            "  border: none;"
            "  border-bottom: 2px solid palette(mid);"
            "  border-right: 1px solid palette(midlight);"
            "  padding: 5px 8px;"
            "  font-weight: 600;"
            "  font-size: 11px;"
            "  text-align: left;"
            "}"
            "QTableView QHeaderView::section:hover {"
            "  background-color: palette(midlight);"
            "}"
            "QTableView QHeaderView::section:pressed {"
            "  background-color: palette(mid);"
            "}"
        )
        tableWidget.horizontalHeader().setDefaultAlignment(
            QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        if model is None:
            model = self._db.get_new_qsql_model()
        if verticalScrollBar is not None:
            tableWidget.setVerticalScrollBar(verticalScrollBar)
        tableWidget.verticalScrollBar().sliderPressed.connect(self.cb_scrollbar_pressed)
        tableWidget.verticalScrollBar().sliderReleased.connect(self.cb_scrollbar_released)
        tableWidget.signals.paginateEvent.connect(self._cb_on_paginate_event)
        tableWidget.setTrackingColumn(tracking_column)

        # "SELECT " + fields + " FROM " + table_name + group_by + " ORDER BY " + order_by + " " + sort_direction + limit)
        self.queries.setQuery(
            model,
            f"SELECT {fields} FROM {table_name}{group_by} ORDER BY {order_by} {sort_direction}{limit}",
            limit=self.get_query_limit()
        )
        tableWidget.setModel(model)

        if delegate is not None:
            # configure the personalized delegate from actions, if any
            action = self._actions.get(delegate)
            if action is not None:
                tableWidget.setItemDelegate(ColorizedDelegate(tableWidget, actions=action))

        header = tableWidget.horizontalHeader()
        if header is not None:
            header.sortIndicatorChanged.connect(self._cb_table_header_clicked)
            header.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
            header.customContextMenuRequested.connect(self.configure_header_contextual_menu)

            for _, col in enumerate(resize_cols):
                header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionsMovable(True)

        cur_idx = self.get_current_view_idx()
        self.cfg.setSettings("{0}{1}".format(Config.STATS_VIEW_DETAILS_COL_STATE, cur_idx), header.saveState())
        return tableWidget

    # ignore updates while the user is using the scrollbar.
    def cb_scrollbar_pressed(self):
        self.set_scrollbar_active(True)

    def cb_scrollbar_released(self):
        self.set_scrollbar_active(False)

    def reset_statusbar(self):
        self.daemonVerLabel.setText("")
        self.uptimeLabel.setText("")
        self.rulesLabel.setText("")
        self.consLabel.setText("")
        self.droppedLabel.setText("")
        self.statusLine.clear()

    def needs_refresh(self):
        diff = datetime.datetime.now() - self._last_update
        if diff.seconds < self._ui_refresh_interval:
            return False

        return True

    def in_detail_view(self, idx):
        return self.IN_DETAIL_VIEW[idx]

    def set_in_detail_view(self, idx, state):
        self.IN_DETAIL_VIEW[idx] = state

    def set_last_selected_item(self, what):
        self.LAST_SELECTED_ITEM = what

    def get_view_context_menu(self, idx):
        return self.TABLES[idx]['context_menu']

    def set_view_context_menu(self, idx, menu):
        self.TABLES[idx]['context_menu'] = menu

    def set_scrollbar_active(self, state):
        self.scrollbar_active = state

    def is_scrollbar_active(self):
        return self.scrollbar_active

    def set_context_menu_active(self, state):
        self._context_menu_active = state

    def is_context_menu_active(self):
        return self._context_menu_active

    def get_view_limit(self):
        limit = constants.LIMITS[self.limitCombo.currentIndex()]
        if limit == "":
            return ""
        return " " + limit

    def get_query_limit(self):
        limit = 0
        if self.limitCombo.currentText() != "":
            limit = int(self.limitCombo.currentText())
        return limit

    def get_view_order(self, field=None):
        cur_idx = self.get_current_view_idx()
        order_field = self.TABLES[cur_idx]['last_order_by']
        if field is not None:
            order_field  = field
        direction = constants.SORT_ORDER[self.TABLES[cur_idx]['last_order_to']]
        if cur_idx in constants.SPLIT_VIEW_KEY and self.get_split_by(cur_idx) and str(order_field) != "1":
            # The identifying key is the outer group; header sorts apply within it.
            return " ORDER BY 1 ASC, %s %s" % (order_field, direction)
        return " ORDER BY %s %s" % (order_field, direction)

    def get_view_config(self, idx):
        return self.TABLES[idx]

    def set_view_config(self, idx, config):
        self.TABLES[idx] = config

    def get_view_name(self, idx):
        return self.TABLES[idx]['name']

    def get_view(self, idx):
        return self.TABLES[idx]['view']

    def set_view(self, idx, view):
        self.TABLES[idx]['view'] = view

    def update_interception_status(self, enabled):
        self.startButton.setDown(enabled)
        self.startButton.setChecked(enabled)
        if enabled:
            self._update_status_label(running=True, text=self.FIREWALL_RUNNING)
        else:
            self._update_status_label(running=False, text=self.FIREWALL_DISABLED)

    def clear_rows_selection(self):
        cur_idx = self.get_current_view_idx()
        self.TABLES[cur_idx]['view'].clearSelection()

    def are_rows_selected(self):
        cur_idx = self.get_current_view_idx()
        view = self.TABLES[cur_idx]['view']
        ret = False
        if view is not None:
            ret = len(view.selectionModel().selectedRows(0)) > 0
        return ret

    def set_filter_line_color(self, text):
        if text == "":
            self.filterLine.setStyleSheet('')
        else:
            self.filterLine.setStyleSheet('background-color: %s' % Themes.success_bg_color())

    # https://stackoverflow.com/questions/40225270/copy-paste-multiple-items-from-qtableview-in-pyqt4
    def copy_selected_rows(self):
        cur_idx = self.get_current_view_idx()
        if self.fw_view_active():
            cur_idx =  constants.TAB_FIREWALL
        elif self.get_current_view_idx() ==  constants.TAB_RULES and not self.fwTable.isVisible():
            cur_idx =  constants.TAB_RULES
        selection = self.TABLES[cur_idx]['view'].selectedRows()
        if selection:
            stream = io.StringIO()
            csv.writer(stream, delimiter=',').writerows(selection)
            QtWidgets.QApplication.clipboard().setText(stream.getvalue())
            stream.close()
            stream = None
        selection = None

    # must be called after setModel() or setQuery()
    def show_columns(self):
        hideNodeCol = self.nodes_count() < 2
        self.eventsTable.setColumnHidden(constants.COL_NODE, hideNodeCol)
        self.rulesTable.setColumnHidden(constants.COL_R_NODE, hideNodeCol)

        for idx in range(len(self.TABLES)):
            self.show_view_columns(idx)

    def show_view_columns(self, idx):
        if idx not in self.TABLES:
            return
        tbl_name = self.TABLES[idx]['name']
        view = self.TABLES[idx]['view']
        if view is None:
            return
        cols_num = len(view.model().headers())
        cols = self.cfg.getSettings(Config.STATS_SHOW_COLUMNS + f"_{tbl_name}")
        if cols is not None:
            for c in range(cols_num):
                view.setColumnHidden(c, str(c) not in cols)

    def on_filter_line_changed(self, text):
        cur_idx = self.get_current_view_idx()
        model = self.TABLES[cur_idx]['view'].model()
        self.set_filter_line_color(text)

        if text == "" and not self.in_detail_view(cur_idx):
            qstr = self.queries.get_view_query(model, cur_idx)
            self.queries.setQuery(model, qstr, limit=self.get_query_limit())
            return

        adv_filter = self.queries.advanced_search(text)
        qstr = None
        if cur_idx == constants.TAB_MAIN:
            self.cfg.setSettings(Config.STATS_FILTER_TEXT, text)
            self.queries.set_events_query(adv_filter)
            return

        elif cur_idx == constants.TAB_NODES:
            qstr = self.queries.get_nodes_filter(
                self.in_detail_view(constants.TAB_NODES),
                model.query().lastQuery(),
                text,
                adv_filter
            )

        elif self.fw_view_active(cur_idx):
            self.TABLES[constants.TAB_FIREWALL]['view'].filterByQuery(text)
            return

        elif self.in_detail_view(cur_idx):
            qstr = self.queries.get_indetail_filter(
                self.in_detail_view(cur_idx),
                model.query().lastQuery(),
                text,
                adv_filter)

        else:
            where_clause = self.queries.get_filter_line(cur_idx, text, adv_filter)
            qstr = self.queries.get_view_query(model, cur_idx, where_clause)

        if qstr is not None:
            self.queries.setQuery(model, qstr, limit=self.get_query_limit(), offset=0)

    def on_splitter_moved(self, tab, pos, index):
        if tab ==  constants.TAB_RULES:
            self.comboRulesFilter.setVisible(pos == 0)
            self.cfg.setSettings(Config.STATS_RULES_SPLITTER_POS, self.rulesSplitter.saveState())
        elif tab ==  constants.TAB_NODES:
            #w = self.nodesSplitter.width()
            #if pos >= w-2:
            #    self._unmonitor_deselected_node()
            self.cfg.setSettings(Config.STATS_NODES_SPLITTER_POS, self.nodesSplitter.saveState())

    def on_table_clicked(self, idx):
        cur_idx = self.get_current_view_idx()
        if cur_idx != constants.TAB_NODES:
            return

        try:
            row = idx.row()
            model = idx.model()
            addr = model.index(row, constants.COL_NODE).data()
            uptime = model.index(row, constants.COL_N_UPTIME).data()
            host = model.index(row, constants.COL_N_HOSTNAME).data()
            node_version = model.index(row, constants.COL_N_VERSION).data()
            kernel = model.index(row, constants.COL_N_KERNEL).data()

            unmonitor = self.LAST_SELECTED_ITEM == addr or (self.LAST_SELECTED_ITEM != addr and self.LAST_SELECTED_ITEM != "")
            monitor = self.LAST_SELECTED_ITEM == "" or self.LAST_SELECTED_ITEM != addr
            if unmonitor:
                self.node_mon.unmonitor_deselected_node(self.LAST_SELECTED_ITEM)

            if monitor:
                self.node_mon.monitor_selected_node(
                    addr,
                    uptime,
                    host,
                    node_version,
                    kernel
                )

            if monitor:
                self.LAST_SELECTED_ITEM = addr
            else:
                self.LAST_SELECTED_ITEM = ""

        except Exception as e:
            print("[stats] exception monitoring node:", e)

    def on_table_header_clicked(self, pos, sortOrder):
        cur_idx = self.get_current_view_idx()
        # TODO: allow ordering by Network column
        if cur_idx ==  constants.TAB_ADDRS and pos == 2:
            return

        model = self.get_active_table().model()
        qstr = model.query().lastQuery().split("ORDER BY")[0]

        q = qstr.strip(" ") + " ORDER BY %d %s" % (pos+1,  constants.SORT_ORDER[sortOrder.value])
        if cur_idx > 0 and self.TABLES[cur_idx]['cmd'].isVisible() is False:
            self.TABLES[cur_idx]['last_order_by'] = pos+1
            self.TABLES[cur_idx]['last_order_to'] = sortOrder.value

            q = qstr.strip(" ") + self.get_view_order()

        q += self.get_view_limit()
        self.queries.setQuery(model, q, limit=self.get_query_limit())

        header = self.get_active_table().horizontalHeader()
        sort_order = QtCore.Qt.SortOrder.DescendingOrder if sortOrder.value == constants.SORT_DESC else QtCore.Qt.SortOrder.AscendingOrder
        header.setSortIndicator(pos, sort_order)

    def on_menu_export_csv_clicked(self, tab_idx):
        tbl_name = self.get_view_name(tab_idx)
        filename = QtWidgets.QFileDialog.getSaveFileName(
            self,
            QC.translate("stats", 'Save as CSV'),
            tbl_name + ".csv",
            'All Files (*);;CSV Files (*.csv)')[0].strip()
        if not filename:
            return
        file_dir = os.path.dirname(filename)
        if not os.path.exists(file_dir):
            Message.ok(
                QC.translate("preferences", "Warning"),
                QC.translate("preferences",
                                "Invalid file selected:<br><br>{0}".format(filename)),
                QtWidgets.QMessageBox.Icon.Warning)
            return

        with self._lock:
            table = self.get_view(tab_idx)
            model = table.model()
            ncols = model.columnCount()
            nrows = model.rowCount()
            cols = []

            for col in range(0, ncols):
                cols.append(model.headerData(col, QtCore.Qt.Orientation.Horizontal))

            with open(filename, 'w') as csvfile:
                w = csv.writer(csvfile, dialect='excel')
                w.writerow(cols)
                w.writerows(model.dumpRows(nolimits=True))

    def on_menu_node_export_clicked(self, triggered):
        outdir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            QC.translate("stats", 'Select a directory to export rules'),
            os.path.expanduser("~"),
            QtWidgets.QFileDialog.Option.ShowDirsOnly | QtWidgets.QFileDialog.Option.DontResolveSymlinks
        )
        if outdir == "":
            return

        node = self.nodesLabel.text()
        if self.node_export_rules(node, outdir) is False:
            Message.ok(
                "Rules export error",
                QC.translate("stats",
                             "Error exporting rules"
                             ),
                QtWidgets.QMessageBox.Icon.Warning)
        else:
            Message.ok(
                "Rules export",
                QC.translate("stats", "Rules exported to {0}".format(outdir)),
                QtWidgets.QMessageBox.Icon.Information)

    def on_menu_node_import_clicked(self, triggered):
        rulesdir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            QC.translate("stats", 'Select a directory with rules to import (JSON files)'),
            os.path.expanduser("~"),
            QtWidgets.QFileDialog.Option.ShowDirsOnly | QtWidgets.QFileDialog.Option.DontResolveSymlinks
        )
        if rulesdir == '':
            return

        node = self.nodesLabel.text()
        nid, notif, rules = self.node_import_rules(addr=node, rulesdir=rulesdir, callback=self._notification_callback)
        if nid is not None:
            self.save_ntf(nid, notif)
            # TODO: add rules per node and after receiving the notification
            for node in self.node_list():
                self.node_add_rules(node, rules)

            Message.ok(
                "Rules import",
                QC.translate("stats", "Rules imported fine"),
                QtWidgets.QMessageBox.Icon.Information)
            if self.get_current_view_idx() ==  constants.TAB_RULES:
                self.refresh_active_table()
        else:
            Message.ok(
                "Rules import error",
                QC.translate("stats",
                             "Error importing rules from {0}".format(rulesdir)
                             ),
                QtWidgets.QMessageBox.Icon.Warning)

    def on_menu_export_clicked(self, triggered):
        outdir = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            QC.translate("stats", 'Select a directory to export rules'),
            os.path.expanduser("~"),
            QtWidgets.QFileDialog.Option.ShowDirsOnly | QtWidgets.QFileDialog.Option.DontResolveSymlinks
        )
        if outdir == "":
            return

        errors = []
        for node in self.node_list():
            if self.node_export_rules(node, outdir) is False:
                errors.append(node)
           # apply_to_node()...

        if len(errors) > 0:
            errorlist = ""
            for e in errors:
                errorlist = errorlist + e + "<br>"
            Message.ok(
                "Rules export error",
                QC.translate("stats",
                             "Error exporting rules of the following nodes:<br><br>{0}"
                             .format(errorlist)
                             ),
                QtWidgets.QMessageBox.Icon.Warning)
        else:
            Message.ok(
                "Rules export",
                QC.translate("stats", "Rules exported to {0}".format(outdir)),
                QtWidgets.QMessageBox.Icon.Information)

    def on_menu_import_clicked(self, triggered):
        rulesdir = QtWidgets.QFileDialog.getExistingDirectory(
           self,
           QC.translate("stats", 'Select a directory with rules to import (JSON files)'),
           os.path.expanduser("~"),
           QtWidgets.QFileDialog.Option.ShowDirsOnly | QtWidgets.QFileDialog.Option.DontResolveSymlinks
        )
        if rulesdir == '':
            return

        nid, notif, rules = self.node_import_all_rules(rulesdir, self._notification_callback)
        if nid is not None:
            self.save_ntf(nid, notif)
            # TODO: add rules per node and after receiving the notification
            for node in self.node_list():
                self.node_add_rules(node, rules)

            Message.ok(
                "Rules import",
                QC.translate("stats", "Rules imported fine"),
                QtWidgets.QMessageBox.Icon.Information)
            if self.get_current_view_idx() ==  constants.TAB_RULES:
                self.refresh_active_table()
        else:
            Message.ok(
                "Rules import error",
                QC.translate("stats",
                             "Error importing rules from {0}".format(rulesdir)
                             ),
                QtWidgets.QMessageBox.Icon.Warning)

    def on_cmd_back_clicked(self, idx):
        try:
            cur_idx = self.get_current_view_idx()
            self.set_in_detail_view(cur_idx, False)

            self.set_active_widgets(cur_idx, False)
            if cur_idx == constants.TAB_RULES:
                self.restore_rules_tab_widgets(True)
                return
            elif cur_idx == constants.TAB_PROCS:
                self.cmdProcDetails.setVisible(False)

            model = self.get_active_table().model()
            where_clause = None
            if self.TABLES[cur_idx]['filterLine'] is not None:
                filter_text = self.TABLES[cur_idx]['filterLine'].text()
                where_clause = self.queries.get_filter_line(cur_idx, filter_text)

            qstr = self.queries.get_view_query(model, cur_idx, where_clause)
            self.queries.setQuery(model, qstr, limit=self.get_query_limit(), offset=0)
        finally:
            self.get_search_widget().setCompleter(self.queries.get_completer(cur_idx))
            self.restore_details_view_columns(
                self.TABLES[cur_idx]['view'].horizontalHeader(),
                "{0}{1}".format(Config.STATS_VIEW_COL_STATE, cur_idx)
            )
            self.restore_scroll_value()
            #self.restore_last_selected_row()

    def set_active_widgets(self, prev_idx, state, label_txt=""):
        cur_idx = self.get_current_view_idx()
        self.clear_rows_selection()
        self.sync_split_model(cur_idx, detail=state)
        self.update_split_control()
        if self.TABLES[cur_idx].get('label') is not None:
            self.TABLES[cur_idx]['label'].setVisible(state)
            self.TABLES[cur_idx]['label'].setText(label_txt)
        if self.TABLES[cur_idx].get('cmd') is not None:
            self.TABLES[cur_idx]['cmd'].setVisible(state)

        if self.TABLES[cur_idx]['filterLine'] is not None:
            self.TABLES[cur_idx]['filterLine'].setVisible(not state)

        if self.TABLES[cur_idx].get('cmdCleanStats') is not None:
            if cur_idx == constants.TAB_RULES or cur_idx == constants.TAB_NODES:
                self.TABLES[cur_idx]['cmdCleanStats'].setVisible(state)

        if cur_idx == constants.TAB_NODES:
            # when in detail view
            trackingCol = constants.COL_TIME
            if not state:
                trackingCol = constants.COL_NODE
            self.TABLES[cur_idx]['view'].setTrackingColumn(trackingCol)
            self.update_nodes_interception_status(state)
            self.nodeDeleteButton.setVisible(state)
            self.nodeActionsButton.setVisible(state)

        elif cur_idx == constants.TAB_RULES and self.rulesTable.isVisible():
            # Use constants.COL_TIME as index when in detail view. Otherwise COL_R_NAME
            # (col number 2) will be used, leading to incorrect selections.
            trackingCol = constants.COL_TIME
            if not state:
                trackingCol = constants.COL_R_NAME
            self.TABLES[cur_idx]['view'].setTrackingColumn(trackingCol)

        header = self.TABLES[cur_idx]['view'].horizontalHeader()
        if state == True:
            # going to details state
            self.cfg.setSettings("{0}{1}".format(Config.STATS_VIEW_COL_STATE, prev_idx), header.saveState())
        else:
            # going to normal state
            self.cfg.setSettings("{0}{1}".format(Config.STATS_VIEW_DETAILS_COL_STATE, cur_idx), header.saveState())

    def set_rules_tab_active(self, row, cur_idx, name_idx, node_idx):
        self.restore_rules_tab_widgets(False)
        self.comboRulesFilter.setVisible(False)

        r_name = row.model().index(row.row(), name_idx).data()
        node = row.model().index(row.row(), node_idx).data()
        self.nodeRuleLabel.setText(node)

        self.alertsTable.setVisible(False)
        self.rulesTable.setVisible(True)
        self.set_current_tab(cur_idx)

        return r_name, node

    def fw_view_active(self, cur_idx=None):
        """the firewall rules table is what the user is looking at"""
        if cur_idx is None:
            cur_idx = self.get_current_view_idx()
        return cur_idx == constants.TAB_FIREWALL or \
            (cur_idx == constants.TAB_RULES and self.fwTable.isVisible())

    def update_view_actions(self):
        """the buttons at the right of the filter bar: what this view can
        export or import"""
        idx = self.get_current_view_idx()
        actions = []
        view = self.TABLES.get(idx, {}).get('view')
        model = view.model() if view is not None else None
        rows = getattr(model, 'totalRowCount', model.rowCount() if model is not None else 0)
        has_data = bool(rows)
        raw_data = has_data
        table = self.TABLES.get(idx, {}).get('name')
        if table:
            from PyQt6.QtSql import QSqlQuery
            query = QSqlQuery(self._db_sqlite)
            if query.exec("SELECT 1 FROM " + table + " LIMIT 1"):
                raw_data = query.next()
            query.finish()
        show_filter = raw_data or bool(self.filterBar.chips()) or bool(self.filterBar.text())
        self.filterBar._input.setVisible(show_filter)
        self.filterBar._search_icon.setVisible(show_filter)
        if idx == constants.TAB_RULES:
            actions.append((
                QC.translate("stats", "New rule..."),
                QC.translate("stats", "Opens the rule editor with an empty application rule."),
                self._cb_new_rule_clicked))
            actions.append((
                QC.translate("stats", "Import rules..."),
                QC.translate("stats", "Loads the rules found in a directory of JSON files into a node."),
                lambda: self.on_menu_import_clicked(False)))
            actions.append((
                QC.translate("stats", "Export rules..."),
                QC.translate("stats", "Saves the rules of every node as JSON files in a directory."),
                lambda: self.on_menu_export_clicked(False)))
        if has_data:
            actions.append((
                QC.translate("stats", "Export CSV..."),
                QC.translate("stats", "Saves the rows of this view as a CSV file."),
                lambda i=idx: self.on_menu_export_csv_clicked(i)))
        self.filterBar.setActions(actions)

    def get_active_table(self):
        if self.fw_view_active():
            return self.TABLES[constants.TAB_FIREWALL]['view']
        elif self.get_current_view_idx() == constants.TAB_RULES and self.alertsTable.isVisible():
            return self.TABLES[constants.TAB_ALERTS]['view']

        return self.TABLES[self.get_current_view_idx()]['view']

    def refresh_active_table(self):
        cur_idx = self.get_current_view_idx()
        if cur_idx == constants.TAB_FIREWALL:
            self.TABLES[cur_idx]['view'].refresh()
            return
        model = self.get_active_table().model()
        if cur_idx in constants.SPLIT_VIEW_KEY and not self.in_detail_view(cur_idx):
            self.apply_split(cur_idx)
        else:
            lastQuery = model.query().lastQuery()
            if " LIMIT " in lastQuery:
                lastQuery = lastQuery.split(" LIMIT ")[0]
            lastQuery += self.get_view_limit()
            self.queries.setQuery(model, lastQuery, limit=self.get_query_limit())
        self.TABLES[cur_idx]['view'].refresh()

    # --- split by: extra grouping columns on the summary views

    def _split_setting(self, idx, key):
        return "{0}_{1}".format(key, self.TABLES[idx]['name'])

    def get_split_by(self, idx):
        if idx not in constants.SPLIT_VIEW_KEY:
            return []
        path = self._split_setting(idx, Config.STATS_SPLIT_BY)
        if self.cfg.settings.contains(path):
            keys = [str(k) for k in self.cfg.getList(path, [])]
        else:
            keys = list(constants.SPLIT_DEFAULTS.get(idx, []))
        own = constants.SPLIT_VIEW_KEY[idx]
        return [k for k, _, _ in constants.SPLIT_DIMENSIONS if k in keys and k != own]

    def set_split_by(self, idx, keys):
        self.cfg.setSettings(self._split_setting(idx, Config.STATS_SPLIT_BY), [str(k) for k in keys])

    def get_enrichment(self, idx):
        path = self._split_setting(idx, Config.STATS_SHOW_ENRICHMENT)
        if self.cfg.settings.contains(path):
            keys = [str(k) for k in self.cfg.getList(path, [])]
        else:
            keys = [k for k, _ in constants.ENRICH_COLUMNS]
        return [k for k, _ in constants.ENRICH_COLUMNS if k in keys]

    def set_enrichment(self, idx, keys):
        self.cfg.setSettings(self._split_setting(idx, Config.STATS_SHOW_ENRICHMENT), [str(k) for k in keys])

    def split_ip_column(self, idx, split):
        """index of the column holding an IP in the summary query, or None"""
        if constants.SPLIT_VIEW_KEY.get(idx) == "ip":
            return constants.COL_WHAT
        if "ip" in split:
            return 2 + split.index("ip")
        return None

    def available_enrichers(self):
        out = []
        for key, label in constants.ENRICH_COLUMNS:
            if key == "asn" and (AsnDB.instance().is_available() or GeoDB.instance().has_asn()):
                out.append((key, QC.translate("stats", label)))
            elif key == "country" and GeoDB.instance().has_country():
                out.append((key, QC.translate("stats", label)))
        return out

    def sync_split_model(self, idx, detail=False):
        """point the view's model at the IP column to enrich (none in detail view)"""
        if idx not in constants.SPLIT_VIEW_KEY:
            return False
        model = self.TABLES[idx]['view'].model()
        if not isinstance(model, AddressTableModel):
            return False
        if detail:
            return model.setEnrichment(None, [])
        split = self.get_split_by(idx)
        ipcol = self.split_ip_column(idx, split)
        keys = [k for k, _ in self.available_enrichers() if k in self.get_enrichment(idx)]
        return model.setEnrichment(ipcol, keys)

    def view_anchor(self, idx):
        """the key (first column) of the top visible row, or of the current
        row when one is selected: what the person is looking at"""
        view = self.TABLES[idx]['view']
        model = view.model()
        row = 0
        sel = view.selectionModel()
        if sel is not None:
            selected = sel.selectedRows()
            cur = sel.currentIndex()
            if selected:
                row = selected[0].row()
            elif cur.isValid() and sel.isSelected(cur):
                row = cur.row()
        if model.rowCount() == 0:
            return None
        value = model.index(min(row, model.rowCount() - 1), 0).data()
        return None if value is None else str(value)

    def offset_of_key(self, model, qstr, key, cap=50000):
        """row number of the first row whose first column equals `key` in
        the ordered query, or None"""
        if key is None:
            return None
        base, _ = model._split_limit(qstr)
        q = model._exec(base)
        n = 0
        while q.next() and n < cap:
            v = q.value(0)
            if v is not None and str(v) == key:
                return n
            n += 1
        return None

    def clamp_view_order(self, idx):
        """the sort column must exist in the query about to run: the key,
        hits, then one column per grouping dimension"""
        ncols = 2 + len(self.get_split_by(idx))
        try:
            order_by = int(str(self.TABLES[idx]['last_order_by']).split(",")[0])
        except ValueError:
            return
        if order_by > ncols:
            self.TABLES[idx]['last_order_by'] = "1"
            header = self.TABLES[idx]['view'].horizontalHeader()
            header.blockSignals(True)
            header.setSortIndicator(0, QtCore.Qt.SortOrder(self.TABLES[idx]['last_order_to']))
            header.blockSignals(False)

    def apply_split(self, idx, offset=None):
        """rebuild the summary query of a view from its split settings"""
        view = self.TABLES[idx]['view']
        model = view.model()
        columns = model.columnCount()
        self.sync_split_model(idx)
        qstr = self.queries.get_view_query(model, idx)
        self.queries.setQuery(model, qstr, limit=self.get_query_limit(), offset=offset)
        if model.columnCount() != columns:
            view._columns_auto_fitted = False
        if idx == self.get_current_view_idx():
            self.filterBar.setSplitCount(model.totalRowCount if self.get_split_by(idx) else None)

    @staticmethod
    def _sql_text(value):
        return "'" + str(value).replace("'", "''") + "'"

    def split_dimension_stats(self, row_pairs=None):
        """for the Group by menu: how many rows the view would have with each
        dimension toggled, and how many distinct values it holds under the
        current filter. With `row_pairs` ([(key, value)] of one row) the
        counts are for that row only: how many rows it would become."""
        idx = self.get_current_view_idx()
        if idx not in constants.SPLIT_VIEW_KEY or self.in_detail_view(idx):
            return {}
        model = self.TABLES[idx]['view'].model()
        base = getattr(model, "baseQueryStr", "") or ""
        conditions = []
        if "FROM connections AS c" in base and " WHERE " in base:
            tail = base.split(" WHERE ", 1)[1]
            for stop in (" GROUP BY ", " ORDER BY "):
                if stop in tail:
                    tail = tail.split(stop, 1)[0]
            conditions.append("(" + tail.strip() + ")")
        cols = {k: col for k, _, col in constants.SPLIT_DIMENSIONS}
        for key, value in (row_pairs or []):
            col = cols.get(key)
            if col is None or value is None:
                continue
            text = str(value)
            if key == "uid" and text.endswith(")") and "(" in text:
                text = text.rsplit("(", 1)[1][:-1]
            conditions.append(f"c.{col} = {self._sql_text(text)}")
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        split = list(self.get_split_by(idx))
        own = constants.SPLIT_VIEW_KEY[idx]
        stats = {}
        from PyQt6 import QtSql
        with self._lock:
            for key, label, col in constants.SPLIT_DIMENSIONS:
                if key == own:
                    continue
                toggled = [k for k in split if k != key] if key in split else split + [key]
                grouped = self.queries.get_split_query(idx, toggled, where or None)
                rows = distinct = None
                sample = ""
                q = QtSql.QSqlQuery(self._db_sqlite)
                if q.exec(f"SELECT count(*) FROM ({grouped})") and q.next():
                    rows = int(q.value(0) or 0)
                q = QtSql.QSqlQuery(self._db_sqlite)
                if q.exec(f"SELECT count(DISTINCT c.{col}), MIN(c.{col}) FROM connections AS c{where}") and q.next():
                    distinct = int(q.value(0) or 0)
                    sample = q.value(1)
                stats[key] = (rows, distinct, "" if sample is None else str(sample))
        return stats

    def update_split_control(self):
        """sync the filter bar's split button with the current view"""
        idx = self.get_current_view_idx()
        show = idx in constants.SPLIT_VIEW_KEY and not self.in_detail_view(idx)
        self.filterBar.setSplitVisible(show)
        if not show:
            return
        own = constants.SPLIT_VIEW_KEY[idx]
        dims = [(k, QC.translate("stats", label)) for k, label, _ in constants.SPLIT_DIMENSIONS if k != own]
        split = self.get_split_by(idx)
        enrichers = []
        if self.split_ip_column(idx, split) is not None:
            enrichers = self.available_enrichers()
        self.filterBar.blockSignals(True)
        self.filterBar.setSplitOptions(dims, split, enrichers, self.get_enrichment(idx))
        self.filterBar.blockSignals(False)

    def restore_scroll_value(self):
        if self.LAST_SCROLL_VALUE is None:
            return
        cur_idx = self.get_current_view_idx()
        self.TABLES[cur_idx]['view'].vScrollBar.setValue(self.LAST_SCROLL_VALUE)
        self.LAST_SCROLL_VALUE = None

    def restore_last_selected_row(self):
        cur_idx = self.get_current_view_idx()
        col = constants.COL_TIME
        if cur_idx ==  constants.TAB_RULES:
            col =  constants.TAB_RULES
        elif cur_idx ==  constants.TAB_NODES:
            col =  constants.TAB_RULES

        #self.TABLES[cur_idx]['view'].selectItem(self.LAST_SELECTED_ITEM, col)
        #self.LAST_SELECTED_ITEM = ""

    def restore_details_view_columns(self, header, settings_key):
        header.blockSignals(True)
        # In order to resize the last column of a view, we firstly force a
        # resizeToContens call.
        # Secondly set resizeMode to Interactive (allow to move columns by
        # users + programmatically)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)

        col_state = self.cfg.getSettings(settings_key)
        if type(col_state) == QtCore.QByteArray:
            header.restoreState(col_state)
        header.setSectionsMovable(True)

        header.blockSignals(False)

    def restore_rules_tab_widgets(self, active):
        self.delRuleButton.setVisible(not active)
        self.editRuleButton.setVisible(not active)
        self.nodeRuleLabel.setText("")
        self.rulesTreePanel.setVisible(active)

        if not active:
            return

        self.rulesSplitter.refresh()
        self.comboRulesFilter.setVisible(self.rulesTreePanel.width() == 0)

        items = self.rulesTreePanel.selectedItems()
        if len(items) == 0:
            self.queries.set_rules_filter()
            return

        rindex = item_m = self.rulesTreePanel.indexFromItem(items[0], 0)
        parent = item_m.parent()

        # find current root item of the tree panel
        while rindex.parent().isValid():
            rindex = rindex.parent()
        rnum = rindex.row()

        if parent is not None and rnum != constants.RULES_TREE_FIREWALL:
            self.queries.set_rules_filter(parent.row(), item_m.row(), item_m.data())
        else:
            # when going back to the rules view, reset selection and select the
            # Apps view.
            index = self.rulesTreePanel.model().index(constants.RULES_TREE_APPS, 0)
            self.rulesTreePanel.setCurrentIndex(index)
            self.queries.set_rules_filter()

    def view_delete_node(self):
        ret = Message.yes_no(
            QC.translate("stats", "    You are about to delete this node.    "),
            QC.translate("stats", "    Are you sure?"),
            QtWidgets.QMessageBox.Icon.Warning)
        if ret == QtWidgets.QMessageBox.StandardButton.Cancel:
            return

        addr = self.TABLES[ constants.TAB_NODES]['label'].text()
        if self._db.remove("DELETE FROM nodes WHERE addr = ?", [addr]) is False:
            Message.ok("",
                QC.translate("stats",
                                "<b>Error deleting node</b><br><br>",
                                "{0}").format(addr),
                QtWidgets.QMessageBox.Icon.Warning)
            return

        self.node_delete(addr)
        self.TABLES[ constants.TAB_NODES]['cmd'].click()
        self.TABLES[ constants.TAB_NODES]['label'].setText("")
        self.refresh_active_table()

    def update_nodes_interception_status(self, show=True, disable=False):
        addr = self.TABLES[ constants.TAB_NODES]['label'].text()
        node_cfg = self.node_get(addr)
        if node_cfg is None:
            self.nodeStartButton.setVisible(False)
            self.nodePrefsButton.setVisible(False)
            self.nodeDeleteButton.setVisible(False)
            self.nodeActionsButton.setVisible(False)
            return
        self.nodeStartButton.setVisible(show)
        self.nodePrefsButton.setVisible(show)
        self.nodeActionsButton.setVisible(show)
        if not node_cfg['data'].isFirewallRunning or disable:
            self.nodeStartButton.setChecked(False)
            self.nodeStartButton.setDown(False)
            self.nodeStartButton.setIcon(self.iconStart)
        else:
            self.nodeStartButton.setIcon(self.iconPause)
            self.nodeStartButton.setChecked(True)
            self.nodeStartButton.setDown(True)

    def update_status(self):
        self.startButton.setDown(self.daemon_connected)
        self.startButton.setChecked(self.daemon_connected)
        self.startButton.setDisabled(not self.daemon_connected)
        if self.daemon_connected:
            self._update_status_label(running=True, text=self.FIREWALL_RUNNING)
        else:
            self._update_status_label(running=False, text=self.FIREWALL_STOPPED)
            self.statusLabel.setStyleSheet('color: %s; margin: 5px' % Themes.error_color())
