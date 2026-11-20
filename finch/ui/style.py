"""The quick look picker at the top of the main menu: theme, accent color, and light or dark."""
import math

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk  # noqa: E402

from .. import themes  # noqa: E402

SCHEMES = (('system', 'Follow the system', 'emblem-system-symbolic'),
           ('light', 'Light', 'weather-clear-symbolic'),
           ('dark', 'Dark', 'weather-clear-night-symbolic'))


def _rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _swatch(tip, draw, data):
    b = Gtk.Button(tooltip_text=tip, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, focus_on_click=False)
    b.add_css_class('swatch')
    b.add_css_class('flat')
    b.set_overflow(Gtk.Overflow.HIDDEN)
    area = Gtk.DrawingArea(content_width=30, content_height=30)
    area.set_draw_func(draw, data)
    b.set_child(area)
    return b


def _grid():
    return Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=6,
                       column_spacing=6, row_spacing=6, homogeneous=True)


class StylePicker(Gtk.Box):
    def __init__(self, settings):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.settings = settings
        self.add_css_class('style-picker')

        self.schemes = Gtk.Box(css_classes=['linked'], halign=Gtk.Align.CENTER)
        self.scheme_btns = {}
        group = None
        for key, tip, icon in SCHEMES:
            b = Gtk.ToggleButton(icon_name=icon, tooltip_text=tip, focus_on_click=False, group=group)
            b.add_css_class('scheme-btn')
            group = group or b
            b.connect('toggled', lambda btn, k=key: btn.get_active() and self.settings.set('scheme', k))
            self.schemes.append(b)
            self.scheme_btns[key] = b
        self.append(self.schemes)

        self.append(self._label('Theme'))
        self.theme_grid = _grid()
        self.theme_btns = {}
        for tid, theme in themes.THEMES.items():
            b = _swatch(theme['label'], self._draw_theme, tid)
            b.connect('clicked', lambda _b, t=tid: self.settings.set('theme', t))
            self.theme_grid.append(b)
            self.theme_btns[tid] = b
        self.append(self.theme_grid)

        self.append(self._label('Color'))
        self.accent_grid = _grid()
        self.accent_btns = {}
        for color, name in themes.ACCENTS:
            b = _swatch(name, self._draw_accent, color)
            b.connect('clicked', lambda _b, c=color: self.settings.set('accent', c))
            self.accent_grid.append(b)
            self.accent_btns[color] = b
        self.append(self.accent_grid)

        self._sig = settings.connect('changed', lambda _s, k: k in ('theme', 'accent', 'scheme') and self.sync())
        self.sync()

    def _label(self, text):
        lab = Gtk.Label(label=text, xalign=0, margin_start=4)
        lab.add_css_class('pick-label')
        return lab

    def _draw_theme(self, _a, cr, w, h, tid):
        win, _head, accent, _fg, _stage = themes.swatch(tid)
        cr.arc(w / 2, h / 2, w / 2, 0, 2 * math.pi)
        cr.clip()
        cr.set_source_rgb(*_rgb(win))
        cr.paint()
        cr.set_source_rgb(*_rgb(accent))
        cr.move_to(w / 2, h / 2)
        cr.arc(w / 2, h / 2, w / 2, -math.pi / 4, 3 * math.pi / 4)
        cr.close_path()
        cr.fill()

    def _draw_accent(self, _a, cr, w, h, color):
        if not color:
            # The theme's own color: half its accent, half its window.
            self._draw_theme(_a, cr, w, h, self.settings['theme'])
            return
        cr.set_source_rgb(*_rgb(color))
        cr.arc(w / 2, h / 2, w / 2, 0, 2 * math.pi)
        cr.fill()

    def sync(self):
        for tid, b in self.theme_btns.items():
            (b.add_css_class if tid == self.settings['theme'] else b.remove_css_class)('selected')
        for color, b in self.accent_btns.items():
            (b.add_css_class if color == self.settings['accent'] else b.remove_css_class)('selected')
            b.get_child().queue_draw()
        own = themes.THEMES.get(self.settings['theme'], themes.THEMES['sedge'])['dark'] is None
        self.schemes.set_sensitive(own)
        self.schemes.set_tooltip_text(None if own else 'This theme sets light or dark itself')
        btn = self.scheme_btns.get(self.settings['scheme'])
        if btn and not btn.get_active():
            btn.set_active(True)
