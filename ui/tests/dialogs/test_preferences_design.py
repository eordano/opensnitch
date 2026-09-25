"""The redesigned Preferences dialog must still host every control declared in
preferences.ui (the settings code addresses them by name)."""
import re
from PyQt6 import QtWidgets, QtGui

import opensnitch.proto as proto
proto.import_()

from opensnitch.dialogs.preferences import PreferencesDialog, design

CONTROL = re.compile(r"^(combo|spin|line|check|radio|tpl|enableChecksums|dbFileButton|dbLabel|"
                     r"uidCheck|dstPortCheck|dstIPCheck|checkSum|popupsCheck|showAdvancedCheck|"
                     r"cmdTestNotifs|cmdNodeRulesPath|cmdServerLogFile|labelNode|labelUI|labelDB|labelTheme)")
# retired on purpose: the -/+ helpers (spin boxes have arrows) and the node duration upstream disabled
RETIRED = re.compile(r"^cmd.*(Up|Down)$|^comboNodeDuration$|^labelNodeDuration$|^labelNodeName$|^labelNodeVersion$|^popupsCheck$|^showAdvancedCheck$")


def _on_a_page(dialog, widget):
    w = widget
    while w is not None:
        if w is dialog._design_holder:
            return False
        if w is dialog.stackedWidget:
            return True
        w = w.parentWidget()
    return False


class TestPreferencesDesign:
    def setup_method(self):
        self.prefs = PreferencesDialog(appicon=QtGui.QIcon())
        self.prefs.show()
        QtWidgets.QApplication.processEvents()

    def teardown_method(self):
        self.prefs.close()

    def test_every_control_lives_on_a_page(self, qtbot):
        qtbot.addWidget(self.prefs)
        missing = []
        for w in self.prefs.findChildren(QtWidgets.QWidget):
            name = w.objectName()
            if not CONTROL.match(name) or RETIRED.match(name):
                continue
            if not _on_a_page(self.prefs, w):
                missing.append(name)
        assert missing == []

    def test_categories_match_pages(self, qtbot):
        qtbot.addWidget(self.prefs)
        assert self.prefs.listWidget.count() == self.prefs.stackedWidget.count() == 7
        assert self.prefs.TAB_NODES == design.PAGE_NODES
        self.prefs.listWidget.setCurrentRow(design.PAGE_STORAGE)
        QtWidgets.QApplication.processEvents()
        assert self.prefs.stackedWidget.currentIndex() == design.PAGE_STORAGE
        assert self.prefs.comboDBType.isVisible()

    def test_hidden_controls_take_their_label_along(self, qtbot):
        qtbot.addWidget(self.prefs)
        self.prefs.listWidget.setCurrentRow(design.PAGE_STORAGE)
        QtWidgets.QApplication.processEvents()
        assert not self.prefs.dbFileButton.isVisible()
        label = self.prefs._dbFileFollow.targets[0]
        assert not label.isVisible()
        self.prefs.dbFileButton.setVisible(True)
        QtWidgets.QApplication.processEvents()
        assert label.isVisible()

    def test_buttons_are_standard(self, qtbot):
        qtbot.addWidget(self.prefs)
        assert self.prefs.acceptButton.text() == "OK"
        assert self.prefs.cancelButton.text() == "Cancel"
        assert self.prefs.applyButton.text() == "Apply"

    def test_search_filters_rows_and_categories(self, qtbot):
        qtbot.addWidget(self.prefs)
        d = self.prefs
        d.searchLine.setText("checksum")
        QtWidgets.QApplication.processEvents()
        visible = [i for i in range(d.listWidget.count()) if not d.listWidget.item(i).isHidden()]
        assert visible == [design.PAGE_PROMPTS, design.PAGE_NODES]
        assert d.stackedWidget.currentIndex() == design.PAGE_PROMPTS
        assert d.checkSum.isVisible()
        assert not d.comboUIAction.isVisible()
        d.listWidget.setCurrentRow(design.PAGE_NODES)
        QtWidgets.QApplication.processEvents()
        assert d.enableChecksums.isVisible()
        assert not d.tabNodeWidget.isTabVisible(design.NODE_TAB_LOGGING)
        d.searchLine.clear()
        QtWidgets.QApplication.processEvents()
        assert all(not d.listWidget.item(i).isHidden() for i in range(d.listWidget.count()))
        assert d.tabNodeWidget.isTabVisible(design.NODE_TAB_LOGGING)
        d.listWidget.setCurrentRow(design.PAGE_PROMPTS)
        QtWidgets.QApplication.processEvents()
        assert d.comboUIAction.isVisible()
        # controls the settings code hid stay hidden after the search is cleared
        assert not d.dbFileButton.isVisible()

    def test_asking_radios_drive_the_stored_controls(self, qtbot):
        qtbot.addWidget(self.prefs)
        d = self.prefs
        d.radioAskNever.setChecked(True)
        assert d.popupsCheck.isChecked()
        d.radioAskAuto.setChecked(True)
        assert not d.popupsCheck.isChecked() and d.spinUITimeout.value() > 0
        d.radioAskWait.setChecked(True)
        assert not d.popupsCheck.isChecked() and d.spinUITimeout.value() == -1
        # settings code loading values moves the radios
        d.spinUITimeout.setValue(15)
        assert d.radioAskAuto.isChecked()
        d.popupsCheck.setChecked(True)
        assert d.radioAskNever.isChecked()

    def test_alert_preview_is_the_real_dialog(self, qtbot):
        qtbot.addWidget(self.prefs)
        d = self.prefs
        d.listWidget.setCurrentRow(design.PAGE_PROMPTS)
        QtWidgets.QApplication.processEvents()
        d.dstPortCheck.setChecked(True)
        d.uidCheck.setChecked(False)
        d.alertPreview.render()
        assert not d.alertPreview.pixmap().isNull()
        dlg = d.alertPreview.dialog
        assert dlg.checkDstPort.isChecked() and not dlg.checkUserID.isChecked()
        assert d.alertPreview.pixmap().width() > 300
        # the sample window never sends a rule: its buttons only hide it
        d.alertPreview.open_window()
        assert dlg.isVisible()
        dlg.allowButton.click()
        assert not dlg.isVisible()

    def test_pending_node_changes_ask_before_leaving(self, qtbot, monkeypatch):
        qtbot.addWidget(self.prefs)
        d = self.prefs
        from opensnitch.dialogs.preferences import utils, settings
        d.listWidget.setCurrentRow(design.PAGE_NODES)
        QtWidgets.QApplication.processEvents()
        d.node_needs_update = True
        asked = []
        saved = []
        monkeypatch.setattr(utils, "ask_node_changes", lambda win: asked.append(1) or "cancel")
        monkeypatch.setattr(settings, "save_nodes_config", lambda win: saved.append(1) or True)
        d.listWidget.setCurrentRow(design.PAGE_STORAGE)
        QtWidgets.QApplication.processEvents()
        assert asked == [1] and d.stackedWidget.currentIndex() == design.PAGE_NODES
        monkeypatch.setattr(utils, "ask_node_changes", lambda win: "apply")
        d.listWidget.setCurrentRow(design.PAGE_STORAGE)
        QtWidgets.QApplication.processEvents()
        assert saved == [1] and d.stackedWidget.currentIndex() == design.PAGE_STORAGE
        assert not d.node_needs_update
        # cancel/close asks too; discard just closes
        d.node_needs_update = True
        monkeypatch.setattr(utils, "ask_node_changes", lambda win: "discard")
        d.reject()
        assert not d.isVisible() and not d.node_needs_update
