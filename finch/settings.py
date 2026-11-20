"""Settings, kept as a small JSON file in ~/.config/finch/settings.json."""
import json
import os

from gi.repository import GLib, GObject

CONFIG = os.path.join(GLib.get_user_config_dir(), 'finch')
DATA = os.path.join(GLib.get_user_data_dir(), 'finch')
CACHE = os.path.join(GLib.get_user_cache_dir(), 'finch')


def _country():
    for var in ('LC_ALL', 'LC_MESSAGES', 'LANG'):
        val = os.environ.get(var, '')
        if '_' in val:
            cc = val.split('_', 1)[1][:2]
            if cc.isalpha():
                return cc.upper()
    return 'US'


DEFAULTS = {
    # Look (the theme keys match Fireside's themes module)
    'theme': 'sedge',
    'scheme': 'system',
    'accent': '',
    'radius': 16,
    'seek_height': 5,
    'controls_opacity': 0.9,
    # Playback
    'volume': 0.8,
    'muted': False,
    'speed': 1.0,
    'skip_back': 15,
    'skip_forward': 30,
    'continuous': True,          # play the next item in Up Next when an episode ends
    # Podcasts
    'refresh_hours': 6,          # 0 = only when asked
    'auto_download': 0,          # newest new episodes to download per show after a refresh
    'delete_played': False,
    'download_dir': '',
    'episode_filter': 'all',     # all, unplayed, downloaded
    # Radio
    'country': _country(),
    # Window
    'width': 1120,
    'height': 740,
    'last_page': 'new',
}


class Settings(GObject.Object):
    __gsignals__ = {'changed': (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self):
        super().__init__()
        self._path = os.path.join(CONFIG, 'settings.json')
        self._data = dict(DEFAULTS)
        try:
            with open(self._path) as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        for key, value in (saved.items() if isinstance(saved, dict) else ()):
            default = DEFAULTS.get(key)
            if key in DEFAULTS and (type(value) is type(default) or
                                    (isinstance(default, float) and type(value) is int)):
                self._data[key] = value
        self._pending = 0

    def __getitem__(self, key):
        return self._data[key]

    def set(self, key, value):
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self.emit('changed', key)
        if self._pending:
            GLib.source_remove(self._pending)
        self._pending = GLib.timeout_add(400, self.flush)

    def reset(self, keys):
        for key in keys:
            self.set(key, DEFAULTS[key])

    def flush(self):
        if self._pending:
            GLib.source_remove(self._pending)
            self._pending = 0
        try:
            os.makedirs(CONFIG, exist_ok=True)
            tmp = self._path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self._data, f, indent=1)
            os.replace(tmp, self._path)
        except OSError:
            pass
        return False

    def download_dir(self):
        return self._data['download_dir'] or os.path.join(DATA, 'episodes')
