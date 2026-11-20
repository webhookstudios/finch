"""Color themes and the app's own stylesheet.

Every theme is a full palette. The Sedge theme follows the system's light or dark choice
(or the one picked in Preferences); the others carry their own. The palette is written as
libadwaita CSS variables one step above the Sedge kit, so the whole app takes it on.
"""
import gi

gi.require_version('Adw', '1')
gi.require_version('Gtk', '4.0')
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

THEMES = {
    'sedge': {
        'label': 'Sedge', 'dark': None,
        'light_colors': dict(accent_bg='#247268', accent='#1d665d', window_bg='#eef2ec', window_fg='#1e2b26',
                      view_bg='#f8f9f5', headerbar_bg='#e5eae2', sidebar_bg='#e5eae2', card_bg='#f8f9f5',
                      popover_bg='#fbfcf9', dialog_bg='#f3f5f0', muted='#52615a', line='#c9d4cc',
                      stage='#121915'),
        'dark_colors': dict(accent_bg='#287f74', accent='#74c7ba', window_bg='#18201c', window_fg='#e4ebe6',
                     view_bg='#1d2621', headerbar_bg='#212b26', sidebar_bg='#1f2924',
                     card_bg='rgb(228 235 230 / 6%)', popover_bg='#26312b', dialog_bg='#212b26',
                     muted='#9aaba2', line='#33413a', stage='#0d1210'),
    },
    'ember': {
        'label': 'Ember', 'dark': True,
        'colors': dict(accent_bg='#c8602a', accent='#f0a072', window_bg='#1c1714', window_fg='#f1e6dc',
                       view_bg='#211a16', headerbar_bg='#261e19', sidebar_bg='#231c17',
                       card_bg='rgb(241 230 220 / 6%)', popover_bg='#2c231d', dialog_bg='#261e19',
                       muted='#b3a294', line='#3d3129', stage='#0e0b09'),
    },
    'lantern': {
        'label': 'Lantern', 'dark': True,
        'colors': dict(accent_bg='#d4951c', accent_fg='#1a1206', accent='#f2c15a', window_bg='#000000',
                       window_fg='#f7f2e6', view_bg='#070605', headerbar_bg='#0b0a08', sidebar_bg='#0b0a08',
                       card_bg='rgb(247 242 230 / 7%)', popover_bg='#15130f', dialog_bg='#0f0d0b',
                       muted='#b9ae96', line='#2b2720', stage='#000000'),
    },
    'midnight': {
        'label': 'Midnight', 'dark': True,
        'colors': dict(accent_bg='#3f6fd1', accent='#8fb1f5', window_bg='#121725', window_fg='#e2e8f5',
                       view_bg='#161c2c', headerbar_bg='#1a2133', sidebar_bg='#182030',
                       card_bg='rgb(226 232 245 / 6%)', popover_bg='#1f2840', dialog_bg='#1a2133',
                       muted='#93a0bb', line='#2a3550', stage='#080b13'),
    },
    'moss': {
        'label': 'Moss', 'dark': True,
        'colors': dict(accent_bg='#617f28', accent='#b5d27a', window_bg='#171a12', window_fg='#e6eadb',
                       view_bg='#1b1f15', headerbar_bg='#20251a', sidebar_bg='#1e2218',
                       card_bg='rgb(230 234 219 / 6%)', popover_bg='#262c1f', dialog_bg='#20251a',
                       muted='#a4ad92', line='#343b29', stage='#0b0d08'),
    },
    'dusk': {
        'label': 'Dusk', 'dark': True,
        'colors': dict(accent_bg='#a8466f', accent='#eb9bbd', window_bg='#1d1620', window_fg='#efe3ee',
                       view_bg='#221a26', headerbar_bg='#271e2b', sidebar_bg='#241c28',
                       card_bg='rgb(239 227 238 / 6%)', popover_bg='#2d2332', dialog_bg='#271e2b',
                       muted='#b49fb2', line='#3d3042', stage='#0f0b11'),
    },
    'slate': {
        'label': 'Slate', 'dark': True,
        'colors': dict(accent_bg='#4f6f8f', accent='#a7c1db', window_bg='#1a1c1f', window_fg='#e5e7ea',
                       view_bg='#1f2125', headerbar_bg='#24272b', sidebar_bg='#212428',
                       card_bg='rgb(229 231 234 / 6%)', popover_bg='#2a2d32', dialog_bg='#24272b',
                       muted='#9da3ab', line='#363a40', stage='#0c0d0f'),
    },
    'meadow': {
        'label': 'Meadow', 'dark': False,
        'colors': dict(accent_bg='#4f7a28', accent='#3f6420', window_bg='#f1f4e8', window_fg='#22281a',
                       view_bg='#f9fbf3', headerbar_bg='#e6ebd8', sidebar_bg='#e6ebd8', card_bg='#f9fbf3',
                       popover_bg='#fcfdf8', dialog_bg='#f4f7ec', muted='#5c654c', line='#d2dac0',
                       stage='#151a10'),
    },
    'sky': {
        'label': 'Sky', 'dark': False,
        'colors': dict(accent_bg='#2f6db5', accent='#245a98', window_bg='#eef3f8', window_fg='#1b2633',
                       view_bg='#f7fafd', headerbar_bg='#e2eaf3', sidebar_bg='#e2eaf3', card_bg='#f7fafd',
                       popover_bg='#fbfdff', dialog_bg='#f2f6fa', muted='#55657a', line='#cbd7e4',
                       stage='#0f151c'),
    },
    'blossom': {
        'label': 'Blossom', 'dark': False,
        'colors': dict(accent_bg='#b04a75', accent='#953b61', window_bg='#f8eff2', window_fg='#2e1f25',
                       view_bg='#fdf7f9', headerbar_bg='#f0e2e7', sidebar_bg='#f0e2e7', card_bg='#fdf7f9',
                       popover_bg='#fffafc', dialog_bg='#faf2f5', muted='#6e5860', line='#e3cfd6',
                       stage='#1a1215'),
    },
    'driftwood': {
        'label': 'Driftwood', 'dark': False,
        'colors': dict(accent_bg='#a4532c', accent='#8e4522', window_bg='#f3ede4', window_fg='#2f2620',
                       view_bg='#faf7f1', headerbar_bg='#ebe3d7', sidebar_bg='#ebe3d7', card_bg='#faf7f1',
                       popover_bg='#fdfbf7', dialog_bg='#f6f1ea', muted='#6f6156', line='#d9cdbd',
                       stage='#1a1512'),
    },
    'birch': {
        'label': 'Birch', 'dark': False,
        'colors': dict(accent_bg='#3b5a4a', accent='#2f4a3c', window_bg='#f4f5f3', window_fg='#1f2421',
                       view_bg='#fbfbfa', headerbar_bg='#eaecea', sidebar_bg='#eaecea', card_bg='#fbfbfa',
                       popover_bg='#ffffff', dialog_bg='#f7f8f6', muted='#5d655f', line='#d3d8d4',
                       stage='#111312'),
    },
}

