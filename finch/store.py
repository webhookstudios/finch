"""Everything Finch remembers: subscribed shows and their episodes, what's been heard and how far,
the Up Next queue, downloads, and saved radio stations. Kept in ~/.local/share/finch/library.json."""
import hashlib
import json
import os
import re
import threading
import time

from gi.repository import GLib, GObject

from . import feeds, net
from .settings import DATA

NEW_DAYS = 14


def _slug(text):
    return re.sub(r'[^\w\- ]+', '', text).strip()[:60] or 'Podcast'


class Library(GObject.Object):
    __gsignals__ = {
        'podcasts-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'episode-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'queue-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'stations-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'refreshing': (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        'download-progress': (GObject.SignalFlags.RUN_FIRST, None, (str, float)),
        'message': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.path = os.path.join(DATA, 'library.json')
        self.podcasts = {}      # feed url -> show dict (with 'episodes')
        self.state = {}         # episode id -> {'pos', 'played', 'file', 'seen'}
        self.queue = []         # episode ids
        self.favorites = []     # station dicts
        self.recent = []        # station dicts, newest first
        self.downloading = {}   # episode id -> fraction (0..1, or -1 when the size is unknown)
        self._cancel = set()
        self._dl_sem = threading.Semaphore(2)
        self._save_id = 0
        self.refreshing = False
        self._load()

    # ---- saving --------------------------------------------------------------------------

    def _load(self):
        try:
            with open(self.path) as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        self.podcasts = {p['feed']: p for p in data.get('podcasts', []) if isinstance(p, dict) and 'feed' in p}
        self.state = data.get('state', {}) if isinstance(data.get('state'), dict) else {}
        self.queue = [e for e in data.get('queue', []) if isinstance(e, str)]
        self.favorites = [s for s in data.get('favorites', []) if isinstance(s, dict) and s.get('url')]
        self.recent = [s for s in data.get('recent', []) if isinstance(s, dict) and s.get('url')]
        # A download that vanished from disk is no longer downloaded.
        for st in self.state.values():
            if st.get('file') and not os.path.exists(st['file']):
                st.pop('file', None)

    def save(self, now=False):
        if self._save_id:
            GLib.source_remove(self._save_id)
            self._save_id = 0
        if not now:
            self._save_id = GLib.timeout_add(600, lambda: self.save(True) and False)
            return
        data = {'podcasts': list(self.podcasts.values()), 'state': self.state, 'queue': self.queue,
                'favorites': self.favorites, 'recent': self.recent}
        try:
            os.makedirs(DATA, exist_ok=True)
            tmp = self.path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(data, f)
            os.replace(tmp, self.path)
        except OSError:
            pass

    # ---- shows ---------------------------------------------------------------------------

    def shows(self):
        return sorted(self.podcasts.values(), key=lambda p: p['title'].lower())

    def is_subscribed(self, feed):
        return feed in self.podcasts

    def preview(self, feed, done, fail):
        """Fetch a feed without subscribing (for the Discover page)."""
        if feed in self.podcasts:
            done(self.podcasts[feed])
            return
        net.run(lambda: dict(feeds.parse(net.fetch(feed), feed), feed=feed), done=done, fail=fail)

    def subscribe(self, feed, show=None, done=None, fail=None):
        feed = feed.strip()

        def added(data):
            data['feed'] = feed
            data['added'] = int(time.time())
            data['refreshed'] = int(time.time())
            # Episodes already out count as seen, so subscribing doesn't flood New Episodes.
            for ep in data['episodes'][3:]:
                self.state.setdefault(ep['id'], {})['seen'] = True
            self.podcasts[feed] = data
            self.save()
            self.emit('podcasts-changed')
            self._auto_download(data, data['episodes'][:3])
            if done:
                done(data)
        if show and show.get('episodes') is not None:
            added(dict(show))
            return
        net.run(lambda: feeds.parse(net.fetch(feed), feed), done=added,
                fail=fail or (lambda m: self.emit('message', m)))

    def unsubscribe(self, feed):
        show = self.podcasts.pop(feed, None)
        if not show:
            return
        ids = {e['id'] for e in show['episodes']}
        for i in ids:
            st = self.state.pop(i, None)
            if st and st.get('file'):
                net._rm(st['file'])
        self.queue = [q for q in self.queue if q not in ids]
        self.save()
        self.emit('podcasts-changed')
        self.emit('queue-changed')

    def refresh(self, feeds_to_check=None):
        if self.refreshing or not self.podcasts:
            return
        self.refreshing = True
        self.emit('refreshing', True)
        targets = list(feeds_to_check or self.podcasts)

        def work():
            out = {}
            for feed in targets:
                try:
                    out[feed] = feeds.parse(net.fetch(feed), feed)
                except Exception:
                    continue
            return out
        net.run(work, done=self._refreshed, fail=lambda m: self._refreshed({}))

    def _refreshed(self, results):
        for feed, fresh in results.items():
            old = self.podcasts.get(feed)
            if not old:
                continue
            known = {e['id'] for e in old['episodes']}
            new = [e for e in fresh['episodes'] if e['id'] not in known]
            fresh.update(feed=feed, added=old.get('added', 0), refreshed=int(time.time()))
            self.podcasts[feed] = fresh
            if new:
                self._auto_download(fresh, new)
        self.refreshing = False
        self.save()
        self.emit('refreshing', False)
        self.emit('podcasts-changed')

    # ---- episodes ------------------------------------------------------------------------

    def episode(self, ep_id):
        """(show, episode) for an id, or (None, None)."""
        for show in self.podcasts.values():
            for ep in show['episodes']:
                if ep['id'] == ep_id:
                    return show, ep
        return None, None

    def st(self, ep_id):
        return self.state.get(ep_id, {})

    def new_episodes(self):
        cutoff = time.time() - NEW_DAYS * 86400
        out = []
        for show in self.podcasts.values():
            for ep in show['episodes']:
                s = self.st(ep['id'])
                if ep['date'] >= cutoff and not s.get('played') and not s.get('seen'):
                    out.append((show, ep))
        out.sort(key=lambda se: se[1]['date'], reverse=True)
        return out

    def downloaded(self):
        out = [(show, ep) for show in self.podcasts.values() for ep in show['episodes']
               if self.st(ep['id']).get('file') or ep['id'] in self.downloading]
        out.sort(key=lambda se: se[1]['date'], reverse=True)
        return out

    def set_position(self, ep_id, pos, duration=0):
        s = self.state.setdefault(ep_id, {})
        s['pos'] = round(pos, 1)
        s['seen'] = True
        if duration and pos > duration - 30 and duration > 60:
            self.mark_played(ep_id, True)
            return
        self.save()

    def mark_played(self, ep_id, played=True):
        s = self.state.setdefault(ep_id, {})
        s['played'] = played
        s['seen'] = True
        if played:
            s.pop('pos', None)
            if ep_id in self.queue:
                self.queue.remove(ep_id)
                self.emit('queue-changed')
            if self.settings['delete_played'] and s.get('file'):
                self.delete_download(ep_id, quiet=True)
        self.save()
        self.emit('episode-changed', ep_id)

    def mark_seen(self, ids):
        for i in ids:
            self.state.setdefault(i, {})['seen'] = True
        self.save()
        self.emit('podcasts-changed')

    def play_uri(self, ep):
        f = self.st(ep['id']).get('file')
        return GLib.filename_to_uri(f, None) if f and os.path.exists(f) else ep['url']

    # ---- Up Next -------------------------------------------------------------------------

    def enqueue(self, ep_id, front=False):
        if ep_id in self.queue:
            self.queue.remove(ep_id)
        if front:
            self.queue.insert(0, ep_id)
        else:
            self.queue.append(ep_id)
        self.save()
        self.emit('queue-changed')

    def dequeue(self, ep_id):
        if ep_id in self.queue:
            self.queue.remove(ep_id)
            self.save()
            self.emit('queue-changed')

    def move_in_queue(self, ep_id, step):
        if ep_id not in self.queue:
            return
        i = self.queue.index(ep_id)
        j = max(0, min(len(self.queue) - 1, i + step))
        self.queue.insert(j, self.queue.pop(i))
        self.save()
        self.emit('queue-changed')

    def clear_queue(self):
        self.queue = []
        self.save()
        self.emit('queue-changed')

    # ---- downloads -----------------------------------------------------------------------

    def _auto_download(self, show, eps):
        n = self.settings['auto_download']
        for ep in eps[:n] if n else []:
            if not self.st(ep['id']).get('played'):
                self.download(ep['id'])

    def download(self, ep_id):
        show, ep = self.episode(ep_id)
        if not ep or ep_id in self.downloading or self.st(ep_id).get('file'):
            return
        ext = os.path.splitext(ep['url'].split('?', 1)[0])[1].lower()
        if ext not in feeds.AUDIO_EXT:
            ext = '.mp4' if 'video' in ep.get('mime', '') else '.mp3'
        name = f"{time.strftime('%Y-%m-%d', time.localtime(ep['date'] or time.time()))} {_slug(ep['title'])}"
        path = os.path.join(self.settings.download_dir(), _slug(show['title']), name + ext)
        self.downloading[ep_id] = 0.0
        self.emit('download-progress', ep_id, 0.0)
        last = [0.0]

        def progress(got, total):
            frac = got / total if total else -1.0
            if frac < 0 or frac - last[0] >= 0.01:
                last[0] = frac
                self.downloading[ep_id] = frac
                GLib.idle_add(lambda: self.emit('download-progress', ep_id, frac) and False)

        def work():
            with self._dl_sem:
                return net.download(ep['url'], path, progress, lambda: ep_id in self._cancel)

        def done(p):
            self.downloading.pop(ep_id, None)
            self.state.setdefault(ep_id, {})['file'] = p
            self.save()
            self.emit('download-progress', ep_id, 1.0)
            self.emit('episode-changed', ep_id)

        def failed(msg):
            self.downloading.pop(ep_id, None)
            if ep_id in self._cancel:
                self._cancel.discard(ep_id)
            else:
                self.emit('message', f"Couldn't download “{ep['title']}”. {msg}")
            self.emit('download-progress', ep_id, -2.0)
            self.emit('episode-changed', ep_id)
        net.run(work, done=done, fail=failed)

    def cancel_download(self, ep_id):
        if ep_id in self.downloading:
            self._cancel.add(ep_id)

    def delete_download(self, ep_id, quiet=False):
        s = self.state.get(ep_id, {})
        f = s.pop('file', None)
        if f:
            net._rm(f)
            try:
                os.rmdir(os.path.dirname(f))  # only goes if the show's folder is now empty
            except OSError:
                pass
        self.save()
        if not quiet:
            self.emit('episode-changed', ep_id)

    def download_size(self):
        total = 0
        for s in self.state.values():
            try:
                total += os.path.getsize(s['file']) if s.get('file') else 0
            except OSError:
                pass
        return total

    # ---- radio ---------------------------------------------------------------------------

    @staticmethod
    def station_key(st):
        return st.get('uuid') or hashlib.sha1(st['url'].encode()).hexdigest()[:16]

    def is_favorite(self, st):
        k = self.station_key(st)
        return any(self.station_key(s) == k for s in self.favorites)

    def toggle_favorite(self, st):
        k = self.station_key(st)
        if self.is_favorite(st):
            self.favorites = [s for s in self.favorites if self.station_key(s) != k]
        else:
            self.favorites.append(dict(st))
        self.save()
        self.emit('stations-changed')

    def played_station(self, st):
        k = self.station_key(st)
        self.recent = [dict(st)] + [s for s in self.recent if self.station_key(s) != k]
        del self.recent[30:]
        self.save()
        self.emit('stations-changed')

    def clear_recent(self):
        self.recent = []
        self.save()
        self.emit('stations-changed')
