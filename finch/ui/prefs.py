"""Preferences: look, podcasts and radio."""
import math
import os

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .. import themes  # noqa: E402

LOOK_KEYS = ('theme', 'scheme', 'accent')


def _rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _rr(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class ThemeCard(Gtk.Button):
    """A small drawing of Finch in a theme's colors: a sidebar, a list and the player bar."""

    def __init__(self, tid, settings):
        super().__init__(tooltip_text=themes.THEMES[tid]['label'])
        self.tid = tid
        self.add_css_class('flat')
        self.add_css_class('theme-card')
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_top=6, margin_bottom=6,
                      margin_start=6, margin_end=6)
        art = Gtk.DrawingArea(content_width=128, content_height=78)
        art.set_draw_func(self._draw)
        box.append(art)
        label = Gtk.Label(label=themes.THEMES[tid]['label'])
        label.add_css_class('theme-name')
        box.append(label)
        self.set_child(box)
        self.connect('clicked', lambda *_: settings.set('theme', tid))

    def _draw(self, _a, cr, w, h):
        win, head, accent, fg, _stage = themes.swatch(self.tid)
        _rr(cr, 0, 0, w, h, 10)
        cr.clip()
        cr.set_source_rgb(*_rgb(win))
        cr.paint()
        cr.set_source_rgb(*_rgb(head))
        cr.rectangle(0, 0, w * 0.3, h)
        cr.fill()
        cr.rectangle(0, h - 16, w, 16)
        cr.fill()
        for i in range(3):
            cr.set_source_rgba(*_rgb(fg), 0.18)
            _rr(cr, w * 0.36, 8 + i * 16, w * 0.58, 11, 3)
            cr.fill()
        cr.set_source_rgb(*_rgb(accent))
        cr.arc(w / 2, h - 8, 5, 0, 2 * math.pi)
        cr.fill()
        cr.rectangle(w * 0.62, h - 9, w * 0.3 * 0.5, 2)
        cr.fill()


