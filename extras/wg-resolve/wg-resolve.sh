#!/bin/sh
set -eu

# dependencies: dig, ip, ping and wg

WG_ENDPOINT_DOMAIN="${WG_ENDPOINT%%:*}"
WG_ENDPOINT_PORT="${WG_ENDPOINT##*:}"

if ! ip netns exec "$WG_NAMESPACE" ping -q -c 1 -W "${WG_TIMEOUT:-5}" "$WG_GATEWAY"; then
    echo 'probe failed, resolving endpoint'
    ip netns exec "$WG_NAMESPACE" wg set "$WG_INTERFACE" peer "$WG_PEER" endpoint "$(dig +short "$WG_ENDPOINT_DOMAIN"):$WG_ENDPOINT_PORT"
fi
