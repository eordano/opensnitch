"""A read-only walkthrough of the settings page on screen.

The tour is a panel inside the preferences dialog, not a window: on Wayland a
window cannot place itself, and a panel can sit right next to the rows it
talks about. One step per section; every row of the section is explained
with its current value.
"""
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC


def tr(text):
    return QC.translate('preferences', text)


def plain(text):
    doc = QtGui.QTextDocument()
    doc.setHtml(text)
    return doc.toPlainText()


# what each setting does, by the control's object name (or the row's label
# when the control has none)
EXPLANATIONS = {
    "comboUILang": "The language of every label and message. System default follows your desktop.",
    "comboUITheme": "A colour and widget theme for this window and the alert. System uses your desktop's Qt style.",
    "spinUIDensity": "The spacing of the theme: lower values pack controls closer together.",
    "checkAutostart": "Starts the tray process when you log in, so alerts can be shown from the first connection.",
    "checkPersistInterception": "If filtering was paused when the GUI closed, it stays paused at the next start.",
    "comboUIQtPlatform": "The display backend Qt uses (wayland, xcb). Change it only if the window fails to appear.",
    "checkUIAutoScreen": "Lets Qt pick the scale factor from the screen's pixel density.",
    "lineUIScreenFactor": "A fixed scale factor for the interface, used when automatic scaling is off.",
    "Never ask: apply the default answer and show a notification": "Every new connection gets the default answer below; you only see a notification.",
    "Ask, and apply the default answer after": "The alert appears and, if you do not answer in time, the default answer below is applied.",
    "Ask, and wait for my answer": "The alert stays until you answer; the connection waits meanwhile.",
    "comboUIAction": "What happens to a connection when the alert is not answered: allow, deny or reject it.",
    "comboUIDuration": "How long the rule made from an unanswered alert lasts.",
    "comboUITarget": "Which part of the connection that rule matches: the executable, the command line, the destination host, and so on.",
    "comboUIDialogPos": "Where the alert window appears on the screen.",
    "uidCheck": "Extra fields the rule made from an alert also matches on, so the rule is narrower.",
    "checkUIRules": "Hides temporary rules shorter than this from the Rules view, so it shows the lasting ones.",
    "radioSysNotifs": "Notifications go through the desktop's notification service (D-Bus).",
    "radioQtNotifs": "Notifications are balloons from the tray icon, without D-Bus.",
    "cmdTestNotifs": "Sends one notification the chosen way, so you can see how it looks.",
    "tplMissedPopup": "The text of the notification sent when an alert ends without your answer; %field% placeholders are replaced with the connection's values.",
    "spinUIRefresh": "How often the Events table reloads from the database; 0 stops automatic reloads.",
    "checkApplyToNodes": "Sends the settings below to every connected node instead of only the selected one.",
    "comboNodeAddress": "The address the node's daemon connects to for this GUI: a unix socket, or host:port.",
    "comboNodeMonitorMethod": "How the daemon finds the process behind a connection: ebpf is the most accurate, proc the most compatible.",
    "comboNodeAction": "What the daemon does with new connections while this GUI is not running.",
    "checkInterceptUnknown": "Also shows alerts for connections whose process could not be found.",
    "comboServerAddr": "The address this GUI listens on for nodes: a unix socket for the local daemon, or an IP and port for remote ones.",
    "comboAuthType": "How nodes prove who they are: none, TLS with a server certificate, or mutual TLS where nodes present one too.",
    "lineCACertFile": "The certificate authority that signed the nodes' certificates, for mutual TLS.",
    "lineCertFile": "This GUI's certificate, presented to nodes over TLS.",
    "lineCertKeyFile": "The private key that belongs to the certificate above.",
    "comboServerLogLevel": "How much the GUI writes to its log, from errors only to debug detail.",
    "comboServerLogOutput": "Where the GUI's log goes: the terminal it was started from, or a file.",
    "lineServerLogFile": "The file the GUI log is written to when Write to is a file.",
    "comboGrpcMsgSize": "The largest message a node may send in one go, for example a big rule set; larger values use more memory.",
    "spinGrpcMaxWorkers": "How many threads serve node connections at once.",
    "spinGrpcMaxClients": "How many nodes may be connected at the same time.",
    "spinGrpcKeepalive": "How often the GUI pings each node to keep the connection open.",
    "spinGrpcKeepaliveTimeout": "A node that does not answer pings for this long is treated as disconnected.",
    "comboDBType": "Keep events in memory (lost when the GUI closes) or in a database file on disk.",
    "checkDBJrnlWal": "Write-ahead logging makes writes faster and keeps a second file next to the database.",
    "spinDBMaxDays": "Events older than this are deleted.",
    "spinDBPurgeInterval": "How often old events are looked for and deleted.",
}


