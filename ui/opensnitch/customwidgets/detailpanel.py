from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC


class DetailFieldWidget(QtWidgets.QWidget):
    def __init__(self, label, value="", parent=None):
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)

        self._label = QtWidgets.QLabel(label)
        self._label.setFixedWidth(90)
        self._label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
        )
        self._label.setStyleSheet(
            "QLabel {"
            "  font-size: 11px;"
            "  color: palette(text);"
            "  font-weight: 600;"
            "}"
        )
        self._label.setBuddy(None)
        layout.addWidget(self._label)

        self._value = QtWidgets.QLabel(value)
        self._value.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse |
            QtCore.Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._value.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        self._value.setAccessibleName(label)
        self._value.setStyleSheet(
            "QLabel {"
            "  font-size: 12px;"
            "  color: palette(text);"
            "  font-family: monospace;"
            "}"
            "QLabel:focus {"
            "  background: palette(midlight);"
            "}"
        )
        self._value.setWordWrap(True)
        layout.addWidget(self._value, 1)

    def setValue(self, text):
        val = str(text) if text else ""
        self._value.setText(val)
        self._value.setAccessibleDescription(val)

    def value(self):
        return self._value.text()


class ConnectionDetailPanel(QtWidgets.QWidget):
    closed = QtCore.pyqtSignal()
    createRuleRequested = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = {}
        self._last_action = None
        self._build_ui()
        self.setVisible(False)

    def _make_section_header(self, text):
        label = QtWidgets.QLabel(text)
        label.setStyleSheet(
            "QLabel {"
            "  font-size: 10px;"
            "  font-weight: 700;"
            "  text-transform: uppercase;"
            "  letter-spacing: 1px;"
            "  color: palette(text);"
            "  padding: 0px;"
            "  margin: 0px;"
            "}"
        )
        return label

    def _make_separator(self):
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        sep.setStyleSheet(
            "QFrame { color: palette(mid); margin: 0px; }"
        )
        sep.setFixedHeight(1)
        return sep

    def _build_ui(self):
        self.setObjectName("detailPanel")
        self.setMinimumWidth(300)
        self.setAccessibleName(QC.translate("detail", "Connection detail panel"))
        self.setAccessibleDescription(
            QC.translate("detail", "Shows detailed information about the selected connection")
        )
        self.setStyleSheet(
            "#detailPanel {"
            "  border-left: 1px solid palette(mid);"
            "  background: palette(base);"
            "}"
        )

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QtWidgets.QWidget()
        header.setObjectName("detailHeader")
        header.setStyleSheet(
            "#detailHeader {"
            "  border-bottom: 1px solid palette(mid);"
            "  background: palette(window);"
            "}"
        )
        hl = QtWidgets.QHBoxLayout(header)
        hl.setContentsMargins(12, 10, 8, 10)
        hl.setSpacing(8)

        self._title = QtWidgets.QLabel(QC.translate("detail", "Connection Detail"))
        self._title.setStyleSheet(
            "QLabel { font-weight: 700; font-size: 14px; }"
        )
        self._title.setAccessibleName(QC.translate("detail", "Panel heading"))
        hl.addWidget(self._title, 1)

        close_btn = QtWidgets.QToolButton()
        close_btn.setText("x")
        close_btn.setFixedSize(26, 26)
        close_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        close_btn.setAccessibleName(QC.translate("detail", "Close detail panel"))
        close_btn.setToolTip(QC.translate("detail", "Close detail panel (Escape)"))
        close_btn.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape))
        close_btn.setStyleSheet(
            "QToolButton {"
            "  border: none;"
            "  font-size: 18px;"
            "  font-weight: 700;"
            "  color: palette(text);"
            "  border-radius: 13px;"
            "}"
            "QToolButton:hover {"
            "  background: palette(midlight);"
            "  color: palette(text);"
            "}"
            "QToolButton:focus {"
            "  outline: 2px solid palette(highlight);"
            "  border-radius: 13px;"
            "}"
        )
        close_btn.clicked.connect(self._on_close)
        hl.addWidget(close_btn)
        main_layout.addWidget(header)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setAccessibleName(QC.translate("detail", "Connection fields"))

        content = QtWidgets.QWidget()
        self._content_layout = QtWidgets.QVBoxLayout(content)
        self._content_layout.setContentsMargins(12, 12, 12, 12)
        self._content_layout.setSpacing(2)

        self._fields = {}

        # Section: Connection
        self._content_layout.addWidget(
            self._make_section_header(QC.translate("detail", "CONNECTION"))
        )
        self._content_layout.addSpacing(4)
        connection_fields = [
            ("time", QC.translate("detail", "Time")),
            ("action", QC.translate("detail", "Action")),
            ("protocol", QC.translate("detail", "Protocol")),
        ]
        for key, label in connection_fields:
            field = DetailFieldWidget(label, parent=content)
            self._fields[key] = field
            self._content_layout.addWidget(field)

        # Separator + Section: Process
        self._content_layout.addSpacing(8)
        self._content_layout.addWidget(self._make_separator())
        self._content_layout.addSpacing(8)
        self._content_layout.addWidget(
            self._make_section_header(QC.translate("detail", "PROCESS"))
        )
        self._content_layout.addSpacing(4)
        process_fields = [
            ("process", QC.translate("detail", "Process")),
            ("cmdline", QC.translate("detail", "Command")),
            ("pid", QC.translate("detail", "PID")),
            ("uid", QC.translate("detail", "UID")),
        ]
        for key, label in process_fields:
            field = DetailFieldWidget(label, parent=content)
            self._fields[key] = field
            self._content_layout.addWidget(field)

        # Separator + Section: Network
        self._content_layout.addSpacing(8)
        self._content_layout.addWidget(self._make_separator())
        self._content_layout.addSpacing(8)
        self._content_layout.addWidget(
            self._make_section_header(QC.translate("detail", "NETWORK"))
        )
        self._content_layout.addSpacing(4)
        network_fields = [
            ("src_ip", QC.translate("detail", "Source IP")),
            ("src_port", QC.translate("detail", "Source Port")),
            ("dst_ip", QC.translate("detail", "Dest IP")),
            ("dst_host", QC.translate("detail", "Dest Host")),
            ("dst_port", QC.translate("detail", "Dest Port")),
        ]
        for key, label in network_fields:
            field = DetailFieldWidget(label, parent=content)
            self._fields[key] = field
            self._content_layout.addWidget(field)

        # Separator + Section: Matching Rule
        self._content_layout.addSpacing(8)
        self._content_layout.addWidget(self._make_separator())
        self._content_layout.addSpacing(8)
        self._content_layout.addWidget(
            self._make_section_header(QC.translate("detail", "MATCHING RULE"))
        )
        self._content_layout.addSpacing(4)
        rule_fields = [
            ("node", QC.translate("detail", "Node")),
            ("rule", QC.translate("detail", "Rule")),
        ]
        for key, label in rule_fields:
            field = DetailFieldWidget(label, parent=content)
            self._fields[key] = field
            self._content_layout.addWidget(field)

        self._content_layout.addStretch(1)

        # the "Create rule..." action lives in the bulk action bar, next to
        # Allow/Deny Selected

        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

    def showConnection(self, data):
        self._data = data
        for key, field in self._fields.items():
            field.setValue(data.get(key, ""))

        action = data.get("action", "")
        if action == self._last_action:
            self.setVisible(True)
            return
        self._last_action = action
        if action == "deny":
            self._title.setText(QC.translate("detail", "Blocked Connection"))
            self._title.setStyleSheet(
                "QLabel { font-weight: 700; font-size: 14px; color: palette(text); }"
            )
            self.setStyleSheet(
                "#detailPanel {"
                "  border-left: 1px solid palette(mid);"
                "  background: qlineargradient("
                "    x1:0, y1:0, x2:0, y2:1,"
                "    stop:0 rgba(192, 57, 43, 18),"
                "    stop:1 palette(base)"
                "  );"
                "}"
            )
        elif action == "allow":
            self._title.setText(QC.translate("detail", "Allowed Connection"))
            self._title.setStyleSheet(
                "QLabel { font-weight: 700; font-size: 14px; color: palette(text); }"
            )
            self.setStyleSheet(
                "#detailPanel {"
                "  border-left: 1px solid palette(mid);"
                "  background: qlineargradient("
                "    x1:0, y1:0, x2:0, y2:1,"
                "    stop:0 rgba(39, 174, 96, 18),"
                "    stop:1 palette(base)"
                "  );"
                "}"
            )
        else:
            self._title.setText(QC.translate("detail", "Connection Detail"))
            self._title.setStyleSheet(
                "QLabel { font-weight: 700; font-size: 14px; }"
            )
            self.setStyleSheet(
                "#detailPanel {"
                "  border-left: 1px solid palette(mid);"
                "  background: palette(base);"
                "}"
            )

        self.setVisible(True)

    def hideDetail(self):
        self.setVisible(False)
        self._data = {}
        self._last_action = None

    def currentData(self):
        return self._data

    def _on_close(self):
        self.hideDetail()
        self.closed.emit()

    def _on_create_rule(self):
        if self._data:
            self.createRuleRequested.emit(self._data)
