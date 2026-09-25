from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import QCoreApplication as QC

from opensnitch.config import Config
from opensnitch.dialogs.conndetails import ConnDetails
from opensnitch.firewall import Rules as FwRules
from opensnitch.utils import Message, Icons
from opensnitch.customwidgets.firewalltableview import FirewallTableModel
from . import (
    constants,
    views
)

ALL_NODES="all"

class MenusManager(views.ViewsManager):
    def __init__(self, parent):
        super().__init__(parent)

    def configure_main_btn_menu(self):
        menu = QtWidgets.QMenu(self)
        menu.addAction(
            Icons.new(self, "go-up"),
            QC.translate("stats", "Export rules")).triggered.connect(self.on_menu_node_export_clicked)
        menu.addAction(
            Icons.new(self, "go-down"),
            QC.translate("stats", "Import rules")).triggered.connect(self.on_menu_node_import_clicked)
        self.nodeActionsButton.setMenu(menu)

        menuActions = QtWidgets.QMenu(self)
        menuActions.addAction(
            Icons.new(self, "go-up"),
            QC.translate("stats", "Export rules")).triggered.connect(self.on_menu_export_clicked)
        menuActions.addAction(
            Icons.new(self, "go-down"),
            QC.translate("stats", "Import rules")).triggered.connect(self.on_menu_import_clicked)

        menuExport = QtWidgets.QMenu(QC.translate("stats", "Export to CSV"), self)
        menuExport.setIcon(Icons.new(self, "document-save"))
        for idx in range(constants.TAB_MAIN, constants.TAB_TOTAL):
            if not idx in self.TABLES:
                continue
            act = QtGui.QAction(
                QC.translate("stats", self.get_view_name(idx)), self
            )
            act.triggered.connect(lambda checked=False, i=idx: self.on_menu_export_csv_clicked(i))
            menuExport.addAction(act)
        menuActions.addMenu(menuExport)
        menuActions.addSeparator()

        menuActions.addAction(
            Icons.new(self, "application-exit"),
            QC.translate("stats", "Quit")).triggered.connect(self._on_menu_exit_clicked)
        self.actionsButton.setMenu(menuActions)

    def configure_header_contextual_menu(self, pos):
        cur_idx = self.get_current_view_idx()
        # TODO: allow to configure in-detail columns
        #if self.in_detail_view(cur_idx):
        #    return
        #state = "detail_" if self.in_detail_view(cur_idx) else ""
        table = self.get_active_table()
        model = table.model()

        menu = QtWidgets.QMenu(self)

        if self.fw_view_active(cur_idx):
            cur_idx = constants.TAB_FIREWALL
            # TODO: handle properly the hidden columns, for example when the
            # user selects a fw chain that displays the up/down buttons column.
            return
        if cur_idx == constants.TAB_RULES and self.alertsTable.isVisible():
            cur_idx = constants.TAB_ALERTS
        tbl_name = self.TABLES[cur_idx]['name']

        headers = model.headers()
        headers_sel = []
        cols = self.cfg.getSettings(Config.STATS_SHOW_COLUMNS + f"_{tbl_name}")
        if cols is None:
            cols = []
        cols_len = len(cols)
        for i, h in enumerate(headers):
            haction = menu.addAction(h)
            if h == "":
                haction.setVisible(False)
            else:
                haction.setCheckable(True)
                haction.setChecked(str(i) in cols or cols_len == 0)
            headers_sel.append(haction)

        action = menu.exec(QtGui.QCursor.pos())
        new_cols = []
        for i, h in enumerate(headers_sel):
            if not h.isVisible():
                continue
            if h == action:
                self.TABLES[cur_idx]['view'].setColumnHidden(i, not h.isChecked())
            if h.isChecked():
                new_cols.append(str(i))
        self.cfg.setSettings(Config.STATS_SHOW_COLUMNS + f"_{tbl_name}", new_cols)

    def configure_events_contextual_menu(self, pos):
        try:
            cur_idx = self.get_current_view_idx()
            table = self.get_active_table()
            model = table.model()

            selection = table.selectionModel().selectedRows()
            if not selection:
                return False

            menu = QtWidgets.QMenu()
            _menu_details = menu.addAction(QC.translate("stats", "Details"))
            rulesMenu = QtWidgets.QMenu(QC.translate("stats", "Rules"))
            _menu_new_rule = rulesMenu.addAction(QC.translate("stats", "New"))
            _menu_edit_rule = rulesMenu.addAction(QC.translate("stats", "Edit"))
            menu.addMenu(rulesMenu)
            self.set_view_context_menu(constants.TAB_MAIN, menu)

            # move away menu a few pixels to the right, to avoid clicking on it by mistake
            action = menu.exec(QtGui.QCursor.pos())

            model = table.model()

            if action == _menu_new_rule:
                self.table_menu_new_rule_from_row(cur_idx, model, selection)
            elif action == _menu_edit_rule:
                self.table_menu_edit(cur_idx, model, selection)
            elif action == _menu_details:
                coltime = model.index(selection[0].row(), constants.COL_TIME).data()
                o = ConnDetails(self)
                o.showByField("time", coltime)

        except Exception as e:
            print("_configure_events_contextual_menu() exception:", e)
        finally:
            self.clear_rows_selection()
            return True

    def configure_fwrules_contextual_menu(self, pos):
        try:
            cur_idx = self.get_current_view_idx()
            table = self.get_active_table()

            selection = table.selectionModel().selectedRows()
            if not selection:
                return False

            model = table.model()
            menu = QtWidgets.QMenu()
            exportMenu = QtWidgets.QMenu(QC.translate("stats", "Export"))
            nodesMenu = QtWidgets.QMenu(QC.translate("stats", "Apply to"))

            is_rule_enabled = model.index(selection[0].row(), FirewallTableModel.COL_ENABLED).data()
            rule_action = model.index(selection[0].row(), FirewallTableModel.COL_ACTION).data()
            rule_action = rule_action.lower()

            nodes_menu = []
            if self.nodes_count() > 1:
                nodes_menu.append(
                    [
                        nodesMenu.addAction(QC.translate("stats", "All")),
                        ALL_NODES
                    ])
                for node in self.node_list():
                    nodes_menu.append([nodesMenu.addAction(node), node])
                menu.addMenu(nodesMenu)

            actionsMenu = QtWidgets.QMenu(QC.translate("stats", "Action"), self)
            _action_accept = actionsMenu.addAction(Config.ACTION_ACCEPT)
            _action_drop = actionsMenu.addAction(Config.ACTION_DROP)
            _action_reject = actionsMenu.addAction(Config.ACTION_REJECT)
            _action_return = actionsMenu.addAction(Config.ACTION_RETURN)
            if rule_action == Config.ACTION_ACCEPT or \
                    rule_action == Config.ACTION_DROP or \
                    rule_action == Config.ACTION_RETURN or \
                    rule_action == Config.ACTION_REJECT:
                menu.addSeparator()
                menu.addMenu(actionsMenu)

            _menu_new = menu.addAction(QC.translate("stats", "New"))
            _label_enable = QC.translate("stats", "Disable")
            if is_rule_enabled == "False":
                _label_enable = QC.translate("stats", "Enable")
            _menu_enable = menu.addAction(_label_enable)
            _menu_delete = menu.addAction(QC.translate("stats", "Delete"))
            _menu_edit = menu.addAction(QC.translate("stats", "Edit"))

            menu.addSeparator()
            _toClipboard = exportMenu.addAction(QC.translate("stats", "To clipboard"))
            #_toDisk = exportMenu.addAction(QC.translate("stats", "To disk"))
            menu.addMenu(exportMenu)
            self.set_view_context_menu(constants.TAB_FIREWALL, menu)

            # move away menu a few pixels to the right, to avoid clicking on it by mistake
            action = menu.exec(QtGui.QCursor.pos())

            model = table.model()

            if self.nodes_count() > 1:
                for nmenu in nodes_menu:
                    node_action = nmenu[0]
                    node_addr = nmenu[1]
                    if action == node_action:
                        ret = Message.yes_no(
                            QC.translate("stats", "    Apply this rule to {0}  ".format(node_addr)),
                            QC.translate("stats", "    Are you sure?"),
                            QtWidgets.QMessageBox.Icon.Warning)
                        if ret == QtWidgets.QMessageBox.StandardButton.Cancel:
                            return False
                        if node_addr == ALL_NODES:
                            self.table_menu_apply_to_all_nodes(cur_idx, model, selection, node_addr)
                        else:
                            self.table_menu_apply_to_node(cur_idx, model, selection, node_addr)
                        return False

            # block fw rules signals, to prevent reloading them per operation,
            # which can lead to race conditions.
            self._fw.rules.blockSignals(True)
            if action == _menu_new:
                self.new_fw_rule()
            elif action == _menu_delete:
                self.table_menu_delete(cur_idx, model, selection)
            elif action == _menu_enable:
                self.table_menu_enable(cur_idx, model, selection, is_rule_enabled)
            elif action == _menu_edit:
                self.table_menu_edit(cur_idx, model, selection)
            elif action == _action_accept or \
                action == _action_drop or \
                action == _action_reject or \
                action == _action_return:
                self.table_menu_change_rule_field(cur_idx, model, selection, FwRules.FIELD_TARGET, action.text())
            elif action == _toClipboard:
                self.table_menu_export_clipboard(cur_idx, model, selection)
            #elif action == _toDisk:
            #    self.table_menu_export_disk(cur_idx, model, selection)

            self._fw.rules.blockSignals(False)

        except Exception as e:
            print("fwrules contextual menu error:", e)
        finally:
            self.clear_rows_selection()
            return True

    # the daemon's "deny" is a drop: the packet is discarded without an answer
    ACTION_WORDS = (
        ("allow", Config.ACTION_ALLOW),
        ("drop", Config.ACTION_DENY),
        ("reject", Config.ACTION_REJECT),
    )

    def build_rules_menu(self, selection):
        """the menu of the rules table: every entry names what it does.
        Returns (menu, handlers) where handlers maps QAction -> callable(model)."""
        menu = QtWidgets.QMenu()
        handlers = {}
        cur_idx = self.get_current_view_idx()
        current_action = ""
        current_duration = ""
        is_rule_enabled = "True"
        if selection:
            is_rule_enabled = str(selection[0][constants.COL_R_ENABLED])
            if len(selection) == 1:
                current_action = str(selection[0][constants.COL_R_ACTION]).lower()
                current_duration = str(selection[0][constants.COL_R_DURATION])

        if self.nodes_count() > 1:
            nodesMenu = menu.addMenu(QC.translate("stats", "Apply to node"))
            act = nodesMenu.addAction(QC.translate("stats", "All nodes"))
            handlers[act] = lambda model, addr=ALL_NODES: self._rules_menu_apply_to(cur_idx, model, selection, addr)
            for node in self.node_list():
                act = nodesMenu.addAction(self.node_hostname(node) or node)
                handlers[act] = lambda model, addr=node: self._rules_menu_apply_to(cur_idx, model, selection, addr)

        for word, value in self.ACTION_WORDS:
            if value == current_action:
                continue
            act = menu.addAction(QC.translate("stats", "Change action to {0}").format(QC.translate("stats", word)))
            handlers[act] = lambda model, v=value: self.table_menu_change_rule_field(cur_idx, model, selection, "action", v)

        durMenu = menu.addMenu(QC.translate("stats", "Change expiration"))
        for label, value in (
            (QC.translate("stats", "Never (always)"), Config.DURATION_ALWAYS),
            (QC.translate("stats", "Until reboot"), Config.DURATION_UNTIL_RESTART),
            (Config.DURATION_12h, Config.DURATION_12h),
            (Config.DURATION_1h, Config.DURATION_1h),
            (Config.DURATION_30m, Config.DURATION_30m),
            (Config.DURATION_15m, Config.DURATION_15m),
            (Config.DURATION_5m, Config.DURATION_5m),
        ):
            act = durMenu.addAction(label)
            if value == current_duration:
                act.setEnabled(False)
                act.setToolTip(QC.translate("stats", "The rule already expires this way."))
            handlers[act] = lambda model, v=value: self.table_menu_change_rule_field(cur_idx, model, selection, "duration", v)
        menu.addSeparator()

        if is_rule_enabled == "False":
            act = menu.addAction(Icons.new(self, "media-playback-start"), QC.translate("stats", "Enable rule"))
        else:
            act = menu.addAction(Icons.new(self, "media-playback-pause"), QC.translate("stats", "Disable rule"))
        handlers[act] = lambda model: self.table_menu_enable(cur_idx, model, selection, is_rule_enabled)

        act = menu.addAction(QC.translate("stats", "Duplicate"))
        handlers[act] = lambda model: self.table_menu_duplicate(cur_idx, model, selection)
        act = menu.addAction(Icons.new(self, "document-edit"), QC.translate("stats", "Edit"))
        handlers[act] = lambda model: self.table_menu_edit(cur_idx, model, selection)
        delete_icon = QtGui.QIcon.fromTheme("edit-delete-remove")
        if delete_icon.isNull():
            delete_icon = Icons.new(self, "dialog-cancel")
        act = menu.addAction(delete_icon, QC.translate("stats", "Delete"))
        handlers[act] = lambda model: self.table_menu_delete(cur_idx, model, selection)

        menu.addSeparator()
        act = menu.addAction(Icons.new(self, "edit-copy"), QC.translate("stats", "Copy"))
        handlers[act] = lambda model: self.table_menu_export_clipboard(cur_idx, model, selection)
        act = menu.addAction(Icons.new(self, "document-save-as"), QC.translate("stats", "Save as..."))
        handlers[act] = lambda model: self.table_menu_export_disk(cur_idx, model, selection)
        return menu, handlers

    def _rules_menu_apply_to(self, cur_idx, model, selection, node_addr):
        ret = Message.yes_no(
            QC.translate("stats", "Apply this rule to {0}?").format(
                QC.translate("stats", "all nodes") if node_addr == ALL_NODES else node_addr),
            QC.translate("stats", "Are you sure?"),
            QtWidgets.QMessageBox.Icon.Warning)
        if ret == QtWidgets.QMessageBox.StandardButton.Cancel:
            return
        if node_addr == ALL_NODES:
            self.table_menu_apply_to_all_nodes(cur_idx, model, selection, node_addr)
        else:
            self.table_menu_apply_to_node(cur_idx, model, selection, node_addr)

    def configure_rules_contextual_menu(self, pos):
        try:
            table = self.get_active_table()
            selection = table.selectedRows()
            if not selection:
                return False
            menu, handlers = self.build_rules_menu(selection)
            self.set_view_context_menu(constants.TAB_RULES, menu)
            action = menu.exec(QtGui.QCursor.pos())
            handler = handlers.get(action)
            if handler is not None:
                handler(table.model())
        except Exception as e:
            print("rules contextual menu exception:", e)
        finally:
            return True

    def build_history_menu(self, idx, row):
        """the menu of a summary row (Hosts, Processes, Addresses, Ports,
        Users): filter here, open the events, drill down, copy, export"""
        menu = QtWidgets.QMenu()
        handlers = {}
        view = self.TABLES[idx]['view']
        model = view.model()
        key = constants.SPLIT_VIEW_KEY[idx]
        labels = {k: QC.translate("stats", label) for k, label, _ in constants.SPLIT_DIMENSIONS}
        value = model.index(row, 0).data()
        pairs = [(key, value)]
        for i, k in enumerate(self.get_split_by(idx)):
            pairs.append((k, model.index(row, 2 + i).data()))
        described = " ".join("{0} {1}".format(labels.get(k, k), v) for k, v in pairs if v not in (None, ""))

        act = menu.addAction(Icons.new(self, "view-list-details"), QC.translate("stats", "Show events for {0}").format(described))
        def _events(pairs=pairs):
            self.set_current_tab(constants.TAB_MAIN)
            self.filterBar.setFilters(pairs)
        handlers[act] = _events

        drill = menu.addMenu(QC.translate("stats", "Drill down by"))
        stats = self.split_dimension_stats(pairs)
        for k, action in self.filterBar._split_actions.items():
            label = self.filterBar.splitLabels().get(k, action.text())
            text, enabled = self.filterBar.describe_split_choice(label, action.isChecked(), stats.get(k))
            item = drill.addAction(text)
            item.setCheckable(True)
            item.setChecked(action.isChecked())
            item.setEnabled(enabled)
            def _drill(a=action, r=row):
                # the clicked row is the anchor the regrouped view keeps in view
                view._rows_selection = {model.index(r, view.trackingCol).data()}
                view.selectIndices()
                view.selectionModel().setCurrentIndex(
                    model.index(r, 0), QtCore.QItemSelectionModel.SelectionFlag.NoUpdate)
                a.setChecked(not a.isChecked())
            handlers[item] = _drill

        menu.addSeparator()
        act = menu.addAction(Icons.new(self, "edit-copy"), QC.translate("stats", "Copy row"))
        handlers[act] = lambda: self.copy_selected_rows()
        act = menu.addAction(Icons.new(self, "document-save"), QC.translate("stats", "Export CSV..."))
        handlers[act] = lambda: self.on_menu_export_csv_clicked(idx)
        return menu, handlers

    def configure_history_contextual_menu(self, pos):
        try:
            idx = self.get_current_view_idx()
            table = self.TABLES[idx]['view']
            index = table.indexAt(pos)
            if not index.isValid():
                return False
            menu, handlers = self.build_history_menu(idx, index.row())
            self.set_context_menu_active(True)
            try:
                action = menu.exec(QtGui.QCursor.pos())
            finally:
                self.set_context_menu_active(False)
            handler = handlers.get(action)
            if handler is not None:
                handler()
        except Exception as e:
            print("history contextual menu exception:", e)
        return False

    def configure_alerts_contextual_menu(self, pos):
        try:
            cur_idx = self.get_current_view_idx()
            table = self.get_active_table()
            model = table.model()

            selection = table.selectionModel().selectedRows()
            if not selection:
                return False

            menu = QtWidgets.QMenu()
            exportMenu = QtWidgets.QMenu(QC.translate("stats", "Export"))

            #is_rule_enabled = model.index(selection[0].row(), constants.COL_R_ENABLED).data()
            #menu_label_enable = QC.translate("stats", "Disable")
            #if is_rule_enabled == "False":
            #    menu_label_enable = QC.translate("stats", "Enable")

            _menu_view = menu.addAction(QC.translate("stats", "View"))
            _menu_delete = menu.addAction(QC.translate("stats", "Delete"))

            menu.addSeparator()
            _toClipboard = exportMenu.addAction(QC.translate("stats", "To clipboard"))
            _toDisk = exportMenu.addAction(QC.translate("stats", "To disk"))
            menu.addMenu(exportMenu)
            self.set_view_context_menu(constants.TAB_ALERTS, menu)

            # move away menu a few pixels to the right, to avoid clicking on it by mistake
            action = menu.exec(QtGui.QCursor.pos())

            model = table.model()

            if action == _menu_delete:
                self.table_menu_delete(cur_idx, model, selection)
            elif action == _menu_view:
                for idx in selection:
                    atime = model.index(idx.row(), constants.COL_TIME).data()
                    anode = model.index(idx.row(), constants.COL_NODE).data()
                    self.display_alert_info(atime, anode)

            elif action == _toClipboard:
                self.table_menu_export_clipboard(cur_idx, model, selection)
            elif action == _toDisk:
                self.table_menu_export_disk(cur_idx, model, selection)

        except Exception as e:
            print("alerts contextual menu exception:", e)
        finally:
            self.clear_rows_selection()
            return True

    def configure_tabs_contextual_menu(self, pos):
        tab_hidden_list = self.cfg.getList(Config.STATS_TAB_HIDDEN_LIST)
        if tab_hidden_list is None:
            tab_hidden_list = []
        tab_list = []

        menu = QtWidgets.QMenu(self)

        for idx, key in enumerate(self.TABLES):
            # some tables/views are not a tab, but part of a group inside a
            # tab.
            if 'isTab' not in self.TABLES[key] or self.TABLES[key]['isTab'] == False:
                continue

            checked = True
            # XXX: when loading the list for the first time, the list is a list of
            # strings. When opening the contextual menu several times, the list
            # is a list of integers.
            if str(key) in tab_hidden_list or key in tab_hidden_list:
                checked = False

            w = self.stackedWidget.widget(idx)
            if w is None:
                continue

            m = menu.addAction(self.TABLES[key]['tabName'])
            m.setObjectName(str(key))
            m.setCheckable(True)
            m.setChecked(checked)
            if idx == constants.TAB_MAIN:
                m.setEnabled(False)
            tab_list.append(m)

        action = menu.exec(QtGui.QCursor.pos())
        if action is None:
            return

        for idx, tab in enumerate(tab_list):
            if tab == action:
                tab_id = tab.objectName()
                if not tab.isChecked():
                    tab_idx = self.get_tab_index_by_name(str(tab_id))
                    if tab_idx is not None:
                        # hides the view and saves the hidden list
                        self._cb_tab_closed(tab_idx)
                    return
                else:
                    # FIXME: when saving the list and reading it again, the
                    # values are integers instead of strings, so we need to
                    # do this sorcery to test that a value is in the list.
                    # PRs to improve it welcome.
                    tab_int = -1
                    try:
                        tab_int = int(tab_id)
                    except:
                        pass
                    tab_removed = None
                    if tab_id in tab_hidden_list:
                        tab_hidden_list.remove(tab_id)
                        tab_removed = tab_id
                    if tab_int in tab_hidden_list:
                        tab_hidden_list.remove(tab_int)
                        tab_removed = str(tab_int)

                    if tab_removed is not None:
                        tab_idx = self.get_tab_index_by_name(str(tab_id))
                        if tab_idx is not None:
                            self.sidebar.setItemVisible(tab_idx, True)
                break

        self.cfg.setSettings(Config.STATS_TAB_HIDDEN_LIST, tab_hidden_list)

