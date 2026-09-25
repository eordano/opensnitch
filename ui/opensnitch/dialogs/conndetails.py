"""The details of one connection, in a window: the same panel the Events view
shows under its table, plus Copy and Create rule."""
import os

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC

from opensnitch.nodes import Nodes
from opensnitch.database import Database
from opensnitch.database.enums import ConnFields
from opensnitch.utils import Utils
from opensnitch.customwidgets.detailpanel import ConnectionDetailPanel


class ConnDetails(QtWidgets.QDialog):
    FIELDS = (
        ("time", ConnFields.Time), ("action", ConnFields.Action), ("protocol", ConnFields.Protocol),
        ("process", ConnFields.Process), ("cmdline", ConnFields.Cmdline), ("pid", ConnFields.PID),
        ("uid", ConnFields.UID), ("src_ip", ConnFields.SrcIP), ("src_port", ConnFields.SrcPort),
        ("dst_ip", ConnFields.DstIP), ("dst_host", ConnFields.DstHost), ("dst_port", ConnFields.DstPort),
        ("node", ConnFields.Node), ("rule", ConnFields.Rule),
    )

    def __init__(self, parent):
        super().__init__(parent)
        self._db = Database.instance()
        self._nodes = Nodes.instance()
        self._data = {}
        self.setWindowTitle(QC.translate("stats", "Connection details"))
        self.setMinimumWidth(560)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.panel = ConnectionDetailPanel(self)
        # the panel's own close control belongs to the events view
        for btn in self.panel.findChildren(QtWidgets.QAbstractButton):
            if btn.toolTip() and "lose" in btn.toolTip() or btn.text() in ("✕", "×", "x", "X"):
                btn.hide()
        layout.addWidget(self.panel, 1)
        buttons = QtWidgets.QHBoxLayout()
        self.copy_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("edit-copy"), QC.translate("stats", "Copy details"))
        self.copy_button.setToolTip(QC.translate("stats", "Copies every field as text."))
        self.copy_button.clicked.connect(self.copy_details)
        self.rule_button = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("list-add"), QC.translate("stats", "Create rule..."))
        self.rule_button.setToolTip(QC.translate("stats", "Opens the rule editor filled in from this connection."))
        self.rule_button.clicked.connect(self._create_rule)
        self.close_button = QtWidgets.QPushButton(QC.translate("stats", "Close"))
        self.close_button.clicked.connect(self.close)
        for b in (self.copy_button, self.rule_button):
            b.setMinimumHeight(32)
            buttons.addWidget(b)
        buttons.addStretch(1)
        self.close_button.setMinimumHeight(32)
        self.close_button.setDefault(True)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

    def showByField(self, field, value):
        records = self._db.get_connection_by_field(field, value)
        if not records.next():
            return False
        data = {key: records.value(col) for key, col in self.FIELDS}
        for key in data:
            data[key] = "" if data[key] is None else str(data[key])
        if self._nodes.is_local(data["node"]):
            data["uid"] = Utils.get_user_id(data["uid"])
        self.show_data(data)
        return True

    def show_data(self, data):
        self._data = dict(data)
        self.panel.showConnection(self._data)
        self.panel.setVisible(True)
        self.show()
        QtWidgets.QApplication.processEvents()
        self.fit_to_content()
        self.raise_()
        self.activateWindow()

    def content_height(self):
        """the rows' height at the panel's real width (long values wrap
        at a narrow hint width but fit on one line here)"""
        scroll = self.panel.findChild(QtWidgets.QScrollArea)
        if scroll is None or scroll.widget() is None:
            return None
        inner = scroll.widget()
        width = max(scroll.viewport().width(), 1)
        layout = inner.layout()
        if layout is not None and layout.hasHeightForWidth():
            height = layout.heightForWidth(width)
        else:
            height = inner.sizeHint().height()
        return height + scroll.frameWidth() * 2

    def fit_to_content(self):
        """as tall as the panel's rows, no more: the panel scrolls inside,
        so its own hint is small"""
        scroll = self.panel.findChild(QtWidgets.QScrollArea)
        content = self.content_height()
        if scroll is not None and content is not None:
            scroll.setMinimumHeight(content)
            scroll.setMaximumHeight(content)
            self.adjustSize()
            scroll.setMinimumHeight(0)
            scroll.setMaximumHeight(QtWidgets.QWIDGETSIZE_MAX)
        screen = self.screen().availableGeometry() if self.screen() else None
        if screen is not None and self.height() > screen.height() - 80:
            self.resize(self.width(), screen.height() - 80)

    def details_text(self):
        order = [k for k, _ in self.FIELDS]
        return "\n".join("{0}: {1}".format(k.replace("_", " "), self._data.get(k, "")) for k in order)

    def copy_details(self):
        QtWidgets.QApplication.clipboard().setText(self.details_text())

    def _create_rule(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "_cb_detail_create_rule"):
            parent._cb_detail_create_rule(dict(self._data))
