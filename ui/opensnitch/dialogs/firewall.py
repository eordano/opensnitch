"""The Firewall page of the main window.

The system firewall (nftables) that the daemon manages on a node: whether its
rules are applied, the default policy of the inbound and outbound chains, and
shortcuts to the rule editor. The rules table itself is appended below this
panel by the events dialog (see StatsDialogBase._setup_firewall_page).
"""
import time
import json

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QCoreApplication as QC

from opensnitch.utils import Icons, Message
from opensnitch.config import Config
from opensnitch.nodes import Nodes
from opensnitch.dialogs.firewall_rule import FwRuleDialog
import opensnitch.firewall as Fw
import opensnitch.firewall.profiles as FwProfiles

import opensnitch.proto as proto
ui_pb2, ui_pb2_grpc = proto.import_()

TITLE_HEIGHT = 32
BUTTON_HEIGHT = 34


class _WrapLabel(QtWidgets.QLabel):
    """word-wrapped label whose minimum height is one line, so it never
    forces the page taller than the words need"""
    def __init__(self, text=""):
        super().__init__(text)
        self.setWordWrap(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self):
        return QtCore.QSize(0, self.fontMetrics().height())


def _hint(text):
    label = _WrapLabel(text)
    label.setStyleSheet("color: palette(placeholder-text);")
    return label


def _heading(text):
    label = QtWidgets.QLabel(text)
    font = label.font()
    font.setBold(True)
    label.setFont(font)
    return label


