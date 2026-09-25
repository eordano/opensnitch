#
# pytest -v tests/test_deny_to_drop.py
#
# Tests to verify that user-facing labels use "Drop" instead of "Deny",
# while internal protocol values remain "deny".
#

import os
import xml.etree.ElementTree as ET
from opensnitch.config import Config


# Path to the UI resource files relative to this test file
UI_DIR = os.path.join(os.path.dirname(__file__), "..", "opensnitch", "res")


class TestDenyToDropUI:
    """Verify that the Deny-to-Drop rename is complete in UI files."""

    def test_stats_ui_has_no_deny_string(self):
        """The stats.ui filter combo must not contain '<string>Deny</string>'."""
        stats_ui_path = os.path.join(UI_DIR, "stats.ui")
        with open(stats_ui_path, "r") as f:
            content = f.read()
        # The combo box items should use "Drop", not "Deny"
        assert "<string>Deny</string>" not in content, (
            "stats.ui still contains '<string>Deny</string>' -- should be '<string>Drop</string>'"
        )

    def test_stats_ui_has_drop_string(self):
        """The stats.ui filter combo must contain '<string>Drop</string>'."""
        stats_ui_path = os.path.join(UI_DIR, "stats.ui")
        with open(stats_ui_path, "r") as f:
            content = f.read()
        assert "<string>Drop</string>" in content, (
            "stats.ui is missing '<string>Drop</string>' in the rules filter combo"
        )

    def test_ruleseditor_action_deny_radio_shows_drop(self):
        """The actionDenyRadio widget in ruleseditor.ui must display 'Drop' text."""
        ruleseditor_path = os.path.join(UI_DIR, "ruleseditor.ui")
        tree = ET.parse(ruleseditor_path)
        root = tree.getroot()

        # Find the widget named actionDenyRadio
        found = False
        for widget in root.iter("widget"):
            if widget.attrib.get("name") == "actionDenyRadio":
                found = True
                # Find the text property
                for prop in widget.findall("property"):
                    if prop.attrib.get("name") == "text":
                        string_el = prop.find("string")
                        assert string_el is not None, "actionDenyRadio has no text string element"
                        assert string_el.text == "Drop", (
                            f"actionDenyRadio text is '{string_el.text}', expected 'Drop'"
                        )
                        break
                else:
                    raise AssertionError("actionDenyRadio widget has no 'text' property")
                break

        assert found, "Could not find widget named 'actionDenyRadio' in ruleseditor.ui"


class TestConfigConstants:
    """Verify Config constants are correctly defined for the Deny-to-Drop rename."""

    def test_action_drop_idx_exists(self):
        """Config.ACTION_DROP_IDX must exist."""
        assert hasattr(Config, "ACTION_DROP_IDX"), "Config.ACTION_DROP_IDX is missing"

    def test_action_drop_idx_value(self):
        """Config.ACTION_DROP_IDX must be 0 (first item in combo boxes)."""
        assert Config.ACTION_DROP_IDX == 0, (
            f"Config.ACTION_DROP_IDX is {Config.ACTION_DROP_IDX}, expected 0"
        )

    def test_action_deny_internal_value(self):
        """Config.ACTION_DENY must remain 'deny' -- this is the internal protocol value."""
        assert Config.ACTION_DENY == "deny", (
            f"Config.ACTION_DENY is '{Config.ACTION_DENY}', expected 'deny' (internal value)"
        )

    def test_action_deny_is_not_drop(self):
        """Config.ACTION_DENY must NOT be 'drop' -- 'deny' is the daemon protocol value."""
        assert Config.ACTION_DENY != "drop", (
            "Config.ACTION_DENY was changed to 'drop' -- it must remain 'deny' for daemon compatibility"
        )


class TestPreferencesComboBox:
    """Verify the preferences combo box uses 'drop' at ACTION_DROP_IDX."""

    def test_preferences_ui_combo_drop_at_index_0(self):
        """The comboUIAction in preferences.ui must show 'drop' at index 0 (ACTION_DROP_IDX)."""
        prefs_path = os.path.join(UI_DIR, "preferences.ui")
        tree = ET.parse(prefs_path)
        root = tree.getroot()

        # Find comboUIAction widget
        for widget in root.iter("widget"):
            if widget.attrib.get("name") == "comboUIAction":
                items = widget.findall("item")
                assert len(items) > Config.ACTION_DROP_IDX, (
                    f"comboUIAction has only {len(items)} items, need at least {Config.ACTION_DROP_IDX + 1}"
                )
                # Get the text of the item at ACTION_DROP_IDX
                item = items[Config.ACTION_DROP_IDX]
                for prop in item.findall("property"):
                    if prop.attrib.get("name") == "text":
                        string_el = prop.find("string")
                        assert string_el is not None
                        assert string_el.text.lower() == "drop", (
                            f"comboUIAction item at index {Config.ACTION_DROP_IDX} is "
                            f"'{string_el.text}', expected 'drop' (or 'Drop')"
                        )
                        return
                raise AssertionError("comboUIAction item at index 0 has no text property")

        raise AssertionError("Could not find comboUIAction widget in preferences.ui")

    def test_preferences_ui_combo_not_deny(self):
        """The comboUIAction in preferences.ui must NOT show 'deny' at index 0."""
        prefs_path = os.path.join(UI_DIR, "preferences.ui")
        tree = ET.parse(prefs_path)
        root = tree.getroot()

        for widget in root.iter("widget"):
            if widget.attrib.get("name") == "comboUIAction":
                items = widget.findall("item")
                item = items[Config.ACTION_DROP_IDX]
                for prop in item.findall("property"):
                    if prop.attrib.get("name") == "text":
                        string_el = prop.find("string")
                        assert string_el is not None
                        assert string_el.text.lower() != "deny", (
                            f"comboUIAction still shows 'Deny' at index {Config.ACTION_DROP_IDX}"
                        )
                        return
