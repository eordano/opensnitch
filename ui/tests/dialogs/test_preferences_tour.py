from PyQt6 import QtGui, QtCore, QtTest
from opensnitch.dialogs.preferences import PreferencesDialog


def test_tour_follows_page_steps_without_changing_settings(qapp, qtbot):
    prefs = PreferencesDialog(appicon=QtGui.QIcon())
    qtbot.addWidget(prefs)
    prefs.show()
    qapp.processEvents()
    prefs.listWidget.setCurrentRow(0)
    before = prefs.comboUITheme.currentIndex()
    prefs.helpButton.click()
    tour = prefs._settings_tour
    assert prefs.helpButton.text() == 'Tour'
    assert tour.isVisible() and tour.steps and tour.highlight.isVisible()
    assert 'Step 1 of' in tour.heading.text()
    tour.next.click()
    assert tour.index == 1
    tour.back.click()
    assert tour.index == 0
    after = prefs.comboUITheme.currentIndex()
    assert after == before
    QtTest.QTest.keyClick(tour, QtCore.Qt.Key.Key_Escape)
    assert not tour.isVisible() and not tour.highlight.isVisible()
    prefs.listWidget.setCurrentRow(6)
    prefs.helpButton.click()
    tour = prefs._settings_tour
    assert tour.page is prefs.stackedWidget.currentWidget()
    assert 'Storage' in tour.windowTitle()
    prefs.listWidget.setCurrentRow(0)
    assert not tour.isVisible()
