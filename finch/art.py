"""Cover art and station logos: fetched once, scaled down, kept in ~/.cache/finch/art."""
import hashlib
import os

import gi

gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, GLib  # noqa: E402

from . import net  # noqa: E402
from .settings import CACHE  # noqa: E402

ART = os.path.join(CACHE, 'art')
SIZE = 300
_textures = {}
_waiting = {}
_failed = set()


def _path(url):
    return os.path.join(ART, hashlib.sha1(url.encode()).hexdigest() + '.png')


def _make(url):
    data = net.fetch(url, timeout=20, max_bytes=8 * 1024 * 1024)
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    pix = loader.get_pixbuf()
    if pix is None:
        raise ValueError('not an image')
    w, h = pix.get_width(), pix.get_height()
    if max(w, h) > SIZE:
        f = SIZE / max(w, h)
        pix = pix.scale_simple(max(1, round(w * f)), max(1, round(h * f)), GdkPixbuf.InterpType.BILINEAR)
    os.makedirs(ART, exist_ok=True)
    out = _path(url)
    pix.savev(out + '.tmp', 'png', [], [])
    os.replace(out + '.tmp', out)
    return out


def get(url, callback):
    """Calls callback(texture) now if the image is ready, otherwise later. Never calls it on failure."""
    if not url or url in _failed:
        return
    if url in _textures:
        callback(_textures[url])
        return
    p = _path(url)
    if os.path.exists(p):
        try:
            _textures[url] = Gdk.Texture.new_from_filename(p)
            callback(_textures[url])
            return
        except GLib.Error:
            pass
    if url in _waiting:
        _waiting[url].append(callback)
        return
    _waiting[url] = [callback]

    def done(path):
        try:
            tex = Gdk.Texture.new_from_filename(path)
        except GLib.Error:
            failed('')
            return
        _textures[url] = tex
        for cb in _waiting.pop(url, []):
            cb(tex)

    def failed(_msg):
        _failed.add(url)
        _waiting.pop(url, None)
    net.run(_make, url, done=done, fail=failed)
