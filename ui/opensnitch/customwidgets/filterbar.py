import re
import shlex
from opensnitch.customwidgets.filterexpression import compile_filter, FilterError

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC


# a value the search parser reads without quotes; anything else is quoted
_BARE_VALUE = re.compile(r"^[0-9a-zA-Z\.\-_\/:]+$")


def quote_value(value):
    value = str(value)
    if _BARE_VALUE.match(value):
        return value
    return '"' + value.replace('"', '""') + '"'


class FilterChip(QtWidgets.QFrame):
    removed = QtCore.pyqtSignal(object)

    # a chip's text is elided in the middle past this; the tooltip has it all
    MAX_TEXT_WIDTH = 320

    def __init__(self, key, value, parent=None):
        super().__init__(parent)
        self.key = key
        self.value = value
        self.setObjectName("filterChip")
        self.setToolTip(f"{key}:{value}")
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(
            QC.translate("filterbar", "Filter: {0} equals {1}").format(key, value)
        )
        self.setAccessibleDescription(
            QC.translate("filterbar", "Press Delete or Backspace to remove this filter")
        )
        self.setStyleSheet(
            "#filterChip {"
            "  background-color: rgba(0, 120, 215, 200);"
            "  border-radius: 4px;"
            "  padding: 2px 6px;"
            "}"
            "#filterChip:hover {"
            "  background-color: rgba(0, 100, 190, 230);"
            "}"
            "#filterChip:focus {"
            "  outline: 2px solid palette(text);"
            "  outline-offset: 1px;"
            "}"
        )
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 6, 3)
        layout.setSpacing(4)

        label = QtWidgets.QLabel()
        font = label.font()
        font.setPixelSize(12)
        font.setWeight(QtGui.QFont.Weight.DemiBold)
        label.setFont(font)
        label.setText(QtGui.QFontMetrics(font).elidedText(
            f"{key}:{value}", QtCore.Qt.TextElideMode.ElideMiddle, self.MAX_TEXT_WIDTH))
        label.setStyleSheet(
            "QLabel {"
            "  color: palette(highlighted-text);"
            "  background: transparent;"
            "}"
        )
        layout.addWidget(label)

        close_btn = QtWidgets.QToolButton()
        close_btn.setText("x")
        close_btn.setFixedSize(16, 16)
        close_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close_btn.setAccessibleName(
            QC.translate("filterbar", "Remove filter {0}:{1}").format(key, value)
        )
        close_btn.setToolTip(
            QC.translate("filterbar", "Remove this filter")
        )
        close_btn.setStyleSheet(
            "QToolButton {"
            "  border: none;"
            "  color: palette(highlighted-text);"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  background: transparent;"
            "  border-radius: 8px;"
            "}"
            "QToolButton:hover {"
            "  background: rgba(0,0,0,60);"
            "}"
            "QToolButton:focus {"
            "  outline: 1px solid palette(highlighted-text);"
            "}"
        )
        close_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(close_btn)

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Delete, QtCore.Qt.Key.Key_Backspace):
            self.removed.emit(self)
        else:
            super().keyPressEvent(event)


