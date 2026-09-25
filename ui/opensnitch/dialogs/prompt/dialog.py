import threading
import sys
import time
import os
import os.path
import pwd
import json
from datetime import datetime

from PyQt6 import QtCore, QtGui, uic, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC, QEvent

from slugify import slugify

from opensnitch.database.enums import RuleFieldNames
from opensnitch.utils import Icons, logger
from opensnitch.utils.themes import Themes
from opensnitch.desktop_parser import LinuxDesktopParser
from opensnitch.config import Config
from opensnitch.version import version
from opensnitch.actions import Actions
from opensnitch.plugins import PluginBase
from opensnitch.rules import Rules, Rule
from opensnitch.nodes import Nodes

from . import (
    utils,
    constants,
    checksums as check_sums,
    details
)
import opensnitch.proto as proto
ui_pb2, ui_pb2_grpc = proto.import_()

from opensnitch.utils.network_aliases import NetworkAliases

DIALOG_UI_PATH = "%s/../../res/prompt.ui" % os.path.dirname(sys.modules[__name__].__file__)
class PromptDialog(QtWidgets.QDialog, uic.loadUiType(DIALOG_UI_PATH)[0]):
    _prompt_trigger = QtCore.pyqtSignal()
    _tick_trigger = QtCore.pyqtSignal()
    _timeout_trigger = QtCore.pyqtSignal()

    TYPE = "popups"

    def __init__(self, parent=None, appicon=None):
        QtWidgets.QDialog.__init__(self, parent, QtCore.Qt.WindowType.WindowStaysOnTopHint)
        # Other interesting flags: QtCore.Qt.Tool | QtCore.Qt.BypassWindowManagerHint
        self._cfg = Config.get()
        self._rules = Rules.instance()
        self._nodes = Nodes.instance()
        self.logger = logger.get(__name__)

        self.setupUi(self)
        self.setWindowIcon(appicon)
        self.installEventFilter(self)

        self._width = None
        self._height = None

        dialog_geometry = self._cfg.getSettings("promptDialog/geometry")
        if dialog_geometry == QtCore.QByteArray:
            self.restoreGeometry(dialog_geometry)

        self.setWindowTitle("OpenSnitch v%s" % version)

        self._actions = Actions.instance()
        self._action_list = self._actions.getByType(PluginBase.TYPE_POPUPS)
        self._configure_plugins()

        self._lock = threading.Lock()
        self._con = None
        self._rule = None
        self._local = True
        self._peer = None
        self._prompt_trigger.connect(self.on_connection_prompt_triggered)
        self._timeout_trigger.connect(self.on_timeout_triggered)
        self._tick_trigger.connect(self.on_tick_triggered)
        self._tick = int(self._cfg.getSettings(self._cfg.DEFAULT_TIMEOUT_KEY)) if self._cfg.hasKey(self._cfg.DEFAULT_TIMEOUT_KEY) else constants.DEFAULT_TIMEOUT
        self._tick_thread = None
        self._done = threading.Event()
        self._timeout_text = ""
        self._timeout_triggered = False

        self._apps_parser = LinuxDesktopParser()

        self.appDescriptionLabel.setVisible(False)

        self._ischeckAdvanceded = True
        self._ctrl_once_engaged = False
        self._saved_duration_idx = 0
        self._con = None
        self.checkAdvanced.setVisible(False)
        self._rebuild_rule_grid()

        self.checkAdvanced.clicked.connect(self._button_clicked)
        self.durationCombo.activated.connect(self._button_clicked)
        self.whatCombo.activated.connect(self._button_clicked)
        self.whatIPCombo.activated.connect(self._button_clicked)
        self.checkDstIP.clicked.connect(self._button_clicked)
        self.checkDstPort.clicked.connect(self._button_clicked)
        self.checkUserID.clicked.connect(self._button_clicked)
        self.cmdInfo.clicked.connect(self._cb_cmdinfo_clicked)
        self.cmdBack.clicked.connect(self._cb_cmdback_clicked)

        self.cmdUpdateRule.clicked.connect(lambda: self._cb_update_rule_clicked(updateAll=False))
        self.cmdUpdateRuleAll.clicked.connect(lambda: self._cb_update_rule_clicked(updateAll=True))
        self.cmdBackChecksums.clicked.connect(self._cb_cmdback_clicked)
        self.messageLabel.linkActivated.connect(self._cb_warninglbl_clicked)

        self.dstIPLblCheck.mousePressEvent = lambda x: self._cb_label_clicked(constants.DSTIP_LBL_CLICKED)
        self.dstPortLblCheck.mousePressEvent = lambda x: self._cb_label_clicked(constants.DSTPORT_LBL_CLICKED)
        self.userLblCheck.mousePressEvent = lambda x: self._cb_label_clicked(constants.USER_LBL_CLICKED)
        self.checksumLblCheck.mousePressEvent = lambda x: self._cb_label_clicked(constants.CHECKSUM_LBL_CLICKED)

        self.allowIcon = Icons.new(self, "emblem-default")
        denyIcon = Icons.new(self, "emblem-important")
        rejectIcon = Icons.new(self, "window-close")
        backIcon = Icons.new(self, "go-previous")
        infoIcon = Icons.new(self, "dialog-information")

        self.cmdInfo.setIcon(infoIcon)
        self.cmdBack.setIcon(backIcon)
        self.cmdBackChecksums.setIcon(backIcon)

        self._default_action = self._cfg.getInt(self._cfg.DEFAULT_ACTION_KEY)

        self.allowButton.clicked.connect(lambda: self._on_action_clicked(Config.ACTION_ALLOW_IDX))
        self.allowButton.setIcon(self.allowIcon)
        self.allowButton.setToolTip("Allow (Enter)")
        self._allow_text = QC.translate("popups", "Allow")
        self._action_text = [
            QC.translate("popups", "Drop"),
            QC.translate("popups", "Allow"),
            QC.translate("popups", "Reject")
        ]
        self._action_icon = [denyIcon, self.allowIcon, rejectIcon]

        self.actionButton.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.DelayedPopup)
        self.actionButton.setMenu(None)
        self.actionButton.setText(self._action_text[Config.ACTION_DROP_IDX])
        self.actionButton.setIcon(self._action_icon[Config.ACTION_DROP_IDX])
        if self._default_action != Config.ACTION_ALLOW_IDX:
            self.actionButton.setText(self._action_text[self._default_action])
            self.actionButton.setIcon(self._action_icon[self._default_action])
        self.actionButton.clicked.connect(self._on_deny_btn_clicked)
        self.actionButton.setToolTip("Drop (Esc)")
        self.durationCombo.setToolTip("Duration (Ctrl+Tab to cycle)")

        bar = self.horizontalLayout
        while bar.count():
            item = bar.takeAt(0)
            w = item.widget()
            if w and w not in (self.actionButton, self.allowButton):
                w.setParent(None)
        bar.addWidget(self.actionButton, 1)
        bar.addWidget(self.allowButton, 1)
        self.actionButton.setMinimumHeight(32)
        self.allowButton.setMinimumHeight(32)
        self.actionButton.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.actionButton.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)

        # One stylesheet for the whole dialog; Qt applies it to children created
        # after this call too, so widget setup below only tags a promptRole.
        self.setStyleSheet(Themes.prompt_stylesheet())

        self._preview_label = QtWidgets.QLabel(self)
        self._preview_label.setWordWrap(True)
        self._preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setProperty("promptRole", "preview")
        self._preview_label.setProperty("once", "false")
        layout = self.stackedWidget.widget(constants.PAGE_MAIN).layout()
        if layout is not None:
            layout.addWidget(self._preview_label)

        self.whatCombo.activated.connect(self._update_preview)
        self.durationCombo.activated.connect(self._update_preview)
        self.checkDstPort.toggled.connect(lambda _: self._update_preview())
        self.checkUserID.toggled.connect(lambda _: self._update_preview())

    def _update_preview(self, _idx=None):
        if self._con is None:
            self._preview_label.setText("")
            return

        action = self._action_text[self._default_action]
        app_name = os.path.basename(self._con.process_path) or "this process"
        duration_text = self.durationCombo.currentText()

        # Build user-friendly constraint descriptions
        dest_parts = []
        if self.checkDstHost.isChecked():
            host_val = self.hostCombo.currentText() if self.hostCombo.isVisible() else self._con.dst_host
            dest_parts.append('<b>%s</b>' % host_val)
        elif self.checkDstIP.isChecked():
            dest_parts.append('<b>%s</b>' % self._con.dst_ip)
        if self.checkDstPort.isChecked():
            dest_parts.append('port <b>%s</b>' % self._con.dst_port)
        if self.checkProtocol.isChecked():
            proto_val = self.protocolCombo.currentText() if self.protocolCombo.isVisible() else self._con.protocol
            dest_parts.append('via <b>%s</b>' % proto_val.upper())

        source_parts = []
        if self.checkCmdline.isChecked():
            source_parts.append('from <b>%s</b>' % utils.collapse_nix_hash(self._con.process_path))
        if self.checkArgs.isChecked():
            args = ' '.join(self._con.process_args[1:]) if len(self._con.process_args) > 1 else ""
            if args:
                source_parts.append('when arguments match <b>%s</b>' % args)
        if self.checkUserID.isChecked():
            uid_text = self.uidLabel.text() or str(self._con.user_id)
            source_parts.append('from user <b>%s</b>' % uid_text)
        if self.checkPID.isChecked():
            source_parts.append('from PID <b>%s</b>' % self._con.process_id)

        deny_text = self._action_text[Config.ACTION_REJECT_IDX] if self.checkReject.isChecked() else self._action_text[Config.ACTION_DROP_IDX]
        action_pair = 'Allow/%s' % deny_text

        if self._ctrl_once_engaged or not self.checkSaveRule.isChecked():
            self._preview_label.setText(
                '%s this one connection from <b>%s</b> -- no rule saved' % (action_pair, app_name)
            )
            return

        sentence = '%s connections from <b>%s</b>' % (action_pair, app_name)
        if dest_parts:
            sentence += ' to %s' % ', '.join(dest_parts)
        if source_parts:
            sentence += ' %s' % ', '.join(source_parts)
        sentence += ' <b>%s</b>' % duration_text

        self._preview_label.setText(sentence)

    def _rebuild_rule_grid(self):
        """Replace the flat details grid with a symmetric 3-column rule builder.

        Layout per row:
            from-value  |  ☐left  LABEL  ☐right  |  to-value
        Checkboxes on the side that makes sense:
            IP   -- right (destination)
            PORT -- right (destination)
            USER -- left  (source)
            HASH -- left  (source)
        """
        old_layout = self.gridLayout_2
        page = old_layout.parentWidget()

        while old_layout.count():
            item = old_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        QtWidgets.QWidget().setLayout(old_layout)

        ROW_HEIGHT = 26

        grid = QtWidgets.QGridLayout()
        grid.setContentsMargins(8, 6, 8, 2)
        grid.setVerticalSpacing(4)
        grid.setHorizontalSpacing(4)

        # Columns: 0=from-value  1=☐left  2=label  3=☐right  4=to-value
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 0)
        grid.setColumnStretch(4, 3)

        # Style via the promptRole property, never setObjectName: _left/_right
        # are handed widgets that came from res/prompt.ui, whose object names
        # are used elsewhere and must survive.
        def _left(w):
            w.setProperty("promptRole", "value")
            w.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
            return w

        def _right(w):
            w.setProperty("promptRole", "value")
            w.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
            return w

        def _center(text):
            lbl = QtWidgets.QLabel(text)
            lbl.setProperty("promptRole", "header")
            # Qt Style Sheets support neither text-transform nor letter-spacing,
            # so the header's small-caps look has to come from the font. It was
            # declared in QSS before and silently ignored.
            font = lbl.font()
            font.setCapitalization(QtGui.QFont.Capitalization.AllUppercase)
            font.setLetterSpacing(QtGui.QFont.SpacingType.AbsoluteSpacing, 2)
            lbl.setFont(font)
            lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            return lbl

        def _dash(align_right=True):
            d = QtWidgets.QLabel("--")
            d.setProperty("promptRole", "dash")
            flag = QtCore.Qt.AlignmentFlag.AlignRight if align_right else QtCore.Qt.AlignmentFlag.AlignLeft
            d.setAlignment(flag | QtCore.Qt.AlignmentFlag.AlignVCenter)
            return d

        def _row_right_check(label_text, check_widget, left_widget, right_widget):
            nonlocal row
            grid.setRowMinimumHeight(row, ROW_HEIGHT)
            grid.addWidget(left_widget, row, 0)
            grid.addWidget(QtWidgets.QWidget(), row, 1)
            grid.addWidget(_center(label_text), row, 2)
            grid.addWidget(check_widget, row, 3)
            grid.addWidget(right_widget, row, 4)
            row += 1

        def _row_left_check(label_text, check_widget, left_widget, right_widget):
            nonlocal row
            grid.setRowMinimumHeight(row, ROW_HEIGHT)
            grid.addWidget(left_widget, row, 0)
            grid.addWidget(check_widget, row, 1)
            grid.addWidget(_center(label_text), row, 2)
            grid.addWidget(QtWidgets.QWidget(), row, 3)
            grid.addWidget(right_widget, row, 4)
            row += 1

        def _row_no_check(label_text, left_widget, right_widget=None):
            nonlocal row
            grid.setRowMinimumHeight(row, ROW_HEIGHT)
            grid.addWidget(left_widget, row, 0)
            grid.addWidget(QtWidgets.QWidget(), row, 1)
            grid.addWidget(_center(label_text), row, 2)
            grid.addWidget(QtWidgets.QWidget(), row, 3)
            grid.addWidget(right_widget or QtWidgets.QWidget(), row, 4)
            row += 1

        row = 0

        # Hide the old whatCombo -- CMD/ARGS checkboxes replace it
        self.whatCombo.setVisible(False)

        # -- CMD: command path ☐ | CMD | ☐ arguments --
        self.checkCmdline = QtWidgets.QCheckBox()
        self.checkArgs = QtWidgets.QCheckBox()
        self.cmdLabel = QtWidgets.QLabel("")
        self.argsGridLabel = QtWidgets.QLabel("")
        self.argsGridLabel.setWordWrap(True)

        grid.setRowMinimumHeight(row, ROW_HEIGHT)
        grid.addWidget(_left(self.cmdLabel), row, 0)
        grid.addWidget(self.checkCmdline, row, 1)
        grid.addWidget(_center("COMMAND"), row, 2)
        grid.addWidget(self.checkArgs, row, 3)
        grid.addWidget(_right(self.argsGridLabel), row, 4)
        row += 1

        self.checkCmdline.toggled.connect(lambda _: self._update_preview())
        self.checkArgs.toggled.connect(lambda _: self._update_preview())

        # -- PID: pid value | ☐ PID | -- --
        self.checkPID = QtWidgets.QCheckBox()
        self.pidLabel = QtWidgets.QLabel("")
        _row_left_check("PROCESS", self.checkPID, _left(self.pidLabel), _dash(False))
        self.checkPID.toggled.connect(lambda _: self._update_preview())

        # -- HASH: checksum-value | ☐ HASH | -- --
        self.checksumLabel.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse | QtCore.Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.checksumLblCheck.setVisible(False)
        self._hashRowIdx = row
        _row_left_check("HASH", self.checkSum, _left(self.checksumLabel), _dash(False))

        # -- HOST: -- | HOST ☐ | hostname combo --
        self.checkDstHost = QtWidgets.QCheckBox()
        self.dstHostLabel = QtWidgets.QLabel("")
        self.hostCombo = QtWidgets.QComboBox()
        self.hostCombo.setVisible(False)

        host_right = QtWidgets.QWidget()
        host_right_layout = QtWidgets.QHBoxLayout(host_right)
        host_right_layout.setContentsMargins(0, 0, 0, 0)
        host_right_layout.setSpacing(0)
        host_right_layout.addWidget(_right(self.dstHostLabel))
        host_right_layout.addWidget(self.hostCombo)

        _row_right_check("HOST", self.checkDstHost, _dash(), host_right)
        self.checkDstHost.toggled.connect(self._on_host_check_toggled)

        # -- IP: sourceIP | IP ☐ | destIP combo --
        self.ipCombo = QtWidgets.QComboBox()
        self.ipCombo.setVisible(False)

        ip_right = QtWidgets.QWidget()
        ip_right_layout = QtWidgets.QHBoxLayout(ip_right)
        ip_right_layout.setContentsMargins(0, 0, 0, 0)
        ip_right_layout.setSpacing(0)
        ip_right_layout.addWidget(_right(self.destIPLabel))
        ip_right_layout.addWidget(self.ipCombo)

        _row_right_check("IP", self.checkDstIP, _left(self.sourceIPLabel), ip_right)
        self.checkDstIP.toggled.connect(self._on_ip_check_toggled)
        self.whatIPCombo.setVisible(False)
        self.dstIPLblCheck.setVisible(False)

        # Mutual exclusion: HOST <-> IP
        self.checkDstHost.toggled.connect(self._on_host_toggled)
        self.checkDstIP.toggled.connect(self._on_ip_toggled)

        # -- PORT: -- | PORT ☐ | port-value --
        _row_right_check("PORT", self.checkDstPort, _dash(), _right(self.destPortLabel))
        self.dstPortLblCheck.setVisible(False)

        # -- PROTO: -- | PROTO ☐ | protocol combo --
        self.checkProtocol = QtWidgets.QCheckBox()
        self.protocolCombo = QtWidgets.QComboBox()
        self.protocolCombo.addItems(["tcp", "udp", "tcp6", "udp6", "udplite", "udplite6", "icmp", "icmp6", "sctp", "sctp6"])
        self.protocolCombo.setVisible(False)
        self.protocolLabel = QtWidgets.QLabel("")

        proto_right = QtWidgets.QWidget()
        proto_right_layout = QtWidgets.QHBoxLayout(proto_right)
        proto_right_layout.setContentsMargins(0, 0, 0, 0)
        proto_right_layout.setSpacing(0)
        proto_right_layout.addWidget(_right(self.protocolLabel))
        proto_right_layout.addWidget(self.protocolCombo)

        _row_right_check("PROTO", self.checkProtocol, _dash(), proto_right)
        self.checkProtocol.toggled.connect(self._on_proto_check_toggled)

        # -- USER: uid-value | ☐ USER | -- --
        _row_left_check("USER", self.checkUserID, _left(self.uidLabel), _dash(False))
        self.userLblCheck.setVisible(False)

        # -- WORK DIR: cwd-value | WORK DIR | -- --
        _row_no_check("FROM DIR", _left(self.cwdLabel))
        self.label_2.setVisible(False)

        # -- BEHAVIOR: ☐ Drop | DENY | Reject ☐ --
        self.checkDrop = QtWidgets.QCheckBox()
        self.checkReject = QtWidgets.QCheckBox()
        self._dropLabel = QtWidgets.QLabel("Drop")
        self._rejectLabel = QtWidgets.QLabel("Reject")
        _left(self._dropLabel)
        _right(self._rejectLabel)

        grid.setRowMinimumHeight(row, ROW_HEIGHT)
        grid.addWidget(self._dropLabel, row, 0)
        grid.addWidget(self.checkDrop, row, 1)
        grid.addWidget(_center("ACTION"), row, 2)
        grid.addWidget(self.checkReject, row, 3)
        grid.addWidget(self._rejectLabel, row, 4)
        row += 1

        self.checkDrop.setChecked(True)
        self.checkDrop.toggled.connect(lambda c: self._on_deny_mode_toggled(c, self.checkDrop, self.checkReject, Config.ACTION_DROP_IDX))
        self.checkReject.toggled.connect(lambda c: self._on_deny_mode_toggled(c, self.checkReject, self.checkDrop, Config.ACTION_REJECT_IDX))

        # -- RULE: ☐ RULE | duration combo or "once (no rule)" --
        self.checkSaveRule = QtWidgets.QCheckBox()
        self.checkSaveRule.setChecked(True)
        self.checkSaveRule.setToolTip("Uncheck to allow/deny once without saving a rule")
        self._ruleOnceLabel = QtWidgets.QLabel("once (no rule)")
        self._ruleOnceLabel.setProperty("promptRole", "once")
        self._ruleOnceLabel.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self._ruleOnceLabel.setVisible(False)

        rule_right = QtWidgets.QWidget()
        rule_right_layout = QtWidgets.QHBoxLayout(rule_right)
        rule_right_layout.setContentsMargins(0, 0, 0, 0)
        rule_right_layout.setSpacing(0)
        self.durationCombo.setParent(None)
        rule_right_layout.addWidget(self.durationCombo)
        rule_right_layout.addWidget(self._ruleOnceLabel)

        _row_right_check("ADD RULE", self.checkSaveRule, QtWidgets.QWidget(), rule_right)
        self.checkSaveRule.toggled.connect(self._on_save_rule_toggled)

        self._ruleGrid = grid

        page_layout = page.layout()
        if page_layout:
            page_layout.addLayout(grid, page_layout.rowCount(), 0)
        else:
            new_layout = QtWidgets.QVBoxLayout(page)
            new_layout.addLayout(grid)

    _DURATION_LABELS = {
        "once": "once",
        "30s": "for 30 seconds",
        "5m": "for 5 minutes",
        "15m": "for 15 minutes",
        "30m": "for 30 minutes",
        "1h": "for 1 hour",
        "12h": "for 12 hours",
        "until reboot": "until reboot",
        "forever": "forever",
    }

    def _rewrite_duration_labels(self):
        for i in range(self.durationCombo.count()):
            raw = self.durationCombo.itemText(i)
            friendly = self._DURATION_LABELS.get(raw, raw)
            if friendly != raw:
                self.durationCombo.setItemText(i, friendly)

    def _on_deny_mode_toggled(self, checked, own_check, other_check, action_idx):
        if checked and other_check.isChecked():
            other_check.blockSignals(True)
            other_check.setChecked(False)
            other_check.blockSignals(False)
        if not checked and not other_check.isChecked():
            own_check.setChecked(True)
            return
        if checked:
            self._default_action = action_idx
            self.actionButton.setText(self._action_text[action_idx])
            self.actionButton.setIcon(self._action_icon[action_idx])
        self._update_preview()

    def _on_save_rule_toggled(self, checked):
        self.durationCombo.setVisible(checked)
        self._ruleOnceLabel.setVisible(not checked)
        self._update_preview()

    def _on_host_check_toggled(self, checked):
        self.dstHostLabel.setVisible(not checked)
        self.hostCombo.setVisible(checked)

    def _on_ip_check_toggled(self, checked):
        self.destIPLabel.setVisible(not checked)
        self.ipCombo.setVisible(checked)

    def _on_proto_check_toggled(self, checked):
        self.protocolLabel.setVisible(not checked)
        self.protocolCombo.setVisible(checked)
        self._update_preview()

    def _on_host_toggled(self, checked):
        if checked and self.checkDstIP.isChecked():
            self.checkDstIP.blockSignals(True)
            self.checkDstIP.setChecked(False)
            self.checkDstIP.blockSignals(False)
        self._update_preview()

    def _on_ip_toggled(self, checked):
        if checked and self.checkDstHost.isChecked():
            self.checkDstHost.blockSignals(True)
            self.checkDstHost.setChecked(False)
            self.checkDstHost.blockSignals(False)
        self._update_preview()

    def _cb_label_clicked(self, what):
        if what == constants.DSTIP_LBL_CLICKED:
            self.checkDstIP.toggle()
        elif what == constants.DSTPORT_LBL_CLICKED:
            self.checkDstPort.toggle()
        elif what == constants.USER_LBL_CLICKED:
            self.checkUserID.toggle()
        elif what == constants.CHECKSUM_LBL_CLICKED:
            self.checkSum.toggle()

    def _configure_plugins(self):
        """configure the plugins that apply to this dialog.
        When configuring the plugins on a particular view, they'll add,
        change or extend the existing functionality.
        """
        for conf in self._action_list:
            action = self._action_list[conf]
            for name in action['actions']:
                try:
                    action['actions'][name].configure(self)
                except Exception as e:
                    self.logger.warning("popups._configure_plugins() exception: %s, you may want to enable this plugin -", name, repr(e))

    def _pre_popup_plugins(self, con):
        pass

    def _post_popup_plugins(self, conn):
        """Actions performed on the pop-up once the connection details have
        been displayed on the screen.
        """
        if self._action_list is None:
            return

        for conf in self._action_list:
            action = self._action_list[conf]
            for name in action['actions']:
                try:
                    action['actions'][name].run(self, (conn,))
                except Exception as e:
                    self.logger.debug("popups._post_popup_plugins() exception: %s - %s", name, repr(e))

    def get_main_widget(self):
        """returns the central widget of the pop-up"""
        return self.stackedWidget

    def get_connection(self):
        """returns the current connection that is awaiting approval"""
        return self._con

    def get_peer(self):
        """returns the address and hostname of the node"""
        return self._peer, self._hostname

    def get_message_text(self):
        return self.messageLabel.text()

    def set_app_name(self, text):
        self.appNameLabel.setText(text)

    def set_app_description(self, text):
        self.appDescriptionLabel.setText(text)

    def set_app_path(self, text):
        self.appPathLabel.setText(text)

    def set_app_args(self, text):
        self.argsLabel.setText(text)

    def set_message_text(self, text):
        self.messageLabel.setText(text)
        self.messageLabel.setToolTip(text)

    def set_message_style(self, style):
        self.messageLabel.setStyleSheet(style)

    def set_icon_pixmap(self, pixmap):
        """set the icon of the popup"""
        self.iconLabel.setPixmap(pixmap)

    def set_default_action(self, action):
        self._default_action = action

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress:
            self.stop_countdown()
            return True
        return False

    def showEvent(self, event):
        super(PromptDialog, self).showEvent(event)
        self.activateWindow()
        self.adjust_size()
        self.move_popup()

    def adjust_size(self):
        if self._width is None or self._height is None:
            self._width = self.width()
            self._height = self.height()

        self.resize(QtCore.QSize(self._width, self._height))

    def move_popup(self):
        popup_pos = self._cfg.getInt(self._cfg.DEFAULT_POPUP_POSITION)
        screen = self.screen().virtualSiblingAt(QtGui.QCursor.pos())
        if not screen:
            return
        point = screen.availableGeometry()
        if popup_pos == self._cfg.POPUP_TOP_RIGHT:
            self.move(point.topRight())
        elif popup_pos == self._cfg.POPUP_TOP_LEFT:
            self.move(point.topLeft())
        elif popup_pos == self._cfg.POPUP_BOTTOM_RIGHT:
            self.move(point.bottomRight())
        elif popup_pos == self._cfg.POPUP_BOTTOM_LEFT:
            self.move(point.bottomLeft())

    def stop_countdown(self):
        action_idx = self._cfg.getInt(self._cfg.DEFAULT_ACTION_KEY)
        if action_idx == Config.ACTION_ALLOW_IDX:
            self.allowButton.setText(self._allow_text)
            self.allowButton.setIcon(self.allowIcon)
        else:
            self.actionButton.setText(self._action_text[action_idx])
            self.actionButton.setIcon(self._action_icon[action_idx])
        if self._tick_thread is not None:
            self._tick_thread.stop = True

    def _check_advanced_toggled(self, state):
        self.checkDstIP.setVisible(state)
        self.whatIPCombo.setVisible(state)
        self.destIPLabel.setVisible(not state)
        self.checkDstPort.setVisible(state == True and (self._con is not None and self._con.dst_port != 0))
        self.checkProtocol.setVisible(state)
        self.checkUserID.setVisible(state)
        self.checkSum.setVisible(self._con.process_checksums[Config.OPERAND_PROCESS_HASH_MD5] != "" and state)
        self.checksumLblCheck.setVisible(self._con.process_checksums[Config.OPERAND_PROCESS_HASH_MD5] != "" and state)
        self.checksumLabel.setVisible(self._con.process_checksums[Config.OPERAND_PROCESS_HASH_MD5] != "" and state)
        self.stackedWidget.setCurrentIndex(constants.PAGE_MAIN)

        self._ischeckAdvanceded = state
        self.adjust_size()
        self.move_popup()

    def _button_clicked(self):
        self.stop_countdown()

    def _cb_warninglbl_clicked(self, link):
        self.stop_countdown()
        if link == constants.WARNING_LABEL:
            self.stackedWidget.setCurrentIndex(constants.PAGE_CHECKSUMS)

    def _cb_cmdinfo_clicked(self):
        self.stackedWidget.setCurrentIndex(constants.PAGE_DETAILS)
        self.stop_countdown()

    def _cb_update_rule_clicked(self, updateAll=False):
        self.labelChecksumStatus.setStyleSheet('')
        curRule = self.comboChecksumRule.currentText()
        if curRule == "":
            return

        for idx in range(0, self.comboChecksumRule.count()):
            comboRule = self.comboChecksumRule.itemText(idx)

            if not updateAll and comboRule != curRule:
                continue

            rule, error = check_sums.update_rule(self._peer, self._rules, comboRule, self._con)
            if rule is None:
                self.labelChecksumStatus.setStyleSheet('color: %s' % Themes.error_color())
                self.labelChecksumStatus.setText("✘ " + error)
                return

            self._nodes.send_notification(
                self._peer,
                ui_pb2.Notification(
                    id=int(str(time.time()).replace(".", "")),
                    type=ui_pb2.CHANGE_RULE,
                    data="",
                    rules=[rule]
                )
            )
            self.labelChecksumStatus.setStyleSheet('color: %s' % Themes.ok_color())
            self.labelChecksumStatus.setText("✔" + QC.translate("popups", "Rule updated."))

    def _cb_cmdback_clicked(self):
        self.stackedWidget.setCurrentIndex(constants.PAGE_MAIN)
        self.stop_countdown()

    def promptUser(self, connection, is_local, peer):
        # one at a time
        with self._lock:
            # reset state
            if self._tick_thread is not None and self._tick_thread.is_alive():
                self._tick_thread.join()
            self._cfg.reload()
            self._tick = int(self._cfg.getSettings(self._cfg.DEFAULT_TIMEOUT_KEY)) if self._cfg.hasKey(self._cfg.DEFAULT_TIMEOUT_KEY) else constants.DEFAULT_TIMEOUT
            self._tick_thread = threading.Thread(target=self._timeout_worker)
            self._tick_thread.stop = self._ischeckAdvanceded
            self._timeout_triggered = False
            self._rule = None
            self._local = is_local
            self._con = connection

            # XXX: workaround for protobufs that don't report the address of
            # the node. In this case the addr is "unix:/local"
            proto, addr = self._nodes.get_addr(peer)
            self._hostname = self._nodes.get_node_hostname("%s:%s" % (proto, addr))
            self._peer = proto
            if addr is not None:
                self._peer = proto+":"+addr

            self._done.clear()
            # trigger and show dialog
            self._prompt_trigger.emit()
            # start timeout thread
            self._tick_thread.start()
            # wait for user choice or timeout
            self._done.wait()

            return self._rule, self._timeout_triggered

    def _timeout_worker(self):
        if self._tick == 0:
            self._timeout_trigger.emit()
            return
        if self._tick < 0:
            # no countdown: the prompt waits for the user
            return

        while self._tick > 0 and self._done.is_set() is False:
            t = threading.currentThread()
            # stop only stops the coundtdown, not the thread itself.
            if getattr(t, "stop", True):
                self._tick = int(self._cfg.getSettings(self._cfg.DEFAULT_TIMEOUT_KEY))
                time.sleep(1)
                continue

            self._tick -= 1
            self._tick_trigger.emit()
            time.sleep(1)

        if not self._done.is_set():
            self._timeout_trigger.emit()

    @QtCore.pyqtSlot()
    def on_connection_prompt_triggered(self):
        self.stackedWidget.setCurrentIndex(constants.PAGE_MAIN)
        self.reset_widgets()
        self._render_connection(self._con)
        if self._tick != 0:
            self.show()
        # render details after displaying the pop-up.

        self._display_checksums_warning(self._peer, self._con)
        details.render(self._peer, self.connDetails, self._con)
        self._update_preview()

    @QtCore.pyqtSlot()
    def on_tick_triggered(self):
        self._set_cmd_action_text()

    @QtCore.pyqtSlot()
    def on_timeout_triggered(self):
        self._timeout_triggered = True
        self._send_rule()

    def reset_widgets(self):
        self.appNameLabel.setText("")
        self.appPathLabel.setText("")
        self.argsLabel.setText("")
        self.appDescriptionLabel.setText("")
        self.messageLabel.setText("")
        self.cwdLabel.setText("")
        self.sourceIPLabel.setText("")
        self.destIPLabel.setText("")
        self.destPortLabel.setText("")
        self.protocolLabel.setText("")
        self.uidLabel.setText("")
        self.checksumLabel.setText("")
        self.labelChecksumStatus.setText("")

    def _hide_widget(self, widget, hide):
        widget.setVisible(not hide)

    def _set_cmd_action_text(self):
        action_idx = self._cfg.getInt(self._cfg.DEFAULT_ACTION_KEY)
        countdown = " ({0}s)".format(self._tick) if self._tick > 0 else ""
        if action_idx == Config.ACTION_ALLOW_IDX:
            self.allowButton.setText(self._allow_text + countdown)
            self.allowButton.setIcon(self.allowIcon)
            self.actionButton.setText(self._action_text[Config.ACTION_DROP_IDX])
        else:
            self.allowButton.setText(self._allow_text)
            self.actionButton.setText(self._action_text[action_idx] + countdown)
            self.actionButton.setIcon(self._action_icon[action_idx])

    def _display_checksums_warning(self, peer, con):
        self.set_message_style('')
        self.labelChecksumStatus.setText('')
        is_valid = True
        checksums = con.process_checksums
        expected_list = []

        records = self._rules.get_by_field(peer, RuleFieldNames.OpData, con.process_path, RuleFieldNames.Time)

        if records is not None and records.first():
            rules_names = []
            while True:
                if not records.next():
                    break
                rule = Rule.new_from_records(records)

                if not rule.enabled:
                    continue
                if rule.duration == Config.DURATION_ONCE:
                    continue

                rules_names.append(rule.name)
                validates, expected = check_sums.verify(checksums, rule)
                if not validates:
                    expected_list.append(expected)
                is_valid &= validates

            if is_valid:
                return ""

            self.set_message_style('color: red')
            self.set_message_text(
                QC.translate("popups", "WARNING, bad checksum (<a href='#warning-checksum'>More info</a>)"
                                )
            )
            self.labelChecksumNote.setText(
                QC.translate(
                    "popups",
                    "<font color=\"red\">WARNING, checksums differ for at least one rule.</font><br><br>Current process ({0}):<br>{1}<br><br>Expected from the rule:<br>{2}"
                    .format(
                        con.process_id,
                        checksums[Config.OPERAND_PROCESS_HASH_MD5],
                        expected_list
                    ))
            )

            self.comboChecksumRule.clear()
            self.comboChecksumRule.addItems(rules_names)

            return "<b>WARNING</b><br>bad md5<br>This process:{0}<br>Expected from rule: {1}<br><br>".format(
                checksums[Config.OPERAND_PROCESS_HASH_MD5],
                expected
            )

        return ""

    def _render_connection(self, con):
        app_name, app_icon, description, _ = self._apps_parser.get_info_by_path(con.process_path, "terminal")
        app_args = " ".join(con.process_args)
        utils.set_app_description(self.appDescriptionLabel, description)
        utils.set_app_path(self.appPathLabel, app_name, app_args, con)
        utils.set_app_args(self.argsLabel, app_name, app_args)

        self.checksumLabel.setText(con.process_checksums[Config.OPERAND_PROCESS_HASH_MD5])
        self.checkSum.setChecked(False)

        if app_name == "":
            self.appPathLabel.setVisible(False)
            self.argsLabel.setVisible(False)
            self.argsLabel.setText("")
            app_name = QC.translate("popups", "Unknown process %s" % con.process_path)
            #with self._lock:
            self.set_app_name(QC.translate("popups", "Outgoing connection"))
        else:
            utils.set_elide_text(self.appNameLabel, "%s" % app_name, max_size=42)
            self.appNameLabel.setToolTip(app_name)

        #if len(self._con.process_args) == 0 or self._con.process_args[0] == "":

        self.cwdLabel.setToolTip("%s %s" % (QC.translate("popups", "Process launched from:"), con.process_cwd))
        utils.set_elide_text(self.cwdLabel, con.process_cwd, max_size=32)

        pixmap = Icons.get_by_appname(app_icon)
        self.set_icon_pixmap(pixmap)

        message = utils.get_popup_message(self._local, self._peer, self._hostname, app_name, con)

        self.set_message_text(message)

        self.sourceIPLabel.setText(con.src_ip)
        self.destIPLabel.setText(con.dst_ip)
        has_host = con.dst_host != "" and con.dst_host != con.dst_ip
        self.dstHostLabel.setText(con.dst_host if has_host else "")
        self._hide_widget(self.checkDstHost, not has_host)
        self._hide_widget(self.dstHostLabel, not has_host)
        self.hostCombo.clear()
        if has_host:
            self.hostCombo.addItem(con.dst_host)
            parts = con.dst_host.split('.')
            for i in range(1, len(parts) - 1):
                self.hostCombo.addItem("*.%s" % '.'.join(parts[i:]))
        self.hostCombo.setVisible(False)

        self.ipCombo.clear()
        self.ipCombo.addItem(con.dst_ip)
        parts = con.dst_ip.split('.')
        if len(parts) == 4:
            import ipaddress
            for i in range(1, len(parts)):
                self.ipCombo.addItem("%s.*" % '.'.join(parts[:i]))
            for cidr in [24, 16, 8]:
                net = str(ipaddress.ip_network(con.dst_ip + "/%d" % cidr, strict=False))
                self.ipCombo.addItem(net)
            alias = NetworkAliases.get_alias(con.dst_ip)
            if alias:
                self.ipCombo.addItem(alias)
        self.ipCombo.setVisible(False)

        if con.dst_port == 0:
            self.destPortLabel.setText("")
        else:
            self.destPortLabel.setText(str(con.dst_port))
        self._hide_widget(self.destPortLabel, con.dst_port == 0)

        self.protocolLabel.setText(con.protocol)
        idx = self.protocolCombo.findText(con.protocol, QtCore.Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            self.protocolCombo.setCurrentIndex(idx)
        self.protocolCombo.setVisible(False)
        self.checkProtocol.setChecked(False)
        no_hash = con.process_checksums[Config.OPERAND_PROCESS_HASH_MD5] == ""
        for col in range(5):
            item = self._ruleGrid.itemAtPosition(self._hashRowIdx, col)
            if item and item.widget():
                item.widget().setVisible(not no_hash)
        self.checksumLabel.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse | QtCore.Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self._hide_widget(self.checkDstPort, con.dst_port == 0)

        if self._local:
            try:
                uid = "{0} ({1})".format(con.user_id, pwd.getpwuid(con.user_id).pw_name)
            except:
                uid = ""
        else:
            uid = "{0}".format(con.user_id)

        self.uidLabel.setText(uid)

        self.whatCombo.clear()
        self.whatIPCombo.clear()

        utils.add_fixed_options_to_combo(self.whatCombo, con, uid)
        if con.process_path.startswith(constants.APPIMAGE_PREFIX):
            utils.add_appimage_pattern_to_combo(self.whatCombo, con)
        elif con.process_path.startswith(constants.SNAP_PREFIX):
            utils.add_snap_pattern_to_combo(self.whatCombo, con)
        utils.add_dst_networks_to_combo(self.whatCombo, con.dst_ip)

        if con.dst_host != "" and con.dst_host != con.dst_ip:
            utils.add_dsthost_to_combo(self, con.dst_host)

        utils.add_ip_regexp_to_combo(self.whatCombo, self.whatIPCombo, con)
        utils.add_dst_networks_to_combo(self.whatIPCombo, con.dst_ip)

        self._default_action = self._cfg.getInt(self._cfg.DEFAULT_ACTION_KEY)
        is_reject = self._default_action == Config.ACTION_REJECT_IDX
        self.checkDrop.setChecked(not is_reject)
        self.checkReject.setChecked(is_reject)
        utils.set_default_duration(self._cfg, self.durationCombo)
        self._rewrite_duration_labels()

        utils.set_default_target(self.whatCombo, con, self._cfg, app_name, app_args)

        if len(con.process_args) > 0:
            cmd_path = con.process_args[0]
            cmd_args = ' '.join(con.process_args[1:])
        else:
            cmd_path = ""
            cmd_args = ""
        self.cmdLabel.setText(utils.truncate_text(utils.collapse_nix_hash(cmd_path), 40))
        self.cmdLabel.setToolTip(cmd_path)
        self.argsGridLabel.setText(utils.truncate_text(cmd_args, 50) if cmd_args else "--")
        self.argsGridLabel.setToolTip(cmd_args)
        self._hide_widget(self.cmdLabel, cmd_path == "")
        self._hide_widget(self.checkCmdline, cmd_path == "")
        self._hide_widget(self.argsGridLabel, cmd_args == "")
        self._hide_widget(self.checkArgs, cmd_args == "")

        self.pidLabel.setText(str(con.process_id))
        self._hide_widget(self.pidLabel, int(con.process_id) <= 0)
        self._hide_widget(self.checkPID, int(con.process_id) <= 0)

        save_rule = self._cfg.getBool(self._cfg.DEFAULT_POPUP_SAVE_RULE) if self._cfg.hasKey(self._cfg.DEFAULT_POPUP_SAVE_RULE) else True
        self.checkSaveRule.setChecked(save_rule)

        self.checkDstIP.setChecked(self._cfg.getBool(self._cfg.DEFAULT_POPUP_ADVANCED_DSTIP))
        self.checkDstPort.setChecked(self._cfg.getBool(self._cfg.DEFAULT_POPUP_ADVANCED_DSTPORT))
        self.checkUserID.setChecked(self._cfg.getBool(self._cfg.DEFAULT_POPUP_ADVANCED_UID))
        self.checkSum.setChecked(self._cfg.getBool(self._cfg.DEFAULT_POPUP_ADVANCED_CHECKSUM))
        self.checkDstHost.setChecked(self._cfg.getBool(self._cfg.DEFAULT_POPUP_ADVANCED_DSTHOST))
        self.checkCmdline.setChecked(self._cfg.getBool(self._cfg.DEFAULT_POPUP_ADVANCED_CMD))
        self.checkArgs.setChecked(self._cfg.getBool(self._cfg.DEFAULT_POPUP_ADVANCED_ARGS))
        self.checkPID.setChecked(self._cfg.getBool(self._cfg.DEFAULT_POPUP_ADVANCED_PID))

        self._set_cmd_action_text()
        self.checkAdvanced.setFocus()

        self.setFixedSize(self.size())

        self._post_popup_plugins(con)

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        ctrl = bool(mods & QtCore.Qt.KeyboardModifier.ControlModifier)

        if key == QtCore.Qt.Key.Key_Return or key == QtCore.Qt.Key.Key_Enter:
            self._on_action_clicked(Config.ACTION_ALLOW_IDX)
            return

        if key == QtCore.Qt.Key.Key_Escape:
            self._on_deny_btn_clicked(None)
            return

        if key == QtCore.Qt.Key.Key_Tab and ctrl:
            idx = (self.durationCombo.currentIndex() + 1) % self.durationCombo.count()
            self.durationCombo.setCurrentIndex(idx)
            self.stop_countdown()
            self._update_preview()
            return

        if key == QtCore.Qt.Key.Key_Control:
            self._ctrl_once_engaged = True
            self._saved_duration_idx = self.durationCombo.currentIndex()
            self.durationCombo.setCurrentIndex(0)
            self._update_once_visuals(True)
            self._update_preview()
            return

        super(PromptDialog, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Control:
            self._ctrl_once_engaged = False
            if hasattr(self, '_saved_duration_idx'):
                self.durationCombo.setCurrentIndex(self._saved_duration_idx)
            self._update_once_visuals(False)
            self._update_preview()
            return
        super(PromptDialog, self).keyReleaseEvent(event)

    def _update_once_visuals(self, once_mode):
        # Dynamic property drives the QLabel#promptPreview[once="true"] rule in
        # the dialog stylesheet. Qt only re-evaluates selectors on repolish, so
        # the unpolish/polish pair is required for the change to show.
        self._preview_label.setProperty("once", "true" if once_mode else "false")
        self._preview_label.style().unpolish(self._preview_label)
        self._preview_label.style().polish(self._preview_label)
        if once_mode:
            self.allowButton.setText("%s (once)" % self._allow_text)
            self.actionButton.setText("%s (once)" % self._action_text[self._default_action])
            self.whatCombo.setEnabled(False)
            self.durationCombo.setEnabled(False)
        else:
            self._set_cmd_action_text()
            self.allowButton.setText(self._allow_text)
            self.whatCombo.setEnabled(True)
            self.durationCombo.setEnabled(True)

    # prevent a click on the window's x
    # from quitting the whole application
    def closeEvent(self, e):
        self._send_rule()
        e.ignore()

    def close(self):
        self.stop_countdown()
        self._done.set()
        self.hide()

    def _on_action_clicked(self, action):
        self._default_action = action
        self._send_rule()

    def _on_deny_btn_clicked(self, action):
        self._default_action = self._cfg.getInt(self._cfg.DEFAULT_ACTION_KEY)
        if self._default_action == Config.ACTION_ALLOW_IDX:
            self._default_action = Config.ACTION_DROP_IDX
        self._send_rule()

    # uint32(-1): the daemon's UserId when the socket owner is unknown too.
    _UNKNOWN_UID = 0xFFFFFFFF

    def _unknown_process_operator(self):
        """Operand/data pair for a connection with no process path."""
        if 0 <= self._con.user_id < self._UNKNOWN_UID:
            return Config.OPERAND_USER_ID, str(self._con.user_id)
        if self._con.dst_host and self._con.dst_host != self._con.dst_ip:
            return Config.OPERAND_DEST_HOST, self._con.dst_host
        if self._con.dst_ip:
            return Config.OPERAND_DEST_IP, self._con.dst_ip
        return None

    def _is_list_rule(self):
        return self.checkUserID.isChecked() or \
            self.checkDstPort.isChecked() or \
            self.checkDstIP.isChecked() or \
            self.checkDstHost.isChecked() or \
            self.checkCmdline.isChecked() or \
            self.checkArgs.isChecked() or \
            self.checkPID.isChecked() or \
            self.checkSum.isChecked()

    def _save_checkbox_prefs(self):
        self._cfg.setSettings(self._cfg.DEFAULT_POPUP_ADVANCED_DSTHOST, self.checkDstHost.isChecked())
        self._cfg.setSettings(self._cfg.DEFAULT_POPUP_ADVANCED_CMD, self.checkCmdline.isChecked())
        self._cfg.setSettings(self._cfg.DEFAULT_POPUP_ADVANCED_ARGS, self.checkArgs.isChecked())
        self._cfg.setSettings(self._cfg.DEFAULT_POPUP_ADVANCED_PID, self.checkPID.isChecked())
        self._cfg.setSettings(self._cfg.DEFAULT_POPUP_SAVE_RULE, self.checkSaveRule.isChecked())

    def _send_rule(self):
        try:
            self._cfg.setSettings("promptDialog/geometry", self.saveGeometry())
            self._save_checkbox_prefs()
            self._rule = ui_pb2.Rule(name="user.choice")
            self._rule.created = int(datetime.now().timestamp())
            self._rule.enabled = True
            if not self.checkSaveRule.isChecked():
                self._rule.duration = Config.DURATION_ONCE
            else:
                self._rule.duration = utils.get_duration(self.durationCombo.currentIndex())

            self._rule.action = Config.ACTION_ALLOW
            if self._default_action == Config.ACTION_DROP_IDX:
                # TODO: use ACTION_DROP when 'drop' is added to the daemon
                self._rule.action = Config.ACTION_DENY
            elif self._default_action == Config.ACTION_REJECT_IDX:
                self._rule.action = Config.ACTION_REJECT

            if self._con.process_path.startswith(constants.APPIMAGE_PREFIX):
                _, _, appimage_data = utils.get_combo_operator(constants.FIELD_APPIMAGE, "", self._con)
                self._rule.operator.type = Config.RULE_TYPE_REGEXP
                self._rule.operator.operand = Config.OPERAND_PROCESS_PATH
                self._rule.operator.data = appimage_data
                self._rule.operator.sensitive = True
            elif self._con.process_path.startswith(constants.SNAP_PREFIX):
                _, _, snap_data = utils.get_combo_operator(constants.FIELD_SNAP, "", self._con)
                self._rule.operator.type = Config.RULE_TYPE_REGEXP
                self._rule.operator.operand = Config.OPERAND_PROCESS_PATH
                self._rule.operator.data = snap_data
                self._rule.operator.sensitive = True
            else:
                self._rule.operator.type = Config.RULE_TYPE_SIMPLE
                self._rule.operator.operand = Config.OPERAND_PROCESS_PATH
                self._rule.operator.data = self._con.process_path
            unknown_process = self._rule.operator.data == ""
            if unknown_process:
                # InterceptUnknown: the daemon saw the socket but could not
                # attribute it to a binary (pid 0, empty path). Key the rule on
                # what it does know instead of discarding the user's answer.
                fallback = self._unknown_process_operator()
                if fallback is None:
                    self.logger.debug("popups: Invalid rule, discarding: %s", repr(self._rule))
                    self._rule = None
                    return
                self._rule.operator.operand, self._rule.operator.data = fallback

            rule_temp_name = utils.get_rule_name(self._rule, self._is_list_rule())
            if unknown_process:
                rule_temp_name = slugify("%s %s unknown-process %s %s" % (
                    self._rule.action, self._rule.duration,
                    self._rule.operator.operand, self._rule.operator.data))
            self._rule.name = rule_temp_name

            data = []

            if self.checkDstHost.isChecked() and self._con.dst_host and self._con.dst_host != self._con.dst_ip:
                host_val = self.hostCombo.currentText() if self.hostCombo.isVisible() else self._con.dst_host
                if host_val.startswith("*."):
                    dsthost = r'\.'.join(host_val[2:].split('.')).replace("*", "")
                    dsthost = r'^(|.*\.)%s$' % dsthost
                    data.append({"type": Config.RULE_TYPE_REGEXP, "operand": Config.OPERAND_DEST_HOST, "data": dsthost, "sensitive": True})
                else:
                    data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_DEST_HOST, "data": host_val})
                rule_temp_name = slugify("%s %s" % (rule_temp_name, host_val))
            elif self.checkDstIP.isChecked():
                ip_val = self.ipCombo.currentText() if self.ipCombo.isVisible() else self._con.dst_ip
                if '/' in ip_val:
                    data.append({"type": Config.RULE_TYPE_NETWORK, "operand": Config.OPERAND_DEST_NETWORK, "data": ip_val})
                elif '*' in ip_val:
                    ip_re = r'\.'.join(ip_val.split('.')).replace("*", ".*")
                    data.append({"type": Config.RULE_TYPE_REGEXP, "operand": Config.OPERAND_DEST_IP, "data": ip_re, "sensitive": True})
                else:
                    data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_DEST_IP, "data": ip_val})
                rule_temp_name = slugify("%s %s" % (rule_temp_name, ip_val))

            if self.checkDstPort.isChecked():
                data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_DEST_PORT, "data": str(self._con.dst_port)})
                rule_temp_name = slugify("%s %s" % (rule_temp_name, str(self._con.dst_port)))

            if self.checkProtocol.isChecked():
                proto_val = self.protocolCombo.currentText() if self.protocolCombo.isVisible() else self._con.protocol
                data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_PROTOCOL, "data": proto_val.lower()})
                rule_temp_name = slugify("%s %s" % (rule_temp_name, proto_val))

            if self.checkUserID.isChecked():
                data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_USER_ID, "data": str(self._con.user_id)})
                rule_temp_name = slugify("%s %s" % (rule_temp_name, str(self._con.user_id)))

            if self.checkSum.isChecked() and self.checksumLabel.text() != "":
                data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_PROCESS_HASH_MD5, "data": self.checksumLabel.text()})

            if self.checkCmdline.isChecked() and self._con.process_path != "":
                data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_PROCESS_PATH, "data": self._con.process_path})

            if self.checkArgs.isChecked():
                cmdline = ' '.join(self._con.process_args)
                if cmdline:
                    data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_PROCESS_COMMAND, "data": cmdline})

            if self.checkPID.isChecked():
                data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_PROCESS_ID, "data": str(self._con.process_id)})

            is_list_rule = self._is_list_rule()

            # If the user has selected to filter by cmdline, always also
            # filter by the absolute path to the binary.
            # argv[0] is attacker-controlled via execve(), so we cannot
            # trust it regardless of whether it looks absolute or not.
            if self._rule.operator.operand == Config.OPERAND_PROCESS_COMMAND:
                is_list_rule = True
                data.append({"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_PROCESS_PATH, "data": str(self._con.process_path)})

            if is_list_rule:
                _main_op = {
                    "type": self._rule.operator.type,
                    "operand": self._rule.operator.operand,
                    "data": self._rule.operator.data
                }
                if self._rule.operator.type == Config.RULE_TYPE_REGEXP:
                    _main_op["sensitive"] = True
                data.append(_main_op)
                # We need to send back the operator list to the AskRule() call
                # as json string, in order to add it to the DB.
                self._rule.operator.data = json.dumps(data)
                self._rule.operator.type = Config.RULE_TYPE_LIST
                self._rule.operator.operand = Config.RULE_TYPE_LIST
                for op in data:
                    self._rule.operator.list.extend([
                        ui_pb2.Operator(
                            type=op['type'],
                            operand=op['operand'],
                            sensitive=False if op.get('sensitive') is None else op['sensitive'],
                            data="" if op.get('data') is None else op['data']
                        )
                    ])

            exists = self._rules.exists(self._rule, self._peer)
            if not exists:
                self._rule.name = self._rules.new_unique_name(rule_temp_name, self._peer, "")

            self.hide()
            if self._ischeckAdvanceded:
                self.checkAdvanced.toggle()
            self._ischeckAdvanceded = False

        except Exception as e:
            self.logger.warning("[pop-up] exception creating a rule: %s", repr(e))
        finally:
            # signal that the user took a decision and
            # a new rule is available
            self._done.set()
            self.hide()
