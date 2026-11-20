"""Radio pages: browse and search stations, favorites, and recently played."""
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk  # noqa: E402

from .. import directory, net  # noqa: E402
from .pages import Page  # noqa: E402
from .widgets import StationRow, boxed_list, clear, status  # noqa: E402

# A fixed list: the directory's own most-used tags mix languages and place names.
FALLBACK_TAGS = ['pop', 'rock', 'news', 'talk', 'jazz', 'classical', 'country', 'dance', 'hip hop', 'oldies',
                 '80s', '90s', 'chillout', 'ambient', 'lofi', 'blues', 'soul', 'r&b', 'reggae', 'electronic',
                 'metal', 'indie', 'folk', 'latin', 'sports', 'comedy', 'christian', 'kids']


class BrowsePage(Page):
    def __init__(self, win):
        super().__init__(win, 'radio-browse', 'Radio', 'Stations from around the world')
        self.tool('list-add-symbolic', 'Add a station by its stream address', win.ask_station)
        controls = Gtk.Box(spacing=8, margin_start=24, margin_end=24, margin_bottom=10)
        self.search = Gtk.SearchEntry(placeholder_text='Search stations', hexpand=True)
        self.search.connect('search-changed', lambda *_: self._queue_load())
        controls.append(self.search)
        self.countries = [('', 'Every country')]
        self.country = Gtk.DropDown.new_from_strings(['Every country'])
        self.country.set_tooltip_text('Country')
        self.country.set_enable_search(True)
        self._country_sig = self.country.connect('notify::selected', lambda *_: self._country_picked())
        controls.append(self.country)
        self.body.insert_child_after(controls, self.head)

        self.chips = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, margin_start=24, margin_end=24,
                                 margin_bottom=12, column_spacing=6, row_spacing=6, max_children_per_line=30)
        self.body.insert_child_after(self.chips, controls)
        self.tag = ''
        self._fill_chips(['All'] + FALLBACK_TAGS)

        self.list = boxed_list()
        self.stack.add_named(self.list, 'list')
        self.stack.add_named(Gtk.Box(), 'blank')
        from gi.repository import Adw
        self.stack.add_named(Adw.Spinner(width_request=40, height_request=40, halign=Gtk.Align.CENTER,
                                         valign=Gtk.Align.START, margin_top=40), 'loading')
        self.err = status('network-offline-symbolic', 'No stations found')
        self.stack.add_named(self.err, 'error')
        self._timer = 0
        self._token = 0
        self._loaded_once = False

    def refresh(self):
        if not self._loaded_once:
            self._loaded_once = True
            net.run(directory.countries, done=self._got_countries)
            self._load()

    def _got_countries(self, items):
        want = self.win.settings['country']
        self.countries = [('', 'Every country')] + list(items)
        self.country.handler_block(self._country_sig)
        self.country.set_model(Gtk.StringList.new([n for _c, n in self.countries]))
        idx = next((i for i, (c, _n) in enumerate(self.countries) if c.upper() == want.upper()), 0)
        self.country.set_selected(idx)
        self.country.handler_unblock(self._country_sig)

    def _country_picked(self):
        code = self.countries[self.country.get_selected()][0] if self.country.get_selected() < len(self.countries) else ''
        self.win.settings.set('country', code or self.win.settings['country'])
        self._load()

    def _current_country(self):
        i = self.country.get_selected()
        if len(self.countries) > 1 and i < len(self.countries):
            return self.countries[i][0]
        return self.win.settings['country']

    def _fill_chips(self, tags):
        clear(self.chips)
        self.chip_buttons = []
        for t in tags:
            b = Gtk.Button(label=t if t[0].isdigit() else ('R&B' if t == 'r&b' else t.title()))
            b.add_css_class('chip')
            b.tag = '' if t == 'All' else t
            b.connect('clicked', self._chip)
            self.chips.append(b)
            self.chip_buttons.append(b)
        self._mark_chips()

    def _mark_chips(self):
        for b in self.chip_buttons:
            (b.add_css_class if b.tag == self.tag else b.remove_css_class)('selected')

    def _chip(self, b):
        self.tag = b.tag
        self._mark_chips()
        self._load()

    def _queue_load(self):
        from gi.repository import GLib
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(450, self._load)

    def _load(self):
        from gi.repository import GLib
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0
        self.stack.set_visible_child_name('loading')
        self._token += 1
        tok = self._token
        name = self.search.get_text().strip()
        # A name search looks everywhere; browsing stays in the chosen country.
        country = '' if name else self._current_country()
        net.run(lambda: directory.stations(name=name, tag=self.tag, countrycode=country, limit=80),
                done=lambda res: tok == self._token and self._show(res),
                fail=lambda m: tok == self._token and self._fail(m))
        return False

    def _show(self, stations):
        clear(self.list)
        for st in stations:
            self.list.append(StationRow(self.win, st))
        if stations:
            self.stack.set_visible_child_name('list')
        else:
            self.err.set_title('No stations found')
            self.err.set_description('Try another genre, country or name.')
            self.stack.set_visible_child_name('error')

    def _fail(self, msg):
        self.err.set_title('Couldn’t reach the radio directory')
        self.err.set_description(msg)
        self.stack.set_visible_child_name('error')


class FavoritesPage(Page):
    def __init__(self, win):
        super().__init__(win, 'radio-fav', 'Favorite Stations')
        self.tool('list-add-symbolic', 'Add a station by its stream address', win.ask_station)
        self.list = boxed_list()
        self.stack.add_named(self.list, 'list')
        self.stack.add_named(status('starred-symbolic', 'No favorite stations',
                                    'Star a station in Radio to keep it here.'), 'empty')
        self.library.connect('stations-changed', lambda *_: self.get_mapped() and self.refresh())

    def refresh(self):
        clear(self.list)
        for st in self.library.favorites:
            self.list.append(StationRow(self.win, st))
        self.stack.set_visible_child_name('list' if self.library.favorites else 'empty')


class RecentPage(Page):
    def __init__(self, win):
        super().__init__(win, 'radio-recent', 'Recently Played')
        self.tool('edit-clear-all-symbolic', 'Clear this list', lambda: self.library.clear_recent())
        self.list = boxed_list()
        self.stack.add_named(self.list, 'list')
        self.stack.add_named(status('document-open-recent-symbolic', 'Nothing played yet',
                                    'Stations you listen to show up here.'), 'empty')
        self.library.connect('stations-changed', lambda *_: self.get_mapped() and self.refresh())

    def refresh(self):
        clear(self.list)
        for st in self.library.recent:
            self.list.append(StationRow(self.win, st))
        self.stack.set_visible_child_name('list' if self.library.recent else 'empty')
