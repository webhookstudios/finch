#!/usr/bin/python3
"""Drives the real window against the live podcast and radio directories, with sound muted and
throwaway settings folders. Needs an internet connection.

    python3 tests/ui.py [screenshot-dir]
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
tmp = tempfile.mkdtemp(prefix='finch-test-')
for var in ('XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
    os.environ[var] = os.path.join(tmp, var.lower())

import gi  # noqa: E402

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from finch import feeds  # noqa: E402
from finch.app import FinchApp  # noqa: E402
from finch.ui.widgets import EpisodeRow, StationRow, ShowTile  # noqa: E402

SHOTS = sys.argv[1] if len(sys.argv) > 1 else None
app = FinchApp()
app.set_flags(app.get_flags() | Gio.ApplicationFlags.NON_UNIQUE)
failures, steps = [], []
ctx = {}


def check(what, ok):
    print(('ok   ' if ok else 'FAIL ') + what, flush=True)
    if not ok:
        failures.append(what)


def shot(name, tries=6):
    if not SHOTS:
        return
    win = app.win
    snap = Gtk.Snapshot()
    Gtk.WidgetPaintable.new(win).snapshot(snap, win.get_width(), win.get_height())
    node = snap.to_node()
    if node is None:
        if tries:
            GLib.timeout_add(250, lambda: shot(name, tries - 1) and False)
        return
    win.get_renderer().render_texture(node, None).save_to_png(os.path.join(SHOTS, name + '.png'))
    print('shot ' + name, flush=True)


def children(container, kind):
    out, c = [], container.get_first_child()
    while c:
        if isinstance(c, kind):
            out.append(c)
        c = c.get_next_sibling()
    return out


def step(delay):
    def deco(fn):
        steps.append((delay, fn))
        return fn
    return deco


@step(1500)
def start():
    w = app.win
    check('opens on New Episodes', w.nav.get_visible_page().get_tag() == 'new')
    w.go('discover')


@step(6000)
def discover_top():
    page = app.win.page('discover')
    tiles = children(page.grid, ShowTile)
    check(f'popular podcasts listed ({len(tiles)})', len(tiles) >= 10)
    shot('01-discover')
    page.search.set_text('history podcast')
    page._run()


@step(5000)
def search_results():
    page = app.win.page('discover')
    tiles = children(page.grid, ShowTile)
    check(f'search found shows ({len(tiles)})', len(tiles) >= 3)
    if tiles:
        ctx['show'] = tiles[0].show
        app.win.open_show(tiles[0].show['feed'], tiles[0].show)


@step(7000)
def show_page():
    page = app.win.nav.get_visible_page()
    rows = children(page.list, EpisodeRow)
    check(f'show page lists episodes ({len(rows)})', len(rows) >= 3)
    ctx['page'] = page
    page._toggle_sub()


@step(3000)
def subscribed():
    lib = app.win.library
    feed = ctx['show']['feed']
    check('subscribed', lib.is_subscribed(feed))
    show = lib.podcasts.get(feed, {})
    ctx['eps'] = show.get('episodes', [])
    check('episodes stored', len(ctx['eps']) >= 3)
    check('new episodes listed', 1 <= len(lib.new_episodes()) <= 3)
    shot('02-show')
    app.win.play_episode(ctx['eps'][0]['id'])


@step(9000)
def episode_playing():
    p = app.win.player
    check(f'episode plays ({p.state})', p.state == 'playing')
    check(f'length known ({p.duration:.0f} s)', p.duration > 60)
    ctx['pos0'] = p.position()
    p.skip(30)
    app.win.set_speed(1.5)


@step(4000)
def skipped():
    p = app.win.player
    pos = p.position()
    check(f'skip and speed keep playing ({ctx["pos0"]:.1f} → {pos:.1f} s)', pos > ctx['pos0'] + 30 and p.state == 'playing')
    app.win.set_speed(1.0)
    w = app.win
    w._save_position()
    check('position saved', w.library.st(ctx['eps'][0]['id']).get('pos', 0) > 20)
    w.library.enqueue(ctx['eps'][1]['id'])
    w.library.enqueue(ctx['eps'][2]['id'])
    w.go('queue')
    w.library.download(ctx['eps'][2]['id'])


@step(4000)
def queue_and_download():
    w = app.win
    rows = children(w.page('queue').list, EpisodeRow)
    check(f'Up Next shows 2 episodes ({len(rows)})', len(rows) == 2)
    i = ctx['eps'][2]['id']
    frac = w.library.downloading.get(i)
    done = w.library.st(i).get('file')
    check(f'download running or done ({frac}, {bool(done)})', done or (frac is not None))
    shot('03-up-next')
    w.library.cancel_download(i)
    w.play_next()


@step(6000)
def next_played():
    w = app.win
    check('Play next took the first Up Next episode', w.player.item and w.player.item['id'] == ctx['eps'][1]['id'])
    check('it left Up Next', ctx['eps'][1]['id'] not in w.library.queue)
    w.go('radio-browse')


@step(9000)
def radio_list():
    w = app.win
    page = w.page('radio-browse')
    rows = children(page.list, StationRow)
    check(f'stations listed ({len(rows)})', len(rows) >= 10)
    if rows:
        ctx['station'] = rows[0].station
        w.toggle_station(rows[0].station)
        w.library.toggle_favorite(rows[0].station)


@step(9000)
def radio_playing():
    w = app.win
    p = w.player
    check(f'station plays ({p.state})', p.state == 'playing' and p.live)
    check('station saved to favorites and recent', len(w.library.favorites) == 1 and len(w.library.recent) == 1)
    check('seek bar hidden for live radio', not w.bar.seek_row.get_visible())
    shot('04-radio')
    tag = page_tag = w.page('radio-browse')
    tag.tag = 'jazz'
    tag._load()
    ctx['page_tag'] = page_tag


@step(7000)
def genre():
    rows = children(ctx['page_tag'].list, StationRow)
    check(f'jazz genre lists stations ({len(rows)})', len(rows) >= 5)
    app.win.go('radio-fav')


@step(1200)
def favorites():
    rows = children(app.win.page('radio-fav').list, StationRow)
    check('favorites page shows the station', len(rows) == 1)
    app.win.player.pause()
    check('stopping a live station', app.win.player.state == 'stopped')
    app.settings.set('theme', 'ember')
    app.win.go('subs')


@step(2500)
def subs_ember():
    tiles = children(app.win.page('subs').grid, ShowTile)
    check('subscriptions grid shows the show', len(tiles) == 1)
    shot('05-subscriptions-ember')
    app.settings.set('theme', 'sedge')
    data = feeds.write_opml(app.win.library.shows())
    check('OPML export lists the feed', feeds.read_opml(data) == [ctx['show']['feed']])
    app.activate_action('preferences')


@step(1200)
def prefs():
    shot('06-preferences')
    d = app.win.get_visible_dialog()
    check('preferences open', d is not None)
    if d:
        d.force_close()
    app.win.library.save(now=True)
    from finch.store import Library
    again = Library(app.settings)
    check('library reloads from disk', ctx['show']['feed'] in again.podcasts and len(again.favorites) == 1)


@step(300)
def done():
    print('PASS' if not failures else f'{len(failures)} FAILED', flush=True)
    app.win.close()
    app.quit()


def run(i=0):
    if i >= len(steps):
        return
    delay, fn = steps[i]

    def go():
        try:
            fn()
        except Exception as e:
            import traceback
            traceback.print_exc()
            check(f'{fn.__name__} raised {e!r}', False)
        run(i + 1)
        return False
    GLib.timeout_add(delay, go)


def started(_a):
    if app.win is None:
        print('FAIL window did not open')
        app.quit()
        return
    app.settings.set('muted', True)
    app.win.set_default_size(1120, 740)
    run()


app.connect('activate', lambda a: GLib.idle_add(started, a))
status = app.run([sys.argv[0]])
sys.exit(1 if failures else status)
