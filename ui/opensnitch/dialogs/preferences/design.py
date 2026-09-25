"""The Preferences dialog, laid out by hand.

preferences.ui still declares every control (so settings.py, signals.py and
the sections keep their widget names), but the pages it draws are discarded
and the controls are re-homed here into a category list with one scrollable
page each:

    General        language, theme, autostart, display scaling
    Prompts        the "new connection" dialog: timeout, default answer, fields
    Notifications  desktop notifications and the missed-prompt message
    Events         the events table: refresh and columns
    Nodes          per-daemon configuration (behaviour, rules, logging, security, advanced)
    Server         the endpoint daemons connect to, its TLS and gRPC limits
    Storage        where events are kept and for how long
"""

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC

from opensnitch.utils import Icons
from opensnitch.config import Config

PAGE_GENERAL = 0
PAGE_PROMPTS = 1
PAGE_NOTIFICATIONS = 2
PAGE_EVENTS = 3
PAGE_NODES = 4
PAGE_SERVER = 5
PAGE_STORAGE = 6

SEARCH_HEIGHT = 32

NODE_TAB_BEHAVIOUR = 0
NODE_TAB_RULES = 1
NODE_TAB_LOGGING = 2
NODE_TAB_SECURITY = 3
NODE_TAB_ADVANCED = 4


def _tr(text):
    return QC.translate("preferences", text)


class Entry:
    """one searchable setting: the widgets that make up its row and the words
    that find it"""
    HIGHLIGHT = "background-color: rgba(255, 200, 0, 90); border-radius: 3px; padding: 1px 3px;"

    def __init__(self, page, form, widgets, text):
        self.page = page
        self.form = form
        self.widgets = [w for w in widgets if w is not None]
        self.text = text.lower()
        self._styles = {}

    def matches(self, needle):
        return needle in self.text

    def is_radio(self):
        return any(isinstance(w, QtWidgets.QRadioButton) for w in self.widgets)

    def set_visible(self, visible, hidden_by_code):
        """returns whether anything of the entry ends up visible"""
        shown = False
        for w in self.widgets:
            show = visible and not hidden_by_code.get(w, False)
            w.setVisible(show)
            shown = shown or show
        return shown

    def highlight(self, on):
        """mark the words of a hit: the label, checkbox or radio of the row"""
        for w in self.widgets:
            if not isinstance(w, (QtWidgets.QLabel, QtWidgets.QCheckBox, QtWidgets.QRadioButton)):
                continue
            if isinstance(w, WrapLabel):
                continue
            if on:
                if w not in self._styles:
                    self._styles[w] = w.styleSheet()
                w.setStyleSheet(self._styles[w] + self.HIGHLIGHT)
            elif w in self._styles:
                w.setStyleSheet(self._styles.pop(w))


def _widgets_in(layout):
    out = []
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.widget() is not None:
            out.append(item.widget())
        elif item.layout() is not None:
            out.extend(_widgets_in(item.layout()))
    return out


def _words(*widgets):
    parts = []
    for w in widgets:
        if w is None:
            continue
        if isinstance(w, QtWidgets.QLayout):
            parts.append(_words(*_widgets_in(w)))
            continue
        for attr in ("text", "toolTip", "placeholderText", "title"):
            fn = getattr(w, attr, None)
            if callable(fn):
                try:
                    parts.append(str(fn()))
                except TypeError:
                    pass
        if isinstance(w, QtWidgets.QComboBox):
            parts.extend(w.itemText(i) for i in range(w.count()))
    return " ".join(parts)


class Form(QtWidgets.QFormLayout):
    def __init__(self, page=None):
        super().__init__()
        self.page = page
        self.section = None
        self.setContentsMargins(18, 6, 8, 10)
        self.setHorizontalSpacing(16)
        self.setVerticalSpacing(10)
        self.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.DontWrapRows)
        # left-aligned labels keep their x when a longer label appears in a row below
        self.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)

    def _register(self, widgets, extra=""):
        if self.page is None:
            return
        flat = []
        for w in widgets:
            if isinstance(w, QtWidgets.QLayout):
                flat.extend(_widgets_in(w))
            elif w is not None:
                flat.append(w)
        self.page.entries.append(Entry(self.page, self, flat, _words(*widgets) + " " + extra))

    def row(self, label, field, tip=""):
        """label: str (a new QLabel) or an existing QLabel to reuse (renamed
        with `tip` as tooltip); field: a widget or a layout"""
        if isinstance(label, str):
            label = QtWidgets.QLabel(label)
        if tip:
            label.setToolTip(tip)
            if isinstance(field, QtWidgets.QWidget) and field.toolTip() == "":
                field.setToolTip(tip)
        _unfix(label)
        if isinstance(field, QtWidgets.QWidget):
            _unfix(field)
            if isinstance(label, QtWidgets.QLabel):
                label.setBuddy(field)
        else:
            inner = _widgets_in(field)
            if inner and isinstance(label, QtWidgets.QLabel):
                label.setBuddy(inner[0])
        self.addRow(label, field)
        self._register([label, field], tip)
        return label

    def check(self, box, text, tip=""):
        box.setText(text)
        if tip:
            box.setToolTip(tip)
        self.addRow(box)
        self._register([box], tip)
        return box

    def wide(self, widget):
        _unfix(widget)
        self.addRow(widget)
        self._register([widget])
        return widget

    def line(self, layout, extra=""):
        """a spanning row made of several controls"""
        self.addRow(layout)
        self._register([layout], extra)
        return layout

    def note(self, text):
        label = WrapLabel(text)
        label.setOpenExternalLinks(True)
        label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
        label.setStyleSheet("color: palette(placeholder-text);")
        self.addRow(label)
        self._register([label])
        return label