class TourStep:
    def __init__(self, title, entries, grid=False):
        self.title = title
        self.entries = entries
        self.grid = grid

    @property
    def widgets(self):
        return [w for e in self.entries for w in e.widgets if w.isVisible()]

    @property
    def section(self):
        return self.title if self.grid else None


class SettingsTour(QtWidgets.QFrame):
    WIDTH = 420
    GAP = 12

    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.page = owner.stackedWidget.currentWidget()
        self.steps = self._build_steps()
        self.index = 0
        self.setObjectName("settingsTour")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "#settingsTour { background: palette(window); border: 1px solid palette(highlight);"
            "  border-radius: 6px; }"
        )
        self.setFixedWidth(self.WIDTH)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        self.title = QtWidgets.QLabel(tr('Tour') + ' — ' + self.page.title)
        self.title.setStyleSheet("color: palette(placeholder-text); font-size: 11px;")
        layout.addWidget(self.title)
        self.heading = QtWidgets.QLabel()
        self.heading.setWordWrap(True)
        self.heading.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        font = self.heading.font(); font.setBold(True); self.heading.setFont(font)
        self.body = QtWidgets.QLabel()
        self.body.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.body.setWordWrap(True)
        self.body.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        self.body.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        # a long section scrolls inside the panel instead of growing past the dialog
        self.body_scroll = QtWidgets.QScrollArea()
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.body_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body_scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget > QWidget { background: transparent; }")
        self.body_scroll.setWidget(self.body)
        layout.addWidget(self.heading)
        layout.addWidget(self.body_scroll, 1)
        controls = QtWidgets.QHBoxLayout()
        self.back = QtWidgets.QPushButton(tr('Back'))
        self.end_button = QtWidgets.QPushButton(tr('End tour'))
        self.next = QtWidgets.QPushButton(tr('Next'))
        self.next.setDefault(True)
        for button in (self.back, self.end_button, self.next):
            button.setMinimumHeight(32)
            controls.addWidget(button)
        layout.addLayout(controls)
        self.back.clicked.connect(lambda: self.advance(-1))
        self.next.clicked.connect(lambda: self.advance(1))
        self.end_button.clicked.connect(self.close)
        self.highlight = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Shape.Rectangle, self.page.viewport())
        self.highlight.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        owner.stackedWidget.currentChanged.connect(self.close)
        if self.page._tabs is not None:
            self.page._tabs.currentChanged.connect(self.close)
        self.page.verticalScrollBar().valueChanged.connect(self.position_highlight)
        self.page.viewport().installEventFilter(self)
        owner.installEventFilter(self)
        owner.finished.connect(self.close)

    # --- steps: one per section

    def _build_steps(self):
        steps = []
        by_title = {}
        for entry in self.page.entries:
            widgets = [w for w in entry.widgets if w.isVisibleTo(self.page)]
            if not widgets:
                continue
            title = getattr(entry.form, "section_title", None) or self.page.title
            step = by_title.get(title)
            if step is None:
                step = TourStep(title, [])
                by_title[title] = step
                steps.append(step)
            step.entries.append(entry)
        for step in steps:
            boxes = [w for e in step.entries for w in e.widgets if isinstance(w, QtWidgets.QCheckBox)]
            step.grid = len(step.entries) > 3 and len(boxes) == sum(len(e.widgets) for e in step.entries)
        return steps

    @staticmethod
    def _label_of(entry):
        for w in entry.widgets:
            if isinstance(w, (QtWidgets.QLabel, QtWidgets.QCheckBox, QtWidgets.QRadioButton)) and w.text():
                return plain(w.text()).replace('&', '')
        return ""

    @staticmethod
    def _value_of(entry):
        for w in entry.widgets:
            if isinstance(w, QtWidgets.QComboBox):
                return w.currentText() or tr("empty")
            if isinstance(w, QtWidgets.QRadioButton):
                return tr("chosen") if w.isChecked() else tr("not chosen")
            if isinstance(w, QtWidgets.QCheckBox):
                return tr("on") if w.isChecked() else tr("off")
            if isinstance(w, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                return w.text()
            if isinstance(w, QtWidgets.QLineEdit):
                return w.text() or tr("empty")
            if isinstance(w, (QtWidgets.QPlainTextEdit, QtWidgets.QTextEdit)):
                return (w.toPlainText().strip().splitlines() or [tr("empty")])[0]
        return ""

    @classmethod
    def _explanation_of(cls, entry):
        for w in entry.widgets:
            text = EXPLANATIONS.get(w.objectName())
            if text:
                return tr(text)
        label = cls._label_of(entry)
        if label in EXPLANATIONS:
            return tr(EXPLANATIONS[label])
        for w in entry.widgets:
            if w.toolTip():
                return plain(w.toolTip())
        return ""

    def _describe(self, step):
        if step.grid:
            boxes = [w for e in step.entries for w in e.widgets if isinstance(w, QtWidgets.QCheckBox)]
            on = [plain(w.text()).replace('&', '') for w in boxes if w.isChecked()]
            off = [plain(w.text()).replace('&', '') for w in boxes if not w.isChecked()]
            parts = [tr('Tick the ones you want; each becomes a column of the table.')]
            if on:
                parts.append(tr('Shown now: {0}.').format(', '.join(on)))
            if off:
                parts.append(tr('Hidden now: {0}.').format(', '.join(off)))
            return ' '.join(parts)
        lines = []
        for entry in step.entries:
            label = self._label_of(entry)
            value = self._value_of(entry)
            why = self._explanation_of(entry)
            if not label and not why:
                continue
            if isinstance(entry.widgets[0], QtWidgets.QPushButton) and not why:
                continue
            head = "<b>{0}</b>".format(label) if label else ""
            if value and not isinstance(entry.widgets[0], QtWidgets.QPushButton):
                head += ": {0}".format(value)
            line = head
            if why:
                line += ("<br>" if head else "") + why
            lines.append(line)
        return "<br><br>".join(lines) or tr('Nothing to explain here.')

    # --- flow

    def start(self):
        self.show()
        self.raise_()
        self.show_step()

    def advance(self, delta):
        if self.index + delta >= len(self.steps):
            self.close()
            return
        self.index = max(0, self.index + delta)
        self.show_step()

    def show_step(self):
        if not self.steps:
            self.heading.setText(tr('No settings to tour on this page'))
            self.body.setText(tr('Choose a settings page or clear the settings search, then start Tour again.'))
            self.back.setEnabled(False); self.next.setEnabled(False)
            self.place()
            return
        step = self.steps[self.index]
        self.heading.setText(tr('Step {0} of {1}: {2}').format(self.index + 1, len(self.steps), step.title))
        self.body.setText(self._describe(step))
        self.back.setEnabled(self.index > 0)
        self.next.setText(tr('Finish') if self.index == len(self.steps) - 1 else tr('Next'))
        widgets = step.widgets
        if widgets:
            self.page.ensureWidgetVisible(widgets[0], 12, 40)
        self.position_highlight()
        QtCore.QTimer.singleShot(0, self.position_highlight)

    # --- geometry

    def target_rect(self):
        rect = QtCore.QRect()
        if not self.steps:
            return rect
        for widget in self.steps[self.index].widgets:
            if widget.isVisibleTo(self.page):
                rect = rect.united(QtCore.QRect(widget.mapTo(self.page.viewport(), QtCore.QPoint()), widget.size()))
        return rect

    def position_highlight(self, *args):
        if not self.steps or not self.isVisible():
            return
        rect = self.target_rect()
        self.highlight.setGeometry(rect.adjusted(-3, -3, 3, 3))
        self.highlight.show(); self.highlight.raise_()
        self.place(rect)

    def wanted_height(self, available):
        """the panel's natural height, capped to what the dialog can show;
        the body scrolls when capped"""
        inner = self.body.heightForWidth(self.WIDTH - 24 - 16) if self.body.hasHeightForWidth() else self.body.sizeHint().height()
        chrome = self.title.sizeHint().height() + self.heading.sizeHint().height() + self.next.sizeHint().height() + 10 + 10 + 8 * 3
        natural = inner + chrome + 4
        return min(natural, available)

    def place(self, rect=None):
        """beside the highlighted section, never over it: right, else left,
        else over the category list, else below, else above; top edges
        aligned, inside the dialog"""
        w = self.WIDTH
        area = self.owner.rect().adjusted(self.GAP, self.GAP, -self.GAP, -self.GAP)
        h = self.wanted_height(area.height())
        if rect is None or rect.isNull():
            self.move(area.right() - w, area.top())
            self.resize(w, h)
            return
        target = QtCore.QRect(self.page.viewport().mapTo(self.owner, rect.topLeft()), rect.size())
        candidates = [
            QtCore.QPoint(target.right() + self.GAP, target.top()),
            QtCore.QPoint(target.left() - self.GAP - w, target.top()),
            QtCore.QPoint(area.left(), target.top()),
            QtCore.QPoint(target.left(), target.bottom() + self.GAP),
            QtCore.QPoint(target.left(), target.top() - self.GAP - h),
        ]
        chosen = None
        for point in candidates:
            box = QtCore.QRect(point, QtCore.QSize(w, h))
            if area.contains(box) and not box.intersects(target):
                chosen = point
                break
        if chosen is None:
            # slide the top edge up until the box fits the dialog; over the
            # category list first, where nothing of the page is hidden
            for x in (area.left(), area.right() - w):
                y = min(max(target.top(), area.top()), area.bottom() - h)
                chosen = QtCore.QPoint(x, y)
                if not QtCore.QRect(chosen, QtCore.QSize(w, h)).intersects(target):
                    break
        self.move(chosen)
        self.resize(w, h)
        self.raise_()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.Resize:
            QtCore.QTimer.singleShot(0, self.position_highlight)
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self.highlight.hide()
        super().closeEvent(event)
