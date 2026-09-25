#
# Regression tests for issue #1568 -- Help button freezes UI
#
# The bug was caused by blocking webbrowser.open() calls on the main thread.
# The fix uses non-blocking QDesktopServices.openUrl() instead.
# These tests ensure the fix is not reverted.
#
# pytest -v tests/test_help_buttons.py
#

import importlib
import inspect

from unittest.mock import patch, MagicMock
from PyQt6 import QtCore, QtGui

import opensnitch.proto as proto
proto.import_()

from opensnitch.config import Config


class TestHelpButtonsNonBlocking:
    """Verify help handlers use non-blocking Qt calls, not webbrowser.open()."""

    def test_ruleseditor_dialog_does_not_import_webbrowser(self):
        """The ruleseditor dialog module must not import webbrowser."""
        import opensnitch.dialogs.ruleseditor.dialog as mod
        source = inspect.getsource(mod)
        assert "import webbrowser" not in source, (
            "ruleseditor/dialog.py must not import webbrowser (issue #1568)"
        )

    def test_firewall_dialog_does_not_import_webbrowser(self):
        """The firewall dialog module must not import webbrowser."""
        import opensnitch.dialogs.firewall as mod
        source = inspect.getsource(mod)
        assert "import webbrowser" not in source, (
            "firewall.py must not import webbrowser (issue #1568)"
        )

    def test_preferences_utils_does_not_import_webbrowser(self):
        """The preferences utils module must not import webbrowser."""
        import opensnitch.dialogs.preferences.utils as mod
        source = inspect.getsource(mod)
        assert "import webbrowser" not in source, (
            "preferences/utils.py must not import webbrowser (issue #1568)"
        )

    def test_ruleseditor_help_calls_qdesktopservices(self, qapp):
        """cb_help_clicked must call QDesktopServices.openUrl, not webbrowser."""
        white_icon = QtGui.QIcon("../res/icon-white.svg")

        from opensnitch.dialogs.ruleseditor import RulesEditorDialog
        rd = RulesEditorDialog(appicon=white_icon)

        with patch.object(QtGui.QDesktopServices, 'openUrl', return_value=True) as mock_open:
            rd.cb_help_clicked()
            mock_open.assert_called_once()
            url_arg = mock_open.call_args[0][0]
            assert isinstance(url_arg, QtCore.QUrl)
            assert url_arg.toString() == Config.HELP_URL

    def test_firewall_help_calls_qdesktopservices(self, qapp):
        """Firewall dialog help button must call QDesktopServices.openUrl."""
        # Verify by inspecting the source -- instantiating FirewallDialog
        # requires full UI setup, so source inspection is more robust.
        import opensnitch.dialogs.firewall as mod
        source = inspect.getsource(mod)
        assert "QDesktopServices.openUrl" in source, (
            "firewall.py help handler must use QDesktopServices.openUrl (issue #1568)"
        )
        assert "webbrowser.open" not in source, (
            "firewall.py must not use webbrowser.open (issue #1568)"
        )

    def test_preferences_help_uses_quickhelp(self, qapp):
        """Preferences show_help must use QuickHelp.show, not webbrowser."""
        from opensnitch.dialogs.preferences.utils import show_help

        with patch('opensnitch.dialogs.preferences.utils.QuickHelp') as mock_qh:
            show_help()
            mock_qh.show.assert_called_once()

    def test_ruleseditor_help_source_has_no_webbrowser_open(self):
        """The cb_help_clicked method source must not contain webbrowser.open."""
        from opensnitch.dialogs.ruleseditor.dialog import RulesEditorDialog
        source = inspect.getsource(RulesEditorDialog.cb_help_clicked)
        assert "webbrowser" not in source, (
            "cb_help_clicked must not use webbrowser (issue #1568)"
        )
        assert "QDesktopServices" in source, (
            "cb_help_clicked must use QDesktopServices (issue #1568)"
        )