class FilterInput(QtWidgets.QLineEdit):
    """the filter box: completes the token under the cursor. Before the
    colon it offers the fields; after it, the values that column holds in
    the current table (asked from the value provider, narrowed by the
    letters typed so far). Focusing an empty box offers every field;
    arrows move in the list, Tab or Enter take the highlighted entry,
    Escape closes the list (a second Escape clears the box), Space just
    moves on. Enter with no list open applies the filter."""

    ROLE_KIND = QtCore.Qt.ItemDataRole.UserRole + 1
    KIND_FIELD = "field"
    KIND_VALUE = "value"

    backspaceOnEmpty = QtCore.pyqtSignal()

    def __init__(self, fields, parent=None):
        super().__init__(parent)
        self._fields = list(fields)
        self._value_provider = None
        self._model = QtGui.QStandardItemModel(self)
        for key, label, example in self._fields:
            item = QtGui.QStandardItem("{0}:   {1}".format(key, QC.translate("filterbar", label)))
            item.setData(key, QtCore.Qt.ItemDataRole.UserRole)
            item.setData(self.KIND_FIELD, self.ROLE_KIND)
            item.setToolTip("{0}:{1}".format(key, example))
            self._model.appendRow(item)
        self._values_model = QtGui.QStandardItemModel(self)
        self._completer = QtWidgets.QCompleter(self._model, self)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self._completer.setFilterMode(QtCore.Qt.MatchFlag.MatchStartsWith)
        self._completer.setWidget(self)
        self._completer.activated[QtCore.QModelIndex].connect(self._take)
        self._completer.popup().installEventFilter(self)
        self.textEdited.connect(self._offer)

    def _token_span(self):
        text = self.text()
        end = self.cursorPosition()
        start = text.rfind(" ", 0, end) + 1
        return start, end

    def setValueProvider(self, provider):
        """provider(key, prefix) -> the values to offer after `key:`"""
        self._value_provider = provider

    def _offer(self, _text=""):
        start, end = self._token_span()
        token = self.text()[start:end]
        if ":" in token:
            key, _, prefix = token.partition(":")
            self._offer_values(key.lower(), prefix.lstrip('"'))
            return
        if self._completer.model() is not self._model:
            self._completer.setModel(self._model)
        self._completer.setCompletionPrefix(token)
        self._show_popup()

    def _offer_values(self, key, prefix):
        values = self._value_provider(key, prefix) if self._value_provider else []
        self._values_model.clear()
        for value in values:
            item = QtGui.QStandardItem(str(value))
            item.setData(str(value), QtCore.Qt.ItemDataRole.UserRole)
            item.setData(self.KIND_VALUE, self.ROLE_KIND)
            self._values_model.appendRow(item)
        if self._completer.model() is not self._values_model:
            self._completer.setModel(self._values_model)
        self._completer.setCompletionPrefix(prefix)
        self._show_popup()

    def _show_popup(self):
        if self._completer.completionCount() == 0:
            self._completer.popup().hide()
            return
        rect = self.cursorRect()
        rect.setWidth(max(260, self._completer.popup().sizeHintForColumn(0) + 24))
        self._completer.complete(rect)
        self._completer.popup().setCurrentIndex(self._completer.completionModel().index(0, 0))

    def _take(self, index):
        start, end = self._token_span()
        text = self.text()
        if index.data(self.ROLE_KIND) == self.KIND_VALUE:
            key = text[start:end].partition(":")[0]
            replacement = key + ":" + quote_value(index.data(QtCore.Qt.ItemDataRole.UserRole))
        else:
            key = index.data(QtCore.Qt.ItemDataRole.UserRole)
            if key is None:
                key = str(index.data()).split(":")[0]
            replacement = key + ":"
        self.setText(text[:start] + replacement + text[end:])
        self.setCursorPosition(start + len(replacement))
        self._completer.popup().hide()
        if replacement.endswith(":"):
            # the field is in: offer its values right away
            QtCore.QTimer.singleShot(0, self._offer)

    def offersFields(self):
        return self._completer.popup().isVisible() and self._completer.model() is self._model

    def offersValues(self):
        return self._completer.popup().isVisible() and self._completer.model() is self._values_model

    def completionKeys(self):
        m = self._completer.completionModel()
        return [str(m.index(r, 0).data()).split(":")[0] for r in range(m.rowCount())]

    def completionValues(self):
        m = self._completer.completionModel()
        return [str(m.index(r, 0).data()) for r in range(m.rowCount())]

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if event.reason() != QtCore.Qt.FocusReason.PopupFocusReason:
            QtCore.QTimer.singleShot(0, self._offer)

    def eventFilter(self, obj, event):
        if obj is self._completer.popup() and event.type() == QtCore.QEvent.Type.KeyPress:
            key = event.key()
            if key in (QtCore.Qt.Key.Key_Tab, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Enter):
                idx = self._completer.popup().currentIndex()
                if not idx.isValid():
                    idx = self._completer.completionModel().index(0, 0)
                if idx.isValid():
                    self._take(idx)
                return True
            if key == QtCore.Qt.Key.Key_Space:
                self._completer.popup().hide()
                self.insert(" ")
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            if self._completer.popup().isVisible():
                self._completer.popup().hide()
            else:
                self.clear()
            return
        if event.key() == QtCore.Qt.Key.Key_Down and not self._completer.popup().isVisible():
            self._offer()
            return
        if event.key() == QtCore.Qt.Key.Key_Backspace and self.text() == "":
            self.backspaceOnEmpty.emit()
            return
        super().keyPressEvent(event)


