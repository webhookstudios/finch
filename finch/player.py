"""Audio playback: a GStreamer playbin with speed control that keeps voices at their normal pitch."""
import gi

gi.require_version('Gst', '1.0')
gi.require_version('GstAudio', '1.0')
gi.require_version('GstPbutils', '1.0')
from gi.repository import GLib, GObject, Gst, GstAudio, GstPbutils  # noqa: E402

Gst.init(None)
SECOND = Gst.SECOND


class Player(GObject.Object):
    """What's loaded is described by `item`: {'kind': 'episode'|'station', 'id', 'title',
    'subtitle', 'image', 'uri'}. Radio has no end and no seeking."""
    __gsignals__ = {
        'state-changed': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'position': (GObject.SignalFlags.RUN_FIRST, None, (float, float)),
        'item-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'now-playing': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        'buffering': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'eos': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'error': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__()
        self.item = None
        self.state = 'stopped'
        self.rate = 1.0
        self.duration = 0.0
        self.now_playing = ''
        self._want = False
        self._buffering = False
        self._start = None
        self._ready = False
        self._known = 0.0
        self._ticker = 0
        self.pb = Gst.ElementFactory.make('playbin', 'player')
        self.pb.props.video_sink = Gst.ElementFactory.make('fakesink', None)
        self.pb.props.flags = 0x2 | 0x10  # audio and software volume only
        self.pb.props.audio_filter = Gst.parse_bin_from_description(
            'audioconvert ! scaletempo ! audioconvert', True)
        bus = self.pb.get_bus()
        bus.add_signal_watch()
        bus.connect('message', self._on_message)

    @property
    def live(self):
        return bool(self.item and self.item['kind'] == 'station')

    def load(self, item, start=0.0, play=True):
        self.pb.set_state(Gst.State.NULL)
        self.item = item
        self.duration = 0.0
        self.now_playing = ''
        self._ready = False
        self._known = start or 0.0
        self._start = start if start and start > 1 and item['kind'] != 'station' else None
        self._want = play
        self.pb.props.uri = item['uri']
        self.emit('item-changed')
        self.emit('position', self._known, 0.0)
        self.pb.set_state(Gst.State.PAUSED if self._start else (Gst.State.PLAYING if play else Gst.State.PAUSED))

    def play(self):
        if self.item:
            self._want = True
            if self.live and self.state == 'stopped':
                self.load(self.item)  # reconnect to the live stream
                return
            if not self._buffering:
                self.pb.set_state(Gst.State.PLAYING)

    def pause(self):
        self._want = False
        if self.live:
            # Pausing a live stream would play stale audio later; stop and reconnect on play.
            self.pb.set_state(Gst.State.NULL)
            self._set_state('stopped')
            self._stop_tick()
        else:
            self.pb.set_state(Gst.State.PAUSED)

    def toggle(self):
        if self.state == 'playing' or (self._want and self._buffering):
            self.pause()
        else:
            self.play()

    def stop(self):
        self._want = False
        self.pb.set_state(Gst.State.NULL)
        self.item = None
        self._set_state('stopped')
        self._stop_tick()
        self.emit('item-changed')

    def position(self):
        ok, pos = self.pb.query_position(Gst.Format.TIME)
        if ok and pos > 0:
            self._known = pos / SECOND
        return self._known

    def seek(self, seconds):
        if not self.item or self.live:
            return
        seconds = max(0.0, seconds)
        if self.duration:
            seconds = min(seconds, self.duration - 0.5)
        self.pb.seek(self.rate, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                     Gst.SeekType.SET, int(seconds * SECOND), Gst.SeekType.NONE, -1)
        self._known = seconds
        self.emit('position', seconds, self.duration)

    def skip(self, delta):
        self.seek(self.position() + delta)

    def set_rate(self, rate):
        self.rate = rate
        if self.item and not self.live and self._ready:
            self.pb.seek(rate, Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                         Gst.SeekType.SET, int(self.position() * SECOND), Gst.SeekType.NONE, -1)

    def set_volume(self, v):
        self.pb.set_volume(GstAudio.StreamVolumeFormat.CUBIC, max(0.0, min(1.25, v)))

    def set_muted(self, m):
        self.pb.props.mute = m

    # ---- bus -----------------------------------------------------------------------------

    def _set_state(self, s):
        if s != self.state:
            self.state = s
            self.emit('state-changed', s)

    def _on_message(self, _bus, msg):
        t = msg.type
        if t == Gst.MessageType.STATE_CHANGED and msg.src == self.pb:
            _o, new, _p = msg.parse_state_changed()
            if new == Gst.State.PLAYING:
                self._set_state('playing')
                self._start_tick()
            elif new == Gst.State.PAUSED and not self._buffering:
                self._set_state('paused')
                self._stop_tick()
                self._tick()
        elif t == Gst.MessageType.ASYNC_DONE:
            ok, dur = self.pb.query_duration(Gst.Format.TIME)
            if ok and dur > 0 and not self.live:
                self.duration = dur / SECOND
            if self._start is not None:
                start, self._start = self._start, None
                self.seek(start)
                if self._want:
                    self.pb.set_state(Gst.State.PLAYING)
                return
            if not self._ready:
                self._ready = True
                if self.rate != 1.0 and not self.live:
                    self.set_rate(self.rate)
            self._tick()
        elif t == Gst.MessageType.DURATION_CHANGED and not self.live:
            ok, dur = self.pb.query_duration(Gst.Format.TIME)
            if ok and dur > 0:
                self.duration = dur / SECOND
        elif t == Gst.MessageType.TAG and self.live:
            ok, title = msg.parse_tag().get_string(Gst.TAG_TITLE)
            if ok and title and title.strip() and title.strip() != self.now_playing:
                self.now_playing = title.strip()
                self.emit('now-playing', self.now_playing)
        elif t == Gst.MessageType.BUFFERING:
            pct = msg.parse_buffering()
            self.emit('buffering', pct)
            if pct < 100 and not self._buffering:
                self._buffering = True
                if self._want:
                    self.pb.set_state(Gst.State.PAUSED)
            elif pct >= 100 and self._buffering:
                self._buffering = False
                if self._want:
                    self.pb.set_state(Gst.State.PLAYING)
        elif t == Gst.MessageType.EOS:
            self._stop_tick()
            self.pb.set_state(Gst.State.PAUSED)
            self.emit('eos')
        elif t == Gst.MessageType.ERROR:
            err, debug = msg.parse_error()
            self.pb.set_state(Gst.State.NULL)
            self._buffering = False
            self._set_state('stopped')
            self._stop_tick()
            self.emit('error', err.message)
        elif t == Gst.MessageType.ELEMENT and GstPbutils.is_missing_plugin_message(msg):
            self.emit('error', 'An extra part is needed to play this: '
                      + GstPbutils.missing_plugin_message_get_description(msg) + '.')

    def _start_tick(self):
        if not self._ticker:
            self._ticker = GLib.timeout_add(500, self._tick)

    def _stop_tick(self):
        if self._ticker:
            GLib.source_remove(self._ticker)
            self._ticker = 0

    def _tick(self):
        if not self.duration and not self.live:
            ok, dur = self.pb.query_duration(Gst.Format.TIME)
            if ok and dur > 0:
                self.duration = dur / SECOND
        self.emit('position', self.position(), self.duration)
        return True

    def shutdown(self):
        self._stop_tick()
        self.pb.set_state(Gst.State.NULL)