class PrefsDialog(Adw.PreferencesDialog):
    def __init__(self, win):
        super().__init__(title='Preferences', search_enabled=False)
        self.win = win
        self.settings = win.settings
        self.add(self._look())
        self.add(self._podcasts())
        self.add(self._radio())
        self._sig = self.settings.connect('changed', lambda _s, k: k in ('theme', 'accent') and self._sync())
        self.connect('closed', lambda *_: self.settings.disconnect(self._sig))
        self._sync()

    def _switch(self, key, title, subtitle=None):
        row = Adw.SwitchRow(title=title, subtitle=subtitle or '', active=self.settings[key])
        row.connect('notify::active', lambda r, _p: self.settings.set(key, r.get_active()))
        return row

    def _combo(self, key, title, options, subtitle=None):
        ids = [o[0] for o in options]
        row = Adw.ComboRow(title=title, subtitle=subtitle or '', model=Gtk.StringList.new([o[1] for o in options]))
        row.set_selected(ids.index(self.settings[key]) if self.settings[key] in ids else 0)
        row.connect('notify::selected', lambda r, _p: self.settings.set(key, ids[r.get_selected()]))
        return row

    def _spin(self, key, title, lo, hi, step, subtitle=None):
        row = Adw.SpinRow(title=title, subtitle=subtitle or '',
                          adjustment=Gtk.Adjustment(lower=lo, upper=hi, step_increment=step,
                                                    page_increment=step * 3, value=self.settings[key]))
        row.connect('notify::value', lambda r, _p: self.settings.set(key, int(r.get_value())))
        return row

    def _look(self):
        page = Adw.PreferencesPage(title='Appearance', icon_name='applications-graphics-symbolic')
        g = Adw.PreferencesGroup(title='Theme')
        self.cards = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, max_children_per_line=5,
                                 min_children_per_line=2, column_spacing=4, row_spacing=4)
        for tid in themes.THEMES:
            self.cards.append(ThemeCard(tid, self.settings))
        g.add(self.cards)
        page.add(g)
        g = Adw.PreferencesGroup()
        self.scheme = self._combo('scheme', 'Light or dark',
                                  [('system', 'Follow system'), ('light', 'Light'), ('dark', 'Dark')])
        g.add(self.scheme)
        page.add(g)
        g = Adw.PreferencesGroup(title='Accent color')
        dots = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=10, min_children_per_line=5,
                           column_spacing=6, row_spacing=6)
        self.dots = []
        for color, name in themes.ACCENTS:
            b = Gtk.Button(tooltip_text=name, halign=Gtk.Align.CENTER)
            b.add_css_class('accent-dot')
            area = Gtk.DrawingArea(content_width=28, content_height=28)
            area.set_draw_func(self._dot, color)
            b.set_child(area)
            b.set_overflow(Gtk.Overflow.HIDDEN)
            b.color = color
            b.connect('clicked', lambda _b, c: self.settings.set('accent', c), color)
            dots.append(b)
            self.dots.append(b)
        g.add(dots)
        page.add(g)
        return page

    def _podcasts(self):
        page = Adw.PreferencesPage(title='Podcasts', icon_name='audio-input-microphone-symbolic')
        g = Adw.PreferencesGroup(title='New episodes')
        g.add(self._combo('refresh_hours', 'Check for new episodes',
                          [(1, 'Every hour'), (3, 'Every 3 hours'), (6, 'Every 6 hours'), (12, 'Every 12 hours'),
                           (24, 'Once a day'), (0, 'Only when I ask')]))
        g.add(self._combo('auto_download', 'Download new episodes',
                          [(0, 'Never'), (1, 'The newest one'), (3, 'The newest 3'), (5, 'The newest 5')],
                          'For each show, after checking'))
        page.add(g)
        g = Adw.PreferencesGroup(title='Listening')
        g.add(self._switch('continuous', 'Keep playing', 'Start the next episode in Up Next when one ends'))
        g.add(self._spin('skip_back', 'Skip back', 5, 120, 5, 'Seconds'))
        g.add(self._spin('skip_forward', 'Skip forward', 5, 300, 5, 'Seconds'))
        page.add(g)
        g = Adw.PreferencesGroup(title='Downloads')
        g.add(self._switch('delete_played', 'Delete after playing', 'Remove a download once it’s finished'))
        self.dir_row = Adw.ActionRow(title='Save downloads in')
        btn = Gtk.Button(icon_name='folder-open-symbolic', tooltip_text='Choose a folder', valign=Gtk.Align.CENTER)
        btn.add_css_class('flat')
        btn.connect('clicked', self._choose_dir)
        self.dir_row.add_suffix(btn)
        self.dir_row.set_activatable_widget(btn)
        self._show_dir()
        g.add(self.dir_row)
        page.add(g)
        return page

    def _radio(self):
        page = Adw.PreferencesPage(title='Radio', icon_name='finch-radio-symbolic')
        g = Adw.PreferencesGroup(title='Radio',
                                 description='Stations come from Radio Browser, an open directory kept by '
                                             'volunteers. Finch tells it when you play a station, which keeps '
                                             'its popular lists up to date.')
        row = Adw.EntryRow(title='Home country code (two letters, like US or GB)', text=self.settings['country'])
        row.connect('changed', lambda r: len(r.get_text().strip()) == 2 and r.get_text().strip().isalpha()
                    and self.settings.set('country', r.get_text().strip().upper()))
        g.add(row)
        page.add(g)
        return page

    def _dot(self, _a, cr, w, h, color):
        if color:
            cr.set_source_rgb(*_rgb(color))
            cr.arc(w / 2, h / 2, w / 2, 0, 2 * math.pi)
            cr.fill()
            return
        win, _head, accent, _fg, _st = themes.swatch(self.settings['theme'])
        cr.set_source_rgb(*_rgb(accent))
        cr.arc(w / 2, h / 2, w / 2, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*_rgb(win))
        cr.arc(w / 2, h / 2, w / 2, -0.785, 2.356)
        cr.fill()

    def _sync(self):
        c = self.cards.get_first_child()
        while c:
            card = c.get_child()
            (card.add_css_class if card.tid == self.settings['theme'] else card.remove_css_class)('selected')
            c = c.get_next_sibling()
        for d in self.dots:
            (d.add_css_class if d.color == self.settings['accent'] else d.remove_css_class)('selected')
            d.get_child().queue_draw()
        own = themes.THEMES[self.settings['theme']]['dark'] is None
        self.scheme.set_sensitive(own)
        self.scheme.set_subtitle('' if own else 'Set by the theme')

    def _show_dir(self):
        self.dir_row.set_subtitle(self.settings.download_dir().replace(os.path.expanduser('~'), '~', 1))

    def _choose_dir(self, *_):
        dlg = Gtk.FileDialog(title='Save downloads in')

        def done(d, res):
            try:
                f = d.select_folder_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                self.settings.set('download_dir', f.get_path())
                self._show_dir()
        dlg.select_folder(self.win, None, done)


Gio  # imported for callers
