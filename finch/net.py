"""Small network helpers: fetch in a worker thread, hand the answer back on the main loop."""
import os
import threading
import urllib.error
import urllib.request

from gi.repository import GLib

from . import __version__

UA = f'Finch/{__version__} (+https://github.com/webhookstudios/finch)'
MAX_BYTES = 30 * 1024 * 1024


class NetError(Exception):
    pass


def fetch(url, timeout=25, max_bytes=MAX_BYTES, headers=None):
    """GET a URL and return its bytes. Runs on the calling thread."""
    if not url.lower().startswith(('http://', 'https://')):
        raise NetError('Only web addresses (http or https) can be opened.')
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*', **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        raise NetError(f'The server answered {e.code}.') from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        reason = getattr(e, 'reason', e)
        raise NetError(f"Couldn't reach it ({reason}).") from e
    if len(data) > max_bytes:
        raise NetError('That is too large to read.')
    return data


def run(fn, *args, done=None, fail=None):
    """Call fn(*args) on a worker thread; then done(result) or fail(message) on the main loop."""
    def work():
        try:
            result = fn(*args)
        except Exception as e:  # report every failure the same way
            msg = str(e) or e.__class__.__name__
            if fail:
                GLib.idle_add(lambda: fail(msg) and False)
            return
        if done:
            GLib.idle_add(lambda: done(result) and False)
    threading.Thread(target=work, daemon=True).start()


def download(url, path, progress=None, cancelled=None, timeout=30):
    """Stream a URL to path, through path + '.part'. progress(done_bytes, total_or_0) is called
    on this (worker) thread. Returns the path, or raises NetError."""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    tmp = path + '.part'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(tmp, 'wb') as out:
            total = int(resp.headers.get('Content-Length') or 0)
            got = 0
            while True:
                if cancelled and cancelled():
                    raise NetError('Cancelled.')
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                if progress:
                    progress(got, total)
        os.replace(tmp, path)
        return path
    except urllib.error.HTTPError as e:
        _rm(tmp)
        raise NetError(f'The server answered {e.code}.') from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        _rm(tmp)
        raise NetError(f'The download stopped ({getattr(e, "reason", e)}).') from e
    except NetError:
        _rm(tmp)
        raise


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass
