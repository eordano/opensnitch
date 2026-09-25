from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC


class StatusLine(QtWidgets.QWidget):
    """the daemon figures under the tables: "Connections 1 234 · Dropped 12 ·
    Uptime 0:00:45 · Rules 30 · Daemon 1.6.7". A figure without a value is
    not shown; with several nodes only the count of nodes and the version."""

    KEYS = [
        ("nodes", "Nodes"),
        ("connections", "Connections"),
        ("dropped", "Dropped"),
        ("uptime", "Uptime"),
        ("rules", "Rules"),
        ("version", "Daemon"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusLine")
        self.setAccessibleName(QC.translate("stats", "Daemon status"))
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(18)
        self._pairs = {}
        for key, label in self.KEYS:
            cell = QtWidgets.QWidget()
            hl = QtWidgets.QHBoxLayout(cell)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(6)
            name = QtWidgets.QLabel(QC.translate("stats", label))
            name.setStyleSheet("color: palette(placeholder-text); font-size: 12px;")
            value = QtWidgets.QLabel("")
            value.setStyleSheet("font-weight: 600; font-size: 12px;")
            value.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
            hl.addWidget(name)
            hl.addWidget(value)
            cell.setVisible(False)
            layout.addWidget(cell)
            self._pairs[key] = (cell, value)
        layout.addStretch(1)
        self._empty = QtWidgets.QLabel(QC.translate("stats", "No daemon connected"))
        self._empty.setStyleSheet("color: palette(placeholder-text); font-size: 12px; font-style: italic;")
        layout.insertWidget(0, self._empty)

    def set(self, **values):
        """values: nodes, connections, dropped, uptime, rules, version;
        None or "" hides the figure"""
        shown = 0
        for key, (cell, label) in self._pairs.items():
            v = values.get(key)
            text = "" if v is None else str(v)
            label.setText(text)
            cell.setVisible(text != "")
            shown += text != ""
        self._empty.setVisible(shown == 0)

    def clear(self):
        self.set()

    def values(self):
        return {k: v.text() for k, (c, v) in self._pairs.items() if c.isVisibleTo(self)}
