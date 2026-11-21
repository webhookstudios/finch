"""The bar along the bottom: what's playing, play controls, seek bar, speed, sleep timer and volume."""
import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from .widgets import Art, fmt_time  # noqa: E402

SPEEDS = (0.5, 0.75, 0.9, 1.0, 1.1, 1.2, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0)
SLEEP = ((15, '15 minutes'), (30, '30 minutes'), (45, '45 minutes'), (60, '1 hour'), (90, '1 hour 30 minutes'))


def _btn(icon, tip, cb=None, action=None):
    b = Gtk.Button(icon_name=icon, tooltip_text=tip, valign=Gtk.Align.CENTER, focus_on_click=False)
    b.add_css_class('flat')
    if cb:
        b.connect('clicked', lambda *_: cb())
    if action:
        b.set_action_name(action)
    return b


class PlayerBar(Gtk.Box):
    def __init__(self, win):
        super().__init__(spacing=14)
        self.win, self.player, self.settings = win, win.player, win.settings
        self.add_css_class('playerbar')
        self._dragging = False
        self._seek_timer = 0
        self._dur = 0.0

        # What's playing
        now = Gtk.Button(focus_on_click=False, tooltip_text='Show this show’s page')
        now.add_css_class('flat')
        now.connect('clicked', lambda *_: win.reveal_current())
        nbox = Gtk.Box(spacing=12)
        self.art = Art(52)
        nbox.append(self.art)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, width_request=180)
        top = Gtk.Box(spacing=6)
        self.live = Gtk.Label(label='LIVE', valign=Gtk.Align.CENTER)
        self.live.add_css_class('badge-live')
        top.append(self.live)
        self.title = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=28)
        self.title.add_css_class('bar-title')
        top.append(self.title)
        text.append(top)
        self.sub = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=34)
        self.sub.add_css_class('caption')
        self.sub.add_css_class('dim-label')
        text.append(self.sub)
        nbox.append(text)
        now.set_child(nbox)
        self.now = now
        self.append(now)

        # Middle: buttons over the seek bar
        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, valign=Gtk.Align.CENTER, spacing=2)
        btns = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        self.back = _btn('media-seek-backward-symbolic', '', lambda: self._skip(-self.settings['skip_back']))
        self.play = _btn('media-playback-start-symbolic', 'Play (Space)', lambda: self.player.toggle())
        self.play.remove_css_class('flat')
        self.play.add_css_class('suggested-action')
        self.play.add_css_class('play')
        self.fwd = _btn('media-seek-forward-symbolic', '', lambda: self._skip(self.settings['skip_forward']))
        self.next = _btn('media-skip-forward-symbolic', 'Play the next episode in Up Next', lambda: win.play_next())
        for w in (self.back, self.play, self.fwd, self.next):
            btns.append(w)
        mid.append(btns)
        self.seek_row = Gtk.Box(spacing=8)
        self.cur = Gtk.Label(label='0:00', xalign=1)
        self.cur.add_css_class('time')
        self.seek = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, hexpand=True, draw_value=False,
                              focus_on_click=False, has_tooltip=True)
        self.seek.add_css_class('seek')
        self.seek.set_range(0, 1)
        self.seek.connect('change-value', self._seek_changed)
        self.seek.connect('query-tooltip', self._seek_tip)
        self.left = Gtk.Label(label='0:00', xalign=0)
        self.left.add_css_class('time')
        for w in (self.cur, self.seek, self.left):
            self.seek_row.append(w)
        mid.append(self.seek_row)
        self.append(mid)

        # Right: speed, sleep, volume
        right = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)
        self.speed = Gtk.MenuButton(icon_name='finch-speed-symbolic', focus_on_click=False,
                                    direction=Gtk.ArrowType.UP)
        self.speed.add_css_class('flat')
        sm = Gio.Menu()
        for r in SPEEDS:
            sm.append(f'{r:g}×', f'win.speed::{r:g}')
        self.speed.set_menu_model(sm)
        right.append(self.speed)
        self.sleep = Gtk.MenuButton(icon_name='finch-sleep-symbolic', focus_on_click=False,
                                    direction=Gtk.ArrowType.UP, tooltip_text='Sleep timer')
        self.sleep.add_css_class('flat')
        slm = Gio.Menu()
        opts = Gio.Menu()
        for mins, label in SLEEP:
            opts.append(label, f'win.sleep::{mins}')
        opts.append('End of this episode', 'win.sleep::end')
        slm.append_section(None, opts)
        off = Gio.Menu()
        off.append('Turn off', 'win.sleep::off')
        slm.append_section(None, off)
        self.sleep.set_menu_model(slm)
        right.append(self.sleep)
        self.mute = _btn('audio-volume-high-symbolic', 'Mute', lambda: self.settings.set('muted', not self.settings['muted']))
        right.append(self.mute)
        self.vol = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, draw_value=False, width_request=96,
                             focus_on_click=False, valign=Gtk.Align.CENTER)
        self.vol.add_css_class('vol')
        self.vol.set_range(0, 1.25)
        self.vol.set_increments(0.05, 0.1)
        self.vol.add_mark(1.0, Gtk.PositionType.BOTTOM, None)
        self.vol.set_value(self.settings['volume'])
        self._vol_sig = self.vol.connect('value-changed', self._vol_moved)
        right.append(self.vol)
        # The percentage beside the slider: shown while the volume is being changed, then it fades.
        # Its space is always kept, so the slider never moves under the pointer.
        self.vol_pct = Gtk.Label(width_chars=4, xalign=0, can_target=False)
        self.vol_pct.add_css_class('vol-pct')
        right.append(self.vol_pct)
        self._sliding = False
        self._pct_timer = 0
        watch = Gtk.EventControllerLegacy(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        watch.connect('event', self._vol_event)
        self.vol.add_controller(watch)
        self.append(right)

        self.player.connect('state-changed', lambda *_: self._sync_state())
        self.player.connect('item-changed', lambda *_: self.sync_item())
        self.player.connect('now-playing', lambda *_: self.sync_item())
        self.player.connect('position', self._position)
        self.settings.connect('changed', self._setting)
        self._sync_skip_tips()
        self._sync_volume()
        self._sync_speed()
        self.sync_item()

    # ---- syncing -------------------------------------------------------------------------

    def sync_item(self):
        item = self.player.item
        self.set_visible(item is not None)
        if not item:
            return
        live = self.player.live
        self.live.set_visible(live)
        if live and self.player.now_playing:
            self.title.set_label(self.player.now_playing)
            self.sub.set_label(item['title'])
        else:
            self.title.set_label(item['title'])
            self.sub.set_label(item.get('subtitle', ''))
        self.title.set_tooltip_text(self.title.get_label())
        self.art.set_url(item.get('image'), icon='finch-radio-symbolic' if live else 'audio-input-microphone-symbolic')
        self.now.set_tooltip_text('Show this station' if live else 'Show this show’s page')
        for w in (self.back, self.fwd, self.speed, self.seek_row):
            w.set_visible(not live)
        self.next.set_visible(not live and bool(self.win.library.queue))
        self._sync_state()

    def _sync_state(self):
        p = self.player
        playing = p.state == 'playing'
        if p.live:
            icon, tip = ('media-playback-stop-symbolic', 'Stop (Space)') if playing else \
                ('media-playback-start-symbolic', 'Listen (Space)')
        else:
            icon, tip = ('media-playback-pause-symbolic', 'Pause (Space)') if playing else \
                ('media-playback-start-symbolic', 'Play (Space)')
        self.play.set_icon_name(icon)
        self.play.set_tooltip_text(tip)
        self.next.set_visible(p.item is not None and not p.live and bool(self.win.library.queue))

    def _position(self, _p, pos, dur):
        self._dur = dur
        if self._dragging or self.player.live:
            return
        self.seek.set_range(0, max(dur, 0.001))
        self.seek.set_value(pos)
        self.seek.set_sensitive(dur > 0)
        self.cur.set_label(fmt_time(pos))
        self.left.set_label('-' + fmt_time(dur - pos) if dur else '–:––')

    def _setting(self, _s, key):
        if key in ('volume', 'muted'):
            self._sync_volume()
        elif key in ('skip_back', 'skip_forward'):
            self._sync_skip_tips()
        elif key == 'speed':
            self._sync_speed()

    def _sync_skip_tips(self):
        self.back.set_tooltip_text(f"Back {self.settings['skip_back']} seconds (Left)")
        self.fwd.set_tooltip_text(f"Forward {self.settings['skip_forward']} seconds (Right)")

    def _sync_speed(self):
        r = self.settings['speed']
        self.speed.set_tooltip_text(f'Speed: {r:g}×')
        (self.speed.add_css_class if r != 1.0 else self.speed.remove_css_class)('accent')

    def sync_sleep(self, label):
        self.sleep.set_tooltip_text(f'Sleep timer: {label}' if label else 'Sleep timer')
        (self.sleep.add_css_class if label else self.sleep.remove_css_class)('accent')

    def _sync_volume(self):
        v, m = self.settings['volume'], self.settings['muted']
        if abs(self.vol.get_value() - v) > 0.001:
            self.vol.handler_block(self._vol_sig)
            self.vol.set_value(v)
            self.vol.handler_unblock(self._vol_sig)
        icon = ('audio-volume-muted-symbolic' if m or v <= 0.001 else 'audio-volume-low-symbolic' if v < 0.34
                else 'audio-volume-medium-symbolic' if v < 0.67 else 'audio-volume-high-symbolic')
        self.mute.set_icon_name(icon)
        self.mute.set_tooltip_text(('Unmute' if m else 'Mute') + f' · Volume {round(v * 100)}%')

    # ---- input ---------------------------------------------------------------------------

    def _skip(self, delta):
        self.player.skip(delta)

    def _seek_changed(self, _s, _scroll, value):
        if not self._dur:
            return True
        self._dragging = True
        value = max(0.0, min(value, self._dur))
        self.seek.set_value(value)
        self.cur.set_label(fmt_time(value))
        self.left.set_label('-' + fmt_time(self._dur - value))
        if self._seek_timer:
            GLib.source_remove(self._seek_timer)
        self._seek_timer = GLib.timeout_add(200, self._finish_seek, value)
        return True

    def _finish_seek(self, value):
        self._seek_timer = 0
        self.player.seek(value)
        self._dragging = False
        return False

    def _seek_tip(self, scale, x, _y, _kb, tooltip):
        if not self._dur:
            return False
        frac = max(0.0, min(1.0, (x - 7) / max(1, scale.get_width() - 14)))
        tooltip.set_text(fmt_time(frac * self._dur))
        return True

    def _vol_moved(self, scale):
        self.settings.set('volume', round(scale.get_value(), 3))
        self._show_pct()

    def _vol_event(self, _c, event):
        if event is None:
            return False
        t = event.get_event_type()
        if t in (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.TOUCH_BEGIN):
            self._sliding = True
            self._show_pct()
        elif t in (Gdk.EventType.BUTTON_RELEASE, Gdk.EventType.TOUCH_END, Gdk.EventType.TOUCH_CANCEL):
            self._sliding = False
            self._hide_pct_soon(500)
        return False

    def _show_pct(self):
        self.vol_pct.set_label(f'{round(self.vol.get_value() * 100)}%')
        self.vol_pct.add_css_class('shown')
        self._hide_pct_soon(900)

    def _hide_pct_soon(self, ms):
        if self._pct_timer:
            GLib.source_remove(self._pct_timer)
        self._pct_timer = GLib.timeout_add(ms, self._hide_pct)

    def _hide_pct(self):
        self._pct_timer = 0
        if self._sliding:
            return False  # still held: the release hides it
        self.vol_pct.remove_css_class('shown')
        return False
