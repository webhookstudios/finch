"""Pieces the pages share: artwork, episode rows, station rows and show tiles."""
import time

import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gio, GLib, Gtk, Pango  # noqa: E402

from .. import art  # noqa: E402


def fmt_time(seconds):
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m}:{s:02d}'


def fmt_length(seconds):
    seconds = int(seconds)
    if seconds <= 0:
        return ''
    h, m = divmod(round(seconds / 60), 60)
    return f'{h} h {m} min' if h else f'{max(m, 1)} min'


def fmt_date(ts):
    if not ts:
        return ''
    days = (time.time() - ts) / 86400
    if days < 1 and time.localtime(ts).tm_mday == time.localtime().tm_mday:
        return 'Today'
    if days < 2:
        return 'Yesterday'
    if days < 7:
        return time.strftime('%A', time.localtime(ts))
    if time.localtime(ts).tm_year == time.localtime().tm_year:
        return time.strftime('%b %-d', time.localtime(ts))
    return time.strftime('%b %-d, %Y', time.localtime(ts))


def flat_button(icon, tip, cb=None):
    b = Gtk.Button(icon_name=icon, tooltip_text=tip, valign=Gtk.Align.CENTER)
    b.add_css_class('flat')
    if cb:
        b.connect('clicked', lambda *_: cb())
    return b


def page_header(title, subtitle=None):
    box = Gtk.Box(spacing=6, margin_start=24, margin_end=18, margin_top=18, margin_bottom=8)
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
    t = Gtk.Label(label=title, xalign=0, ellipsize=Pango.EllipsizeMode.END)
    t.add_css_class('page-title')
    text.append(t)
    sub = Gtk.Label(label=subtitle or '', xalign=0, visible=bool(subtitle), ellipsize=Pango.EllipsizeMode.END)
    sub.add_css_class('dim-label')
    text.append(sub)
    box.append(text)
    box.title, box.sub = t, sub
    return box


