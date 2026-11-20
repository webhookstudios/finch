"""Podcast pages: New Episodes, Subscriptions, a show's page, Up Next, Downloads and Discover."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, GLib, Gtk, Pango  # noqa: E402

from .. import directory, net  # noqa: E402
from .widgets import (Art, EpisodeRow, ShowTile, boxed_list, clear, flat_button, page_header,  # noqa: E402
                      status, tile_grid)

EPISODE_PAGE = 100


class Page(Adw.NavigationPage):
    """A page with a plain header bar, a big serif title in the content and a scrolling body."""

    def __init__(self, win, tag, title, subtitle=None):
        super().__init__(title=title, tag=tag)
        self.win = win
        self.library = win.library
        self.header = Adw.HeaderBar(show_title=False)
        self.head = page_header(title, subtitle)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.body.append(self.head)
        self.stack = Gtk.Stack(vexpand=True)
        self.body.append(self.stack)
        scroller = Gtk.ScrolledWindow(child=self.body, hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scroller = scroller
        view = Adw.ToolbarView(content=scroller)
        view.add_top_bar(self.header)
        self.set_child(view)
        self.connect('showing', lambda *_: self.refresh())

    def tool(self, icon, tip, cb):
        b = flat_button(icon, tip, cb)
        self.head.append(b)
        return b

    def refresh(self):
        pass


# ---- New Episodes ------------------------------------------------------------------------------

class NewPage(Page):
    def __init__(self, win):
        super().__init__(win, 'new', 'New Episodes', 'From the last two weeks, not yet played')
        self.tool('object-select-symbolic', 'Clear this list (marks these as seen)', self._clear)
        self.tool('view-refresh-symbolic', 'Check for new episodes', lambda: self.library.refresh())
        self.list = boxed_list()
        self.stack.add_named(self.list, 'list')
        self.stack.add_named(status('mail-unread-symbolic', 'All caught up',
                                    'New episodes from your shows show up here.'), 'empty')
        self.library.connect('podcasts-changed', lambda *_: self.get_mapped() and self.refresh())

    def refresh(self):
        clear(self.list)
        items = self.library.new_episodes()
        for show, ep in items[:150]:
            self.list.append(EpisodeRow(self.win, show, ep))
        self.stack.set_visible_child_name('list' if items else 'empty')

    def _clear(self):
        self.library.mark_seen([ep['id'] for _s, ep in self.library.new_episodes()])


# ---- Subscriptions -----------------------------------------------------------------------------

class SubsPage(Page):
    def __init__(self, win):
        super().__init__(win, 'subs', 'Subscriptions')
        self.tool('list-add-symbolic', 'Add a podcast by its feed address', win.ask_feed)
        self.tool('document-open-symbolic', 'Import subscriptions (OPML)', win.import_opml)
        self.tool('document-save-symbolic', 'Export subscriptions (OPML)', win.export_opml)
        self.tool('view-refresh-symbolic', 'Check for new episodes', lambda: self.library.refresh())
        self.grid = tile_grid()
        self.grid.connect('child-activated', lambda _g, tile: win.open_show(tile.show['feed']))
        self.stack.add_named(self.grid, 'grid')
        empty = status('audio-input-microphone-symbolic', 'No podcasts yet',
                       'Find shows to follow in Discover, or add one by its feed address.')
        b = Gtk.Button(label='Discover Podcasts', halign=Gtk.Align.CENTER)
        b.add_css_class('pill')
        b.add_css_class('suggested-action')
        b.connect('clicked', lambda *_: win.go('discover'))
        empty.set_child(b)
        self.stack.add_named(empty, 'empty')
        self.library.connect('podcasts-changed', lambda *_: self.get_mapped() and self.refresh())

    def refresh(self):
        clear(self.grid)
        shows = self.library.shows()
        new = {}
        for show, _ep in self.library.new_episodes():
            new[show['feed']] = new.get(show['feed'], 0) + 1
        for show in shows:
            self.grid.append(ShowTile(show, new.get(show['feed'], 0)))
        n = len(shows)
        self.head.sub.set_label(f"{n} show{'' if n == 1 else 's'}" if n else '')
        self.head.sub.set_visible(bool(n))
        self.stack.set_visible_child_name('grid' if shows else 'empty')


# ---- A show ------------------------------------------------------------------------------------

class ShowPage(Adw.NavigationPage):
    """A show's details and episodes. Works for shows you follow and ones you're only looking at."""

    def __init__(self, win, feed, preview=None):
        super().__init__(title=(preview or {}).get('title') or 'Podcast')
        self.win, self.library, self.feed = win, win.library, feed
        self.show = self.library.podcasts.get(feed) or preview
        self.limit = EPISODE_PAGE
        header = Adw.HeaderBar(show_title=False)
        self.refresh_btn = flat_button('view-refresh-symbolic', 'Check for new episodes',
                                       lambda: self.library.refresh([feed]))
        header.pack_end(self.refresh_btn)
        self.web_btn = flat_button('web-browser-symbolic', "Open the show's website", self._open_site)
        header.pack_end(self.web_btn)

        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        top = Gtk.Box(spacing=20, margin_start=24, margin_end=24, margin_top=18, margin_bottom=12)
        self.art = Art(150, None, large=True)
        self.art.set_valign(Gtk.Align.START)
        top.append(self.art)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, hexpand=True)
        self.title = Gtk.Label(xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.title.add_css_class('show-title')
        self.title.set_selectable(True)
        info.append(self.title)
        self.author = Gtk.Label(xalign=0, wrap=True)
        self.author.add_css_class('dim-label')
        info.append(self.author)
        self.desc = Gtk.Label(xalign=0, wrap=True, lines=4, ellipsize=Pango.EllipsizeMode.END,
                              wrap_mode=Pango.WrapMode.WORD_CHAR, margin_top=4)
        self.desc.add_css_class('notes')
        info.append(self.desc)
        actions = Gtk.Box(spacing=8, margin_top=8)
        self.sub_btn = Gtk.Button()
        self.sub_btn.add_css_class('pill')
        self.sub_btn.connect('clicked', self._toggle_sub)
        actions.append(self.sub_btn)
        self.more_btn = Gtk.Button(label='More', valign=Gtk.Align.CENTER)
        self.more_btn.add_css_class('flat')
        self.more_btn.connect('clicked', self._more)
        actions.append(self.more_btn)
        info.append(actions)
        top.append(info)
        self.body.append(top)

        bar = Gtk.Box(spacing=8, margin_start=24, margin_end=24, margin_bottom=8)
        self.count = Gtk.Label(xalign=0, hexpand=True)
        self.count.add_css_class('section-title')
        bar.append(self.count)
        self.filter = Gtk.DropDown.new_from_strings(['All episodes', 'Not played', 'Downloaded'])
        self.filter.set_tooltip_text('Which episodes to show')
        self.filter.set_selected(['all', 'unplayed', 'downloaded'].index(win.settings['episode_filter']))
        self.filter.connect('notify::selected', self._filter_changed)
        bar.append(self.filter)
        self.body.append(bar)
        self.list = boxed_list()
        self.body.append(self.list)
        self.more_eps = Gtk.Button(label='Show more episodes', halign=Gtk.Align.CENTER, margin_bottom=24)
        self.more_eps.add_css_class('pill')
        self.more_eps.connect('clicked', self._show_more)
        self.body.append(self.more_eps)
        self.loading = Adw.Spinner(width_request=40, height_request=40, margin_top=40, halign=Gtk.Align.CENTER)

        self.stack = Gtk.Stack()
        self.stack.add_named(Gtk.ScrolledWindow(child=self.body, hscrollbar_policy=Gtk.PolicyType.NEVER),
                             'show')
        self.stack.add_named(self.loading, 'loading')
        self.error = status('dialog-warning-symbolic', "Couldn't load this podcast")
        self.stack.add_named(self.error, 'error')
        view = Adw.ToolbarView(content=self.stack)
        view.add_top_bar(header)
        self.set_child(view)
        self._sig = self.library.connect('podcasts-changed', self._library_changed)
        self.connect('hidden', self._hidden)

        if self.show and self.show.get('episodes') is not None:
            self.fill()
        else:
            self.stack.set_visible_child_name('loading')
            self.library.preview(feed, self._loaded, self._failed)

    def _hidden(self, *_):
        # A page popped off the stack is gone for good; stop listening.
        if self.get_parent() is None and self._sig:
            self.library.disconnect(self._sig)
            self._sig = 0

    def _loaded(self, show):
        base = self.show or {}
        self.show = dict(show, feed=self.feed)
        for k in ('image', 'author'):
            if not self.show.get(k) and base.get(k):
                self.show[k] = base[k]
        self.fill()

    def _failed(self, msg):
        self.error.set_description(msg)
        self.stack.set_visible_child_name('error')

    def _library_changed(self, *_):
        if self.feed in self.library.podcasts:
            self.show = self.library.podcasts[self.feed]
        self.fill()

    def fill(self):
        s = self.show
        self.set_title(s['title'])
        self.title.set_label(s['title'])
        self.author.set_label(s.get('author') or '')
        self.author.set_visible(bool(s.get('author')))
        self.desc.set_label(s.get('description') or '')
        self.desc.set_visible(bool(s.get('description')))
        self.more_btn.set_visible(len(s.get('description') or '') > 220)
        self.art.set_url(s.get('image'))
        self.web_btn.set_visible(bool(s.get('link')))
        subbed = self.library.is_subscribed(self.feed)
        self.sub_btn.set_label('Unsubscribe' if subbed else 'Subscribe')
        for c in ('suggested-action', 'destructive-action'):
            self.sub_btn.remove_css_class(c)
        self.sub_btn.add_css_class('suggested-action' if not subbed else 'flat')
        self.refresh_btn.set_visible(subbed)
        self.filter.set_visible(subbed)
        self._fill_episodes()
        self.stack.set_visible_child_name('show')

    def _episodes(self):
        eps = self.show.get('episodes') or []
        mode = self.win.settings['episode_filter'] if self.library.is_subscribed(self.feed) else 'all'
        if mode == 'unplayed':
            eps = [e for e in eps if not self.library.st(e['id']).get('played')]
        elif mode == 'downloaded':
            eps = [e for e in eps if self.library.st(e['id']).get('file') or e['id'] in self.library.downloading]
        return eps

    def _fill_episodes(self):
        clear(self.list)
        eps = self._episodes()
        total = len(self.show.get('episodes') or [])
        self.count.set_label(f"{total} episode{'' if total == 1 else 's'}")
        if not self.library.is_subscribed(self.feed):
            show = dict(self.show, feed=self.feed)
            # Episodes can still be played before subscribing; the window keeps them in mind.
            self.win.remember_preview(show)
        for ep in eps[:self.limit]:
            self.list.append(EpisodeRow(self.win, self.show, ep, show_name=False))
        self.more_eps.set_visible(len(eps) > self.limit)
        if not eps:
            row = Adw.ActionRow(title='No episodes match this filter')
            self.list.append(row)

    def _show_more(self, *_):
        self.limit += EPISODE_PAGE
        self._fill_episodes()

    def _filter_changed(self, dd, _p):
        self.win.settings.set('episode_filter', ['all', 'unplayed', 'downloaded'][dd.get_selected()])
        self._fill_episodes()

    def _more(self, *_):
        on = self.desc.get_lines() == 4
        self.desc.set_lines(-1 if on else 4)
        self.desc.set_ellipsize(Pango.EllipsizeMode.NONE if on else Pango.EllipsizeMode.END)
        self.more_btn.set_label('Less' if on else 'More')

    def _toggle_sub(self, *_):
        if self.library.is_subscribed(self.feed):
            dlg = Adw.AlertDialog(heading=f'Unsubscribe from “{self.show["title"]}”?',
                                  body='Its downloaded episodes are deleted too.')
            dlg.add_response('cancel', 'Cancel')
            dlg.add_response('unsub', 'Unsubscribe')
            dlg.set_response_appearance('unsub', Adw.ResponseAppearance.DESTRUCTIVE)
            dlg.set_close_response('cancel')
            dlg.connect('response', lambda _d, r: r == 'unsub' and self.library.unsubscribe(self.feed))
            dlg.present(self.win)
        else:
            self.sub_btn.set_sensitive(False)

            def done(_show):
                self.sub_btn.set_sensitive(True)
                self.win.toast(f'Subscribed to {self.show["title"]}')

            def fail(msg):
                self.sub_btn.set_sensitive(True)
                self.win.toast(msg)
            self.library.subscribe(self.feed, self.show, done, fail)

    def _open_site(self):
        link = self.show.get('link')
        if link:
            Gtk.UriLauncher.new(link).launch(self.win, None, None)


# ---- Up Next -----------------------------------------------------------------------------------

class QueuePage(Page):
    def __init__(self, win):
        super().__init__(win, 'queue', 'Up Next', 'Plays in order after the current episode')
        self.tool('edit-clear-all-symbolic', 'Clear Up Next', lambda: self.library.clear_queue())
        self.list = boxed_list()
        self.stack.add_named(self.list, 'list')
        self.stack.add_named(status('view-list-symbolic', 'Nothing up next',
                                    'Choose Add to Up Next from an episode’s menu.'), 'empty')
        self.library.connect('queue-changed', lambda *_: self.get_mapped() and self.refresh())

    def refresh(self):
        clear(self.list)
        n = 0
        for ep_id in self.library.queue:
            show, ep = self.win.find_episode(ep_id)
            if ep:
                self.list.append(EpisodeRow(self.win, show, ep, queue=True))
                n += 1
        self.stack.set_visible_child_name('list' if n else 'empty')


# ---- Downloads ---------------------------------------------------------------------------------

class DownloadsPage(Page):
    def __init__(self, win):
        super().__init__(win, 'downloads', 'Downloads')
        self.tool('user-trash-symbolic', 'Delete played downloads', self._delete_played)
        self.tool('folder-open-symbolic', 'Open the downloads folder', self._open_folder)
        self.list = boxed_list()
        self.stack.add_named(self.list, 'list')
        self.stack.add_named(status('folder-download-symbolic', 'No downloads',
                                    'Downloaded episodes play without an internet connection.'), 'empty')
        for sig in ('episode-changed', 'podcasts-changed'):
            self.library.connect(sig, lambda *_: self.get_mapped() and self.refresh())

    def refresh(self):
        clear(self.list)
        items = self.library.downloaded()
        for show, ep in items:
            self.list.append(EpisodeRow(self.win, show, ep))
        size = self.library.download_size()
        self.head.sub.set_label(f"{len(items)} episode{'' if len(items) == 1 else 's'} · {GLib.format_size(size)}"
                                if items else '')
        self.head.sub.set_visible(bool(items))
        self.stack.set_visible_child_name('list' if items else 'empty')

    def _delete_played(self):
        n = 0
        for _show, ep in self.library.downloaded():
            if self.library.st(ep['id']).get('played') and self.library.st(ep['id']).get('file'):
                self.library.delete_download(ep['id'], quiet=True)
                n += 1
        self.win.toast(f"Deleted {n} played download{'' if n == 1 else 's'}" if n else 'No played downloads')
        self.refresh()

    def _open_folder(self):
        import os
        from gi.repository import Gio
        d = self.win.settings.download_dir()
        os.makedirs(d, exist_ok=True)
        Gtk.FileLauncher.new(Gio.File.new_for_path(d)).launch(self.win, None, None)


# ---- Discover ----------------------------------------------------------------------------------

class DiscoverPage(Page):
    def __init__(self, win):
        super().__init__(win, 'discover', 'Discover', 'Search for podcasts, or browse what’s popular')
        self.tool('list-add-symbolic', 'Add a podcast by its feed address', win.ask_feed)
        self.search = Gtk.SearchEntry(placeholder_text='Search podcasts by name, topic or host', margin_start=24,
                                      margin_end=24, margin_bottom=12)
        self.search.connect('activate', lambda *_: self._run())
        self.search.connect('search-changed', self._typed)
        self.body.insert_child_after(self.search, self.head)
        self.label = Gtk.Label(xalign=0, margin_start=24, margin_bottom=8)
        self.label.add_css_class('section-title')
        self.body.insert_child_after(self.label, self.search)
        self.grid = tile_grid()
        self.grid.connect('child-activated', lambda _g, t: win.open_show(t.show['feed'], t.show))
        self.stack.add_named(self.grid, 'grid')
        self.stack.add_named(Adw.Spinner(width_request=40, height_request=40, halign=Gtk.Align.CENTER,
                                         valign=Gtk.Align.START, margin_top=40), 'loading')
        self.err = status('network-offline-symbolic', 'Nothing came back')
        self.stack.add_named(self.err, 'error')
        self._timer = 0
        self._token = 0
        self._top = None

    def refresh(self):
        if not self.search.get_text().strip() and self._top is None:
            self._load_top()

    def _load_top(self):
        self.label.set_label('Popular now')
        self.stack.set_visible_child_name('loading')
        self._token += 1
        tok = self._token
        country = self.win.settings['country']

        def done(res):
            self._top = res
            if tok == self._token:
                self._show(res)
        net.run(directory.top_podcasts, country, 40, done=done, fail=lambda m: tok == self._token and self._fail(m))

    def _typed(self, *_):
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(450, self._run)

    def _run(self):
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = 0
        term = self.search.get_text().strip()
        if not term:
            if self._top is not None:
                self.label.set_label('Popular now')
                self._show(self._top)
            else:
                self._load_top()
            return False
        if term.lower().startswith(('http://', 'https://')):
            self.win.open_show(term)
            return False
        self.label.set_label(f'Results for “{term}”')
        self.stack.set_visible_child_name('loading')
        self._token += 1
        tok = self._token
        net.run(directory.search_podcasts, term, self.win.settings['country'],
                done=lambda r: tok == self._token and self._show(r),
                fail=lambda m: tok == self._token and self._fail(m))
        return False

    def _show(self, results):
        clear(self.grid)
        for s in results:
            self.grid.append(ShowTile(s))
        if results:
            self.stack.set_visible_child_name('grid')
        else:
            self.err.set_title('No podcasts found')
            self.err.set_description('Try other words, or paste the show’s feed address.')
            self.stack.set_visible_child_name('error')

    def _fail(self, msg):
        self.err.set_title('Couldn’t reach the podcast directory')
        self.err.set_description(msg)
        self.stack.set_visible_child_name('error')