def _unfix(w):
    """the .ui pins many controls to odd sizes; let the form decide"""
    sp = w.sizePolicy()
    if sp.verticalPolicy() == QtWidgets.QSizePolicy.Policy.Ignored:
        sp.setVerticalPolicy(QtWidgets.QSizePolicy.Policy.Preferred)
    if sp.horizontalPolicy() in (QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed) \
            and isinstance(w, (QtWidgets.QComboBox, QtWidgets.QLineEdit)):
        sp.setHorizontalPolicy(QtWidgets.QSizePolicy.Policy.Preferred)
    if isinstance(w, QtWidgets.QComboBox):
        w.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        w.setMinimumContentsLength(12)
    w.setSizePolicy(sp)
    w.setMinimumSize(0, 0)
    w.setMaximumSize(16777215, 16777215)


def compact(*widgets, stretch=True):
    """a row of fixed-size controls kept at their natural width"""
    box = QtWidgets.QHBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(6)
    for w in widgets:
        if isinstance(w, QtWidgets.QLineEdit):
            w.setMaximumWidth(110)
        box.addWidget(w)
    if stretch:
        box.addStretch(1)
    return box


def line_with_button(line, button, text):
    button.setText(text)
    box = QtWidgets.QHBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(6)
    box.addWidget(line, 1)
    box.addWidget(button)
    return box


def group(title, form):
    """a section: bold heading over an indented form. Styles disagree on
    where a QGroupBox title goes (Breeze centres it); a heading always sits left."""
    box = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(2)
    heading = QtWidgets.QLabel(title)
    font = heading.font()
    font.setBold(True)
    heading.setFont(font)
    lay.addWidget(heading)
    lay.addLayout(form)
    if isinstance(form, Form):
        form.section = box
        form.section_title = title
    return box


class WrapLabel(QtWidgets.QLabel):
    """word-wrapped label whose minimum height does not balloon: Qt computes a
    wrapped label's minimumSizeHint at a very narrow width, which makes the
    surrounding scroll area think the page needs scrolling"""
    def __init__(self, text=""):
        super().__init__(text)
        self.setWordWrap(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self):
        return QtCore.QSize(0, self.fontMetrics().height())

    def sizeHint(self):
        w = self.width() if self.width() > 50 else 600
        return QtCore.QSize(w, self.heightForWidth(w))


