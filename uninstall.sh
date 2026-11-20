#!/bin/sh
# Removes the menu entry added by install.sh. Your subscriptions, downloads and stations stay.
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
rm -f "$DATA/applications/io.github.webhookstudios.Finch.desktop" \
      "$DATA/icons/hicolor/scalable/apps/io.github.webhookstudios.Finch.svg" \
      "$DATA/icons/hicolor/scalable/actions/finch-radio-symbolic.svg" \
      "$DATA/icons/hicolor/scalable/actions/finch-sleep-symbolic.svg" \
      "$DATA/icons/hicolor/scalable/actions/finch-speed-symbolic.svg"
update-desktop-database "$DATA/applications" 2>/dev/null || true
[ -f "$DATA/icons/hicolor/icon-theme.cache" ] && gtk-update-icon-cache -f -q --ignore-theme-index "$DATA/icons/hicolor" 2>/dev/null || true
echo "Finch's menu entry is removed."
