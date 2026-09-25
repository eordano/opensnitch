from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC


class BulkActionBar(QtWidgets.QWidget):
    exportRequested = QtCore.pyqtSignal()
    selectAllRequested = QtCore.pyqtSignal()
    clearRequested = QtCore.pyqtSignal()
    createRuleRequested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._count = 0
        self._build_ui()
        self.setVisible(False)

    def _build_ui(self):
        self.setObjectName("bulkActionBar")
        self.setFixedHeight(48)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        self.setAccessibleName(QC.translate("bulk", "Bulk actions toolbar"))
        self.setAccessibleDescription(
            QC.translate("bulk", "Actions for multiple selected connections")
        )
        # a plain QWidget only paints a stylesheet background with this attribute
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#bulkActionBar {"
            "  background-color: palette(window);"
            "  border-top: 1px solid palette(mid);"
            "}"
        )

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        self._count_label = QtWidgets.QLabel(
            QC.translate("bulk", "0 selected")
        )
        self._count_label.setAccessibleName(
            QC.translate("bulk", "Selection count")
        )
        self._count_label.setStyleSheet(
            "QLabel {"
            "  color: palette(text);"
            "  font-weight: 700;"
            "  font-size: 14px;"
            "}"
        )
        layout.addWidget(self._count_label)

        select_all_btn = self._make_button(
            QC.translate("bulk", "Select all"),
            QC.translate("bulk", "Selects every row of the current result, not only the visible ones")
        )
        select_all_btn.clicked.connect(self.selectAllRequested.emit)
        layout.addWidget(select_all_btn)

        clear_btn = self._make_button(
            QC.translate("bulk", "Clear"),
            QC.translate("bulk", "Deselects everything and closes the details (Esc)")
        )
        clear_btn.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key.Key_Escape))
        clear_btn.clicked.connect(self.clearRequested.emit)
        layout.addWidget(clear_btn)

        layout.addStretch(1)

        self._create_rule_caption = QC.translate("bulk", "Create rule...")
        self._create_rule_tooltip = QC.translate(
            "bulk", "Opens the rule editor filled in from the selected connection "
                    "(process, destination, port); nothing is saved until you press Save there")
        self._create_rule_btn = self._make_button(self._create_rule_caption, self._create_rule_tooltip)
        rule_icon = QtGui.QIcon.fromTheme("document-new")
        if not rule_icon.isNull():
            self._create_rule_btn.setIcon(rule_icon)
        self._create_rule_btn.clicked.connect(self.createRuleRequested.emit)
        self._create_rule_btn.setEnabled(False)
        layout.addWidget(self._create_rule_btn)

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        sep.setAccessibleName(QC.translate("bulk", "Separator"))
        sep.setStyleSheet("color: palette(mid);")
        layout.addWidget(sep)

        export_btn = self._make_button(
            QC.translate("bulk", "Export CSV..."),
            QC.translate("bulk", "Writes the selected rows, with the visible columns, to a CSV file")
        )
        export_icon = QtGui.QIcon.fromTheme("document-save-as")
        if not export_icon.isNull():
            export_btn.setIcon(export_icon)
        export_btn.clicked.connect(self.exportRequested.emit)
        layout.addWidget(export_btn)


    def _make_button(self, text, tooltip="", accent=False, danger=False):
        btn = QtWidgets.QPushButton(text)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setIconSize(QtCore.QSize(14, 14))
        btn.setFocusPolicy(QtCore.Qt.FocusPolicy.TabFocus)
        if tooltip:
            btn.setToolTip(tooltip)
            btn.setAccessibleDescription(tooltip)
        if danger:
            btn.setStyleSheet(
                "QPushButton {"
                "  padding: 5px 12px;"
                "  border: 1px solid rgba(255,255,255,80);"
                "  border-radius: 3px;"
                "  font-size: 11px;"
                "  font-weight: 600;"
                "  color: #fff;"
                "  background: rgba(192, 57, 43, 180);"
                "}"
                "QPushButton:hover {"
                "  background: rgba(192, 57, 43, 220);"
                "}"
                "QPushButton:focus {"
                "  outline: 2px solid #fff;"
                "  outline-offset: 1px;"
                "}"
            )
        elif accent:
            btn.setStyleSheet(
                "QPushButton {"
                "  padding: 5px 12px;"
                "  border: 1px solid rgba(255,255,255,80);"
                "  border-radius: 3px;"
                "  font-size: 11px;"
                "  font-weight: 600;"
                "  color: #fff;"
                "  background: rgba(39, 174, 96, 180);"
                "}"
                "QPushButton:hover {"
                "  background: rgba(39, 174, 96, 220);"
                "}"
                "QPushButton:focus {"
                "  outline: 2px solid #fff;"
                "  outline-offset: 1px;"
                "}"
            )
        # plain buttons keep the widget style, so they read in every theme
        btn.setMinimumHeight(30)
        return btn

    def setCreateRuleEnabled(self, enabled):
        self._create_rule_btn.setEnabled(enabled)

    CAPTION_VALUES = 3

    def setCreateRuleCaption(self, shared_values=()):
        """with several rows selected, the button names what they share
        ("Create rule to /usr/bin/curl github.com 443"); with nothing shared
        it reads "Create rule..." again"""
        values = [str(v) for v in shared_values if str(v) != ""]
        if not values:
            self._create_rule_btn.setText(self._create_rule_caption)
            self._create_rule_btn.setToolTip(self._create_rule_tooltip)
            return
        shown = values[:self.CAPTION_VALUES]
        text = QC.translate("bulk", "Create rule to {0}").format(" ".join(shown))
        if len(values) > len(shown):
            text += " …"
        self._create_rule_btn.setText(text)
        self._create_rule_btn.setToolTip(QC.translate(
            "bulk", "Opens the rule editor with only what the selected connections share: {0}. "
                    "Nothing is saved until you press Save there").format(", ".join(values)))

    def createRuleCaption(self):
        return self._create_rule_btn.text()

    def count(self):
        return self._count

    def updateCount(self, count):
        self._count = count
        if count == 0:
            self.setVisible(False)
        else:
            self._count_label.setText(
                QC.translate("bulk", "%n connection(s) selected", "", count)
            )
            self.setVisible(True)

    def count(self):
        return self._count