class Art(Gtk.Overlay):
    """Square artwork with an icon until the picture arrives."""

    def __init__(self, size, url=None, icon='audio-input-microphone-symbolic', large=False):
        super().__init__(width_request=size, height_request=size, valign=Gtk.Align.CENTER,
                         halign=Gtk.Align.CENTER)
        self.add_css_class('art-large' if large else 'art')
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.icon = Gtk.Image(icon_name=icon, pixel_size=max(16, size // 3), halign=Gtk.Align.CENTER,
                              valign=Gtk.Align.CENTER)
        self.icon.add_css_class('dim-label')
        self.set_child(self.icon)
        self.pic = Gtk.Picture(content_fit=Gtk.ContentFit.COVER, can_shrink=True, visible=False)
        self.add_overlay(self.pic)
        self._url = None
        self.set_url(url)

    def set_url(self, url, icon=None):
        if icon:
            self.icon.set_from_icon_name(icon)
        self._url = url
        self.pic.set_visible(False)
        self.icon.set_visible(True)
        if url:
            art.get(url, lambda tex, u=url: self._show(u, tex))

    def _show(self, url, tex):
        if url == self._url:
            self.pic.set_paintable(tex)
            self.pic.set_visible(True)
            self.icon.set_visible(False)


class EpisodeRow(Gtk.ListBoxRow):
    """One episode: artwork, title, date and length, how far you got, and its buttons."""

    def __init__(self, win, show, ep, show_name=True, queue=False):
        super().__init__(activatable=True)
        self.win, self.show, self.ep, self.queue = win, show, ep, queue
        self.add_css_class('episode-row')
        lib = win.library
        box = Gtk.Box(spacing=12, margin_start=10, margin_end=8, margin_top=8, margin_bottom=8)
        box.append(Art(52, ep.get('image') or show.get('image')))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True, valign=Gtk.Align.CENTER)
        if show_name:
            s = Gtk.Label(label=show['title'], xalign=0, ellipsize=Pango.EllipsizeMode.END)
            s.add_css_class('caption')
            s.add_css_class('dim-label')
            text.append(s)
        self.title = Gtk.Label(label=ep['title'], xalign=0, wrap=True, lines=2,
                               ellipsize=Pango.EllipsizeMode.END, wrap_mode=Pango.WrapMode.WORD_CHAR)
        self.title.add_css_class('ep-title')
        self.title.add_css_class('heading')
        text.append(self.title)
        meta_box = Gtk.Box(spacing=8)
        self.new = Gtk.Label(label='New', valign=Gtk.Align.CENTER)
        self.new.add_css_class('badge-new')
        meta_box.append(self.new)
        self.meta = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
        self.meta.add_css_class('caption')
        self.meta.add_css_class('dim-label')
        meta_box.append(self.meta)
        text.append(meta_box)
        self.bar = Gtk.ProgressBar(visible=False, margin_top=4)
        self.bar.add_css_class('ep-progress')
        text.append(self.bar)
        box.append(text)

        if queue:
            box.append(flat_button('go-up-symbolic', 'Move up', lambda: lib.move_in_queue(ep['id'], -1)))
            box.append(flat_button('go-down-symbolic', 'Move down', lambda: lib.move_in_queue(ep['id'], 1)))
        self.dl = flat_button('folder-download-symbolic', 'Download', self._download_clicked)
        box.append(self.dl)
        self.play = flat_button('media-playback-start-symbolic', 'Play', lambda: win.play_episode(ep['id']))
        self.play.add_css_class('circular')
        box.append(self.play)
        more = Gtk.MenuButton(icon_name='view-more-symbolic', tooltip_text='More', valign=Gtk.Align.CENTER)
        more.add_css_class('flat')
        more.set_create_popup_func(self._menu)
        box.append(more)
        self.set_child(box)

        win.rows.add(self)  # the window tells live rows about changes; a weak set, so old rows just go
        self.connect('activate', lambda *_: win.show_notes(show, ep))
        self.sync()

    def _menu(self, button):
        lib = self.win.library
        st = lib.st(self.ep['id'])
        i = self.ep['id']
        m = Gio.Menu()
        if self.queue:
            m.append('Remove from Up Next', f'win.dequeue::{i}')
        else:
            m.append('Play Next', f'win.play-next::{i}')
            m.append('Add to Up Next', f'win.enqueue::{i}')
        m.append('Mark as Unplayed' if st.get('played') else 'Mark as Played', f'win.toggle-played::{i}')
        m.append('Show Notes', f'win.show-notes::{i}')
        if self.ep.get('link'):
            m.append('Open Episode Web Page', f'win.open-link::{i}')
        button.set_menu_model(m)

    def _download_clicked(self):
        lib = self.win.library
        i = self.ep['id']
        if i in lib.downloading:
            lib.cancel_download(i)
        elif lib.st(i).get('file'):
            lib.delete_download(i)
        else:
            lib.download(i)

    def key(self):
        return self.ep['id']

    def _sync_play(self):
        p = self.win.player
        mine = p.item is not None and p.item.get('id') == self.ep['id']
        playing = mine and p.state == 'playing'
        self.play.set_icon_name('media-playback-pause-symbolic' if playing else 'media-playback-start-symbolic')
        self.play.set_tooltip_text('Pause' if playing else ('Resume' if self.win.library.st(self.ep['id']).get('pos')
                                                             else 'Play'))
        (self.play.add_css_class if mine else self.play.remove_css_class)('suggested-action')

    def sync(self):
        lib = self.win.library
        st = lib.st(self.ep['id'])
        played = st.get('played', False)
        pos = st.get('pos', 0)
        dur = self.ep.get('duration', 0)
        bits = [fmt_date(self.ep['date'])]
        if played:
            bits.append('Played')
        elif pos and dur:
            bits.append(f'{fmt_length(dur - pos)} left')
        elif dur:
            bits.append(fmt_length(dur))
        if st.get('file'):
            bits.append('Downloaded')
        self.meta.set_label(' · '.join(b for b in bits if b))
        self.new.set_visible(not played and not st.get('seen') and time.time() - self.ep['date'] < 14 * 86400)
        (self.add_css_class if played else self.remove_css_class)('played')
        self.bar.set_visible(bool(pos and dur and not played))
        if pos and dur:
            self.bar.set_fraction(min(1.0, pos / dur))
        i = self.ep['id']
        if i in lib.downloading:
            frac = lib.downloading[i]
            self.dl.set_icon_name('process-stop-symbolic')
            self.dl.set_tooltip_text(('Downloading' + (f' {round(frac * 100)}%' if frac >= 0 else '…'))
                                     + '. Click to stop')
        elif st.get('file'):
            self.dl.set_icon_name('user-trash-symbolic')
            self.dl.set_tooltip_text('Delete the download')
        else:
            self.dl.set_icon_name('folder-download-symbolic')
            self.dl.set_tooltip_text('Download to listen offline')
        self._sync_play()


