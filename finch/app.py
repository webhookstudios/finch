import os
import sys

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import __version__  # noqa: E402

APP_ID = 'io.github.webhookstudios.Finch'
HERE = os.path.dirname(os.path.abspath(__file__))

SHORTCUTS = [
    ('Listening', [('space', 'Play or pause'), ('Left', 'Skip back'), ('Right', 'Skip forward')]),
    ('Finding', [('<Ctrl>f', 'Search'), ('<Ctrl>r', 'Check for new episodes'),
                 ('<Ctrl>n', 'Add a podcast by its address')]),
    ('Window', [('<Ctrl>comma', 'Preferences'), ('<Ctrl>question', 'Keyboard shortcuts'), ('<Ctrl>q', 'Quit')]),
]


class FinchApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.win = None
        GLib.set_application_name('Finch')

    def do_startup(self):
        Adw.Application.do_startup(self)
        from . import sedge
        from .settings import Settings
        from .themes import ThemeManager
        sedge.apply()
        theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        local = os.path.join(os.path.dirname(HERE), 'data', 'icons')
        if os.path.isdir(local):
            theme.add_search_path(local)
        self.settings = Settings()
        self.themes = ThemeManager(self.settings)
        for name, cb in (('preferences', self._prefs), ('shortcuts', self._shortcuts), ('about', self._about),
                         ('quit', lambda *_: self._quit())):
            a = Gio.SimpleAction.new(name, None)
            a.connect('activate', cb)
            self.add_action(a)
        for action, accels in (('app.quit', ['<Ctrl>q']), ('app.preferences', ['<Ctrl>comma']),
                               ('app.shortcuts', ['<Ctrl>question']), ('win.refresh', ['<Ctrl>r']),
                               ('win.search', ['<Ctrl>f']), ('win.add-feed', ['<Ctrl>n'])):
            self.set_accels_for_action(action, accels)

    def _window(self):
        if not self.win:
            from .ui.window import FinchWindow
            from .mpris import Mpris
            self.win = FinchWindow(self)
            try:
                self.win.mpris = Mpris(self, self.win)
            except Exception:  # media keys are a nicety; never let them stop the app
                self.win.mpris = None
        return self.win

    def do_activate(self):
        self._window().present()

    def _quit(self):
        if self.win:
            self.win.close()
        self.quit()

    def _prefs(self, *_):
        from .ui.prefs import PrefsDialog
        PrefsDialog(self._window()).present(self._window())

    def _shortcuts(self, *_):
        dlg = Adw.ShortcutsDialog()
        for title, items in SHORTCUTS:
            sec = Adw.ShortcutsSection(title=title)
            for accel, label in items:
                sec.add(Adw.ShortcutsItem(title=label, accelerator=accel))
            dlg.add(sec)
        dlg.present(self._window())

    def _about(self, *_):
        Adw.AboutDialog(
            application_name='Finch', application_icon=APP_ID, version=__version__,
            developer_name='webhookstudios', license_type=Gtk.License.GPL_2_0,
            website='https://webhookstudioapps.netlify.app',
            issue_url='https://github.com/webhookstudios/finch/issues',
            comments='Podcasts and internet radio, in one place.',
            copyright='© 2026 webhookstudios',
            ).present(self._window())


def main():
    return FinchApp().run(sys.argv)
