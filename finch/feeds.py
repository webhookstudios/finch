"""Reading podcast feeds (RSS 2.0 with the common podcast tags, and plain Atom) and OPML lists."""
import email.utils
import hashlib
import html
import re
import time
import xml.etree.ElementTree as ET

ITUNES = '{http://www.itunes.com/dtds/podcast-1.0.dtd}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}'
MEDIA = '{http://search.yahoo.com/mrss/}'
ATOM = '{http://www.w3.org/2005/Atom}'
AUDIO_EXT = ('.mp3', '.m4a', '.aac', '.ogg', '.oga', '.opus', '.flac', '.wav', '.mp4', '.m4v', '.mov', '.webm')


class FeedError(Exception):
    pass


def text_of(markup):
    """Show notes as plain text: tags dropped, paragraphs and line breaks kept."""
    if not markup:
        return ''
    s = re.sub(r'(?is)<(script|style).*?</\1>', '', markup)
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</(p|div|li|h[1-6])>', '\n\n', s)
    s = re.sub(r'(?i)<li[^>]*>', '• ', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)
    s = re.sub(r'[ \t\r\f\v]+', ' ', s)
    s = re.sub(r' *\n *', '\n', s)
    return re.sub(r'\n{3,}', '\n\n', s).strip()


def _t(el, path):
    found = el.find(path)
    return (found.text or '').strip() if found is not None and found.text else ''


def _duration(value):
    value = (value or '').strip()
    if not value:
        return 0
    try:
        if ':' in value:
            secs = 0
            for part in value.split(':'):
                secs = secs * 60 + float(part or 0)
            return int(secs)
        return int(float(value))
    except ValueError:
        return 0


def _date(value):
    if not value:
        return 0
    try:
        return int(email.utils.parsedate_to_datetime(value.strip()).timestamp())
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d'):
        try:
            return int(time.mktime(time.strptime(value.strip()[:25], fmt)))
        except ValueError:
            continue
    return 0


def episode_id(feed_url, guid):
    return hashlib.sha1(f'{feed_url}\n{guid}'.encode()).hexdigest()[:20]


def parse(data, feed_url):
    """Bytes of a feed → dict with the show's details and a newest-first list of episodes."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise FeedError("That address doesn't lead to a podcast feed.") from e
    if root.tag == ATOM + 'feed':
        return _parse_atom(root, feed_url)
    channel = root.find('channel')
    if channel is None:
        raise FeedError("That address doesn't lead to a podcast feed.")
    image = ''
    it_img = channel.find(ITUNES + 'image')
    if it_img is not None:
        image = it_img.get('href', '')
    image = image or _t(channel, 'image/url')
    show = {
        'title': _t(channel, 'title') or feed_url,
        'author': _t(channel, ITUNES + 'author') or _t(channel, 'managingEditor'),
        'description': text_of(_t(channel, ITUNES + 'summary') or _t(channel, 'description')),
        'image': image,
        'link': _t(channel, 'link'),
        'episodes': [],
    }
    for item in channel.findall('item'):
        enc = item.find('enclosure')
        url = enc.get('url', '') if enc is not None else ''
        mime = enc.get('type', '') if enc is not None else ''
        size = 0
        if enc is not None:
            try:
                size = int(enc.get('length') or 0)
            except ValueError:
                size = 0
        if not url:
            media = item.find(MEDIA + 'content')
            if media is not None:
                url, mime = media.get('url', ''), media.get('type', '')
        if not url:
            continue  # nothing to play
        guid = _t(item, 'guid') or url
        ep_img = item.find(ITUNES + 'image')
        notes = _t(item, CONTENT + 'encoded') or _t(item, 'description') or _t(item, ITUNES + 'summary')
        show['episodes'].append({
            'id': episode_id(feed_url, guid),
            'title': _t(item, 'title') or 'Untitled episode',
            'date': _date(_t(item, 'pubDate')),
            'duration': _duration(_t(item, ITUNES + 'duration')),
            'url': url,
            'mime': mime,
            'size': size,
            'image': ep_img.get('href', '') if ep_img is not None else '',
            'notes': text_of(notes)[:20000],
            'link': _t(item, 'link'),
        })
    show['episodes'].sort(key=lambda e: e['date'], reverse=True)
    return show


def _parse_atom(root, feed_url):
    show = {'title': _t(root, ATOM + 'title') or feed_url, 'author': _t(root, ATOM + 'author/' + ATOM + 'name'),
            'description': text_of(_t(root, ATOM + 'subtitle')), 'image': _t(root, ATOM + 'logo'),
            'link': '', 'episodes': []}
    for entry in root.findall(ATOM + 'entry'):
        url = mime = ''
        size = 0
        for link in entry.findall(ATOM + 'link'):
            if link.get('rel') == 'enclosure':
                url, mime = link.get('href', ''), link.get('type', '')
                try:
                    size = int(link.get('length') or 0)
                except ValueError:
                    size = 0
                break
        if not url:
            continue
        guid = _t(entry, ATOM + 'id') or url
        show['episodes'].append({
            'id': episode_id(feed_url, guid), 'title': _t(entry, ATOM + 'title') or 'Untitled episode',
            'date': _date(_t(entry, ATOM + 'published') or _t(entry, ATOM + 'updated')), 'duration': 0,
            'url': url, 'mime': mime, 'size': size, 'image': '',
            'notes': text_of(_t(entry, ATOM + 'content') or _t(entry, ATOM + 'summary'))[:20000], 'link': ''})
    show['episodes'].sort(key=lambda e: e['date'], reverse=True)
    return show


def read_opml(data):
    """Feed addresses listed in an OPML file."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise FeedError("That file isn't an OPML subscription list.") from e
    out = []
    for el in root.iter('outline'):
        url = el.get('xmlUrl') or el.get('xmlurl')
        if url and url not in out:
            out.append(url)
    return out


def write_opml(podcasts):
    body = ET.Element('body')
    for p in podcasts:
        ET.SubElement(body, 'outline', type='rss', text=p['title'], title=p['title'], xmlUrl=p['feed'])
    opml = ET.Element('opml', version='2.0')
    head = ET.SubElement(opml, 'head')
    ET.SubElement(head, 'title').text = 'Finch subscriptions'
    opml.append(body)
    ET.indent(opml)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(opml, encoding='utf-8')
