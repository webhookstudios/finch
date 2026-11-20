"""The main window: sidebar, pages, the player bar, and what happens when things play."""
import time
import weakref

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from .. import directory, feeds, net  # noqa: E402
from ..player import Player  # noqa: E402
from ..store import Library  # noqa: E402
from .pages import DiscoverPage, DownloadsPage, NewPage, QueuePage, ShowPage, SubsPage  # noqa: E402
from .playerbar import PlayerBar  # noqa: E402
from .radio import BrowsePage, FavoritesPage, RecentPage  # noqa: E402
from .widgets import EpisodeRow, StationRow, fmt_date, fmt_length  # noqa: E402

SIDEBAR = [
    ('Podcasts', [('new', 'New Episodes', 'mail-unread-symbolic'),
                  ('subs', 'Subscriptions', 'audio-input-microphone-symbolic'),
                  ('queue', 'Up Next', 'view-list-symbolic'),
                  ('downloads', 'Downloads', 'folder-download-symbolic'),
                  ('discover', 'Discover', 'system-search-symbolic')]),
    ('Radio', [('radio-browse', 'Browse Stations', 'finch-radio-symbolic'),
               ('radio-fav', 'Favorites', 'starred-symbolic'),
               ('radio-recent', 'Recently Played', 'document-open-recent-symbolic')]),
]
PAGES = {'new': NewPage, 'subs': SubsPage, 'queue': QueuePage, 'downloads': DownloadsPage,
         'discover': DiscoverPage, 'radio-browse': BrowsePage, 'radio-fav': FavoritesPage,
         'radio-recent': RecentPage}


class FinchWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Finch')
        self.app = app
        self.settings = app.settings
        self.set_default_size(self.settings['width'], self.settings['height'])
        self.set_size_request(360, 420)
        self.library = Library(self.settings)
        self.player = Player()
        self.player.set_volume(self.settings['volume'])
        self.player.set_muted(self.settings['muted'])
        self.player.rate = self.settings['speed']
        self.rows = weakref.WeakSet()
        self.previews = {}
        self.pages = {}
        self._last_saved = 0
        self._sleep_id = 0
        self._sleep_end = False
        self._sleep_until = 0
        self._station = None
        self.mpris = None

        self._actions()
        self._build()
        self._wire()
        GLib.timeout_add_seconds(4, self._maybe_refresh)
        GLib.timeout_add_seconds(600, lambda: self._maybe_refresh() or True)
        self.connect('close-request', self._on_close)

    # ---- building ------------------------------------------------------------------------

    def _build(self):
        self.side = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.side.add_css_class('navigation-sidebar')
        self.side.set_header_func(self._side_header)
        self.side.connect('row-selected', self._side_selected)
        self.counts = {}
        for section, items in SIDEBAR:
            for key, label, icon in items:
                row = Gtk.ListBoxRow()
                row.key, row.section = key, section
                box = Gtk.Box(spacing=12)
                box.append(Gtk.Image(icon_name=icon))
                box.append(Gtk.Label(label=label, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END))
                count = Gtk.Label(visible=False)
                count.add_css_class('dim-label')
                count.add_css_class('numeric')
                box.append(count)
                self.counts[key] = count
                row.set_child(box)
                self.side.append(row)

        side_header = Adw.HeaderBar()
        side_header.set_title_widget(Adw.WindowTitle(title='Finch'))
        menu = Gio.Menu()
        look = Gio.Menu()
        picker = Gio.MenuItem.new(None, None)
        picker.set_attribute_value('custom', GLib.Variant('s', 'style'))
        look.append_item(picker)
        menu.append_section(None, look)
        s = Gio.Menu()
        s.append('Add Podcast by Address…', 'win.add-feed')
        s.append('Add Radio Station…', 'win.add-station')
        s.append('Import Subscriptions…', 'win.import-opml')
        s.append('Export Subscriptions…', 'win.export-opml')
        menu.append_section(None, s)
        s = Gio.Menu()
        s.append('Preferences', 'app.preferences')
        s.append('Keyboard Shortcuts', 'app.shortcuts')
        s.append('About Finch', 'app.about')
        menu.append_section(None, s)
        from .style import StylePicker
        pop = Gtk.PopoverMenu.new_from_model(menu)
        self.style_picker = StylePicker(self.settings)
        pop.add_child(self.style_picker, 'style')
        self.menu_btn = Gtk.MenuButton(icon_name='open-menu-symbolic', popover=pop, primary=True,
                                       tooltip_text='Main menu: theme, colors and more')
        side_header.pack_end(self.menu_btn)
        self.refresh_btn = Gtk.Button(icon_name='view-refresh-symbolic', tooltip_text='Check for new episodes (Ctrl+R)',
                                      action_name='win.refresh')
        side_header.pack_start(self.refresh_btn)
        self.refresh_spin = Adw.Spinner(visible=False, width_request=16, height_request=16)
        side_header.pack_start(self.refresh_spin)
        side_view = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=self.side,
                                                                hscrollbar_policy=Gtk.PolicyType.NEVER))
        side_view.add_top_bar(side_header)

        self.nav = Adw.NavigationView()
        self.split = Adw.NavigationSplitView(sidebar=Adw.NavigationPage(title='Finch', child=side_view),
                                             content=Adw.NavigationPage(title='Podcasts', child=self.nav),
                                             min_sidebar_width=210, max_sidebar_width=260)
        self.bar = PlayerBar(self)
        outer = Adw.ToolbarView(content=self.split, bottom_bar_style=Adw.ToolbarStyle.FLAT)
        outer.add_bottom_bar(self.bar)
        self.toasts = Adw.ToastOverlay(child=outer)
        self.set_content(self.toasts)
        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse('max-width: 700sp'))
        bp.add_setter(self.split, 'collapsed', True)
        self.add_breakpoint(bp)
        self.go(self.settings['last_page'] if self.settings['last_page'] in PAGES else 'new')
        self._update_counts()

    def _side_header(self, row, before):
        if before is None or before.section != row.section:
            lab = Gtk.Label(label=row.section, xalign=0, margin_start=12, margin_top=12 if before else 4,
                            margin_bottom=4)
            lab.add_css_class('heading')
            lab.add_css_class('dim-label')
            row.set_header(lab)
        else:
            row.set_header(None)

    def _side_selected(self, _l, row):
        if row is not None and getattr(self, '_current', None) != row.key:
            self.go(row.key)

    def page(self, key):
        if key not in self.pages:
            self.pages[key] = PAGES[key](self)
        return self.pages[key]

    def go(self, key):
        self._current = key
        self.nav.replace([self.page(key)])
        self.split.set_show_content(True)
        self.settings.set('last_page', key)
        i = 0
        while (row := self.side.get_row_at_index(i)) is not None:
            if row.key == key and self.side.get_selected_row() is not row:
                self.side.select_row(row)
            i += 1

    # ---- actions -------------------------------------------------------------------------

    def _add(self, name, cb, param=None, state=None):
        if state is not None:
            a = Gio.SimpleAction.new_stateful(name, GLib.VariantType(param) if param else None, state)
            a.connect('change-state', cb)
        else:
            a = Gio.SimpleAction.new(name, GLib.VariantType(param) if param else None)
            a.connect('activate', cb)
        self.add_action(a)
        return a

    def _actions(self):
        self.speed_action = self._add('speed', lambda _a, v: self.set_speed(float(v.unpack())), 's',
                                      GLib.Variant('s', f"{self.settings['speed']:g}"))
        self._add('sleep', lambda _a, v: self.set_sleep(v.unpack()), 's')
        self._add('enqueue', lambda _a, v: self._enqueue(v.unpack(), False), 's')
        self._add('play-next', lambda _a, v: self._enqueue(v.unpack(), True), 's')
        self._add('dequeue', lambda _a, v: self.library.dequeue(v.unpack()), 's')
        self._add('toggle-played', self._toggle_played, 's')
        self._add('show-notes', lambda _a, v: self.show_notes(*self.find_episode(v.unpack())), 's')
        self._add('open-link', self._open_link, 's')
        self._add('refresh', lambda *_: self.library.refresh())
        self._add('add-feed', lambda *_: self.ask_feed())
        self._add('add-station', lambda *_: self.ask_station())
        self._add('import-opml', lambda *_: self.import_opml())
        self._add('export-opml', lambda *_: self.export_opml())
        self._add('toggle-play', lambda *_: self.player.toggle())
        self._add('search', lambda *_: self._focus_search())

    def _wire(self):
        lib = self.library
        lib.connect('episode-changed', lambda _l, i: self._sync_rows(i))
        lib.connect('download-progress', lambda _l, i, _f: self._sync_rows(i))
        lib.connect('stations-changed', lambda *_: self._sync_rows(None))
        lib.connect('podcasts-changed', lambda *_: self._update_counts())
        lib.connect('queue-changed', lambda *_: (self._update_counts(), self.bar.sync_item()))
        lib.connect('message', lambda _l, m: self.toast(m))
        lib.connect('refreshing', self._refreshing)
        p = self.player
        p.connect('state-changed', self._on_state)
        p.connect('item-changed', lambda *_: self._sync_rows(None, play_only=True))
        p.connect('position', self._on_position)
        p.connect('eos', lambda *_: self._on_eos())
        p.connect('error', lambda _p, m: self.toast(f"Couldn't play this. {m}"))
        self.settings.connect('changed', self._setting)
        keys = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.connect('key-pressed', self._key)
        self.add_controller(keys)

    def _setting(self, _s, key):
        if key == 'volume':
            self.player.set_volume(self.settings['volume'])
        elif key == 'muted':
            self.player.set_muted(self.settings['muted'])

    def _sync_rows(self, ep_id, play_only=False):
        for r in list(self.rows):
            if isinstance(r, EpisodeRow):
                if play_only:
                    r._sync_play()
                elif ep_id is None or r.key() == ep_id:
                    r.sync()
            elif isinstance(r, StationRow):
                r.sync()
        self._update_counts()

    def _update_counts(self):
        lib = self.library
        values = {'new': len(lib.new_episodes()), 'queue': len(lib.queue),
                  'downloads': sum(1 for s in lib.state.values() if s.get('file')) + len(lib.downloading)}
        for key, n in values.items():
            self.counts[key].set_label(str(n))
            self.counts[key].set_visible(n > 0)

    def _refreshing(self, _l, on):
        self.refresh_spin.set_visible(on)
        self.refresh_btn.set_visible(not on)

    def _maybe_refresh(self):
        hours = self.settings['refresh_hours']
        if hours and self.library.podcasts:
            oldest = min(p.get('refreshed', 0) for p in self.library.podcasts.values())
            if time.time() - oldest > hours * 3600:
                self.library.refresh()
        return False

    # ---- finding episodes ----------------------------------------------------------------

    def remember_preview(self, show):
        self.previews[show['feed']] = show

    def find_episode(self, ep_id):
        show, ep = self.library.episode(ep_id)
        if ep:
            return show, ep
        for show in self.previews.values():
            for ep in show.get('episodes', []):
                if ep['id'] == ep_id:
                    return show, ep
        return None, None

    def open_show(self, feed, preview=None):
        if not feed:
            self.toast('This show has no public feed, so it can’t be played here.')
            return
        self.nav.push(ShowPage(self, feed, preview))

    def reveal_current(self):
        item = self.player.item
        if not item:
            return
        if item['kind'] == 'station':
            self.go('radio-recent')
        else:
            show, _ep = self.find_episode(item['id'])
            if show:
                self.open_show(show['feed'], show)

    # ---- playing -------------------------------------------------------------------------

    def play_episode(self, ep_id):
        p = self.player
        if p.item and p.item.get('id') == ep_id:
            p.toggle()
            return
        show, ep = self.find_episode(ep_id)
        if not ep:
            return
        self._save_position()
        st = self.library.st(ep_id)
        start = 0 if st.get('played') else st.get('pos', 0)
        if st.get('played'):
            self.library.mark_played(ep_id, False)
        item = {'kind': 'episode', 'id': ep_id, 'title': ep['title'], 'subtitle': show['title'],
                'image': ep.get('image') or show.get('image'), 'uri': self.library.play_uri(ep),
                'feed': show['feed']}
        p.rate = self.settings['speed']
        p.load(item, start=start)
        self.library.dequeue(ep_id)
        if ep_id in self.library.state or show['feed'] in self.library.podcasts:
            self.library.state.setdefault(ep_id, {})['seen'] = True
            self.library.save()
        self._update_counts()

    def toggle_station(self, st):
        key = self.library.station_key(st)
        p = self.player
        if p.item and p.item.get('id') == key:
            p.toggle()
            return
        self._save_position()
        self._station = st
        subtitle = ', '.join(st.get('tags', [])[:3]) or st.get('country', '') or 'Internet radio'
        item = {'kind': 'station', 'id': key, 'title': st['name'], 'subtitle': subtitle,
                'image': st.get('favicon'), 'uri': st['url']}
        url = st['url'].split('?', 1)[0].lower()
        if url.endswith(('.pls', '.m3u', '.m3u8')) and not url.endswith('.m3u8'):
            # A playlist file, not the stream itself: read it to find the stream.
            net.run(lambda: _first_stream(st['url']), done=lambda u: p.load(dict(item, uri=u)),
                    fail=lambda m: self.toast(f"Couldn't open that station. {m}"))
        else:
            p.load(item)
        self.library.played_station(st)
        if st.get('uuid'):
            net.run(directory.count_click, st['uuid'])

    def play_next(self):
        cur = self.player.item.get('id') if self.player.item else None
        for ep_id in list(self.library.queue):
            if ep_id != cur and self.find_episode(ep_id)[1]:
                self.play_episode(ep_id)
                return True
        return False

    def set_speed(self, rate):
        rate = max(0.5, min(3.0, round(rate, 2)))
        self.settings.set('speed', rate)
        self.speed_action.set_state(GLib.Variant('s', f'{rate:g}'))
        self.player.set_rate(rate)

    def set_sleep(self, value):
        if self._sleep_id:
            GLib.source_remove(self._sleep_id)
            self._sleep_id = 0
        self._sleep_end = False
        self._sleep_until = 0
        if value == 'off':
            self.bar.sync_sleep('')
            self.toast('Sleep timer off')
        elif value == 'end':
            self._sleep_end = True
            self.bar.sync_sleep('end of this episode')
            self.toast('Stops at the end of this episode')
        else:
            mins = int(value)
            self._sleep_until = time.time() + mins * 60
            self._sleep_id = GLib.timeout_add_seconds(30, self._sleep_tick)
            self.bar.sync_sleep(f'{mins} min')
            self.toast(f'Stops in {fmt_length(mins * 60)}')

    def _sleep_tick(self):
        left = self._sleep_until - time.time()
        if left <= 0:
            self._sleep_id = 0
            self.player.pause()
            self.bar.sync_sleep('')
            self.toast('Sleep timer stopped playback')
            return False
        self.bar.sync_sleep(f'{max(1, round(left / 60))} min left')
        return True

    def _on_state(self, _p, state):
        self._sync_rows(None, play_only=True)
        if state != 'playing':
            self._save_position()

    def _on_position(self, _p, pos, dur):
        item = self.player.item
        if item and item['kind'] == 'episode' and time.time() - self._last_saved > 10 and pos > 0:
            self._save_position()

    def _save_position(self):
        item = self.player.item
        if not item or item['kind'] != 'episode':
            return
        self._last_saved = time.time()
        pos, dur = self.player.position(), self.player.duration
        if pos > 1 and not self.library.st(item['id']).get('played'):
            self.library.set_position(item['id'], pos, dur)
            self._sync_rows(item['id'])

    def _on_eos(self):
        item = self.player.item
        if not item:
            return
        if item['kind'] == 'episode':
            self.library.mark_played(item['id'], True)
            if self._sleep_end:
                self._sleep_end = False
                self.bar.sync_sleep('')
                self.player.seek(0)
                self.toast('Sleep timer stopped playback')
                return
            if self.settings['continuous'] and self.play_next():
                return
            self.player.seek(0)
        else:
            # A station that ends has dropped; try once more.
            GLib.timeout_add_seconds(2, lambda: self.player.item is item and self.player.load(item) and False)

    # ---- episode actions -----------------------------------------------------------------

    def _enqueue(self, ep_id, front):
        show, ep = self.find_episode(ep_id)
        if show and show['feed'] not in self.library.podcasts:
            self.toast('Subscribe to this show to add its episodes to Up Next.')
            return
        self.library.enqueue(ep_id, front)
        self.toast('Plays next' if front else 'Added to Up Next')

    def _toggle_played(self, _a, v):
        i = v.unpack()
        played = self.library.st(i).get('played', False)
        self.library.mark_played(i, not played)
        self._update_counts()

    def _open_link(self, _a, v):
        _show, ep = self.find_episode(v.unpack())
        if ep and ep.get('link'):
            Gtk.UriLauncher.new(ep['link']).launch(self, None, None)

    def show_notes(self, show, ep):
        if not ep:
            return
        dlg = Adw.Dialog(title=ep['title'], content_width=560, content_height=620)
        header = Adw.HeaderBar()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_start=24, margin_end=24,
                      margin_top=12, margin_bottom=24)
        sub = Gtk.Label(label=show['title'], xalign=0, wrap=True)
        sub.add_css_class('dim-label')
        box.append(sub)
        title = Gtk.Label(label=ep['title'], xalign=0, wrap=True, selectable=True)
        title.add_css_class('show-title')
        box.append(title)
        meta = Gtk.Label(label=' · '.join(x for x in (fmt_date(ep['date']), fmt_length(ep.get('duration', 0))) if x),
                         xalign=0)
        meta.add_css_class('dim-label')
        box.append(meta)
        btns = Gtk.Box(spacing=8)
        play = Gtk.Button(label='Play')
        play.add_css_class('pill')
        play.add_css_class('suggested-action')
        play.connect('clicked', lambda *_: (self.play_episode(ep['id']), dlg.close()))
        btns.append(play)
        box.append(btns)
        notes = Gtk.Label(label=ep.get('notes') or 'This episode has no notes.', xalign=0, wrap=True,
                          selectable=True, wrap_mode=Pango.WrapMode.WORD_CHAR, margin_top=8)
        notes.add_css_class('notes')
        box.append(notes)
        view = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=box, hscrollbar_policy=Gtk.PolicyType.NEVER,
                                                          vexpand=True))
        view.add_top_bar(header)
        dlg.set_child(view)
        dlg.present(self)

    # ---- dialogs -------------------------------------------------------------------------

    def _ask(self, heading, body, placeholder, verb, done, extra=None):
        dlg = Adw.AlertDialog(heading=heading, body=body)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        entry = Gtk.Entry(placeholder_text=placeholder, activates_default=True, width_chars=40)
        box.append(entry)
        if extra:
            box.append(extra)
        dlg.set_extra_child(box)
        dlg.add_response('cancel', 'Cancel')
        dlg.add_response('ok', verb)
        dlg.set_response_appearance('ok', Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response('ok')
        dlg.set_close_response('cancel')
        dlg.connect('response', lambda _d, r: r == 'ok' and entry.get_text().strip() and done(entry.get_text().strip()))
        dlg.present(self)
        entry.grab_focus()
        return entry

    def ask_feed(self):
        def done(url):
            if '://' not in url:
                url = 'https://' + url
            self.open_show(url)
        self._ask('Add a Podcast', 'Paste the address of the show’s RSS feed.', 'https://…/feed.xml', 'Open', done)

    def ask_station(self):
        name = Gtk.Entry(placeholder_text='Station name')

        def done(url):
            if '://' not in url:
                url = 'http://' + url
            st = {'uuid': '', 'name': name.get_text().strip() or url, 'url': url, 'favicon': '', 'tags': [],
                  'country': '', 'countrycode': '', 'codec': '', 'bitrate': 0, 'homepage': ''}
            if not self.library.is_favorite(st):
                self.library.toggle_favorite(st)
            self.toast(f"Added {st['name']} to favorite stations")
            self.toggle_station(st)
        self._ask('Add a Radio Station', 'Paste the address of the stream (it often ends in .mp3, .aac or .pls).',
                  'http://…', 'Add and Listen', done, extra=name)

    def import_opml(self):
        dlg = Gtk.FileDialog(title='Import Subscriptions')
        f = Gtk.FileFilter(name='Subscription lists (OPML)')
        for p in ('*.opml', '*.xml'):
            f.add_pattern(p)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(f)
        dlg.set_filters(store)

        def chosen(d, res):
            try:
                file = d.open_finish(res)
                ok, data, _etag = file.load_contents(None)
                urls = feeds.read_opml(bytes(data))
            except (GLib.Error, feeds.FeedError) as e:
                self.toast(str(getattr(e, 'message', e)))
                return
            new = [u for u in urls if u not in self.library.podcasts]
            if not new:
                self.toast('You already follow every show in that list.')
                return
            self.toast(f"Adding {len(new)} show{'' if len(new) == 1 else 's'}…")
            for u in new:
                self.library.subscribe(u, fail=lambda m, u=u: self.toast(f"Skipped {u}: {m}"))
        dlg.open(self, None, chosen)

    def export_opml(self):
        if not self.library.podcasts:
            self.toast('There are no subscriptions to export yet.')
            return
        dlg = Gtk.FileDialog(title='Export Subscriptions', initial_name='Finch subscriptions.opml')

        def chosen(d, res):
            try:
                file = d.save_finish(res)
                file.replace_contents(feeds.write_opml(self.library.shows()), None, False,
                                      Gio.FileCreateFlags.REPLACE_DESTINATION, None)
                self.toast(f'Saved {file.get_basename()}')
            except GLib.Error as e:
                if not e.matches(Gtk.DialogError.quark(), Gtk.DialogError.DISMISSED):
                    self.toast(f"Couldn't save it: {e.message}")
        dlg.save(self, None, chosen)

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(text), timeout=4))

    # ---- keys and closing ----------------------------------------------------------------

    def _focus_search(self):
        page = self.nav.get_visible_page()
        entry = getattr(page, 'search', None)
        if entry is None:
            self.go('discover')
            entry = self.page('discover').search
        entry.grab_focus()

    def _key(self, _c, keyval, _code, mods):
        if self.get_visible_dialog() is not None:
            return False
        focus = self.get_focus()
        if isinstance(focus, (Gtk.Text, Gtk.Editable)):
            return False
        if mods & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        name = Gdk.keyval_name(keyval)
        if name == 'space' and self.player.item:
            if isinstance(focus, Gtk.Button):
                return False
            self.player.toggle()
            return True
        if name in ('Left', 'Right') and self.player.item and not self.player.live and \
                not isinstance(focus, (Gtk.Scale,)):
            self.player.skip(-self.settings['skip_back'] if name == 'Left' else self.settings['skip_forward'])
            return True
        return False

    def _on_close(self, *_):
        self._save_position()
        if not self.is_maximized():
            w, h = self.get_default_size()
            self.settings.set('width', w)
            self.settings.set('height', h)
        self.settings.flush()
        self.library.save(now=True)
        self.player.shutdown()
        return False


def _first_stream(url):
    text = net.fetch(url, max_bytes=256 * 1024).decode('utf-8', 'replace')
    for line in text.splitlines():
        line = line.strip()
        if '=' in line and line.lower().startswith('file'):
            line = line.split('=', 1)[1].strip()
        if line.lower().startswith(('http://', 'https://')):
            return line
    raise net.NetError('That playlist has no stream in it.')
