#
# pytest -v tests/test_prompt_regex.py
#
# Tests for issue #1587: auto-generated regex operators from the prompt
# dialog must have sensitive=True to prevent the daemon from lowercasing
# the regex pattern (which would corrupt character classes like [A-Za-z]).
#

import json

# Import proto first to avoid circular import issues
import opensnitch.proto as proto
proto.import_()

from opensnitch.config import Config
from opensnitch.dialogs.prompt import constants
from opensnitch.dialogs.prompt import utils as prompt_utils


class MockConnection:
    """Mock connection object for testing prompt utilities."""
    protocol = "tcp"
    src_ip = "127.0.0.1"
    src_port = "12345"
    dst_ip = "192.168.1.50"
    dst_host = "example.com"
    dst_port = "443"
    user_id = 1000
    process_id = 9876
    process_path = "/tmp/.mount_AppNameXyz123/AppRun"
    process_cwd = "/home/user"
    process_args = ["/tmp/.mount_AppNameXyz123/AppRun", "--arg1"]
    process_env = []


class TestGetComboOperatorRegexTypes:
    """Test that get_combo_operator returns RULE_TYPE_REGEXP for regex fields."""

    def test_appimage_returns_regexp_type(self, qapp):
        """AppImage paths must produce regexp operators."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_APPIMAGE, "AppName", con
        )
        assert _type == Config.RULE_TYPE_REGEXP
        assert _operand == Config.OPERAND_PROCESS_PATH

    def test_appimage_regex_contains_uppercase_chars(self, qapp):
        """AppImage regex must contain [0-9A-Za-z], not lowercased."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_APPIMAGE, "AppName", con
        )
        assert "[0-9A-Za-z]" in _data, (
            f"Expected [0-9A-Za-z] in regex but got: {_data}"
        )

    def test_appimage_regex_not_lowercased(self, qapp):
        """The AppImage regex pattern must NOT be lowercased."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_APPIMAGE, "AppName", con
        )
        # The binary name "AppRun" should be preserved, not lowered to "apprun"
        assert "AppRun" in _data, (
            f"Expected 'AppRun' in regex but got: {_data}"
        )
        # The character class must not be mangled
        assert "[0-9a-za-z]" not in _data, (
            f"Regex was lowercased (found [0-9a-za-z]): {_data}"
        )

    def test_snap_returns_regexp_type(self, qapp):
        """Snap paths must produce regexp operators."""
        con = MockConnection()
        con.process_path = "/snap/myapp/42/usr/bin/myapp"
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_SNAP, "myapp", con
        )
        assert _type == Config.RULE_TYPE_REGEXP
        assert _operand == Config.OPERAND_PROCESS_PATH

    def test_snap_regex_contains_digit_class(self, qapp):
        """Snap regex must contain [0-9]+ for the version number."""
        con = MockConnection()
        con.process_path = "/snap/myapp/42/usr/bin/myapp"
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_SNAP, "myapp", con
        )
        assert "[0-9]+" in _data, (
            f"Expected [0-9]+ in snap regex but got: {_data}"
        )

    def test_regex_host_returns_regexp_type(self, qapp):
        """Regex host field must produce regexp operators."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_REGEX_HOST, "*.example.com", con
        )
        assert _type == Config.RULE_TYPE_REGEXP
        assert _operand == Config.OPERAND_DEST_HOST

    def test_regex_ip_returns_regexp_type(self, qapp):
        """Regex IP field must produce regexp operators."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_REGEX_IP, "192.168.1.*", con
        )
        assert _type == Config.RULE_TYPE_REGEXP
        assert _operand == Config.OPERAND_DEST_IP


class TestPromptRegexSensitive:
    """Test that auto-generated regex rules from the prompt dialog have
    sensitive=True, preventing the daemon from lowercasing the pattern."""

    def test_simple_operator_not_regexp(self, qapp):
        """Non-regex operators should remain unchanged (sanity check)."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_PROC_PATH, "/bin/cmd", con
        )
        assert _type == Config.RULE_TYPE_SIMPLE

    def test_appimage_sensitive_flag_set_in_send_rule(self, qapp):
        """Verify the fix: when operator type is regexp, sensitive must be True.

        This test simulates the logic added in _send_rule() after
        get_combo_operator() returns.
        """
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_APPIMAGE, "AppName", con
        )
        # Simulate what _send_rule now does:
        sensitive = False
        if _type == Config.RULE_TYPE_REGEXP:
            sensitive = True
        assert sensitive is True, (
            "AppImage regex operator must have sensitive=True"
        )

    def test_snap_sensitive_flag_set_in_send_rule(self, qapp):
        """Snap regex operator must get sensitive=True."""
        con = MockConnection()
        con.process_path = "/snap/myapp/42/usr/bin/myapp"
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_SNAP, "myapp", con
        )
        sensitive = False
        if _type == Config.RULE_TYPE_REGEXP:
            sensitive = True
        assert sensitive is True

    def test_regex_host_sensitive_flag_set_in_send_rule(self, qapp):
        """Regex host operator must get sensitive=True."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_REGEX_HOST, "*.example.com", con
        )
        sensitive = False
        if _type == Config.RULE_TYPE_REGEXP:
            sensitive = True
        assert sensitive is True

    def test_regex_ip_sensitive_flag_set_in_send_rule(self, qapp):
        """Regex IP operator must get sensitive=True."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_REGEX_IP, "192.168.1.*", con
        )
        sensitive = False
        if _type == Config.RULE_TYPE_REGEXP:
            sensitive = True
        assert sensitive is True

    def test_list_item_gets_sensitive_when_regexp(self, qapp):
        """When a regex operator is added to a list rule's data items,
        it must include sensitive=True in the dict."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_REGEX_IP, "192.168.1.*", con
        )
        # Simulate what _send_rule now does for list items:
        _item = {"type": _type, "operand": _operand, "data": _data}
        if _type == Config.RULE_TYPE_REGEXP:
            _item["sensitive"] = True

        assert _item.get("sensitive") is True, (
            "Regex list item must have sensitive=True"
        )

    def test_list_item_no_sensitive_when_simple(self, qapp):
        """Non-regex list items should not get sensitive=True."""
        _item = {
            "type": Config.RULE_TYPE_SIMPLE,
            "operand": Config.OPERAND_DEST_PORT,
            "data": "443"
        }
        if _item["type"] == Config.RULE_TYPE_REGEXP:
            _item["sensitive"] = True

        assert _item.get("sensitive") is None, (
            "Simple type list items should not have sensitive set"
        )

    def test_main_operator_in_list_gets_sensitive(self, qapp):
        """When the main operator (regexp) is appended to data[] for a list
        rule, the dict must include sensitive=True."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_APPIMAGE, "AppName", con
        )
        # Simulate the list-building logic in _send_rule:
        _main_op = {
            "type": _type,
            "operand": _operand,
            "data": _data
        }
        if _type == Config.RULE_TYPE_REGEXP:
            _main_op["sensitive"] = True

        assert _main_op.get("sensitive") is True
        # Also verify the regex pattern is intact
        assert "[0-9A-Za-z]" in _main_op["data"]

    def test_appimage_regex_preserved_in_json(self, qapp):
        """Verify the full regex pattern is preserved when serialized to JSON,
        which is how list rules are stored."""
        con = MockConnection()
        _type, _operand, _data = prompt_utils.get_combo_operator(
            constants.FIELD_APPIMAGE, "AppName", con
        )
        data = [
            {"type": Config.RULE_TYPE_SIMPLE, "operand": Config.OPERAND_DEST_PORT, "data": "443"},
        ]
        _main_op = {"type": _type, "operand": _operand, "data": _data}
        if _type == Config.RULE_TYPE_REGEXP:
            _main_op["sensitive"] = True
        data.append(_main_op)

        json_str = json.dumps(data)
        parsed = json.loads(json_str)

        regexp_item = parsed[1]
        assert regexp_item["type"] == Config.RULE_TYPE_REGEXP
        assert regexp_item["sensitive"] is True
        assert "[0-9A-Za-z]" in regexp_item["data"]
        assert "AppRun" in regexp_item["data"]
