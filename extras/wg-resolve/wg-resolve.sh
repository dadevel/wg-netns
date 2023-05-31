#!/bin/sh
set -eu

# dependencies: cut, getent, ip, ping and wg

WG_ENDPOINT_DOMAIN="${WG_ENDPOINT%%:*}"
WG_ENDPOINT_PORT="${WG_ENDPOINT##*:}"

if ! ip netns exec "$WG_NAMESPACE" ping -q -c 1 -W "${WG_TIMEOUT:-5}" "$WG_GATEWAY"; then
    echo 'probe failed, resolving endpoint'
    ip netns exec "$WG_NAMESPACE" wg set "$WG_INTERFACE" peer "$WG_PEER" endpoint "$(getent hosts -- "$WG_ENDPOINT_DOMAIN" | cut -d ' ' -f 1):$WG_ENDPOINT_PORT"
fi
