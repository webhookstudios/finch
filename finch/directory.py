"""Finding shows and stations.

Podcasts: Apple's public podcast search and charts (no account or key needed).
Radio: the open Radio Browser directory (radio-browser.info), run by volunteers.
All calls block, so run them through net.run().
"""
import json
import urllib.parse

from .net import fetch

RADIO = 'https://all.api.radio-browser.info/json'


def _json(url):
    return json.loads(fetch(url).decode('utf-8', 'replace'))


def _show(r):
    return {'title': r.get('collectionName') or r.get('trackName') or '',
            'author': r.get('artistName') or '',
            'feed': r.get('feedUrl') or '',
            'image': r.get('artworkUrl600') or r.get('artworkUrl100') or '',
            'genre': r.get('primaryGenreName') or ''}


def search_podcasts(term, country='US', limit=40):
    q = urllib.parse.urlencode({'media': 'podcast', 'entity': 'podcast', 'term': term,
                                'limit': limit, 'country': country})
    data = _json(f'https://itunes.apple.com/search?{q}')
    return [s for s in (_show(r) for r in data.get('results', [])) if s['feed']]


def top_podcasts(country='us', limit=40):
    """The current chart for a country, with feed addresses filled in."""
    chart = _json(f'https://rss.applemarketingtools.com/api/v2/{country.lower()}/podcasts/top/{limit}/podcasts.json')
    ids = [r['id'] for r in chart.get('feed', {}).get('results', []) if r.get('id')]
    if not ids:
        return []
    found = _json('https://itunes.apple.com/lookup?' + urllib.parse.urlencode({'id': ','.join(ids),
                                                                               'country': country}))
    by_id = {str(r.get('collectionId')): _show(r) for r in found.get('results', [])}
    return [by_id[i] for i in ids if i in by_id and by_id[i]['feed']]


def _station(r):
    return {'uuid': r.get('stationuuid', ''), 'name': (r.get('name') or '').strip() or 'Unnamed station',
            'url': r.get('url_resolved') or r.get('url') or '', 'favicon': r.get('favicon') or '',
            'tags': [t for t in (r.get('tags') or '').split(',') if t][:6], 'country': r.get('country') or '',
            'countrycode': r.get('countrycode') or '', 'codec': r.get('codec') or '',
            'bitrate': r.get('bitrate') or 0, 'homepage': r.get('homepage') or '',
            'language': r.get('language') or ''}


def stations(name='', tag='', countrycode='', language='', order='clickcount', limit=60):
    params = {'hidebroken': 'true', 'order': order, 'reverse': 'true', 'limit': limit}
    for k, v in (('name', name), ('tag', tag), ('countrycode', countrycode), ('language', language)):
        if v:
            params[k] = v
    if tag:
        params['tagExact'] = 'false'
    data = _json(f'{RADIO}/stations/search?' + urllib.parse.urlencode(params))
    seen, out = set(), []
    for r in data:
        s = _station(r)
        key = (s['name'].lower(), s['url'])
        if s['url'] and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def popular_tags(limit=40):
    data = _json(f'{RADIO}/tags?' + urllib.parse.urlencode({'order': 'stationcount', 'reverse': 'true',
                                                             'limit': limit * 3, 'hidebroken': 'true'}))
    # Skip tags that are just place names or near-empty labels.
    skip = {'news', 'music', 'radio', 'fm', 'am', 'public radio', 'community radio', 'local news', 'talk & speech'}
    out = []
    for t in data:
        name = (t.get('name') or '').strip()
        if 2 < len(name) < 22 and name not in skip and not name.isdigit():
            out.append(name)
        if len(out) >= limit:
            break
    return out


def countries():
    data = _json(f'{RADIO}/countries?' + urllib.parse.urlencode({'order': 'name', 'hidebroken': 'true'}))
    return sorted({(c.get('iso_3166_1') or '', c.get('name') or '') for c in data
                   if c.get('iso_3166_1') and c.get('stationcount', 0) >= 5}, key=lambda c: c[1])


def count_click(uuid):
    """Radio Browser asks players to report a play so its popularity lists stay useful."""
    if uuid:
        try:
            fetch(f'{RADIO}/url/{urllib.parse.quote(uuid)}', timeout=8, max_bytes=65536)
        except Exception:
            pass