ACCENTS = [
    ('', 'Theme color'),
    ('#247268', 'Teal'),
    ('#c8602a', 'Ember'),
    ('#c9a227', 'Amber'),
    ('#617f28', 'Moss'),
    ('#3f6fd1', 'Blue'),
    ('#7a55c4', 'Violet'),
    ('#a8466f', 'Rose'),
    ('#b4412f', 'Brick'),
    ('#5b6770', 'Graphite'),
]


def _rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return '#' + ''.join(f'{max(0, min(255, round(c))):02x}' for c in rgb)


def _mix(a, b, t):
    ra, rb = _rgb(a), _rgb(b)
    return _hex(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def _luma(hex_color):
    r, g, b = (c / 255 for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def palette(theme_id, dark_now):
    """The colors to use for a theme, and whether they are dark."""
    theme = THEMES.get(theme_id, THEMES['sedge'])
    if theme['dark'] is None:
        return dict(theme['dark_colors' if dark_now else 'light_colors']), dark_now
    return dict(theme['colors']), theme['dark']


def swatch(theme_id):
    """Three colors for a theme's preview card: window, header, accent."""
    pal, dark = palette(theme_id, False)
    return pal['window_bg'], pal['headerbar_bg'], pal['accent_bg'], pal['window_fg'], pal['stage']


def build_css(settings, dark_now):
    pal, dark = palette(settings['theme'], dark_now)
    accent = settings['accent']
    if accent:
        pal['accent_bg'] = accent
        pal['accent'] = _mix(accent, '#ffffff', 0.45) if dark else _mix(accent, '#000000', 0.12)
        pal['accent_fg'] = '#1a1206' if _luma(accent) > 0.55 else '#ffffff'
    fg = pal['window_fg']
    osd = _rgb(pal['popover_bg'] if dark else pal['window_bg'])
    alpha = settings['controls_opacity']
    v = {
        'accent-bg-color': pal['accent_bg'],
        'accent-fg-color': pal.get('accent_fg', '#ffffff'),
        'accent-color': pal['accent'],
        'window-bg-color': pal['window_bg'],
        'window-fg-color': fg,
        'view-bg-color': pal['view_bg'],
        'view-fg-color': fg,
        'headerbar-bg-color': pal['headerbar_bg'],
        'headerbar-fg-color': fg,
        'headerbar-backdrop-color': pal['window_bg'],
        'sidebar-bg-color': pal['sidebar_bg'],
        'sidebar-fg-color': fg,
        'sidebar-backdrop-color': pal['sidebar_bg'],
        'secondary-sidebar-bg-color': pal['sidebar_bg'],
        'secondary-sidebar-fg-color': fg,
        'card-bg-color': pal['card_bg'],
        'card-fg-color': fg,
        'dialog-bg-color': pal['dialog_bg'],
        'dialog-fg-color': fg,
        'popover-bg-color': pal['popover_bg'],
        'popover-fg-color': fg,
        'thumbnail-bg-color': pal['popover_bg'],
        'thumbnail-fg-color': fg,
        'sedge-muted': pal['muted'],
        'sedge-line': pal['line'],
        'fs-stage': pal['stage'],
        'fs-osd-bg': f'rgb({osd[0]} {osd[1]} {osd[2]} / {round(alpha * 100)}%)',
        'fs-osd-fg': fg,
        'fs-glow-a': pal['accent_bg'],
        'fs-glow-b': pal['accent'],
        'fs-radius': f"{settings['radius']}px",
        'fs-seek-h': f"{settings['seek_height']}px",
    }
    css = ':root {\n' + ''.join(f'  --{k}: {val};\n' for k, val in v.items()) + '}\n'
    for name in ('accent_bg_color', 'accent_fg_color', 'accent_color', 'window_bg_color', 'window_fg_color',
                 'view_bg_color', 'view_fg_color', 'headerbar_bg_color', 'headerbar_fg_color',
                 'popover_bg_color', 'popover_fg_color', 'card_bg_color', 'card_fg_color',
                 'dialog_bg_color', 'dialog_fg_color', 'sidebar_bg_color', 'sidebar_fg_color'):
        css += f'@define-color {name} {v[name.replace("_", "-")]};\n'
    return css, dark


APP_CSS = '''
.page-title { font-family: "Young Serif", serif; font-size: 26px; }
.show-title { font-family: "Young Serif", serif; font-size: 24px; }
.section-title { font-family: "Young Serif", serif; font-size: 18px; }
.art { border-radius: 10px; background-color: alpha(currentColor, 0.08); }
.art-large { border-radius: 16px; background-color: alpha(currentColor, 0.08); box-shadow: 0 8px 24px rgb(0 0 0 / 22%); }
.tile { padding: 6px; border-radius: 16px; }
.tile:hover { background-color: alpha(currentColor, 0.06); }
.tile:hover .tile-name { color: var(--accent-color); }
.tile-name { font-weight: 600; }
.badge-new {
  background-color: var(--accent-bg-color); color: var(--accent-fg-color);
  border-radius: 999px; padding: 1px 7px; font-size: 0.75em; font-weight: 700;
}
.badge-live {
  background-color: var(--destructive-bg-color); color: white;
  border-radius: 6px; padding: 1px 6px; font-size: 0.72em; font-weight: 800; letter-spacing: 0.06em;
}
.chip { border-radius: 999px; padding: 4px 12px; min-height: 0; }
.chip.selected { background-color: var(--accent-bg-color); color: var(--accent-fg-color); }
.episode-row.played .ep-title { opacity: 0.55; }
.ep-progress trough { min-height: 3px; border-radius: 999px; }
.ep-progress progress { min-height: 3px; border-radius: 999px; background-color: var(--accent-bg-color); }

.playerbar {
  background-color: var(--headerbar-bg-color);
  border-top: 1px solid var(--sedge-line);
  padding: 8px 14px;
}
.playerbar .bar-title { font-weight: 700; }
.playerbar button.play { min-width: 44px; min-height: 44px; border-radius: 999px; }
.time { font-feature-settings: "tnum"; font-size: 0.86em; opacity: 0.85; min-width: 48px; }
scale.seek trough { min-height: var(--fs-seek-h); border-radius: 999px; background-color: alpha(currentColor, 0.18); }
scale.seek highlight { min-height: var(--fs-seek-h); border-radius: 999px; background-color: var(--accent-bg-color); }
scale.seek slider { min-width: 14px; min-height: 14px; margin: -6px; background-color: var(--accent-bg-color); opacity: 0; transition: opacity 150ms ease-out; }
scale.seek:hover slider, scale.seek:active slider { opacity: 1; }
scale.vol trough { min-height: 4px; border-radius: 999px; }
scale.vol highlight { min-height: 4px; border-radius: 999px; background-color: var(--accent-bg-color); }
.vol-pct { opacity: 0; transition: opacity 180ms ease-out; font-weight: 700; font-feature-settings: "tnum"; font-size: 0.86em; margin-left: 4px; }
.vol-pct.shown { opacity: 1; }

.theme-card { border-radius: 14px; padding: 0; border: 2px solid transparent; }
.theme-card.selected { border-color: var(--accent-bg-color); }
.theme-name { font-size: 0.9em; }
.accent-dot { min-width: 28px; min-height: 28px; border-radius: 999px; padding: 0; }
.accent-dot.selected { box-shadow: 0 0 0 3px var(--window-bg-color), 0 0 0 5px var(--window-fg-color); }
.notes { font-size: 0.95em; }
.style-picker { padding: 6px 4px 2px 4px; }
.style-picker .pick-label { font-size: 0.85em; font-weight: 700; opacity: 0.7; }
.swatch { min-width: 30px; min-height: 30px; padding: 0; border-radius: 999px; }
.swatch.selected { box-shadow: 0 0 0 2px var(--popover-bg-color), 0 0 0 4px var(--accent-bg-color); }
.scheme-btn { padding: 4px 10px; }
'''


class ThemeManager:
    """Keeps the theme stylesheet in step with the settings and the system's dark mode."""
    THEME_KEYS = {'theme', 'scheme', 'accent', 'radius', 'seek_height', 'controls_opacity'}

    def __init__(self, settings):
        self.settings = settings
        display = Gdk.Display.get_default()
        self.style = Adw.StyleManager.get_default()
        static = Gtk.CssProvider()
        static.load_from_string(APP_CSS)
        Gtk.StyleContext.add_provider_for_display(display, static, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, self.provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        settings.connect('changed', self._changed)
        self.style.connect('notify::dark', lambda *_: self.refresh())
        self.refresh()

    def _changed(self, _s, key):
        if key in self.THEME_KEYS:
            self.refresh()

    def refresh(self):
        theme = THEMES.get(self.settings['theme'], THEMES['sedge'])
        if theme['dark'] is None:
            scheme = {'light': Adw.ColorScheme.FORCE_LIGHT, 'dark': Adw.ColorScheme.FORCE_DARK}.get(
                self.settings['scheme'], Adw.ColorScheme.DEFAULT)
        else:
            scheme = Adw.ColorScheme.FORCE_DARK if theme['dark'] else Adw.ColorScheme.FORCE_LIGHT
        if self.style.get_color_scheme() != scheme:
            self.style.set_color_scheme(scheme)  # notify::dark calls refresh again
        css, _dark = build_css(self.settings, self.style.get_dark())
        self.provider.load_from_string(css)
