from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC

from opensnitch.version import version


class StatusDescription(QtWidgets.QLabel):
    """Let the status container grow to fit wrapped text at its current width."""
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.setMinimumHeight(max(0, self.heightForWidth(event.size().width())))

    def setText(self, text):
        super().setText(text)
        self.setMinimumHeight(max(0, self.heightForWidth(self.width())))


class NodeMenu(QtWidgets.QMenu):
    """a menu of checkboxes: clicking or pressing Space/Enter on a checkable
    entry toggles it and keeps the menu open, so several nodes can be picked
    in one visit; Escape or a click outside closes it"""

    def _toggle_without_closing(self, action):
        if action is not None and action.isEnabled() and action.isCheckable():
            action.trigger()
            return True
        return False

    def mouseReleaseEvent(self, event):
        if self._toggle_without_closing(self.actionAt(event.pos())):
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Space, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
            if self._toggle_without_closing(self.activeAction()):
                return
        super().keyPressEvent(event)


class SidebarWidget(QtWidgets.QWidget):

    navigationChanged = QtCore.pyqtSignal(int)
    settingsRequested = QtCore.pyqtSignal()
    interceptToggled = QtCore.pyqtSignal()
    nodeSelected = QtCore.pyqtSignal(list)

    @staticmethod
    def _sections():
        return [
            (QC.translate("sidebar", "ACTIVITY"), [
                (0, QC.translate("sidebar", "Events")),
                (8, QC.translate("sidebar", "Sockets")),
            ]),
            (QC.translate("sidebar", "RULES"), [
                (2, QC.translate("sidebar", "Rules")),
                (9, QC.translate("sidebar", "Firewall")),
            ]),
            (QC.translate("sidebar", "HISTORY"), [
                (3, QC.translate("sidebar", "Hosts")),
                (4, QC.translate("sidebar", "Processes")),
                (5, QC.translate("sidebar", "Addresses")),
                (6, QC.translate("sidebar", "Ports")),
                (7, QC.translate("sidebar", "Users")),
            ]),
        ]

    @staticmethod
    def _tooltips():
        return {
            0: QC.translate("sidebar", "Real-time outbound connection log"),
            1: QC.translate("sidebar", "Connected daemon nodes and system info"),
            2: QC.translate("sidebar", "Application allow/deny rules"),
            3: QC.translate("sidebar", "Destination hostnames contacted"),
            4: QC.translate("sidebar", "Processes that made connections"),
            5: QC.translate("sidebar", "Destination IP addresses"),
            6: QC.translate("sidebar", "Destination ports by traffic volume"),
            7: QC.translate("sidebar", "Connections grouped by system user"),
            8: QC.translate("sidebar", "Live sockets from /proc/net"),
            9: QC.translate("sidebar", "System firewall (nftables) of a node: default policy and packet rules"),
        }

    ICON_NAMES = {
        0: "view-sort-ascending",
        1: "network-workgroup",
        2: "address-book-new",
        3: "computer",
        4: "system-run",
        5: "network-server",
        6: "network-wired",
        7: "system-users",
        8: "network-wired",
        9: "security-high",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons = {}
        self._current = -1
        self._nodes_container = None
        self._build_ui()

    def _build_ui(self):
        self.setAccessibleName(QC.translate("sidebar", "Navigation sidebar"))
        self.setAccessibleDescription(
            QC.translate("sidebar", "Main navigation between views: Events, Rules, Hosts, etc.")
        )
        self.setStyleSheet(
            "SidebarWidget {"
            "  border-right: 1px solid palette(mid);"
            "}"
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._make_brand())
        layout.addWidget(self._make_node_selector())

        nav_scroll = QtWidgets.QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        nav_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setAccessibleName(QC.translate("sidebar", "View navigation"))
        nav_scroll.setStyleSheet("QScrollArea { background: transparent; }")

        nav_widget = QtWidgets.QWidget()
        nav_widget.setStyleSheet("background: transparent;")
        nav_layout = QtWidgets.QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(8, 4, 8, 8)
        nav_layout.setSpacing(2)

        tooltips = self._tooltips()
        first_section = True
        for section_label, items in self._sections():
            nav_layout.addWidget(self._make_section_header(section_label, first_section))
            first_section = False
            for tab_index, label in items:
                btn = self._make_nav_button(tab_index, label, tooltips)
                nav_layout.addWidget(btn)
                self._buttons[tab_index] = btn

        nav_layout.addStretch(1)
        nav_scroll.setWidget(nav_widget)
        layout.addWidget(nav_scroll, 1)

        layout.addWidget(self._make_footer())

    def _make_brand(self):
        brand = QtWidgets.QWidget()
        brand.setObjectName("brandWidget")
        brand.setStyleSheet(
            "#brandWidget {"
            "  border-bottom: 1px solid palette(mid);"
            "  background: transparent;"
            "}"
        )
        bl = QtWidgets.QHBoxLayout(brand)
        bl.setContentsMargins(14, 8, 14, 8)
        bl.setSpacing(10)

        mark = QtWidgets.QLabel("OS")
        mark.setFixedSize(24, 24)
        mark.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        mark.setStyleSheet(
            "QLabel {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "  border-radius: 6px;"
            "  font-weight: 700;"
            "  font-size: 11px;"
            "}"
        )
        bl.addWidget(mark)

        title_col = QtWidgets.QVBoxLayout()
        title_col.setSpacing(0)
        name = QtWidgets.QLabel("OpenSnitch")
        name.setStyleSheet(
            "QLabel {"
            "  font-weight: 700;"
            "  font-size: 15px;"
            "  color: palette(text);"
            "  background: transparent;"
            "}"
        )
        title_col.addWidget(name)

        ver_label = QtWidgets.QLabel("v" + version)
        ver_label.setStyleSheet(
            "QLabel {"
            "  font-size: 10px;"
            "  color: palette(text);"
            "  background: transparent;"
            "}"
        )
        title_col.addWidget(ver_label)
        bl.addLayout(title_col)
        bl.addStretch()

        return brand

    def _make_section_header(self, text, is_first=False):
        header = QtWidgets.QLabel(text)
        top_pad = 4 if is_first else 16
        header.setStyleSheet(
            "QLabel {"
            f"  padding: {top_pad}px 8px 6px 8px;"
            "  font-size: 11px;"
            "  font-weight: 700;"
            "  letter-spacing: 1.2px;"
            "  color: palette(text);"
            "  background: transparent;"
            "}"
        )
        return header

    def _make_nav_button(self, tab_index, label, tooltips=None):
        btn = QtWidgets.QPushButton(label)
        btn.setFlat(True)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        btn.setProperty("tabIndex", tab_index)
        btn.setProperty("selected", False)
        btn.setIconSize(QtCore.QSize(16, 16))
        btn.setStyleSheet(self._nav_button_style())
        tip = (tooltips or {}).get(tab_index, "")
        btn.setToolTip(tip)
        btn.setAccessibleName(label)
        btn.setAccessibleDescription(tip)

        icon_name = self.ICON_NAMES.get(tab_index)
        if icon_name:
            icon = QtGui.QIcon.fromTheme(icon_name)
            if icon.isNull() and tab_index == 8:
                icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DriveNetIcon)
            if not icon.isNull():
                btn.setIcon(icon)

        btn.clicked.connect(lambda checked, idx=tab_index: self._on_click(idx))
        return btn

    def _nav_button_style(self):
        return (
            "QPushButton {"
            "  text-align: left;"
            "  padding: 7px 10px;"
            "  border: none;"
            "  border-left: 3px solid transparent;"
            "  border-radius: 0px;"
            "  font-size: 13px;"
            "  color: palette(text);"
            "}"
            "QPushButton:focus {"
            "  outline: 2px solid palette(highlight);"
            "  outline-offset: -2px;"
            "}"
            "QPushButton:hover {"
            "  background-color: palette(midlight);"
            "  border-left: 3px solid palette(midlight);"
            "}"
            "QPushButton[selected=\"true\"] {"
            "  background-color: palette(midlight);"
            "  border-left: 3px solid palette(highlight);"
            "  color: palette(text);"
            "  font-weight: 600;"
            "}"
        )

    NODE_ROW_HEIGHT = 36
    ACTION_HEIGHT = 36
    SHIELD_HEIGHT = 56

    def _make_node_selector(self):
        """one control for "which node am I looking at": a full-width menu
        button under the brand. Picking a node filters the events by it and
        makes it the node of the Firewall page; the last entry opens the
        Nodes view."""
        holder = QtWidgets.QWidget()
        holder.setObjectName("nodeSelectorHolder")
        holder.setStyleSheet(
            "#nodeSelectorHolder {"
            "  border-bottom: 1px solid palette(mid);"
            "  background: transparent;"
            "}"
        )
        hl = QtWidgets.QVBoxLayout(holder)
        hl.setContentsMargins(8, 8, 8, 8)
        hl.setSpacing(6)

        self._node_btn = QtWidgets.QToolButton()
        self._node_btn.setObjectName("nodeSelector")
        self._node_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self._node_btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._node_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._node_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        self._node_btn.setMinimumHeight(self.NODE_ROW_HEIGHT + 4)
        self._node_btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self._node_btn.setAccessibleName(QC.translate("sidebar", "Node"))
        self._node_btn.setToolTip(QC.translate(
            "sidebar",
            "The nodes you are looking at. Check one or several: the events are "
            "filtered by them and the Firewall page follows. All nodes shows everything."
        ))
        self._node_btn.setStyleSheet(
            "QToolButton {"
            "  text-align: left;"
            "  padding: 4px 10px;"
            "  border: 1px solid palette(mid);"
            "  border-radius: 6px;"
            "  font-size: 13px;"
            "  color: palette(text);"
            "  background: palette(base);"
            "}"
            "QToolButton:hover { border-color: palette(highlight); }"
            "QToolButton:focus { outline: 2px solid palette(highlight); outline-offset: 1px; }"
            "QToolButton[selected=\"true\"] { border: 2px solid palette(highlight); }"
            "QToolButton::menu-indicator {"
            "  subcontrol-origin: padding; subcontrol-position: center right; right: 8px;"
            "}"
        )
        self._node_menu = NodeMenu(self._node_btn)
        self._node_menu.setToolTipsVisible(True)
        self._node_btn.setMenu(self._node_menu)
        hl.addWidget(self._node_btn)

        self._node_list = []
        self._selected_nodes = []
        self._buttons[1] = self._node_btn
        self._rebuild_node_menu()

        # Two targets: a wide status card (what is happening; opens Nodes)
        # and a square play/pause button that changes it.
        shield_row = QtWidgets.QHBoxLayout()
        shield_row.setSpacing(6)

        self._shield = QtWidgets.QFrame()
        self._shield.setObjectName("shieldButton")
        self._shield.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        self._shield.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self._shield.setMinimumHeight(self.SHIELD_HEIGHT)
        self._shield.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self._shield.setToolTip(QC.translate(
            "sidebar", "Whether connections are being filtered, and for how long the daemon has run."
        ))
        self._shield.setAccessibleName(QC.translate("sidebar", "Filtering status"))
        self._shield_filtering = None

        sl = QtWidgets.QGridLayout(self._shield)
        sl.setContentsMargins(10, 6, 10, 6)
        sl.setHorizontalSpacing(10)
        sl.setVerticalSpacing(2)

        self._shield_icon = QtWidgets.QLabel()
        self._shield_icon.setFixedSize(28, 28)
        self._shield_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._shield_icon.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._shield_icon.setText("\u26e8")
        sl.addWidget(self._shield_icon, 0, 0)

        self._shield_label = QtWidgets.QLabel()
        self._shield_label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._shield_label.setStyleSheet(
            "QLabel { font-weight: 600; font-size: 12px;"
            "  color: palette(text); background: transparent; }"
        )
        sl.addWidget(self._shield_label, 0, 1, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

        # the uptime spans icon and state on its own line, so it never breaks
        self._shield_sub = StatusDescription()
        self._shield_sub.setWordWrap(False)
        self._shield_sub.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter)
        self._shield_sub.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._shield_sub.setStyleSheet(
            "QLabel { font-size: 10px; color: palette(text);"
            "  background: transparent; }"
        )
        sl.addWidget(self._shield_sub, 1, 0, 1, 2)
        sl.setColumnStretch(1, 1)
        shield_row.addWidget(self._shield, 1)

        self._toggle_btn = QtWidgets.QPushButton()
        self._toggle_btn.setObjectName("filterToggle")
        self._toggle_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        self._toggle_btn.setFixedWidth(self.SHIELD_HEIGHT)
        self._toggle_btn.setMinimumHeight(self.SHIELD_HEIGHT)
        self._toggle_btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
        self._toggle_btn.setIconSize(QtCore.QSize(22, 22))
        self._toggle_btn.setAccessibleName(QC.translate("sidebar", "Pause or resume filtering"))
        self._toggle_btn.clicked.connect(self.interceptToggled.emit)
        shield_row.addWidget(self._toggle_btn)

        hl.addLayout(shield_row)
        self.updateShield(True)
        return holder

    @staticmethod
    def _dot_icon(color):
        pix = QtGui.QPixmap(12, 12)
        pix.fill(QtCore.Qt.GlobalColor.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(color)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 8, 8)
        painter.end()
        return QtGui.QIcon(pix)

    def _node_text(self, addr, hostname):
        short_addr = addr.split("/")[-1] if "/" in addr else addr
        return "{0}  {1}".format(hostname, short_addr) if hostname else addr

    def _all_selected(self):
        """an empty selection means every node; so does every node checked"""
        return not self._selected_nodes

    def _normalize(self, addrs):
        known = [a for a, _, _ in self._node_list]
        picked = [a for a in known if a in addrs]
        if len(picked) == len(known):
            return []
        return picked

    def _rebuild_node_menu(self):
        self._node_menu.clear()
        self._node_actions = {}
        self._all_action = self._node_menu.addAction(QC.translate("sidebar", "All nodes"))
        self._all_action.setCheckable(True)
        self._all_action.setToolTip(QC.translate("sidebar", "Show every node. Uncheck nodes below to narrow the view."))
        self._all_action.triggered.connect(lambda checked=False: self._pick_all_nodes())
        for addr, hostname, online in self._node_list:
            # no icon on the rows: the style draws the check box only then
            text = self._node_text(addr, hostname)
            if not online:
                text += "  " + QC.translate("sidebar", "(offline)")
            act = self._node_menu.addAction(text)
            act.setCheckable(True)
            act.setToolTip(addr)
            act.triggered.connect(lambda checked=False, a=addr: self._toggle_node(a))
            self._node_actions[addr] = act
        if not self._node_list:
            none = self._node_menu.addAction(QC.translate("sidebar", "No nodes connected"))
            none.setEnabled(False)
        self._node_menu.addSeparator()
        manage = self._node_menu.addAction(QC.translate("sidebar", "Show the Nodes page"))
        manage.setToolTip(QC.translate(
            "sidebar", "Every daemon that has connected to this interface, with its version and settings."))
        manage.triggered.connect(lambda checked=False: self._on_click(1))
        self._sync_node_checks()

    def _sync_node_checks(self):
        """check states follow the selection in place, so the open menu
        stays where it is while nodes are toggled"""
        self._all_action.setChecked(self._all_selected())
        for addr, act in self._node_actions.items():
            act.setChecked(self._all_selected() or addr in self._selected_nodes)
        self._render_node_button()

    def _render_node_button(self):
        pal = self.palette()
        count = len(self._node_list)
        picked = [n for n in self._node_list if n[0] in self._selected_nodes]
        if self._all_selected() or not picked:
            if count == 0:
                text = QC.translate("sidebar", "No nodes connected")
            elif count == 1:
                text = self._node_text(self._node_list[0][0], self._node_list[0][1])
            else:
                text = QC.translate("sidebar", "All nodes ({0})").format(count)
            online = any(o for _, _, o in self._node_list)
        elif len(picked) == 1:
            addr, hostname, online = picked[0]
            text = self._node_text(addr, hostname)
        else:
            text = QC.translate("sidebar", "{0} of {1} nodes").format(len(picked), count)
            online = any(o for _, _, o in picked)
        self._node_btn.setIcon(self._dot_icon(pal.color(
            QtGui.QPalette.ColorRole.Highlight if online else QtGui.QPalette.ColorRole.Dark)))
        self._node_btn.setText(text)

    def _set_selection(self, addrs, emit):
        addrs = self._normalize(addrs)
        changed = addrs != self._selected_nodes
        self._selected_nodes = addrs
        self._sync_node_checks()
        if changed and emit:
            self.nodeSelected.emit(list(addrs))

    def _pick_all_nodes(self):
        self._set_selection([], emit=True)

    def _toggle_node(self, addr):
        current = [a for a, _, _ in self._node_list] if self._all_selected() else list(self._selected_nodes)
        if addr in current:
            current.remove(addr)
        else:
            current.append(addr)
        self._set_selection(current, emit=True)

    def selectedNodes(self):
        """addresses of the checked nodes; empty when every node is shown"""
        return list(self._selected_nodes)

    def setSelectedNodes(self, addrs):
        """follow an external change (a chip removed in the filter bar)
        without emitting"""
        self._set_selection(list(addrs or []), emit=False)

    def _make_footer(self):
        footer = QtWidgets.QWidget()
        footer.setObjectName("sidebarFooter")
        footer.setStyleSheet(
            "#sidebarFooter {"
            "  border-top: 1px solid palette(mid);"
            "  background: transparent;"
            "}"
        )
        fl = QtWidgets.QVBoxLayout(footer)
        fl.setContentsMargins(8, 8, 8, 8)
        fl.setSpacing(6)



        settings_btn = QtWidgets.QPushButton(QC.translate("sidebar", "Settings"))
        settings_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        settings_btn.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        settings_btn.setMinimumHeight(self.ACTION_HEIGHT)
        settings_btn.setToolTip(
            QC.translate("sidebar", "Opens Preferences: appearance, authorization alerts, notifications, events, nodes, server, storage.")
        )
        settings_btn.setAccessibleName(QC.translate("sidebar", "Settings"))
        settings_btn.setStyleSheet(self._secondary_button_style())
        settings_icon = QtGui.QIcon.fromTheme("preferences-system")
        if not settings_icon.isNull():
            settings_btn.setIcon(settings_icon)
        settings_btn.setIconSize(QtCore.QSize(16, 16))
        settings_btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        settings_btn.clicked.connect(self.settingsRequested.emit)
        fl.addWidget(settings_btn)

        return footer

    def _small_button_style(self):
        return (
            "QPushButton {"
            "  text-align: center;"
            "  padding: 4px 10px;"
            "  border: 1px solid palette(mid);"
            "  border-radius: 4px;"
            "  font-size: 12px;"
            "  color: palette(text);"
            "}"
            "QPushButton:focus {"
            "  outline: 2px solid palette(highlight);"
            "  outline-offset: 1px;"
            "}"
            "QPushButton:hover {"
            "  background-color: palette(midlight);"
            "}"
        )

    def _secondary_button_style(self):
        return (
            "QPushButton {"
            "  text-align: center;"
            "  padding: 4px 8px;"
            "  border: none;"
            "  border-radius: 4px;"
            "  font-size: 12px;"
            "  color: palette(text);"
            "}"
            "QPushButton:focus {"
            "  outline: 2px solid palette(highlight);"
            "  outline-offset: 1px;"
            "}"
            "QPushButton:hover {"
            "  background-color: palette(midlight);"
            "}"
        )

    def _on_click(self, tab_index):
        self.navigationChanged.emit(tab_index)

    def setCurrentItem(self, tab_index):
        if self._current == tab_index:
            return
        if self._current in self._buttons:
            self._set_selected(self._buttons[self._current], False)
        self._current = tab_index
        if tab_index in self._buttons:
            self._set_selected(self._buttons[tab_index], True)

    def _set_selected(self, btn, selected):
        btn.setProperty("selected", selected)
        btn.style().unpolish(btn)
        btn.style().polish(btn)

    def currentItem(self):
        return self._current

    def setItemIcon(self, tab_index, icon):
        if tab_index in self._buttons:
            self._buttons[tab_index].setIcon(icon)

    def setItemVisible(self, tab_index, visible):
        if tab_index in self._buttons:
            self._buttons[tab_index].setVisible(visible)

    def isItemVisible(self, tab_index):
        if tab_index in self._buttons:
            return self._buttons[tab_index].isVisibleTo(self)
        return False

    def updateShield(self, filtering, uptime_text=""):
        if filtering == self._shield_filtering and uptime_text == getattr(self, "_shield_uptime", None):
            return
        self._shield_filtering = filtering
        self._shield_uptime = uptime_text
        self._shield_sub.setVisible(not filtering or bool(uptime_text))
        if filtering:
            self._shield_label.setText(QC.translate("sidebar", "Filtering"))
            self._shield_sub.setText(uptime_text)
            self._shield.setAccessibleDescription(QC.translate("sidebar", "Filtering is active."))
            self._shield_icon.setStyleSheet(
                "QLabel {"
                "  background-color: palette(highlight);"
                "  color: palette(highlighted-text);"
                "  border-radius: 6px;"
                "  font-size: 16px;"
                "}"
            )
            self._shield.setStyleSheet(
                "#shieldButton {"
                "  text-align: left;"
                "  background-color: transparent;"
                "  border: none;"
                "  border-radius: 6px;"
                "}"
            )
            icon = QtGui.QIcon.fromTheme("media-playback-pause")
            self._toggle_btn.setIcon(icon)
            self._toggle_btn.setText("" if not icon.isNull() else "\u23f8")
            self._toggle_btn.setToolTip(QC.translate(
                "sidebar",
                "Pause filtering on every node. While paused, connections are not "
                "intercepted: rules do not apply and nothing is asked."
            ))
            self._toggle_btn.setStyleSheet(
                "#filterToggle {"
                "  border: 1px solid palette(mid);"
                "  border-radius: 6px;"
                "  background-color: palette(midlight);"
                "  font-size: 18px;"
                "}"
                "#filterToggle:hover { border-color: palette(highlight); }"
                "#filterToggle:focus { outline: 2px solid palette(highlight); outline-offset: 1px; }"
            )
        else:
            self._shield_label.setText(QC.translate("sidebar", "Paused"))
            self._shield_sub.setText(QC.translate("sidebar", "nothing is filtered"))
            self._shield.setAccessibleDescription(QC.translate("sidebar", "Filtering is paused."))
            self._shield_icon.setStyleSheet(
                "QLabel {"
                "  background-color: #d9822b;"
                "  color: white;"
                "  border-radius: 6px;"
                "  font-size: 16px;"
                "}"
            )
            self._shield.setStyleSheet(
                "#shieldButton {"
                "  text-align: left;"
                "  background-color: transparent;"
                "  border: none;"
                "  border-radius: 6px;"
                "}"
            )
            icon = QtGui.QIcon.fromTheme("media-playback-start")
            self._toggle_btn.setIcon(icon)
            self._toggle_btn.setText("" if not icon.isNull() else "\u25b6")
            self._toggle_btn.setToolTip(QC.translate("sidebar", "Resume filtering on every node."))
            self._toggle_btn.setStyleSheet(
                "#filterToggle {"
                "  border: 1px solid #d9822b;"
                "  border-radius: 6px;"
                "  background-color: #d9822b;"
                "  color: white;"
                "  font-size: 18px;"
                "}"
                "#filterToggle:hover { background-color: #c2721f; }"
                "#filterToggle:focus { outline: 2px solid palette(highlight); outline-offset: 1px; }"
            )

    def updateNodes(self, node_list):
        node_list = [tuple(n) for n in node_list] if node_list else []
        if node_list == self._node_list:
            return
        self._node_list = node_list
        self._selected_nodes = self._normalize(self._selected_nodes)
        self._rebuild_node_menu()
