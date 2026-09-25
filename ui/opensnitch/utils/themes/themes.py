import os.path
import sys, glob
from PyQt6 import QtCore, QtGui

from opensnitch.config import Config

# WA for #1373
qtm_home = "{0}/.qt_material/theme/".format(QtCore.QDir.homePath())
if qtm_home not in QtCore.QDir.searchPaths("icon"):
    QtCore.QDir.addSearchPath("icon", qtm_home)

class Themes():
    """Change GUI's appearance.

    "Light" and "Dark" are always available, applied via the native Qt
    color scheme (Qt >= 6.8) with a Fusion palette fallback for older Qt.
    Additional themes come from the qt-material lib when installed:
    https://github.com/dunderlab/qt-material
    """
    THEMES_PATH = [
        os.path.expanduser("~/.config/opensnitch/"),
        os.path.dirname(sys.modules[__name__].__file__) + "/../.."
    ]
    __instance = None

    BUILTIN_THEMES = ["Light", "Dark"]

    AVAILABLE = False
    IS_DARK = False
    try:
        from qt_material import apply_stylesheet as qtmaterial_apply_stylesheet
        from qt_material import list_themes as qtmaterial_themes
        AVAILABLE = True
    except Exception:
        print("qt-material themes not available. Install qt-material if you want more themes: pip3 install qt-material.")

    @staticmethod
    def instance():
        if Themes.__instance == None:
            Themes.__instance = Themes()
        return Themes.__instance

    def __init__(self):
        self._cfg = Config.get()
        theme = self._cfg.getInt(self._cfg.DEFAULT_THEME, 0)

    def available(self):
        # built-in Light/Dark always work; qt-material only adds more themes
        return True

    def qtmaterial_available(self):
        return Themes.AVAILABLE

    def get_saved_theme(self):
        theme = self._cfg.getSettings(self._cfg.DEFAULT_THEME)
        theme_density = self._cfg.getSettings(self._cfg.DEFAULT_THEME_DENSITY_SCALE)
        if theme_density == "" or theme_density == None:
            theme_density = '0'

        try:
            if theme != "" and theme != None:
                themes_list = self.list_themes()
                for idx, tml in enumerate(themes_list):
                    if theme in tml:
                        # 0 == System
                        return idx+1, theme, theme_density
        except Exception as e:
            print("Themes.get_saved_theme() error:", e)
        return 0, "", theme_density

    def save_theme(self, theme_idx, theme, density_scale):
        self._cfg.setSettings(self._cfg.DEFAULT_THEME_DENSITY_SCALE, density_scale)
        if theme_idx == 0:
            self._cfg.setSettings(self._cfg.DEFAULT_THEME, "")
        else:
            self._cfg.setSettings(self._cfg.DEFAULT_THEME, theme)

    def load_theme(self, app):
        try:
            theme_idx, theme_name, theme_density = self.get_saved_theme()
            if theme_name == "":
                return
            if theme_name in Themes.BUILTIN_THEMES or theme_name == "System":
                self._apply_builtin(app, theme_name)
                return
            if not Themes.AVAILABLE:
                return

            invert = "light" in theme_name
            fname = os.path.basename(theme_name)
            Themes.IS_DARK = fname.startswith("dark")

            print("Using theme:", theme_idx, theme_name, "inverted:", invert, "dark:", Themes.IS_DARK)
            # TODO: load {theme}.xml.extra and .xml.css for further
            # customizations.
            extra_opts = {
                'density_scale': theme_density
            }
            Themes.qtmaterial_apply_stylesheet(app, theme=theme_name,  invert_secondary=invert, extra=extra_opts)
        except Exception as e:
            print("Themes.load_theme() exception:", e)

    def change_theme(self, window, theme_name, extra={}):
        try:
            app = QtGui.QGuiApplication.instance()
            if theme_name in Themes.BUILTIN_THEMES or theme_name == "System":
                if app is not None and hasattr(app, "setStyleSheet"):
                    # drop any qt-material stylesheet before going native
                    app.setStyleSheet("")
                self._apply_builtin(app, theme_name)
                return

            invert = "light" in theme_name
            fname = os.path.basename(theme_name)
            Themes.IS_DARK = fname.startswith("dark")

            Themes.qtmaterial_apply_stylesheet(window, theme=theme_name,  invert_secondary=invert, extra=extra)
        except Exception as e:
            print("Themes.change_theme() exception:", e, " - ", window, theme_name)

    def _apply_builtin(self, app, theme_name):
        """Apply Light/Dark via the native color scheme, or follow the system."""
        Themes.IS_DARK = theme_name == "Dark"
        hints = QtGui.QGuiApplication.styleHints()
        if hasattr(hints, "setColorScheme"):
            if theme_name == "Dark":
                hints.setColorScheme(QtCore.Qt.ColorScheme.Dark)
            elif theme_name == "Light":
                hints.setColorScheme(QtCore.Qt.ColorScheme.Light)
            else:
                if hasattr(hints, "unsetColorScheme"):
                    hints.unsetColorScheme()
                else:
                    hints.setColorScheme(QtCore.Qt.ColorScheme.Unknown)
            if theme_name == "System" or Themes.is_dark() == Themes.IS_DARK:
                return
            # the platform theme ignored the request; fall through to the
            # manual palette below

        # Qt < 6.8, or platforms without color-scheme support: emulate with
        # a Fusion palette
        if app is None or not hasattr(app, "setPalette"):
            return
        if theme_name == "Dark":
            app.setStyle("Fusion")
            base = QtGui.QColor(35, 38, 41)
            window = QtGui.QColor(49, 54, 59)
            # construct from the button color so Qt derives the shade roles
            # (light/midlight/mid/dark/shadow) as dark variants too
            pal = QtGui.QPalette(window)
            text = QtGui.QColor(224, 224, 224)
            highlight = QtGui.QColor(61, 118, 194)
            pal.setColor(QtGui.QPalette.ColorRole.Window, window)
            pal.setColor(QtGui.QPalette.ColorRole.WindowText, text)
            pal.setColor(QtGui.QPalette.ColorRole.Base, base)
            pal.setColor(QtGui.QPalette.ColorRole.AlternateBase, window)
            pal.setColor(QtGui.QPalette.ColorRole.ToolTipBase, base)
            pal.setColor(QtGui.QPalette.ColorRole.ToolTipText, text)
            pal.setColor(QtGui.QPalette.ColorRole.Text, text)
            pal.setColor(QtGui.QPalette.ColorRole.Button, window)
            pal.setColor(QtGui.QPalette.ColorRole.ButtonText, text)
            pal.setColor(QtGui.QPalette.ColorRole.Highlight, highlight)
            pal.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(255, 255, 255))
            pal.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(88, 166, 255))
            pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, QtGui.QColor(128, 128, 128))
            pal.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(128, 128, 128))
            app.setPalette(pal)
        else:
            app.setPalette(app.style().standardPalette())

    @staticmethod
    def is_dark():
        """True when the effective palette is dark, regardless of theme source."""
        pal = QtGui.QGuiApplication.palette()
        return pal.color(QtGui.QPalette.ColorRole.Window).lightness() < 128

    # Semantic status colors, readable on both light and dark palettes.
    @staticmethod
    def ok_color():
        return "#66bb6a" if Themes.is_dark() else "#2e7d32"

    @staticmethod
    def error_color():
        return "#ef5350" if Themes.is_dark() else "#c62828"

    @staticmethod
    def warn_color():
        return "#ffa726" if Themes.is_dark() else "#ce5c00"

    @staticmethod
    def success_bg_color():
        return "#1e4620" if Themes.is_dark() else "#d7f0dd"

    # De-emphasised text. The prompt used to hardcode #888/#666, which are
    # picked for a dark palette and turn into low-contrast grey-on-white under a
    # light one; these track the palette like the status colors above.
    @staticmethod
    def muted_color():
        return "#9aa0a6" if Themes.is_dark() else "#5f6368"

    @staticmethod
    def faint_color():
        return "#6e747a" if Themes.is_dark() else "#80868b"

    @staticmethod
    def attention_color():
        """Preview text when the prompt is in "once, no rule" mode."""
        return "#e6a2a2" if Themes.is_dark() else "#a14545"

    @staticmethod
    def prompt_stylesheet():
        """The connection prompt's entire look, in one place.

        Applied once to the dialog and inherited by children, instead of a
        setStyleSheet() call per widget. Selectors key on a `promptRole` dynamic
        property rather than objectName: most of the styled widgets come from
        res/prompt.ui and their object names are load-bearing (click routing and
        the "#warning-checksum" selector), so renaming them to style them breaks
        the dialog. Note Qt Style
        Sheets implement only a subset of CSS: text-transform and letter-spacing
        are *not* supported and were silently doing nothing when this lived
        inline, so the small-caps look of the grid headers is applied through
        QFont by the dialog rather than declared here.
        """
        return """
            QLabel[promptRole="preview"] {
                color: %(muted)s;
                font-style: italic;
                font-size: 12px;
                padding: 4px 8px;
            }
            QLabel[promptRole="preview"][once="true"] {
                color: %(attention)s;
            }
            QLabel[promptRole="header"] {
                color: %(muted)s;
                font-size: 10px;
                font-weight: 600;
                padding: 0px 4px;
            }
            QLabel[promptRole="value"] {
                font-size: 11px;
                padding: 2px 4px;
            }
            QLabel[promptRole="dash"], QLabel[promptRole="once"] {
                color: %(faint)s;
                font-size: 11px;
                padding: 2px 4px;
            }
        """ % {
            "muted": Themes.muted_color(),
            "faint": Themes.faint_color(),
            "attention": Themes.attention_color(),
        }

    def list_local_themes(self):
        themes = []
        if not Themes.AVAILABLE:
            return themes

        try:
            for tdir in self.THEMES_PATH:
                if not os.path.isdir(tdir):
                    continue
                themes += glob.glob(tdir + "/themes/*.xml")
        except Exception:
            pass
        finally:
            return themes

    def list_themes(self):
        themes = list(Themes.BUILTIN_THEMES)
        themes += self.list_local_themes()
        if Themes.AVAILABLE:
            themes += Themes.qtmaterial_themes()
        return themes