class FilterBarWidget(QtWidgets.QWidget):
    filterChanged = QtCore.pyqtSignal(str)
    filterCleared = QtCore.pyqtSignal()
    splitChanged = QtCore.pyqtSignal(list, list)

    # chip key -> ConnFields value understood by Queries.advanced_search()
    FIELD_MAP = {
        "dst": "conn.dsthost",
        "host": "conn.dsthost",
        "dsthost": "conn.dsthost",
        "port": "conn.dstport",
        "dstport": "conn.dstport",
        "srcport": "conn.srcport",
        "ip": "conn.dstip",
        "dstip": "conn.dstip",
        "srcip": "conn.srcip",
        "proto": "conn.proto",
        "protocol": "conn.proto",
        "action": "conn.action",
        "process": "conn.process",
        "proc": "conn.process",
        "cmd": "conn.process_args",
        "cmdline": "conn.process_args",
        "pid": "conn.pid",
        "uid": "conn.uid",
        "rule": "conn.rule",
        "node": "conn.node",
        "state": "socket.state",
        "family": "socket.family",
        "comm": "socket.comm",
        "iface": "socket.iface",
    }

    COMPLETIONS = list(FIELD_MAP.keys())

    # chip keys whose value can list several entries, comma separated
    MULTI_KEYS = ("node",)

    # (chip key, what the person reads, example) for the "Add filter" menu
    FIELDS = [
        ("dst", "Destination host", "github.com"),
        ("ip", "Destination IP", "140.82.121.3"),
        ("port", "Destination port", "443"),
        ("srcport", "Source port", "1024"),
        ("state", "Socket state", "established"),
        ("family", "Address family", "ipv6"),
        ("comm", "Socket process name", "curl"),
        ("iface", "Socket interface", "eth0"),
        ("proto", "Protocol", "tcp"),
        ("process", "Process path", "/usr/bin/curl"),
        ("cmd", "Command line", "--silent"),
        ("pid", "Process id", "4242"),
        ("uid", "User id", "1000"),
        ("action", "Action", "deny"),
        ("rule", "Rule name", "allow-firefox"),
        ("node", "Node", "unix:///tmp/osui.sock"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chips = []
        self._split_actions = {}
        self._enrich_actions = {}
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("filterBarWidget")
        self.setAccessibleName(QC.translate("filterbar", "Connection filter bar"))
        self.setAccessibleDescription(
            QC.translate("filterbar", "Type field:value to filter connections. Example: dst:github.com action:deny")
        )
        self.setStyleSheet(
            "#filterBarWidget {"
            "  border-bottom: 2px solid palette(mid);"
            "  background: palette(base);"
            "}"
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(6)

        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(16, 16)
        icon_label.setAccessibleName(QC.translate("filterbar", "Filter"))
        icon = QtGui.QIcon.fromTheme("edit-find")
        if not icon.isNull():
            icon_label.setPixmap(icon.pixmap(16, 16))
        else:
            icon_label.setText("\U0001f50d")
            icon_label.setStyleSheet("font-size: 12px; background: transparent;")
        self._search_icon = icon_label
        layout.addWidget(icon_label)

        self._chips_layout = QtWidgets.QHBoxLayout()
        self._chips_layout.setContentsMargins(4, 0, 4, 0)
        self._chips_layout.setSpacing(6)
        layout.addLayout(self._chips_layout)

        self._input = FilterInput(self.FIELDS)
        self._input.setPlaceholderText(
            QC.translate("filterbar", "Filter this view: field:value or an expression. Enter applies.")
        )
        self._input.setToolTip(QC.translate(
            "filterbar",
            "Plain text matches the destination host. field:value matches one field; "
            "Use AND, OR, ! or NOT and parentheses; compare with =, !=, <>, <, >, <=, >=. Example: proto:tcp AND (port:80 OR port:443). "
            "Each applied filter becomes a chip you can remove."
        ))
        self._input.setAccessibleName(QC.translate("filterbar", "Filter input"))
        self._input.setAccessibleDescription(
            QC.translate("filterbar", "Type a filter like dst:github.com and press Enter to apply")
        )
        self._input.setFrame(False)
        self._input.setStyleSheet(
            "QLineEdit {"
            "  background: transparent;"
            "  font-size: 13px;"
            "  padding: 4px;"
            "}"
        )
        self._input.returnPressed.connect(self._on_enter)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.backspaceOnEmpty.connect(self._remove_last_chip)
        layout.addWidget(self._input, 1)

        self._clear_btn = QtWidgets.QToolButton()
        self._clear_btn.setText(QC.translate("filterbar", "Clear"))
        self._clear_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setToolTip(QC.translate("filterbar", "Clear all filters"))
        self._clear_btn.setAccessibleName(QC.translate("filterbar", "Clear all filters"))
        self._clear_btn.setMinimumHeight(30)
        self._clear_btn.setStyleSheet(
            "QToolButton {"
            "  border: 1px solid palette(mid);"
            "  border-radius: 4px;"
            "  background: palette(button);"
            "  font-size: 12px;"
            "  color: palette(button-text);"
            "  padding: 2px 8px;"
            "}"
            "QToolButton:hover {"
            "  background: palette(midlight);"
            "}"
            "QToolButton:focus {"
            "  outline: 2px solid palette(highlight);"
            "}"
        )
        self._clear_btn.clicked.connect(self.clearAll)
        self._clear_btn.setVisible(False)
        layout.addWidget(self._clear_btn)

        self._split_btn = QtWidgets.QToolButton()
        self._split_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        self._split_btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        split_icon = QtGui.QIcon.fromTheme("view-column")
        if not split_icon.isNull():
            self._split_btn.setIcon(split_icon)
        self._split_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self._split_btn.setAccessibleName(QC.translate("filterbar", "Group rows by"))
        self._split_count = None
        self._split_btn.setMinimumHeight(30)
        self._split_btn.setStyleSheet(
            "QToolButton {"
            "  border: 1px solid palette(mid);"
            "  border-radius: 4px;"
            "  background: palette(button);"
            "  font-size: 12px;"
            "  color: palette(button-text);"
            "  padding: 2px 8px;"
            "}"
            "QToolButton[active=\"true\"] {"
            "  border-color: palette(highlight);"
            "  font-weight: 600;"
            "}"
            "QToolButton:hover {"
            "  background: palette(midlight);"
            "}"
            "QToolButton:focus {"
            "  outline: 2px solid palette(highlight);"
            "}"
            "QToolButton::menu-indicator { image: none; width: 0; }"
        )
        self._split_menu = QtWidgets.QMenu(self._split_btn)
        self._split_btn.setMenu(self._split_menu)
        self._split_btn.setVisible(False)
        layout.addWidget(self._split_btn)
        self._update_split_label()

        self._actions_layout = QtWidgets.QHBoxLayout()
        self._actions_layout.setContentsMargins(0, 0, 0, 0)
        self._actions_layout.setSpacing(6)
        layout.addLayout(self._actions_layout)
        self._action_buttons = []

    def chips(self):
        return list(self._chips)

    def _drop_chip(self, chip):
        """take a chip out for good: off the list, out of the layout, hidden
        and unparented now (deleteLater alone leaves it painted where it
        was until the event loop gets to it, under whatever comes next)"""
        if chip in self._chips:
            self._chips.remove(chip)
        self._chips_layout.removeWidget(chip)
        chip.hide()
        chip.setParent(None)
        chip.deleteLater()

    def showFilterError(self, message):
        self._input.setAccessibleDescription(message)
        QtWidgets.QToolTip.showText(self._input.mapToGlobal(QtCore.QPoint(0, self._input.height())), message, self._input)

    def _on_enter(self):
        text = self._input.text().strip()
        if not text:
            return

        if re.search(r'[!<>=()]|\b(?:AND|OR|NOT)\b|&&|\|\|', text, re.I):
            try:
                compile_filter(text, {**self.FIELD_MAP, **{v: v for v in self.FIELD_MAP.values()}})
            except FilterError as error:
                self.showFilterError(str(error))
                return
            self._add_chip("expression", text)
            self._input.clear()
            self._emit_filter()
            return
        try:
            parts = shlex.split(text)
        except ValueError:
            parts = text.split()
        added = False
        for part in parts:
            if ":" in part:
                key, _, value = part.partition(":")
                if value:
                    self._add_chip(key.lower(), value)
                    added = True
            else:
                self._add_chip("dst", part)
                added = True

        if added:
            self._input.clear()
            self._emit_filter()

    def filterValue(self, key):
        for chip in self._chips:
            if chip.key == key:
                return chip.value
        return None

    def filterValues(self, key):
        """the entries of a chip that lists several, in order; [] without the chip"""
        value = self.filterValue(key)
        if value is None:
            return []
        if key in self.MULTI_KEYS:
            return [v for v in value.split(",") if v]
        return [value]

    def setValueProvider(self, provider):
        self._input.setValueProvider(provider)

    def chipsFilterText(self):
        """the search text of the chips alone (what the box holds is not applied yet)"""
        return self._build_filter_text() if self._chips else ""

    def setFilter(self, key, value, emit=True):
        """one chip per key: replaces the chip with that key or adds it"""
        for chip in list(self._chips):
            if chip.key == key:
                self._drop_chip(chip)
        self._add_chip(key, value)
        if emit:
            self._emit_filter()

    def removeFilter(self, key, emit=True):
        found = False
        for chip in list(self._chips):
            if chip.key == key:
                found = True
                self._drop_chip(chip)
        self._clear_btn.setVisible(bool(self._chips))
        if found and emit:
            if self._chips:
                self._emit_filter()
            else:
                self.filterCleared.emit()
        return found

    def _on_text_changed(self, text):
        if not self._chips and not text.strip():
            self.filterCleared.emit()

    def _add_chip(self, key, value):
        chip = FilterChip(key, value, self)
        chip.removed.connect(self._remove_chip)
        self._chips.append(chip)
        self._chips_layout.addWidget(chip)
        self._clear_btn.setVisible(True)

    def _remove_last_chip(self):
        if self._chips:
            self._remove_chip(self._chips[-1])

    def _remove_chip(self, chip):
        self._drop_chip(chip)
        self._clear_btn.setVisible(bool(self._chips))
        if self._chips:
            self._emit_filter()
        else:
            self.filterCleared.emit()
        self._input.setFocus()

    def _build_filter_text(self):
        parts = []
        for chip in self._chips:
            if chip.key == "expression":
                parts.append("(" + chip.value + ")")
                continue
            field = self.FIELD_MAP.get(chip.key, None)
            values = self.filterValues(chip.key)
            if field and len(values) > 1:
                parts.append("{0} IN ({1})".format(field, ",".join(quote_value(v) for v in values)))
            elif field:
                parts.append(f"{field}={quote_value(chip.value)}")
            else:
                parts.append(f"conn.dsthost~{quote_value(chip.value)}")
        return " AND ".join(parts)

    def _emit_filter(self):
        self.filterChanged.emit(self._build_filter_text())

    def clearAll(self):
        for chip in list(self._chips):
            self._drop_chip(chip)
        self._input.clear()
        self._clear_btn.setVisible(False)
        self.filterCleared.emit()
        self._input.setFocus()

    def setCompleter(self, completer):
        pass  # the box completes field names on its own

    def setFilterText(self, text):
        self._input.setText(text)

    def text(self):
        return self._input.text()

    def focusInput(self):
        self._input.setFocus()
        self._input.selectAll()

    def activeFilterText(self):
        if self._chips:
            return self._build_filter_text()
        return self._input.text()

    def addFilter(self, key, value):
        self._add_chip(key, value)
        self._emit_filter()

    def setFilters(self, pairs):
        """Replace the chips with key/value pairs and apply them once."""
        for chip in list(self._chips):
            self._drop_chip(chip)
        self._input.clear()
        for key, value in pairs:
            if value is None or str(value).strip() == "":
                continue
            self._add_chip(str(key).lower(), str(value))
        self._clear_btn.setVisible(bool(self._chips))
        if self._chips:
            self._emit_filter()
        else:
            self.filterCleared.emit()

    # --- split by: extra grouping columns for the summary views

    def setActions(self, actions):
        """buttons at the right end of the bar; `actions` is a list of
        (text, tooltip, callback)"""
        for btn in self._action_buttons:
            self._actions_layout.removeWidget(btn)
            btn.hide()
            btn.setParent(None)
            btn.deleteLater()
        self._action_buttons = []
        for text, tooltip, callback in actions:
            btn = QtWidgets.QPushButton(text)
            btn.setToolTip(tooltip)
            btn.setAccessibleName(text)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(30)
            btn.clicked.connect(lambda checked=False, cb=callback: cb())
            self._actions_layout.addWidget(btn)
            self._action_buttons.append(btn)

    def actionTexts(self):
        return [b.text() for b in self._action_buttons]

    def setSplitOptions(self, dimensions, checked, enrichers=(), enrich_checked=()):
        """dimensions: [(key, label)] the current view can be split by.
        enrichers: [(key, label)] lookup columns that can be shown.
        Rebuilds the menu; no signal is emitted."""
        self._split_menu.clear()
        self._split_actions = {}
        self._enrich_actions = {}
        title = self._split_menu.addAction(QC.translate("filterbar", "Drill down by..."))
        title.setEnabled(False)
        self._split_menu.addSeparator()
        self._split_labels = {}
        for key, label in dimensions:
            action = self._split_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(key in checked)
            action.setData(key)
            action.toggled.connect(self._on_split_toggled)
            self._split_actions[key] = action
            self._split_labels[key] = label
        if enrichers:
            self._split_menu.addSeparator()
            title = self._split_menu.addAction(QC.translate("filterbar", "Show"))
            title.setEnabled(False)
            for key, label in enrichers:
                action = self._split_menu.addAction(label)
                action.setCheckable(True)
                action.setChecked(key in enrich_checked)
                action.setData(key)
                action.toggled.connect(self._on_split_toggled)
                self._enrich_actions[key] = action
        self._update_split_label()

    def setSplitStatsProvider(self, fn):
        """fn() -> {key: (rows_if_toggled, distinct_values, sample_value)};
        asked when the menu opens, so each entry says what it would do"""
        self._split_stats_provider = fn
        try:
            self._split_menu.aboutToShow.disconnect(self._describe_split_choices)
        except TypeError:
            pass
        self._split_menu.aboutToShow.connect(self._describe_split_choices)

    @staticmethod
    def describe_split_choice(label, checked, info):
        """(text, enabled) for one dimension given (rows, distinct, sample)"""
        if info is None:
            return label, True
        rows, distinct, sample = info
        if checked:
            return QC.translate("filterbar", "{0}  ({1} rows without it)").format(label, rows), True
        if distinct is not None and distinct <= 1:
            return "{0}: {1}".format(label, sample if sample not in (None, "") else "-"), False
        return QC.translate("filterbar", "{0}  ({1} rows)").format(label, rows), True

    def splitLabels(self):
        return dict(getattr(self, "_split_labels", {}))

    def _describe_split_choices(self):
        provider = getattr(self, "_split_stats_provider", None)
        if provider is None:
            return
        try:
            stats = provider() or {}
        except Exception:
            stats = {}
        for key, action in self._split_actions.items():
            label = self._split_labels.get(key, action.text())
            text, enabled = self.describe_split_choice(label, action.isChecked(), stats.get(key))
            action.setText(text)
            action.setEnabled(enabled)

    def setSplitVisible(self, visible):
        self._split_btn.setVisible(visible)

    def splitKeys(self):
        return [k for k, a in self._split_actions.items() if a.isChecked()]

    def enrichKeys(self):
        return [k for k, a in self._enrich_actions.items() if a.isChecked()]

    def hasEnrichOptions(self):
        return len(self._enrich_actions) > 0

    def _on_split_toggled(self, _checked):
        self._update_split_label()
        self.splitChanged.emit(self.splitKeys(), self.enrichKeys())

    def setSplitCount(self, count):
        """how many groups the current grouping produced; shown on the button"""
        self._split_count = count
        self._update_split_label()

    def _update_split_label(self):
        labels = [a.text() for a in self._split_actions.values() if a.isChecked()]
        if labels:
            text = QC.translate("filterbar", "Group by: {0}").format(", ".join(labels))
            if self._split_count is not None:
                text += "  \u00b7  " + QC.translate("filterbar", "{0} groups").format(self._split_count)
            self._split_btn.setText(text)
            self._split_btn.setToolTip(
                QC.translate("filterbar", "Rows are grouped by {0} as well; hits are counted from the connections history").format(", ".join(labels))
            )
        else:
            self._split_btn.setText(QC.translate("filterbar", "Group by"))
            self._split_btn.setToolTip(
                QC.translate("filterbar", "Add a column to tell apart rows that share the same name")
            )
        self._split_btn.setProperty("active", "true" if labels else "false")
        self._split_btn.style().unpolish(self._split_btn)
        self._split_btn.style().polish(self._split_btn)

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.clearAll()
        else:
            super().keyPressEvent(event)
