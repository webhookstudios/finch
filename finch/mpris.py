"""Media keys and the system's media controls, through the MPRIS D-Bus interface."""
import re

from gi.repository import Gio, GLib

XML = '''
<node>
  <interface name="org.mpris.MediaPlayer2">
    <method name="Raise"/><method name="Quit"/>
    <property name="CanQuit" type="b" access="read"/>
    <property name="CanRaise" type="b" access="read"/>
    <property name="HasTrackList" type="b" access="read"/>
    <property name="Identity" type="s" access="read"/>
    <property name="DesktopEntry" type="s" access="read"/>
    <property name="SupportedUriSchemes" type="as" access="read"/>
    <property name="SupportedMimeTypes" type="as" access="read"/>
  </interface>
  <interface name="org.mpris.MediaPlayer2.Player">
    <method name="Next"/><method name="Previous"/><method name="Pause"/><method name="PlayPause"/>
    <method name="Stop"/><method name="Play"/>
    <method name="Seek"><arg direction="in" name="Offset" type="x"/></method>
    <method name="SetPosition"><arg direction="in" name="TrackId" type="o"/><arg direction="in" name="Position" type="x"/></method>
    <method name="OpenUri"><arg direction="in" name="Uri" type="s"/></method>
    <signal name="Seeked"><arg name="Position" type="x"/></signal>
    <property name="PlaybackStatus" type="s" access="read"/>
    <property name="Rate" type="d" access="readwrite"/>
    <property name="Metadata" type="a{sv}" access="read"/>
    <property name="Volume" type="d" access="readwrite"/>
    <property name="Position" type="x" access="read"/>
    <property name="MinimumRate" type="d" access="read"/>
    <property name="MaximumRate" type="d" access="read"/>
    <property name="CanGoNext" type="b" access="read"/>
    <property name="CanGoPrevious" type="b" access="read"/>
    <property name="CanPlay" type="b" access="read"/>
    <property name="CanPause" type="b" access="read"/>
    <property name="CanSeek" type="b" access="read"/>
    <property name="CanControl" type="b" access="read"/>
  </interface>
</node>
'''
PATH = '/org/mpris/MediaPlayer2'
PLAYER = 'org.mpris.MediaPlayer2.Player'


class Mpris:
    def __init__(self, app, win):
        self.app, self.win = app, win
        self.conn = None
        self.ids = []
        self.owner = Gio.bus_own_name(Gio.BusType.SESSION, 'org.mpris.MediaPlayer2.finch',
                                      Gio.BusNameOwnerFlags.NONE, self._acquired, None, None)
        p = win.player
        p.connect('state-changed', lambda *_: self.changed('PlaybackStatus', 'CanPlay', 'CanPause', 'CanSeek'))
        p.connect('item-changed', lambda *_: self.changed('Metadata', 'CanGoNext', 'CanSeek'))
        p.connect('now-playing', lambda *_: self.changed('Metadata'))
        win.settings.connect('changed', lambda _s, k: self.changed('Volume') if k == 'volume' else
                             self.changed('Rate') if k == 'speed' else None)

    def _acquired(self, conn, _name):
        self.conn = conn
        for iface in Gio.DBusNodeInfo.new_for_xml(XML).interfaces:
            self.ids.append(conn.register_object(PATH, iface, self._call, self._get, self._set))

    def changed(self, *names):
        if not self.conn:
            return
        props = {n: v for n in names if (v := self._value(PLAYER, n)) is not None}
        self.conn.emit_signal(None, PATH, 'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                              GLib.Variant('(sa{sv}as)', (PLAYER, props, [])))

    def _call(self, _c, _s, _p, _iface, method, params, inv):
        w, p = self.win, self.win.player
        if method == 'Raise':
            w.present()
        elif method == 'Quit':
            self.app.quit()
        elif method == 'Next':
            w.play_next()
        elif method == 'Previous':
            p.seek(0)
        elif method == 'Pause':
            p.pause()
        elif method == 'Play':
            p.play()
        elif method == 'PlayPause':
            p.toggle()
        elif method == 'Stop':
            p.pause()
        elif method == 'Seek':
            p.skip(params.unpack()[0] / 1e6)
        elif method == 'SetPosition':
            p.seek(params.unpack()[1] / 1e6)
        inv.return_value(None)

    def _get(self, _c, _s, _p, iface, prop):
        return self._value(iface, prop)

    def _set(self, _c, _s, _p, _iface, prop, value):
        if prop == 'Volume':
            self.win.settings.set('volume', max(0.0, min(1.25, float(value.unpack()))))
        elif prop == 'Rate':
            self.win.set_speed(float(value.unpack()))
        return True

    def _value(self, iface, prop):
        V = GLib.Variant
        if iface != PLAYER:
            return {'CanQuit': V('b', True), 'CanRaise': V('b', True), 'HasTrackList': V('b', False),
                    'Identity': V('s', 'Finch'), 'DesktopEntry': V('s', 'io.github.webhookstudios.Finch'),
                    'SupportedUriSchemes': V('as', ['http', 'https', 'file']),
                    'SupportedMimeTypes': V('as', ['audio/*'])}.get(prop)
        p = self.win.player
        item = p.item
        if prop == 'PlaybackStatus':
            return V('s', {'playing': 'Playing', 'paused': 'Paused'}.get(p.state, 'Stopped'))
        if prop == 'Rate':
            return V('d', self.win.settings['speed'] if not p.live else 1.0)
        if prop == 'Volume':
            return V('d', self.win.settings['volume'])
        if prop == 'Position':
            return V('x', int(p.position() * 1e6))
        if prop == 'MinimumRate':
            return V('d', 0.5)
        if prop == 'MaximumRate':
            return V('d', 3.0)
        if prop == 'CanGoNext':
            return V('b', bool(self.win.library.queue))
        if prop == 'CanGoPrevious':
            return V('b', item is not None and not p.live)
        if prop in ('CanPlay', 'CanPause'):
            return V('b', item is not None)
        if prop == 'CanSeek':
            return V('b', item is not None and not p.live)
        if prop == 'CanControl':
            return V('b', True)
        if prop == 'Metadata':
            safe = re.sub(r'[^A-Za-z0-9_]', '_', item['id']) if item else ''
            meta = {'mpris:trackid': V('o', '/io/github/webhookstudios/Finch/' + ('t' + safe if item else 'none'))}
            if item:
                title = p.now_playing if p.live and p.now_playing else item['title']
                meta['xesam:title'] = V('s', title)
                meta['xesam:artist'] = V('as', [item['title'] if p.live else item['subtitle']])
                meta['xesam:album'] = V('s', item['subtitle'] if not p.live else 'Radio')
                if item.get('image'):
                    meta['mpris:artUrl'] = V('s', item['image'])
                if p.duration and not p.live:
                    meta['mpris:length'] = V('x', int(p.duration * 1e6))
            return V('a{sv}', meta)
        return None

    def close(self):
        if self.conn:
            for i in self.ids:
                self.conn.unregister_object(i)
        Gio.bus_unown_name(self.owner)
