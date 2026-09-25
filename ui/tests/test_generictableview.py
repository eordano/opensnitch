#
# pytest -v tests/test_generictableview.py
#
# Tests for GenericTableView keyboard navigation methods.
# Verifies fix for issue #1592: NameError on viewport_row in onKeyDown.
#

from unittest.mock import MagicMock, patch, PropertyMock
from PyQt6 import QtWidgets, QtCore
from PyQt6.QtCore import Qt


class TestOnKeyDown:
    """Tests for GenericTableView.onKeyDown() -- issue #1592 fix."""

    def _make_view(self, qapp):
        """Create a GenericTableView with mocked internals for key handler testing."""
        from opensnitch.customwidgets.generictableview import GenericTableView

        # GenericTableView requires a parent widget
        parent = QtWidgets.QWidget()
        view = GenericTableView(parent)

        # Set up a mock model with queryOffset and queryLimit
        mock_model = MagicMock()
        mock_model.queryOffset = 0
        mock_model.queryLimit = 50
        mock_model.totalRowCount = 50

        # Mock selectionModel and its currentIndex
        mock_sel_model = MagicMock()
        mock_index = MagicMock()
        mock_index.row.return_value = 5
        mock_index.data.return_value = "row_5_data"
        mock_sel_model.currentIndex.return_value = mock_index
        view.selectionModel = MagicMock(return_value=mock_sel_model)

        # Patch model() to return our mock
        view.model = MagicMock(return_value=mock_model)

        # Set up scrollbar
        scrollbar = QtWidgets.QScrollBar()
        scrollbar.setMinimum(0)
        scrollbar.setMaximum(100)
        scrollbar.setValue(0)
        view.vScrollBar = scrollbar

        # Set viewport dimensions
        view.maxRowsInViewport = 20

        return view, parent

    def test_onKeyDown_no_crash(self, qapp):
        """onKeyDown must not raise NameError for viewport_row (issue #1592)."""
        view, parent = self._make_view(qapp)

        # This used to crash with: NameError: name 'viewport_row' is not defined
        view.onKeyDown()

    def test_onKeyDown_clears_selection_without_shift(self, qapp):
        """onKeyDown clears _rows_selection when shift is not pressed."""
        view, parent = self._make_view(qapp)
        view.shiftPressed = False
        view._rows_selection = {"old_data"}

        view.onKeyDown()

        # Old selection cleared, new one added
        assert "old_data" not in view._rows_selection
        assert "row_5_data" in view._rows_selection

    def test_onKeyDown_keeps_selection_with_shift(self, qapp):
        """onKeyDown preserves _rows_selection when shift is pressed."""
        view, parent = self._make_view(qapp)
        view.shiftPressed = True
        view._rows_selection = {"old_data"}

        view.onKeyDown()

        assert "old_data" in view._rows_selection
        assert "row_5_data" in view._rows_selection


class TestOnKeyUp:
    """Tests for GenericTableView.onKeyUp() to ensure it still works."""

    def _make_view(self, qapp):
        """Create a GenericTableView with mocked internals for key handler testing."""
        from opensnitch.customwidgets.generictableview import GenericTableView

        parent = QtWidgets.QWidget()
        view = GenericTableView(parent)

        mock_model = MagicMock()
        mock_model.queryOffset = 0
        mock_model.queryLimit = 50
        mock_model.totalRowCount = 50

        mock_sel_model = MagicMock()
        mock_index = MagicMock()
        mock_index.row.return_value = 5
        mock_index.data.return_value = "row_5_data"
        mock_sel_model.currentIndex.return_value = mock_index
        view.selectionModel = MagicMock(return_value=mock_sel_model)

        view.model = MagicMock(return_value=mock_model)

        scrollbar = QtWidgets.QScrollBar()
        scrollbar.setMinimum(0)
        scrollbar.setMaximum(100)
        scrollbar.setValue(10)
        view.vScrollBar = scrollbar

        view.maxRowsInViewport = 20

        return view, parent

    def test_onKeyUp_no_crash(self, qapp):
        """onKeyUp must not crash."""
        view, parent = self._make_view(qapp)

        view.onKeyUp()

    def test_onKeyUp_clears_selection_without_shift(self, qapp):
        """onKeyUp clears _rows_selection when shift is not pressed."""
        view, parent = self._make_view(qapp)
        view.shiftPressed = False
        view._rows_selection = {"old_data"}

        view.onKeyUp()

        assert "old_data" not in view._rows_selection
        assert "row_5_data" in view._rows_selection

    def test_onKeyUp_sets_viewport_row_tracking(self, qapp):
        """onKeyUp sets _last_row_selected and _first_row_selected."""
        view, parent = self._make_view(qapp)
        view._first_row_selected = None
        view._last_row_selected = None

        view.onKeyUp()

        # viewport_row = getMinViewportRow() + row = (scrollbar.value()+1) + 5 = 16
        expected_viewport_row = view.getViewportRowPos(5)
        assert view._last_row_selected == expected_viewport_row
        assert view._first_row_selected == expected_viewport_row