def checkbox_grid(boxes, columns=3):
    grid = QtWidgets.QGridLayout()
    grid.setContentsMargins(18, 4, 8, 8)
    grid.setHorizontalSpacing(24)
    grid.setVerticalSpacing(6)
    for i, b in enumerate(boxes):
        grid.addWidget(b, i // columns, i % columns)
    return grid


class Page(QtWidgets.QScrollArea):
    def __init__(self, title, description=""):
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        body = QtWidgets.QWidget()
        self.body = QtWidgets.QVBoxLayout(body)
        self.body.setContentsMargins(6, 0, 12, 12)
        self.body.setSpacing(12)
        heading = QtWidgets.QLabel(title)
        font = heading.font()
        font.setPointSizeF(font.pointSizeF() * 1.35)
        font.setBold(True)
        heading.setFont(font)
        # same box as the search field on the left, so the two share top and baseline
        heading.setFixedHeight(SEARCH_HEIGHT)
        heading.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.header = QtWidgets.QHBoxLayout()
        self.header.setContentsMargins(0, 0, 0, 0)
        self.header.setSpacing(12)
        self.header.addWidget(heading, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.header.addStretch(1)
        self.body.addLayout(self.header)
        if description:
            desc = WrapLabel(description)
            desc.setStyleSheet("color: palette(placeholder-text);")
            desc.setOpenExternalLinks(True)
            desc.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
            self.body.addWidget(desc)
        self.setWidget(body)
        self._tabs = None
        self.entries = []
        self.title = title

    def add(self, widget_or_layout):
        if isinstance(widget_or_layout, QtWidgets.QWidget):
            self.body.addWidget(widget_or_layout)
        else:
            self.body.addLayout(widget_or_layout)

    def add_header_widget(self, widget):
        self.header.addWidget(widget, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

    def add_tabs(self, tabs):
        self.body.addWidget(tabs, 1)
        self._tabs = tabs

    def finish(self):
        if self._tabs is None:
            self.body.addStretch(1)

    def filter(self, needle, hidden_by_code):
        """show only the entries matching `needle`; returns the match count.
        An empty needle restores every entry to the visibility the settings
        code gave it."""
        count = 0
        by_form = {}
        searching = needle != "" and needle not in self.title.lower()
        hits = {e: (not searching) or e.matches(needle) for e in self.entries}
        # a radio group is one setting: keep the whole group when one option hits
        radio_forms = {e.form for e in self.entries if e.is_radio() and hits[e]}
        for e in self.entries:
            hit = hits[e] or (e.is_radio() and e.form in radio_forms)
            shown = e.set_visible(hit, hidden_by_code)
            e.highlight(searching and hits[e] and shown)
            by_form.setdefault(e.form, False)
            if hit and shown:
                count += 1
                by_form[e.form] = True
        for form, any_hit in by_form.items():
            if form.section is not None:
                form.section.setVisible(any_hit)
        if self._tabs is not None:
            for i in range(self._tabs.count()):
                tab = self._tabs.widget(i)
                forms = [f for f in by_form if f.parentWidget() is tab]
                self._tabs.setTabVisible(i, needle == "" or any(by_form[f] for f in forms))
        return count


class _Follow(QtCore.QObject):
    """hide/show `targets` whenever `source` is hidden/shown by the settings code"""
    def __init__(self, source, targets):
        super().__init__(source)
        self.targets = targets
        source.installEventFilter(self)
        for t in targets:
            t.setVisible(not source.isHidden())

    def eventFilter(self, obj, event):
        if event.type() in (QtCore.QEvent.Type.Hide, QtCore.QEvent.Type.Show,
                            QtCore.QEvent.Type.HideToParent, QtCore.QEvent.Type.ShowToParent):
            hidden = obj.isHidden()
            for t in self.targets:
                t.setVisible(not hidden)
        return False


def follow(source, *targets):
    return _Follow(source, list(targets))


def _park(holder, widget):
    """keep an old container alive but never visible"""
    widget.setParent(holder)
    widget.setVisible(False)


# ---------------------------------------------------------------- pages

def _page_general(d):
    p = Page(_tr("Appearance"), _tr("How the OpenSnitch window looks and behaves."))

    f = Form(p)
    f.row(_tr("Language"), d.comboUILang)
    f.row(_tr("Theme"), d.comboUITheme)
    f.wide(d.labelThemeError)
    d.labelThemeError.setStyleSheet("color: palette(placeholder-text);")
    d.labelUIDensity.setText(_tr("Theme density"))
    f.row(d.labelUIDensity, compact(d.spinUIDensity),
          _tr("Spacing of the qt-material themes: negative values are tighter, positive ones roomier."))
    f.check(d.checkAutostart, _tr("Start the GUI when I log in"))
    f.check(d.checkPersistInterception, _tr("Remember whether interception was paused"),
            _tr("If the firewall was paused when the GUI closed, keep it paused on the next start."))
    p.add(group(_tr("Appearance and start-up"), f))

    f = Form(p)
    f.row(_tr("Qt platform plugin"), d.comboUIQtPlatform,
          _tr("Sets QT_QPA_PLATFORM for the GUI. Leave empty to let Qt choose; "
              "pick xcb if the Wayland session misbehaves."))
    f.check(d.checkUIAutoScreen, _tr("Scale the interface automatically for the screen"))
    d.labelUIScreenFactor.setText(_tr("Scale factor"))
    d.labelUIScreenFactor.setOpenExternalLinks(True)
    d.lineUIScreenFactor.setPlaceholderText(_tr("1, 1.25, 1.5, 2 ... use ; to give one per screen"))
    f.row(d.labelUIScreenFactor, d.lineUIScreenFactor,
          _tr("A global scale factor (1.5 = 150%). Separate several screens with ';'. "
              "Takes effect after restarting the GUI."))
    p.add(group(_tr("Display"), f))
    p.finish()
    return p


class _SampleConnection:
    """what PromptDialog._render_connection() reads, for a believable alert"""
    protocol = "tcp"
    src_ip = "192.168.1.42"
    src_port = 48372
    dst_ip = "140.82.121.6"
    dst_host = "api.github.com"
    dst_port = 443
    user_id = 1000
    process_id = 12345
    process_path = "/usr/bin/curl"
    process_cwd = "/home/user"
    process_args = ["/usr/bin/curl", "https://api.github.com/repos"]
    process_env = {}

    def __init__(self):
        self.process_checksums = {Config.OPERAND_PROCESS_HASH_MD5: "d41d8cd98f00b204e9800998ecf8427e",
                                  "process.hash.sha1": ""}

    def __getattr__(self, name):
        return ""


def _without_top_edge(pix):
    """some styles paint a line along a dialog's top edge; it is not content.
    Drop any dark rows within the first few pixels of the grab."""
    img = pix.toImage()
    if img.width() < 40 or img.height() < 20:
        return pix
    xs = range(20, img.width() - 20, max(1, img.width() // 20))
    def lightness(y):
        return sum(QtGui.QColor(img.pixel(x, y)).lightness() for x in xs) / len(xs)
    base = lightness(8)
    cut = 0
    for y in range(0, 8):
        if lightness(y) < base - 25:
            cut = y + 1
    if cut:
        pix = pix.copy(0, cut, pix.width(), pix.height() - cut)
    return pix


class _AlertPreview(QtWidgets.QLabel):
    """the real alert dialog, rendered off-screen with a sample connection and
    the fields the boxes on this page preselect"""
    WIDTH = 560

    def __init__(self, d, checks):
        super().__init__()
        self.d = d
        self.checks = checks
        self.dialog = None
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        # the column decides the width (never wider than the alert itself); the
        # height follows the scaled render
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setStyleSheet("border: 1px solid palette(mid); border-radius: 4px; background: palette(base); padding: 8px;")
        self._full = None
        self.setToolTip(_tr("How the alert will look. Rendered from the alert dialog itself."))
        self._pending = False

    def _ensure_dialog(self):
        if self.dialog is None:
            from opensnitch.dialogs.prompt.dialog import PromptDialog
            from opensnitch.dialogs.prompt import constants as prompt_constants

            class PreviewPrompt(PromptDialog):
                """the alert with its actions disarmed: buttons and close just hide it"""
                def _send_rule(self):
                    self.hide()

                def closeEvent(self, e):
                    self.hide()
                    e.accept()

            self.dialog = PreviewPrompt(appicon=self.d.windowIcon())
            self.dialog.setWindowTitle(_tr("Sample alert"))
            self.dialog.setWindowFlags(QtCore.Qt.WindowType.Dialog)
            self.dialog._local = True
            self.dialog._peer = "unix:///run/user/1000/opensnitch/osui.sock"
            self.dialog._hostname = "workstation"
            self._page_main = prompt_constants.PAGE_MAIN
        return self.dialog

    def prepare(self):
        dlg = self._ensure_dialog()
        con = _SampleConnection()
        dlg._con = con
        dlg.stackedWidget.setCurrentIndex(self._page_main)
        dlg.reset_widgets()
        dlg._render_connection(con)
        dlg.checkUserID.setChecked(self.checks["uid"].isChecked())
        dlg.checkDstPort.setChecked(self.checks["dstport"].isChecked())
        dlg.checkDstIP.setChecked(self.checks["dstip"].isChecked())
        dlg.checkSum.setChecked(self.checks["checksum"].isChecked())
        dlg._update_preview()
        dlg.set_message_text(_tr("Sample alert: any button just closes it."))
        return dlg

    def render(self):
        self._pending = False
        try:
            dlg = self.prepare()
        except Exception as e:
            self.setText(_tr("The alert could not be rendered: {0}").format(e))
            return
        if not dlg.isVisible():
            dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen, True)
            dlg.show()
            QtWidgets.QApplication.processEvents()
            pix = dlg.grab()
            dlg.hide()
            dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        else:
            pix = dlg.grab()
        pix.setDevicePixelRatio(1)
        self._full = _without_top_edge(pix)
        self._rescale()

    def _rescale(self):
        if self._full is None:
            return
        ratio = self.devicePixelRatioF()
        pad = 2 * 9
        width = max(120, min(self.WIDTH, self.width() - pad))
        scaled = self._full.scaledToWidth(int(width * ratio), QtCore.Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(ratio)
        self.setPixmap(scaled)
        self.setFixedHeight(int(scaled.height() / ratio) + pad)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._full is not None and abs(event.size().width() - event.oldSize().width()) > 2:
            self._rescale()

    def schedule(self, *_):
        if self._pending or not self.isVisible():
            return
        self._pending = True
        QtCore.QTimer.singleShot(0, self.render)

    def showEvent(self, event):
        super().showEvent(event)
        if self.pixmap().isNull():
            self.render()

    def open_window(self):
        dlg = self.prepare()
        dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DontShowOnScreen, False)
        dlg.show()
        geo = self.d.frameGeometry()
        dlg.move(geo.center() - dlg.rect().center())
        dlg.raise_()
        dlg.activateWindow()


def _alert_preview(d, f, holder):
    """the fields the alert preselects, and the alert itself"""
    # the fork's alert always shows the rule fields; the old "advanced view"
    # switch has nothing left to switch, so its checkbox stays parked
    _park(holder, d.showAdvancedCheck)
    checks = {"uid": d.uidCheck, "dstport": d.dstPortCheck, "dstip": d.dstIPCheck, "checksum": d.checkSum}
    d.uidCheck.setText(_tr("User"))
    d.dstPortCheck.setText(_tr("Destination port"))
    d.dstIPCheck.setText(_tr("Destination IP"))
    d.checkSum.setText(_tr("Executable checksum"))
    lbl = QtWidgets.QLabel(_tr("Also match on"))
    lbl.setToolTip(_tr("Fields ticked when the alert opens, so the rule it creates matches on them too. "
                       "The executable is always matched."))
    f.row(lbl, compact(d.uidCheck, d.dstPortCheck, d.dstIPCheck, d.checkSum))
    preview = _AlertPreview(d, checks)
    d.alertPreview = preview
    for box in checks.values():
        box.toggled.connect(preview.schedule)
    open_btn = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("window-new"), _tr("Open Sample"))
    open_btn.setToolTip(_tr("Shows the alert as a window, with a sample connection. Nothing is sent."))
    open_btn.clicked.connect(preview.open_window)
    d.alertPreviewButton = open_btn
    side = QtWidgets.QWidget()
    col = QtWidgets.QVBoxLayout(side)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(8)
    col.addWidget(QtWidgets.QLabel(_tr("Preview")))
    col.addWidget(open_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
    col.addStretch(1)
    open_btn.setMinimumWidth(open_btn.sizeHint().width())
    side.setMinimumWidth(side.sizeHint().width())
    f.row(side, preview)


def _asking_radios(d, f, holder):
    """popupsCheck + spinUITimeout, which the settings code reads, expressed
    as one choice: never ask / ask with a countdown / ask and wait.
    A negative timeout is the prompt's "no countdown"."""
    never = QtWidgets.QRadioButton(_tr("Never ask: apply the default answer and show a notification"))
    never.setToolTip(_tr("The prompt is not shown; the default answer below is applied and a "
                         "desktop notification tells you what happened."))
    auto = QtWidgets.QRadioButton(_tr("Ask, and apply the default answer after"))
    auto.setToolTip(_tr("The prompt shows a countdown; when it reaches zero the default answer is applied."))
    wait = QtWidgets.QRadioButton(_tr("Ask, and wait for my answer"))
    wait.setToolTip(_tr("The prompt stays open until you answer it."))
    d.radioAskNever, d.radioAskAuto, d.radioAskWait = never, auto, wait
    d.spinUITimeout.setSuffix(" " + _tr("s"))
    d.spinUITimeout.setMinimum(-1)
    d.spinUITimeout.setSpecialValueText(_tr("no limit"))
    _park(holder, d.popupsCheck)
    f.wide(never)
    f.line(compact(auto, d.spinUITimeout), _tr("timeout countdown"))
    f.wide(wait)

    state = {"busy": False}

    def from_controls(*_):
        if state["busy"]:
            return
        state["busy"] = True
        if d.popupsCheck.isChecked():
            never.setChecked(True)
        elif d.spinUITimeout.value() < 0:
            wait.setChecked(True)
        else:
            auto.setChecked(True)
        d.spinUITimeout.setEnabled(auto.isChecked())
        state["busy"] = False

    def to_controls(*_):
        if state["busy"]:
            return
        state["busy"] = True
        if never.isChecked():
            d.popupsCheck.setChecked(True)
        else:
            d.popupsCheck.setChecked(False)
            if wait.isChecked():
                d.spinUITimeout.setValue(-1)
            elif d.spinUITimeout.value() <= 0:
                d.spinUITimeout.setValue(20)
        d.spinUITimeout.setEnabled(auto.isChecked())
        state["busy"] = False

    d.popupsCheck.toggled.connect(from_controls)
    d.spinUITimeout.valueChanged.connect(from_controls)
    for r in (never, auto, wait):
        r.toggled.connect(lambda on: on and to_controls())
    from_controls()


def _page_prompts(d, holder):
    p = Page(_tr("Authorization alerts"),
             _tr("What happens when a program opens a connection that no rule covers yet."))

    f = Form(p)
    _asking_radios(d, f, holder)
    p.add(group(_tr("Asking"), f))

    f = Form(p)
    f.row(_tr("Action"), d.comboUIAction,
          _tr("Preselected in the prompt, and applied when the countdown ends."))
    f.row(_tr("Duration"), d.comboUIDuration, _tr("How long the rule created from the prompt lasts."))
    f.row(_tr("Apply the rule to"), d.comboUITarget,
          _tr("Which property of the connection the rule matches on."))
    f.row(_tr("Show the prompt at"), d.comboUIDialogPos)
    p.add(group(_tr("Default answer"), f))

    f = Form(p)
    _alert_preview(d, f, holder)
    p.add(group(_tr("The alert"), f))

    f = Form(p)
    d.checkUIRules.setText(_tr("Do not list temporary rules lasting"))
    d.checkUIRules.setToolTip(
        _tr("Rules of that duration still apply, but are not shown in the Rules view."))
    f.row(d.checkUIRules, d.comboUIRules)
    p.add(group(_tr("Temporary rules"), f))
    p.finish()
    return p


def _page_notifications(d, holder):
    p = Page(_tr("Notifications"), _tr("Messages shown outside the OpenSnitch window."))

    # groupNotifs (a checkable QGroupBox) is the control the settings code
    # reads and writes; it stays parked and a heading checkbox mirrors it, so
    # the title sits left in every style and no stray indicator is drawn.
    head = QtWidgets.QCheckBox(_tr("Show desktop notifications"))
    font = head.font()
    font.setBold(True)
    head.setFont(font)
    d.radioSysNotifs.setText(_tr("Through the desktop (D-Bus)"))
    d.radioQtNotifs.setText(_tr("From the tray icon (Qt)"))
    d.labelNotifsWarning.setStyleSheet("color: palette(placeholder-text);")
    d.cmdTestNotifs.setText(_tr("Send a test notification"))
    f = Form(p)
    f.wide(d.radioSysNotifs)
    f.wide(d.radioQtNotifs)
    d.labelNotifsWarning.setVisible(False)
    f.line(compact(d.cmdTestNotifs))
    body = QtWidgets.QWidget()
    body.setLayout(f)
    _park(holder, d.groupNotifs)
    head.setChecked(d.groupNotifs.isChecked())
    body.setEnabled(head.isChecked())
    head.toggled.connect(d.groupNotifs.setChecked)
    head.toggled.connect(body.setEnabled)
    d.groupNotifs.toggled.connect(head.setChecked)
    d._notifsHeading = head
    f.section = head
    p.add(head)
    p.add(body)

    f = Form(p)
    f.note(_tr("Sent as a notification when a prompt ends without your answer. "
               "Write %field% to insert a value from the connection: "
               "conn.process, conn.process_args, conn.dsthost, conn.dstip, conn.dstport, "
               "conn.proto, conn.srcip, conn.srcport, conn.process_cwd, rule.action, "
               "node.addr, node.hostname."))
    d.tplMissedPopup.setPlaceholderText(_tr("%rule.action% %conn.process% -> %conn.dsthost%:%conn.dstport%"))
    f.wide(d.tplMissedPopup)
    d.tplMissedPopup.setMaximumHeight(90)
    preview = _TemplatePreview(d.tplMissedPopup)
    f.row(_tr("Preview"), preview)
    p.add(group(_tr("Message for unanswered prompts"), f))
    p.finish()
    return p


class _TemplatePreview(QtWidgets.QFrame):
    """the missed-prompt message rendered with a sample connection, mirroring
    service._build_missed_rule_msg()"""
    SAMPLE = {
        "conn.srcport": "48372", "conn.srcip": "192.168.1.42",
        "conn.dsthost": "api.github.com", "conn.dstip": "140.82.121.6", "conn.dstport": "443",
        "conn.proto": "tcp", "conn.process": "/usr/bin/curl",
        "conn.process_cwd": "/home/user", "conn.process_args": "curl https://api.github.com/",
        "conn.uid": "1000", "rule.action": "deny", "conn.action": "deny",
        "node.addr": "unix:///run/user/1000/opensnitch/osui.sock", "node.hostname": "workstation",
    }

    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setStyleSheet("_TemplatePreview { background: palette(base); border: 1px solid palette(mid); border-radius: 4px; }")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(2)
        self.title = QtWidgets.QLabel(self.SAMPLE["conn.process"])
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        self.body = WrapLabel("")
        lay.addWidget(self.title)
        lay.addWidget(self.body)
        editor.textChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        text = self.editor.toPlainText()
        for key, value in self.SAMPLE.items():
            text = text.replace(f"%{key}%", value)
        self.body.setText(text if text.strip() else self.editor.placeholderText())


def _page_events(d):
    p = Page(_tr("Events"), _tr("The connections table in the main window."))

    f = Form(p)
    d.spinUIRefresh.setSuffix(" " + _tr("s"))
    f.row(_tr("Refresh every"), compact(d.spinUIRefresh),
          _tr("0 refreshes as soon as new events arrive."))
    p.add(group(_tr("Updates"), f))

    order = [d.checkHideTime, d.checkHideNode, d.checkHideAction,
             d.checkHideProc, d.checkHideCmdline, d.checkHidePID,
             d.checkHideDstHost, d.checkHideDstIP, d.checkHideDstPort,
             d.checkHideSrcIP, d.checkHideSrcPort, d.checkHideProto,
             d.checkHideUID, d.checkHideRule]
    d.checkHideProc.setText(_tr("Process"))
    d.checkHideCmdline.setText(_tr("Command line"))
    d.checkHideDstHost.setText(_tr("Destination host"))
    d.checkHideDstIP.setText(_tr("Destination IP"))
    d.checkHideDstPort.setText(_tr("Destination port"))
    d.checkHideUID.setText(_tr("User"))
    grid = checkbox_grid(order, columns=3)
    carrier = Form(p)
    section = group(_tr("Columns"), grid)
    carrier.section = section
    carrier.section_title = _tr("Columns")
    for box in order:
        p.entries.append(Entry(p, carrier, [box], _words(box) + " column"))
    p.add(section)
    p.finish()
    return p


def _page_nodes(d, holder):
    p = Page(_tr("Nodes"),
             _tr("This OpenSnitch desktop application can control the firewalls of multiple "
                 "machines (nodes). Each node runs the OpenSnitch daemon and connects to this "
                 "application; the settings below are sent to the node when you press Apply or OK. "
                 "<a href=\"{0}Nodes\">What is a node?</a>").format(Config.HELP_URL))

    d.comboNodes.setMinimumWidth(260)
    d.comboNodes.setToolTip(_tr("The node these settings belong to"))
    p.add_header_widget(d.comboNodes)
    # the code still writes the hostname and version here; the picker already
    # names the node, so these stay parked
    for w in (d.labelNodeName, d.labelNodeVersion):
        _park(holder, w)

    f = Form(p)
    f.setContentsMargins(0, 0, 8, 0)
    f.check(d.checkApplyToNodes, _tr("Apply these settings to every connected node"))
    p.add(f)

    tabs = d.tabNodeWidget
    for i in reversed(range(tabs.count())):
        w = tabs.widget(i)
        tabs.removeTab(i)
        _park(holder, w)

    f = Form(p)
    f.row(_tr("GUI address"), d.comboNodeAddress,
          _tr("Where this node connects to the GUI: unix:///run/user/1000/opensnitch/osui.sock "
              "or an IP and port such as 127.0.0.1:50051."))
    f.row(_tr("Process monitor"), d.comboNodeMonitorMethod,
          _tr("How the daemon finds the process behind a connection: ebpf is the most "
              "accurate, proc the most portable, audit needs auditd."))
    f.row(_tr("While the GUI is away, new connections are"), d.comboNodeAction,
          _tr("Applied when no GUI is connected, and while a prompt is already open."))
    d.labelNodeDuration.setText(_tr("For"))
    f.row(d.labelNodeDuration, d.comboNodeDuration)
    f.check(d.checkInterceptUnknown, _tr("Also ask about connections with no known process"),
            _tr("Connections whose process cannot be determined (usually stale sockets) "
                "are normally let through; enable this to be asked about them."))
    tabs.addTab(_tab(f), _tr("Behaviour"))

    f = Form(p)
    d.lineNodeRulesPath.setPlaceholderText("/etc/opensnitchd/rules")
    f.row(_tr("Rules directory"), line_with_button(d.lineNodeRulesPath, d.cmdNodeRulesPath, _tr("Browse...")),
          _tr("Where the daemon stores its rules. Must exist on the node."))
    f.check(d.enableChecksums, _tr("Verify executable checksums"),
            _tr("Rules can match on the hash of the executable; computing it costs some CPU."))
    d.radioButton.setText("MD5")
    d.radioButton_2.setText("SHA1")
    f.row(_tr("Hash"), compact(d.radioButton, d.radioButton_2))
    tabs.addTab(_tab(f), _tr("Rules"))

    f = Form(p)
    f.row(_tr("Level"), d.comboNodeLogLevel)
    f.row(_tr("Write to"), d.comboNodeLogFile,
          _tr("/dev/stdout sends the log to the journal when the daemon runs under systemd."))
    f.check(d.checkNodeLogUTC, _tr("Timestamps in UTC"))
    f.check(d.checkNodeLogMicro, _tr("Timestamps with microseconds"))
    tabs.addTab(_tab(f), _tr("Logging"))

    f = Form(p)
    f.row(_tr("Authentication"), d.comboNodeAuthType,
          _tr("Simple: no authentication. TLS: the node presents a certificate; "
              "mutual TLS: the GUI presents one too."))
    f.row(_tr("CA certificate"), d.lineNodeCACertFile)
    f.row(_tr("GUI certificate"), d.lineNodeServerCertFile)
    f.row(_tr("Node certificate"), d.lineNodeCertFile)
    f.row(_tr("Node private key"), d.lineNodeCertKeyFile)
    for w in (d.lineNodeCACertFile, d.lineNodeServerCertFile, d.lineNodeCertFile, d.lineNodeCertKeyFile):
        w.setPlaceholderText(_tr("absolute path on the node"))
    f.check(d.checkNodeAuthSkipVerify, _tr("Skip certificate verification"))
    f.row(_tr("Client certificate policy"), d.comboNodeAuthVerifyType)
    f.note(d.label_26.text())
    tabs.addTab(_tab(f), _tr("Security"))

    f = Form(p)
    f.row(_tr("Events sent to the GUI"), compact(d.lineNodeMaxEvents),
          _tr("Connections kept in the daemon's buffer and sent on the next stats update."))
    f.row(_tr("Entries per statistic"), compact(d.lineNodeMaxStats),
          _tr("Top entries kept for each of hosts, processes, addresses, ports and users."))
    sec = QtWidgets.QLabel(_tr("s"))
    f.row(_tr("Check firewall rules every"), compact(d.lineNodeFwMonInterval, sec),
          _tr("Re-adds the interception rules if something removed them. 0 disables the check."))
    d.spinNodeGC.setSuffix(" %")
    f.row(_tr("Go garbage collector target"), compact(d.spinNodeGC),
          _tr("GOGC. Lower values use less memory and more CPU."))
    f.check(d.checkNodeBypassQueue, _tr("Block all outbound traffic if the daemon dies unexpectedly"),
            _tr("By default traffic is let through when nothing answers the netfilter queue."))
    f.check(d.checkNodeFlushConns, _tr("Close established connections when the daemon starts"),
            _tr("Forces programs to reconnect so their connections can be intercepted. "
                "Interrupts downloads in progress."))
    tabs.addTab(_tab(f), _tr("Advanced"))

    p.add_tabs(tabs)
    p.finish()
    return p


def _tab(form):
    w = QtWidgets.QWidget()
    w.setLayout(form)
    return w


def _page_server(d):
    p = Page(_tr("Server"),
             _tr("The GUI listens here for daemons. Changes take effect after restarting the GUI."))

    f = Form(p)
    f.row(_tr("Listen on"), d.comboServerAddr,
          _tr("A unix socket (unix:///run/user/1000/opensnitch/osui.sock) or an IP and port "
              "(127.0.0.1:50051) for daemons on other machines."))
    f.row(_tr("Authentication"), d.comboAuthType,
          _tr("Simple: no authentication. TLS: the GUI presents a certificate; "
              "mutual TLS: nodes must present one too."))
    f.row(_tr("CA certificate"), d.lineCACertFile)
    f.row(_tr("Certificate"), d.lineCertFile)
    f.row(_tr("Private key"), d.lineCertKeyFile)
    for w in (d.lineCACertFile, d.lineCertFile, d.lineCertKeyFile):
        w.setPlaceholderText(_tr("absolute path"))
    f.note(d.label_28.text())
    p.add(group(_tr("Incoming connections"), f))

    f = Form(p)
    f.row(_tr("Level"), d.comboServerLogLevel)
    f.row(_tr("Write to"), d.comboServerLogOutput)
    f.row(_tr("Log file"), line_with_button(d.lineServerLogFile, d.cmdServerLogFile, _tr("Browse...")))
    p.add(group(_tr("GUI log"), f))

    f = Form(p)
    f.row(_tr("Largest message from a node"), d.comboGrpcMsgSize)
    f.row(_tr("Worker threads"), compact(d.spinGrpcMaxWorkers),
          _tr("Each connected node uses about two workers; nodes beyond that are not served."))
    f.row(_tr("Connected nodes"), compact(d.spinGrpcMaxClients), _tr("0 means no limit."))
    d.spinGrpcKeepalive.setSuffix(" ms")
    d.spinGrpcKeepaliveTimeout.setSuffix(" ms")
    f.row(_tr("Ping nodes every"), compact(d.spinGrpcKeepalive))
    f.row(_tr("Drop a node that stays silent for"), compact(d.spinGrpcKeepaliveTimeout))
    p.add(group(_tr("Limits"), f))
    p.finish()
    return p


def _page_storage(d):
    p = Page(_tr("Storage"), _tr("Where the events shown in the GUI are kept."))

    f = Form(p)
    f.row(_tr("Keep events"), d.comboDBType,
          _tr("In memory: lost when the GUI closes. File: an SQLite database on disk."))
    d.dbFileButton.setText(_tr("Choose..."))
    d.dbLabel.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
    file_label = f.row(_tr("Database file"), line_with_button(d.dbLabel, d.dbFileButton, _tr("Choose...")))
    d._dbFileFollow = follow(d.dbFileButton, file_label)
    f.check(d.checkDBJrnlWal, _tr("Use write-ahead logging (faster, one more file next to the database)"))
    p.add(group(_tr("Database"), f))

    f = Form(p)
    d.checkDBMaxDays.setText(_tr("Delete events older than"))
    d.labelDBPurgeDays.setText(_tr("days"))
    f.row(d.checkDBMaxDays, compact(d.spinDBMaxDays, d.labelDBPurgeDays))
    d.labelDBPurgeInterval.setText(_tr("Check every"))
    d.labelDBPurgeMinutes.setText(_tr("minutes"))
    f.row(d.labelDBPurgeInterval, compact(d.spinDBPurgeInterval, d.labelDBPurgeMinutes))
    p.add(group(_tr("Retention"), f))
    p.finish()
    return p


# ---------------------------------------------------------------- dialog

def _buttons(d):
    """standard OK / Cancel / Apply order for the platform, help on the left"""
    layout = d.applyButton.parentWidget().layout()
    bar = None
    for i in range(layout.count()):
        item = layout.itemAt(i)
        if item.layout() is not None and item.layout().indexOf(d.applyButton) != -1:
            bar = item.layout()
    if bar is not None:
        while bar.count():
            bar.takeAt(0)
    d.acceptButton.setText(_tr("OK"))
    d.cancelButton.setText(_tr("Cancel"))
    d.applyButton.setText(_tr("Apply"))
    for b in (d.acceptButton, d.cancelButton, d.applyButton):
        b.setIcon(QtGui.QIcon())
    d.helpButton.setText(_tr("Tour"))
    d.helpButton.setToolTip(_tr("Take a guided tour of this settings page"))
    wiki = QtWidgets.QPushButton(QtGui.QIcon.fromTheme("help-contents"), _tr("Wiki"))
    wiki.setObjectName("wikiButton")
    wiki.setToolTip(Config.HELP_URL)
    wiki.clicked.connect(lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(Config.HELP_URL)))
    d.wikiButton = wiki
    for b in (d.acceptButton, d.cancelButton, d.applyButton, d.helpButton, wiki):
        b.setMinimumSize(96, 34)
    box = QtWidgets.QDialogButtonBox()
    box.addButton(d.helpButton, QtWidgets.QDialogButtonBox.ButtonRole.HelpRole)
    box.addButton(wiki, QtWidgets.QDialogButtonBox.ButtonRole.HelpRole)
    box.addButton(d.acceptButton, QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
    box.addButton(d.applyButton, QtWidgets.QDialogButtonBox.ButtonRole.ApplyRole)
    box.addButton(d.cancelButton, QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
    d.acceptButton.setDefault(True)
    if bar is not None:
        bar.addWidget(box)
    d.statusLabel.setStyleSheet("color: palette(placeholder-text); margin-left: 4px;")
    d.statusLabel.setOpenExternalLinks(True)
    d.statusLabel.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
    d.statusLabel.setWordWrap(True)
    d.statusLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)


def build(d):
    holder = QtWidgets.QWidget(d)
    holder.setVisible(False)
    d._design_holder = holder

    pages = d.stackedWidget
    for i in reversed(range(pages.count())):
        w = pages.widget(i)
        pages.removeWidget(w)
        _park(holder, w)
    d.listWidget.clear()

    specs = [
        ("preferences-desktop", _tr("Appearance"), _page_general(d)),
        ("dialog-question", _tr("Authorization alerts"), _page_prompts(d, holder)),
        ("preferences-desktop-notification", _tr("Notifications"), _page_notifications(d, holder)),
        ("view-list-details", _tr("Events"), _page_events(d)),
        ("computer", _tr("Nodes"), _page_nodes(d, holder)),
        ("network-server", _tr("Server"), _page_server(d)),
        ("drive-harddisk", _tr("Storage"), _page_storage(d)),
    ]
    d.listWidget.setIconSize(QtCore.QSize(22, 22))
    d.listWidget.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
    d.listWidget.setSpacing(2)
    d.listWidget.setUniformItemSizes(True)
    d.listWidget.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    d._pages = []
    for icon_name, text, page in specs:
        icon = Icons.new(d, icon_name)
        pages.addWidget(page)
        item = QtWidgets.QListWidgetItem(icon, text, d.listWidget)
        item.setSizeHint(QtCore.QSize(0, 40))
        d._pages.append(page)
    d.listWidget.setCurrentRow(0)
    pages.setCurrentIndex(0)

    _sidebar(d)
    _buttons(d)
    d.splitter.setSizes([200, 720])
    d.splitter.setStretchFactor(0, 0)
    d.splitter.setStretchFactor(1, 1)
    d.splitter.setChildrenCollapsible(False)
    d.splitter.setHandleWidth(6)
    d.splitter.setStyleSheet("QSplitter::handle { background: transparent; }")
    if d.width() < 920:
        d.resize(920, 660)


def _sidebar(d):
    """search box above the category list; Ctrl+F focuses it"""
    column = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(column)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(8)
    search = QtWidgets.QLineEdit()
    search.setObjectName("prefsSearch")
    search.setPlaceholderText(_tr("Search settings"))
    search.setClearButtonEnabled(True)
    search.setFixedHeight(SEARCH_HEIGHT)
    search.addAction(QtGui.QIcon.fromTheme("edit-find"), QtWidgets.QLineEdit.ActionPosition.LeadingPosition)
    search.setToolTip(_tr("Type to show only the settings whose name, help or values contain the text (Ctrl+F)"))
    lay.addWidget(search)
    column.setMinimumWidth(190)
    column.setMaximumWidth(240)
    d.splitter.replaceWidget(d.splitter.indexOf(d.listWidget), column)
    lay.addWidget(d.listWidget, 1)
    d.listWidget.setVisible(True)
    d.searchLine = search
    d._search_snapshot = None
    search.textChanged.connect(lambda text: _apply_search(d, text))
    QtGui.QShortcut(QtGui.QKeySequence.StandardKey.Find, d, activated=lambda: (search.setFocus(), search.selectAll()))


def _apply_search(d, text):
    needle = text.strip().lower()
    if needle and d._search_snapshot is None:
        snap = {}
        for page in d._pages:
            for e in page.entries:
                for w in e.widgets:
                    snap[w] = w.isHidden()
        d._search_snapshot = snap
    snap = d._search_snapshot or {}
    first_hit = None
    for i, page in enumerate(d._pages):
        count = page.filter(needle, snap)
        item = d.listWidget.item(i)
        item.setHidden(needle != "" and count == 0)
        if count and first_hit is None:
            first_hit = i
    if needle == "":
        d._search_snapshot = None
        return
    current = d.stackedWidget.currentIndex()
    if first_hit is not None and d.listWidget.item(current).isHidden():
        d.listWidget.setCurrentRow(first_hit)
        d.stackedWidget.setCurrentIndex(first_hit)
