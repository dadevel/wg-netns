#!/bin/sh
set -eu

if ! ping -q -c 1 -W "${WG_TIMEOUT:-5}" "$WG_GATEWAY"; then
    echo 'probe failed, resolving endpoint'
    wg set "$WG_INTERFACE" peer "$WG_PEER" endpoint "$WG_ENDPOINT"
fi