class FirewallPanel(QtWidgets.QWidget):
    LOG_TAG = "[fw panel]"

    COMBO_IN = 0
    COMBO_OUT = 1

    POLICY_ACCEPT = 0
    POLICY_DROP = 1

    ALL_NODES = "all"
    ALL_NODES_IDX = 0

    nodeChanged = QtCore.pyqtSignal(str)
    _notification_callback = QtCore.pyqtSignal(str, ui_pb2.NotificationReply)

    def __init__(self, parent=None, appicon=None):
        super().__init__(parent)
        self.appicon = appicon
        self._cfg = Config.get()
        self._fw = Fw.Firewall.instance()
        self._nodes = Nodes.instance()
        self._fw_profiles = {}
        self._fwConfig = None
        self._loading = False
        self._last_profile = {
            self.COMBO_IN: FwProfiles.ProfileAcceptInput.value,
            self.COMBO_OUT: FwProfiles.ProfileAcceptOutput.value
        }
        self._notifications_sent = {}

        self._build_ui()

        self._fwrule_dialog = None
        self._notification_callback.connect(self._cb_notification_callback)
        self._nodes.nodesUpdated.connect(self._cb_nodes_updated)

        self.cmdNewRule.clicked.connect(self.new_rule)
        self.cmdAllowINService.clicked.connect(self.allow_in_service)
        self.cmdAllowOUTService.clicked.connect(self.allow_out_service)
        self.comboInput.currentIndexChanged.connect(lambda: self._cb_combo_policy_changed(self.COMBO_IN))
        self.comboOutput.currentIndexChanged.connect(lambda: self._cb_combo_policy_changed(self.COMBO_OUT))
        self.comboNodes.currentIndexChanged.connect(self._cb_combo_nodes_changed)
        self.chkEnabled.toggled.connect(self._cb_enable_fw_changed)
        self.cmdHelp.clicked.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(Config.HELP_SYSFW_URL))
        )

    # --- layout

    def _build_ui(self):
        self.setObjectName("firewallPanel")
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(6, 0, 6, 4)
        root.setSpacing(8)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(12)
        title = QtWidgets.QLabel(QC.translate("firewall", "Firewall (all of nftables)"))
        font = title.font()
        font.setPointSizeF(font.pointSizeF() * 1.35)
        font.setBold(True)
        title.setFont(font)
        title.setFixedHeight(TITLE_HEIGHT)
        header.addWidget(title, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        header.addStretch(1)

        self.comboNodes = QtWidgets.QComboBox()
        self.comboNodes.setMinimumHeight(TITLE_HEIGHT)
        self.comboNodes.setMinimumWidth(180)
        self.comboNodes.setToolTip(QC.translate("firewall", "The node whose firewall is shown and changed here."))
        self.comboNodes.setAccessibleName(QC.translate("firewall", "Node"))
        header.addWidget(self.comboNodes, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        # the on/off switch and the two default policies share the header
        # line with the title, left of the Wiki button
        self.policiesBox = QtWidgets.QWidget()
        row = QtWidgets.QHBoxLayout(self.policiesBox)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        self.chkEnabled = QtWidgets.QCheckBox(QC.translate("firewall", "Apply these rules on the node"))
        self.chkEnabled.setMinimumHeight(TITLE_HEIGHT)
        self.chkEnabled.setToolTip(QC.translate(
            "firewall",
            "When off, the daemon removes its nftables tables: the default policies and every "
            "rule below stop applying. Application rules are not affected."
        ))
        row.addWidget(self.chkEnabled)

        self.comboInput = QtWidgets.QComboBox()
        self.comboInput.addItem(QC.translate("firewall", "allowed"))
        self.comboInput.addItem(QC.translate("firewall", "dropped"))
        self.comboInput.setMinimumHeight(TITLE_HEIGHT)
        self.comboInput.setMinimumWidth(120)
        self.comboInput.setToolTip(QC.translate(
            "firewall", "Default for connections other machines open to this node (INPUT chain), when no rule matches."
        ))
        lbl_in = QtWidgets.QLabel(QC.translate("firewall", "Inbound connections are"))
        lbl_in.setBuddy(self.comboInput)
        row.addWidget(lbl_in)
        row.addWidget(self.comboInput)

        self.comboOutput = QtWidgets.QComboBox()
        self.comboOutput.addItem(QC.translate("firewall", "allowed"))
        self.comboOutput.addItem(QC.translate("firewall", "dropped"))
        self.comboOutput.setMinimumHeight(TITLE_HEIGHT)
        self.comboOutput.setMinimumWidth(120)
        self.comboOutput.setToolTip(QC.translate(
            "firewall",
            "Default for connections this node opens (OUTPUT chain), when no rule matches. "
            "Dropping blocks everything the rules below do not allow, also while the daemon is not running."
        ))
        lbl_out = QtWidgets.QLabel(QC.translate("firewall", "Outbound connections are"))
        lbl_out.setBuddy(self.comboOutput)
        row.addWidget(lbl_out)
        row.addWidget(self.comboOutput)
        header.addWidget(self.policiesBox, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self.cmdHelp = QtWidgets.QPushButton(QC.translate("firewall", "Wiki"))
        self.cmdHelp.setIcon(Icons.new(self, "help-browser"))
        self.cmdHelp.setMinimumHeight(TITLE_HEIGHT)
        self.cmdHelp.setToolTip(QC.translate("firewall", "Opens the wiki page about system rules."))
        header.addWidget(self.cmdHelp, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header)


        # the empty state: centred over the rules table once the page lends
        # it its table (attach_table); until then a plain line on the panel
        self.lblFwStatus = _WrapLabel("")
        self.lblFwStatus.setOpenExternalLinks(True)
        self.lblFwStatus.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextBrowserInteraction)
        self.lblFwStatus.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.lblFwStatus.setVisible(False)
        self._status_table = None
        root.addWidget(self.lblFwStatus)
        self.statusLabel = _WrapLabel("")
        self.statusLabel.setVisible(False)
        root.addWidget(self.statusLabel)

        # the toolbar of the table below: its name on the left, actions right
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(8)
        rules_title = _heading(QC.translate("firewall", "Rules"))
        rules_title.setToolTip(QC.translate(
            "firewall", "Checked in order, first match wins. Double-click a rule to edit it, right-click for more."
        ))
        bar.addWidget(rules_title)
        bar.addStretch(1)

        self.cmdNewRule = QtWidgets.QPushButton(QC.translate("firewall", "New rule..."))
        self.cmdNewRule.setIcon(Icons.new(self, "document-new"))
        self.cmdNewRule.setMinimumHeight(BUTTON_HEIGHT)
        self.cmdNewRule.setToolTip(QC.translate("firewall", "Opens the rule editor with an empty rule."))
        bar.addWidget(self.cmdNewRule)

        self.cmdAllowINService = QtWidgets.QPushButton(QC.translate("firewall", "Allow inbound port..."))
        self.cmdAllowINService.setIcon(Icons.new(self, "go-down"))
        self.cmdAllowINService.setMinimumHeight(BUTTON_HEIGHT)
        self.cmdAllowINService.setToolTip(QC.translate(
            "firewall", "Rule template: accept connections from other machines to a port on this node."
        ))
        bar.addWidget(self.cmdAllowINService)

        self.cmdAllowOUTService = QtWidgets.QPushButton(QC.translate("firewall", "Allow outbound port..."))
        self.cmdAllowOUTService.setIcon(Icons.new(self, "go-up"))
        self.cmdAllowOUTService.setMinimumHeight(BUTTON_HEIGHT)
        self.cmdAllowOUTService.setToolTip(QC.translate(
            "firewall",
            "Rule template: let connections to a port leave without being intercepted, "
            "so no application rule or alert applies to them."
        ))
        bar.addWidget(self.cmdAllowOUTService)
        root.addLayout(bar)

    def attach_table(self, table):
        """the rules table below this panel: the empty-state text is laid
        over its viewport, centred, instead of sitting top-left above it"""
        self._status_table = table
        layout = self.layout()
        if layout is not None:
            layout.removeWidget(self.lblFwStatus)
        self.lblFwStatus.setParent(table.viewport())
        self.lblFwStatus.setStyleSheet("QLabel { color: palette(placeholder-text); font-size: 14px; }")
        self.lblFwStatus.setContentsMargins(24, 24, 24, 24)
        table.viewport().installEventFilter(self)
        self._place_status()

    def eventFilter(self, obj, event):
        if self._status_table is not None and obj is self._status_table.viewport() \
                and event.type() == QtCore.QEvent.Type.Resize:
            self._place_status()
        return super().eventFilter(obj, event)

    def _place_status(self):
        if self._status_table is not None:
            self.lblFwStatus.setGeometry(self._status_table.viewport().rect())
            self.lblFwStatus.raise_()

    # --- callbacks

    @QtCore.pyqtSlot(str, ui_pb2.NotificationReply)
    def _cb_notification_callback(self, addr, reply):
        self.comboInput.setEnabled(True)
        self.comboOutput.setEnabled(True)
        if reply.id in self._notifications_sent:
            if reply.code == ui_pb2.OK:
                self._set_status_successful(QC.translate("firewall", "Configuration applied."))
            else:
                self._set_status_error(QC.translate("firewall", "There was an error: {0}").format(reply.data))
            del self._notifications_sent[reply.id]
        else:
            print(self.LOG_TAG, "unknown notification:", reply)

    @QtCore.pyqtSlot(int)
    def _cb_nodes_updated(self, total):
        if self.isVisible():
            self.load()

    def _cb_combo_nodes_changed(self, idx):
        addr = self.comboNodes.itemData(idx)
        if idx >= 1:
            self.block_combo_signals()
            self.load_node_fw_policy(addr)
            self.block_combo_signals(False)
        self.nodeChanged.emit(addr if addr is not None else self.ALL_NODES)

    def _cb_combo_policy_changed(self, combo):
        if self.comboNodes.currentIndex() == self.ALL_NODES_IDX and self._nodes.count() > 1:
            ret = Message.yes_no(
                QC.translate("stats", "This change will apply the policy change to all nodes?"),
                QC.translate("stats", "Are you sure?"),
                QtWidgets.QMessageBox.Icon.Warning)
            if ret == QtWidgets.QMessageBox.StandardButton.Cancel:
                return

        self._reset_status_message()
        self.comboInput.setEnabled(False)
        self.comboOutput.setEnabled(False)

        wantedProfile = FwProfiles.ProfileAcceptInput.value
        if combo == self.COMBO_OUT:
            wantedProfile = FwProfiles.ProfileAcceptOutput.value
            if self.comboOutput.currentIndex() == self.POLICY_DROP:
                wantedProfile = FwProfiles.ProfileDropOutput.value
        else:
            if self.comboInput.currentIndex() == self.POLICY_DROP:
                wantedProfile = FwProfiles.ProfileDropInput.value

        if combo == self.COMBO_IN and self.comboInput.currentIndex() == self.POLICY_ACCEPT:
            json_profile = json.dumps(FwProfiles.ProfileDropInput.value)
            for addr in self._nodes.get():
                ok, err = self._fw.delete_profile(addr, json_profile)
                if not ok:
                    print(err)
        elif combo == self.COMBO_OUT and self.comboOutput.currentIndex() == self.POLICY_ACCEPT:
            json_profile = json.dumps(FwProfiles.ProfileDropOutput.value)
            for addr in self._nodes.get():
                self._fw.delete_profile(addr, json_profile)
        elif combo == self.COMBO_OUT and self.comboOutput.currentIndex() == self.POLICY_DROP:
            self._set_status_message(QC.translate(
                "firewall",
                "Outbound connections are now dropped unless a rule allows them. "
                "If the daemon stops, outbound traffic stays blocked."
            ))

        json_profile = json.dumps(wantedProfile)
        for addr in self._nodes.get():
            fwcfg = self._nodes.get_node(addr)['firewall']
            ok, err = self._fw.apply_profile(addr, json_profile)
            if ok:
                self.send_notification(addr, fwcfg)
            else:
                self._set_status_error(QC.translate("firewall", "Policy not applied: {0}").format(err))

        self._last_profile[combo] = wantedProfile

    def _cb_enable_fw_changed(self, enable):
        if self._nodes.count() == 0:
            self.chkEnabled.blockSignals(True)
            self.chkEnabled.setChecked(False)
            self.chkEnabled.blockSignals(False)
            return
        addr = self.comboNodes.itemData(self.comboNodes.currentIndex())
        self.enable_fw(addr, enable)

    def _change_fw_backend(self, addr, node_cfg):
        nid, notif = self._nodes.change_node_config(addr, node_cfg, self._notification_callback)
        self._notifications_sent[nid] = notif

    # --- loading

    def showEvent(self, event):
        super().showEvent(event)
        self.load()

    def load(self):
        if self._loading:
            return
        self._loading = True
        try:
            self._reset_status_message()
            self._load_nodes()
            self.load_fw_policies()
        finally:
            self._loading = False

    def select_node(self, addr):
        """follow the sidebar's node selector"""
        idx = self.comboNodes.findData(addr if addr else self.ALL_NODES)
        if idx >= 0 and idx != self.comboNodes.currentIndex():
            self.comboNodes.setCurrentIndex(idx)

    def current_node(self):
        """address of the node the page shows, or ALL_NODES"""
        addr = self.comboNodes.itemData(self.comboNodes.currentIndex())
        return addr if addr is not None else self.ALL_NODES

    def _load_nodes(self):
        current = self.comboNodes.itemData(self.comboNodes.currentIndex())
        self.comboNodes.blockSignals(True)
        self.comboNodes.clear()
        node_list = self._nodes.get()

        self.comboNodes.addItem(QC.translate("firewall", "All nodes"), self.ALL_NODES)
        for node in node_list:
            hostname = self._nodes.get_node_hostname(node)
            self.comboNodes.addItem(hostname or node, node)

        show_nodes = len(node_list) > 1
        if not show_nodes:
            self.comboNodes.setCurrentIndex(min(1, self.comboNodes.count() - 1))
        else:
            idx = self.comboNodes.findData(current)
            self.comboNodes.setCurrentIndex(idx if idx >= 0 else 0)
        self.comboNodes.setVisible(show_nodes)
        self.comboNodes.blockSignals(False)

    def send_notification(self, node_addr, fw_config):
        self._set_status_message(QC.translate("firewall", "Applying changes..."))

        addr = self.comboNodes.itemData(self.comboNodes.currentIndex())
        if addr == self.ALL_NODES and self._nodes.count() > 1:
            for addr in self._nodes.get():
                nid, notif = self._nodes.reload_fw(addr, fw_config, self._notification_callback)
                self._notifications_sent[nid] = {'addr': addr, 'notif': notif}
            return

        nid, notif = self._nodes.reload_fw(node_addr, fw_config, self._notification_callback)
        self._notifications_sent[nid] = {'addr': node_addr, 'notif': notif}

    def load_fw_policies(self, node_addr=None):
        self.lblFwStatus.setText("")
        self.lblFwStatus.setVisible(False)
        self.chkEnabled.blockSignals(True)
        self.block_combo_signals()

        self._disable_widgets()

        enableFw = False
        try:
            enableFwBtn = (self._nodes.count() > 0)
            self.chkEnabled.setEnabled(enableFwBtn)
            if not enableFwBtn:
                self.lblFwStatus.setText(QC.translate(
                    "firewall", "There are no nodes connected, so there is no firewall to configure."
                ))
                self.lblFwStatus.setVisible(True)
                return

            enableFw = self._nodes.count() > 1
            if node_addr is None and self._nodes.count() == 1:
                node_addr = self.comboNodes.itemData(self.comboNodes.currentIndex())
                if node_addr is not None:
                    enableFw = self.load_node_fw_policy(node_addr)
                return

        except Exception as e:
            self._set_status_error("Firewall status error (report on github please): {0}".format(e))

        finally:
            self._disable_widgets(not enableFw)
            self.chkEnabled.setChecked(enableFw)
            self.chkEnabled.blockSignals(False)
            self.block_combo_signals(False)

    def load_node_fw_policy(self, addr):
        enableFw = False
        try:
            node = self._nodes.get_node(addr)
            self._fwConfig = node['firewall']
            enableFw |= self._fwConfig.Enabled

            if self.fw_is_incompatible(addr, node):
                return False

            pol_in = self._fw.chains.get_policy(addr, Fw.Hooks.INPUT.value)
            pol_out = self._fw.chains.get_policy(addr, Fw.Hooks.OUTPUT.value, Fw.ChainType.MANGLE.value)

            if pol_in is not None:
                self.comboInput.setCurrentIndex(Fw.Policy.values().index(pol_in))
            else:
                self._set_status_error(QC.translate("firewall", "Error getting INPUT chain policy"))
                self._disable_widgets()
            if pol_out is not None:
                self.comboOutput.setCurrentIndex(Fw.Policy.values().index(pol_out))
            else:
                self._set_status_error(QC.translate("firewall", "Error getting OUTPUT chain policy"))
                self._disable_widgets()

        except Exception as e:
            self._set_status_error("Firewall status error (report on github please): {0}".format(e))
            enableFw = False

        return enableFw

    def fw_is_incompatible(self, addr, node):
        """iptables cannot be driven from here; an old system-rules format
        cannot either. Both disable the page and say why."""
        incompatible = False
        node_cfg = json.loads(node['data'].config)
        if node_cfg['Firewall'] == "iptables":
            self._disable_widgets()
            self.chkEnabled.setEnabled(False)
            if self.isVisible() and self.change_fw(addr, node_cfg):
                node_cfg['Firewall'] = "nftables"
                self.chkEnabled.setEnabled(True)
                self.enable_fw(addr, True)
                self._change_fw_backend(addr, node_cfg)
                return False
            incompatible = True

        if node['data'].systemFirewall.Version == 0:
            self._disable_widgets()
            self.chkEnabled.setEnabled(False)
            self.lblFwStatus.setText(
                QC.translate("firewall", "<html>The firewall configuration is outdated; "
                             "it needs the new format: <a href=\"{0}\">learn more</a>"
                             "</html>").format(Config.HELP_SYS_RULES_URL)
            )
            self.lblFwStatus.setVisible(True)
            incompatible = True

        return incompatible

    def change_fw(self, addr, node_cfg):
        ret = Message.yes_no(
            QC.translate("firewall",
                         "In order to configure firewall rules from the GUI, we need to use 'nftables' instead of 'iptables'"),
            QC.translate("firewall", "Change default firewall to 'nftables' on node {0}?").format(addr),
            QtWidgets.QMessageBox.Icon.Warning)
        return ret != QtWidgets.QMessageBox.StandardButton.Cancel

    def enable_fw(self, addr, enable):
        try:
            self._disable_widgets(not enable)
            if enable:
                self._set_status_message(QC.translate("firewall", "Enabling firewall..."))
            else:
                self._set_status_message(QC.translate("firewall", "Disabling firewall..."))

            # a DROP policy must go back to ACCEPT before the tables are
            # removed, or the node is left without traffic
            if not enable and self.comboInput.currentIndex() == self.POLICY_DROP:
                self.comboInput.blockSignals(True)
                self.comboInput.setCurrentIndex(self.POLICY_ACCEPT)
                self.comboInput.blockSignals(False)
                for naddr in self._nodes.get():
                    ok, err = self._fw.apply_profile(naddr, json.dumps(FwProfiles.ProfileAcceptInput.value))
                    if not ok:
                        self._set_status_error(
                            QC.translate("firewall", "Error applying INPUT ACCEPT profile: {0}").format(err))
                        return

            if not enable and self.comboOutput.currentIndex() == self.POLICY_DROP:
                self.comboOutput.blockSignals(True)
                self.comboOutput.setCurrentIndex(self.POLICY_ACCEPT)
                self.comboOutput.blockSignals(False)
                for naddr in self._nodes.get():
                    ok, err = self._fw.apply_profile(naddr, json.dumps(FwProfiles.ProfileAcceptOutput.value))
                    if not ok:
                        self._set_status_error(
                            QC.translate("firewall", "Error applying OUTPUT ACCEPT profile: {0}").format(err))
                        return

            # The daemon ignores a policy change that arrives together with
            # "disabled", so the policy goes first and the switch second.
            if addr == self.ALL_NODES or addr is None:
                targets = list(self._nodes.get())
            else:
                targets = [addr]
            for naddr in targets:
                fwcfg = self._nodes.get_node(naddr)['firewall']
                self.send_notification(naddr, fwcfg)
                time.sleep(0.5)
                fwcfg.Enabled = bool(enable)
                self.send_notification(naddr, fwcfg)

            self.policiesBox.setEnabled(enable)
            time.sleep(0.5)

        except Exception as e:
            self._set_status_error(QC.translate("firewall", "Error: {0}").format(e))

    # --- rule editor (a window; created on first use so the page can be
    # built before the main window knows its icon)

    def rule_editor(self):
        if self._fwrule_dialog is None:
            self._fwrule_dialog = FwRuleDialog(appicon=self.appicon or QtGui.QIcon())
        return self._fwrule_dialog

    def load_rule(self, addr, uuid):
        self.rule_editor().load(addr, uuid)

    def new_rule(self):
        self.rule_editor().new()

    def allow_out_service(self):
        self.rule_editor().exclude_service(self.COMBO_OUT)

    def allow_in_service(self):
        self.rule_editor().exclude_service(self.COMBO_IN)

    # --- status line

    def _set_status_error(self, msg):
        self.statusLabel.setVisible(True)
        self.statusLabel.setStyleSheet('color: red')
        self.statusLabel.setText(msg)

    def _set_status_successful(self, msg):
        self.statusLabel.setVisible(True)
        self.statusLabel.setStyleSheet('color: green')
        self.statusLabel.setText(msg)

    def _set_status_message(self, msg):
        self.statusLabel.setVisible(True)
        self.statusLabel.setStyleSheet('color: darkorange')
        self.statusLabel.setText(msg)

    def _reset_status_message(self):
        self.statusLabel.setText("")
        self.statusLabel.setVisible(False)

    def block_combo_signals(self, state=True):
        self.comboInput.blockSignals(state)
        self.comboOutput.blockSignals(state)
        self.comboNodes.blockSignals(state)

    def _disable_widgets(self, disable=True):
        self.comboInput.setEnabled(not disable)
        self.comboOutput.setEnabled(not disable)
        self.cmdNewRule.setEnabled(not disable)
        self.cmdAllowOUTService.setEnabled(not disable)
        self.cmdAllowINService.setEnabled(not disable)
        self.comboNodes.setEnabled(not disable)


# the class used to be a separate window
FirewallDialog = FirewallPanel
