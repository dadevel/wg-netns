#!/bin/sh
PS4='> '
set -eux

PREFIX="${PREFIX:-/usr/local}"

cd "$(dirname "$0")"
install -m 0755 -D ./wg-netns.py "$PREFIX/bin/wg-netns"
install -m 0644 -D ./wg-netns@.service "$PREFIX/lib/systemd/system/wg-netns@.service"