class StationRow(Gtk.ListBoxRow):
    def __init__(self, win, station):
        super().__init__(activatable=True)
        self.win, self.station = win, station
        box = Gtk.Box(spacing=12, margin_start=10, margin_end=8, margin_top=6, margin_bottom=6)
        box.append(Art(44, station.get('favicon'), icon='finch-radio-symbolic'))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER)
        name = Gtk.Label(label=station['name'], xalign=0, ellipsize=Pango.EllipsizeMode.END)
        name.add_css_class('heading')
        text.append(name)
        bits = []
        if station.get('tags'):
            bits.append(', '.join(station['tags'][:3]))
        if station.get('country'):
            bits.append(station['country'])
        if station.get('codec'):
            bits.append(f"{station['codec']} {station['bitrate']} kb/s" if station.get('bitrate') else station['codec'])
        meta = Gtk.Label(label=' · '.join(bits), xalign=0, ellipsize=Pango.EllipsizeMode.END, visible=bool(bits))
        meta.add_css_class('caption')
        meta.add_css_class('dim-label')
        text.append(meta)
        box.append(text)
        self.star = flat_button('non-starred-symbolic', '', lambda: win.library.toggle_favorite(station))
        box.append(self.star)
        self.play = flat_button('media-playback-start-symbolic', 'Listen', lambda: win.toggle_station(station))
        self.play.add_css_class('circular')
        box.append(self.play)
        self.set_child(box)
        self.set_tooltip_text(station.get('homepage') or station['name'])
        win.rows.add(self)
        self.connect('activate', lambda *_: win.toggle_station(station))
        self.sync()

    def key(self):
        return None  # synced on every station or player change

    def sync(self):
        fav = self.win.library.is_favorite(self.station)
        self.star.set_icon_name('starred-symbolic' if fav else 'non-starred-symbolic')
        self.star.set_tooltip_text('Remove from favorites' if fav else 'Add to favorites')
        (self.star.add_css_class if fav else self.star.remove_css_class)('accent')
        p = self.win.player
        mine = p.item is not None and p.item.get('id') == self.win.library.station_key(self.station)
        on = mine and p.state == 'playing'
        self.play.set_icon_name('media-playback-stop-symbolic' if on else 'media-playback-start-symbolic')
        self.play.set_tooltip_text('Stop' if on else 'Listen')
        (self.play.add_css_class if mine else self.play.remove_css_class)('suggested-action')


class ShowTile(Gtk.FlowBoxChild):
    def __init__(self, show, badge=0):
        super().__init__()
        self.show = show
        self.add_css_class('tile')
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, width_request=160)
        frame = Gtk.Overlay()
        frame.set_child(Art(160, show.get('image')))
        if badge:
            b = Gtk.Label(label=str(badge), halign=Gtk.Align.END, valign=Gtk.Align.START, margin_top=6,
                          margin_end=6)
            b.add_css_class('badge-new')
            b.set_tooltip_text(f"{badge} new episode{'' if badge == 1 else 's'}")
            frame.add_overlay(b)
        box.append(frame)
        name = Gtk.Label(label=show['title'], xalign=0, wrap=True, lines=2, ellipsize=Pango.EllipsizeMode.END,
                         max_width_chars=18, wrap_mode=Pango.WrapMode.WORD_CHAR)
        name.add_css_class('tile-name')
        box.append(name)
        if show.get('author'):
            a = Gtk.Label(label=show['author'], xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=18)
            a.add_css_class('caption')
            a.add_css_class('dim-label')
            box.append(a)
        self.set_child(box)
        self.set_tooltip_text(show['title'])


def boxed_list():
    lst = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, margin_start=24, margin_end=24, margin_bottom=24,
                      valign=Gtk.Align.START)
    lst.add_css_class('boxed-list')
    return lst


def tile_grid():
    return Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, activate_on_single_click=True, column_spacing=12,
                       row_spacing=16, valign=Gtk.Align.START, margin_start=24, margin_end=24, margin_bottom=24,
                       max_children_per_line=10, homogeneous=True)


def status(icon, title, description=''):
    s = Adw.StatusPage(icon_name=icon, title=title, description=description, vexpand=True)
    s.add_css_class('compact')
    return s


def clear(container):
    if isinstance(container, (Gtk.ListBox, Gtk.FlowBox)):
        container.remove_all()
        return
    while (c := container.get_first_child()) is not None:
        container.remove(c)


GLib  # keeps the import for callers that use widgets.GLib
