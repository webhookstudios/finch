#!/bin/sh
# Builds dist/finch-player_<version>_all.deb. Needs only dpkg-deb.
#
# The app is called Finch, but Ubuntu already has an unrelated package and command named
# 'finch', so this package and its command are 'finch-player'.
#
#   /usr/lib/finch-player/      the program (Python)
#   /usr/bin/finch-player       the launcher
#   /usr/share/icons/hicolor/   the app icon and the symbolic icons it uses
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
PKG=finch-player
APP_ID=io.github.webhookstudios.Finch
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' "$ROOT/finch/__init__.py")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

LIB="$STAGE/usr/lib/$PKG"
ICONS="$STAGE/usr/share/icons/hicolor/scalable"
install -d "$LIB/finch/ui" "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/share/applications" \
    "$ICONS/apps" "$ICONS/actions" "$STAGE/usr/share/doc/$PKG"

install -m 644 "$ROOT"/finch/*.py "$LIB/finch/"
install -m 644 "$ROOT"/finch/ui/*.py "$LIB/finch/ui/"
cp -r "$ROOT/finch/sedge" "$LIB/finch/"
find "$LIB/finch/sedge" -name __pycache__ -prune -exec rm -rf {} +
find "$LIB/finch/sedge" -type f -exec chmod 644 {} +
install -m 755 "$ROOT/data/finch-player" "$STAGE/usr/bin/finch-player"
install -m 644 "$ROOT/data/$APP_ID.desktop" "$STAGE/usr/share/applications/"
install -m 644 "$ROOT/data/$APP_ID.svg" "$ICONS/apps/"
install -m 644 "$ROOT"/data/icons/hicolor/scalable/actions/*.svg "$ICONS/actions/"

cat > "$STAGE/usr/share/doc/$PKG/copyright" <<EOT
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Finch
Source: https://github.com/webhookstudios/finch

Files: *
Copyright: $(date +%Y) webhookstudios
License: GPL-2+
 On Debian systems, the full text of the GNU General Public License
 version 2 can be found in /usr/share/common-licenses/GPL-2.

Files: */sedge/fonts/*
Copyright: 2023 The Young Serif Project Authors; 2015 The Public Sans Project Authors
License: OFL-1.1
 The full license texts are in the sedge/fonts/ folder.
EOT
chmod 644 "$STAGE/usr/share/doc/$PKG/copyright"

cat > "$STAGE/DEBIAN/control" <<EOT
Package: $PKG
Version: $VERSION
Architecture: all
Maintainer: webhookstudios <354619278+webhookstudios@users.noreply.github.com>
Installed-Size: $(du -sk "$STAGE/usr" | cut -f1)
Depends: python3 (>= 3.10), python3-gi, python3-gi-cairo, python3-cairo, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.8), gir1.2-gstreamer-1.0, gir1.2-gst-plugins-base-1.0, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good
Recommends: gstreamer1.0-libav, gstreamer1.0-plugins-bad, gstreamer1.0-plugins-ugly, gstreamer1.0-pipewire | gstreamer1.0-pulseaudio
Section: sound
Priority: optional
Homepage: https://webhookstudioapps.netlify.app
Description: Podcasts and internet radio
 Finch finds, follows and plays podcasts and internet radio stations. Search
 for shows or browse what's popular, subscribe, and get new episodes in one
 list. Download episodes to listen offline, line them up in Up Next, change
 the speed, set a sleep timer, and pick up where you left off. Browse
 thousands of radio stations by country and genre, and star your favorites.
 .
 Part of the Sedge family of webhookstudios apps.
EOT

mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/${PKG}_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$OUT" >/dev/null
echo "Built $OUT"
