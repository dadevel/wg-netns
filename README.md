# wg-netns

[wg-quick](https://git.zx2c4.com/wireguard-tools/about/src/man/wg-quick.8) with support for linux network namespaces.
It's a simple python script that implements the steps described at [wireguard.com/netns](https://www.wireguard.com/netns/#ordinary-containerization).

## Setup

Requirements:

- Linux
- Python 3.7 or newer
- `ip` from `iproute2`
- `wg` from `wireguard-tools`

Just download the script and make it executable.

~~~ bash
mkdir -p ~/.local/bin/ && curl -o ~/.local/bin/wg-netns https://raw.githubusercontent.com/dadevel/wg-netns/master/wg-netns.py && chmod 0755 ~/.local/bin/wg-netns
~~~

## Usage

First, create a configuration profile.
You can find two examples below.

`./mini.json`:

~~~ json
{
  "name": "ns-example",
  "interfaces": [
    {
      "name": "wg-example",
      "address": ["10.10.10.192/32", "fc00:dead:beef::192/128"],
      "private-key": "4bvaEZHI...",
      "peers": [
        {
          "public-key": "bELgMXGt...",
          "endpoint": "vpn.example.com:51820",
          "allowed-ips": ["0.0.0.0/0", "::/0"]
        }
      ]
    }
  ]
}
~~~

`./maxi.json`:

~~~ json
{
  "name": "ns-example",
  "dns-server": ["10.10.10.1", "10.10.10.2"],
  "pre-up": "some shell command",
  "post-up": "some shell command",
  "pred-own": "some shell command",
  "post-down": "some shell command",
  "interfaces": [
    {
      "name": "wg-site-a",
      "address": ["10.10.11.172/32", "fc00:dead:beef:1::172/128"],
      "listen-port": 51821,
      "fwmark": 51821,
      "private-key": "nFkQQjN+...",
      "mtu": 1420,
      "peers": [
        {
          "public-key": "Kx+wpJpj...",
          "preshared-key": "5daskLoW...",
          "endpoint": "a.example.com:51821",
          "persistent-keepalive": 25,
          "allowed-ips": ["10.10.11.0/24", "fc00:dead:beef:1::/64"]
        }
      ]
    },
    {
      "name": "wg-site-b",
      "address": ["10.10.12.172/32", "fc00:dead:beef:2::172/128"],
      "listen-port": 51822,
      "fwmark": 51822,
      "private-key": "guYPuE3X...",
      "mtu": 1420,
      "peers": [
        {
          "public-key": "NvZMoyrg...",
          "preshared-key": "cFQuyIX/...",
          "endpoint": "b.example.com:51822",
          "persistent-keepalive": 25,
          "allowed-ips": ["10.10.12.0/24", "fc00:dead:beef:2::/64"]
        }
      ]
    }
  ]
}
~~~

Now it's time to setup your new network namespace and all associated wireguard interfaces.

~~~ bash
wg-netns up ./example.json
~~~

You can verify the success with a combination of `ip` and `wg`.

~~~ bash
ip netns exec ns-example wg show
~~~

Or you can spawn a shell inside the netns.

~~~ bash
ip netns exec ns-example bash -i
~~~

Or connect a container to it.

~~~ bash
podman run -it --rm --network ns:/var/run/netns/ns-example docker.io/alpine wget -O - https://ipinfo.io
~~~

Or do whatever else you want.

### System Service

You can find a `wg-quick@.service` equivalent at [wg-netns@.service](./wg-netns@.service).

### Port Forwarding

With `socat` you can forward TCP traffic from outside a network namespace to a port inside a network namespace.

~~~ bash
socat tcp-listen:$LHOST,reuseaddr,fork "exec:ip netns exec $NETNS socat stdio 'tcp-connect:$RHOST',nofork"
~~~

Example: All connections to port 1234/tcp in the main netns are forwarded into the *ns-example* namespace to port 5678/tcp.

~~~ bash
# terminal 1, create netns and start http server inside
wg-netns up ns-example
hello > ./hello.txt
ip netns exec ns-example python3 -m http.server 5678
# terminal 2, setup port forwarding
socat tcp-listen:1234,reuseaddr,fork "exec:ip netns exec ns-example socat stdio 'tcp-connect:127.0.0.1:5678',nofork"
# terminal 3, test access
curl http://127.0.0.1:1234/hello.txt
~~~

